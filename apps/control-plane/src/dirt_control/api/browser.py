from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dirt_control.audit import add_audit_event
from dirt_control.deps import get_clock, get_session, get_settings
from dirt_control.models import (
    CloudAsset,
    CloudAuditEvent,
    CloudCommand,
    CloudDevice,
    CloudLatestMetric,
    CloudMetricRollup,
    CloudSchedule,
    CloudSite,
    CloudTent,
    GatewayCredential,
)
from dirt_control.retention import prune_expired_assets
from dirt_control.security import (
    UrlSigner,
    expires_from,
    require_browser_user,
    verify_password,
)
from dirt_control.settings import CloudSettings
from dirt_control.storage import S3ObjectStore
from dirt_shared.cloud_contract import PruneAssetsResponse

router = APIRouter(prefix="/api")
COMMAND_EXPIRY_SECONDS = 60
PTZ_COMMAND_TYPES = Literal["ptz_preset", "ptz_look", "ptz_zoom"]
METRIC_HISTORY_RANGES: dict[str, tuple[str, timedelta]] = {
    "1h": ("5m", timedelta(hours=1)),
    "24h": ("1h", timedelta(hours=24)),
    "7d": ("4h", timedelta(days=7)),
}


@dataclass(frozen=True)
class DisplayMetricSpec:
    storage_metric: str
    display_metric: str
    display_unit: str | None = None
    transform: Callable[[float], float] | None = None


def _mist_level_to_pct(value: float) -> float:
    return value * 100.0 / 9.0


DISPLAY_METRIC_BY_STORAGE: dict[str, DisplayMetricSpec] = {
    "fan_duty_pct": DisplayMetricSpec(
        storage_metric="fan_duty_pct",
        display_metric="fan_pct",
        display_unit="%",
    ),
    "humidifier_mist_level": DisplayMetricSpec(
        storage_metric="humidifier_mist_level",
        display_metric="humidifier_intensity_pct",
        display_unit="%",
        transform=_mist_level_to_pct,
    ),
}
DISPLAY_METRIC_BY_PUBLIC: dict[str, DisplayMetricSpec] = {
    spec.display_metric: spec for spec in DISPLAY_METRIC_BY_STORAGE.values()
}


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class CommandCreateRequest(BaseModel):
    idempotency_key: str = Field(min_length=1, max_length=160)
    site_id: str | None = None
    tent_id: str = Field(min_length=1, max_length=80)
    device_id: Literal["obsbot-main"]
    capability_id: Literal["ptz_move"]
    command_type: PTZ_COMMAND_TYPES
    payload: dict[str, Any] = Field(default_factory=dict)


class GatewayCredentialRotateRequest(BaseModel):
    token_sha256: str = Field(min_length=64, max_length=64)


class BrowserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


SyncStatusLabel = Literal["live", "stale", "offline"]


class UserResponse(BrowserResponse):
    username: str


class HealthResponse(BrowserResponse):
    service: Literal["control-plane-api"]
    ok: bool
    site_id: str
    status: SyncStatusLabel
    gateway_last_seen_at: datetime | None
    gateway_heartbeat_age_s: int | None
    gateway_backlog_depth: int
    command_backlog_depth: int
    command_failures_24h: int
    asset_failures_24h: int
    asset_retention_days: int
    commands_enabled: bool


class SiteResponse(BrowserResponse):
    site_id: str
    name: str
    timezone: str
    is_active: bool
    gateway_last_seen_at: datetime | None
    last_catalog_sync_at: datetime | None


class TentResponse(BrowserResponse):
    site_id: str
    tent_id: str
    name: str
    is_active: bool
    synced_at: datetime


class TentStateResponse(BrowserResponse):
    site_id: str
    tent_id: str
    name: str
    is_active: bool
    gateway_last_seen_at: datetime | None
    last_catalog_sync_at: datetime | None


class CurrentMetricResponse(BrowserResponse):
    metric: str
    value: float
    unit: str | None
    capability_id: str
    device_id: str | None
    source_updated_at: datetime
    received_at: datetime
    stale_after_s: int


class MetricHistoryPointResponse(BrowserResponse):
    bucket: str
    bucket_start_at: datetime
    bucket_end_at: datetime
    min: float | None
    avg: float | None
    max: float | None
    sample_count: int
    unit: str | None


class MetricHistoryResponse(BrowserResponse):
    metric: str
    range: str
    points: list[MetricHistoryPointResponse]


class DeviceResponse(BrowserResponse):
    device_id: str
    name: str
    kind: str
    controller: str | None
    is_active: bool
    last_seen_at: datetime | None


@dataclass(frozen=True)
class LightState:
    is_on: bool
    minutes_until_off: float
    minutes_until_on: float


class LightScheduleResponse(BrowserResponse):
    site_id: str
    tent_id: str
    zone_id: str | None
    device_id: str | None
    capability_id: str | None
    schedule_id: str
    kind: str
    enabled: bool
    timezone: str
    starts_local: str
    ends_local: str
    duration_hours: float
    is_on: bool
    minutes_until_off: float
    minutes_until_on: float


class LightSchedulesResponse(BrowserResponse):
    site_id: str
    tent_id: str
    schedules: list[LightScheduleResponse]


class AssetResponse(BrowserResponse):
    asset_id: str
    kind: str
    content_type: str
    byte_size: int
    sha256: str | None
    captured_at: datetime
    uploaded_at: datetime
    signed_url: str
    signed_url_expires_at: datetime


class SyncStatusResponse(BrowserResponse):
    site_id: str
    gateway_last_seen_at: datetime | None
    gateway_backlog_depth: int
    last_catalog_sync_at: datetime | None
    command_backlog_depth: int
    status: SyncStatusLabel


def _display_metric_value(
    value: float | None, display_spec: DisplayMetricSpec | None
) -> float | None:
    if value is None:
        return None
    if display_spec is None or display_spec.transform is None:
        return value
    return round(display_spec.transform(value), 2)


def _current_metric_response(row: CloudLatestMetric) -> CurrentMetricResponse:
    display_spec = DISPLAY_METRIC_BY_STORAGE.get(row.metric)
    display_value = _display_metric_value(row.value, display_spec)
    return CurrentMetricResponse(
        metric=display_spec.display_metric if display_spec else row.metric,
        value=display_value if display_value is not None else row.value,
        unit=display_spec.display_unit if display_spec else row.unit,
        capability_id=row.capability_id,
        device_id=row.device_id,
        source_updated_at=row.source_updated_at,
        received_at=row.received_at,
        stale_after_s=row.stale_after_s,
    )


class CommandResponse(BrowserResponse):
    command_id: str
    idempotency_key: str
    site_id: str
    tent_id: str
    device_id: str
    capability_id: str
    command_type: str
    payload: dict[str, Any]
    status: str
    queued_at: datetime
    expires_at: datetime
    claimed_by: str | None
    claimed_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None
    result: dict[str, Any] | None
    error: str | None


class GatewayCredentialRotateResponse(BrowserResponse):
    credential_id: str
    gateway_id: str
    allowed_site_id: str
    rotated_at: datetime | None


@router.get("/health", response_model=HealthResponse)
async def health(
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> HealthResponse:
    now = clock()
    site = await session.get(CloudSite, settings.default_site_id)
    command_backlog_depth = await _command_backlog_depth(
        session, site_id=settings.default_site_id
    )
    command_failures_24h = (
        await session.scalar(
            select(func.count())
            .select_from(CloudCommand)
            .where(
                CloudCommand.site_id == settings.default_site_id,
                CloudCommand.status.in_(["failed", "rejected", "expired"]),
                CloudCommand.updated_at >= now - timedelta(days=1),
            )
        )
    ) or 0
    asset_failures_24h = (
        await session.scalar(
            select(func.count())
            .select_from(CloudAuditEvent)
            .where(
                CloudAuditEvent.site_id == settings.default_site_id,
                CloudAuditEvent.event_type == "asset_upload_failed",
                CloudAuditEvent.created_at >= now - timedelta(days=1),
            )
        )
    ) or 0
    gateway_heartbeat_age_s = None
    if site is not None and site.gateway_last_seen_at is not None:
        gateway_heartbeat_age_s = int((now - site.gateway_last_seen_at).total_seconds())
    sync_status = _sync_status_label(
        site.gateway_last_seen_at if site else None, now=now
    )
    if site is not None:
        await _audit_missing_device_liveness(
            session,
            site_id=settings.default_site_id,
            now=now,
        )
    return HealthResponse(
        service="control-plane-api",
        ok=True,
        site_id=settings.default_site_id,
        status=sync_status,
        gateway_last_seen_at=site.gateway_last_seen_at if site else None,
        gateway_heartbeat_age_s=gateway_heartbeat_age_s,
        gateway_backlog_depth=site.gateway_backlog_depth if site else 0,
        command_backlog_depth=command_backlog_depth,
        command_failures_24h=command_failures_24h,
        asset_failures_24h=asset_failures_24h,
        asset_retention_days=settings.asset_retention_days,
        commands_enabled=settings.command_creation_enabled
        and settings.gateway_command_claim_enabled,
    )


@router.post("/auth/login", response_model=UserResponse)
async def login(  # noqa: PLR0913
    body: LoginRequest,
    response: Response,
    request: Request,
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> UserResponse:
    if body.username != settings.admin_username or not verify_password(
        body.password, settings.admin_password_hash
    ):
        add_audit_event(
            session,
            now=clock(),
            event_type="auth_login_failed",
            actor_type="browser",
            actor_id=body.username,
        )
        await session.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    request.app.state.sessions.create_cookie(response, body.username)
    add_audit_event(
        session,
        now=clock(),
        event_type="auth_login_succeeded",
        actor_type="browser",
        actor_id=body.username,
    )
    await session.commit()
    return UserResponse(username=body.username)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, request: Request) -> None:
    request.app.state.sessions.clear_cookie(response)


@router.get("/auth/me", response_model=UserResponse)
async def me(user: str = Depends(require_browser_user)) -> UserResponse:
    return UserResponse(username=user)


@router.get("/sites", response_model=list[SiteResponse])
async def sites(
    _: str = Depends(require_browser_user),
    session: AsyncSession = Depends(get_session),
) -> list[SiteResponse]:
    rows = (
        await session.execute(select(CloudSite).order_by(CloudSite.site_id))
    ).scalars()
    return [
        SiteResponse(
            site_id=row.site_id,
            name=row.name,
            timezone=row.timezone,
            is_active=row.is_active,
            gateway_last_seen_at=row.gateway_last_seen_at,
            last_catalog_sync_at=row.last_catalog_sync_at,
        )
        for row in rows
    ]


@router.get("/tents", response_model=list[TentResponse])
async def tents(
    site_id: str | None = None,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> list[TentResponse]:
    scoped_site_id = site_id or settings.default_site_id
    rows = (
        await session.execute(
            select(CloudTent)
            .where(CloudTent.site_id == scoped_site_id)
            .order_by(CloudTent.tent_id)
        )
    ).scalars()
    return [
        TentResponse(
            site_id=row.site_id,
            tent_id=row.tent_id,
            name=row.name,
            is_active=row.is_active,
            synced_at=row.synced_at,
        )
        for row in rows
    ]


@router.get("/tents/{tent_id}/state", response_model=TentStateResponse)
async def tent_state(
    tent_id: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> TentStateResponse:
    site = await session.get(CloudSite, settings.default_site_id)
    tent = (
        await session.execute(
            select(CloudTent).where(
                CloudTent.site_id == settings.default_site_id,
                CloudTent.tent_id == tent_id,
            )
        )
    ).scalar_one_or_none()
    if tent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "tent not found")
    return TentStateResponse(
        site_id=tent.site_id,
        tent_id=tent.tent_id,
        name=tent.name,
        is_active=tent.is_active,
        gateway_last_seen_at=site.gateway_last_seen_at if site else None,
        last_catalog_sync_at=site.last_catalog_sync_at if site else None,
    )


@router.get(
    "/tents/{tent_id}/metrics/current", response_model=list[CurrentMetricResponse]
)
async def current_metrics(
    tent_id: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> list[CurrentMetricResponse]:
    rows = (
        await session.execute(
            select(CloudLatestMetric)
            .where(
                CloudLatestMetric.site_id == settings.default_site_id,
                CloudLatestMetric.tent_id == tent_id,
            )
            .order_by(CloudLatestMetric.metric)
        )
    ).scalars()
    responses: dict[str, CurrentMetricResponse] = {}
    for row in rows:
        response = _current_metric_response(row)
        existing = responses.get(response.metric)
        if existing is None or row.metric == response.metric:
            responses[response.metric] = response
    return list(responses.values())


@router.get("/tents/{tent_id}/metrics/history", response_model=MetricHistoryResponse)
async def metric_history(  # noqa: PLR0913
    tent_id: str,
    metric: str,
    range: str = "24h",
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> MetricHistoryResponse:
    range_spec = METRIC_HISTORY_RANGES.get(range)
    if range_spec is None:
        raise HTTPException(status_code=400, detail="invalid range")
    bucket, window = range_spec
    cutoff = clock() - window
    display_spec = DISPLAY_METRIC_BY_PUBLIC.get(metric)
    storage_metric = display_spec.storage_metric if display_spec else metric
    rows = (
        await session.execute(
            select(CloudMetricRollup)
            .where(
                CloudMetricRollup.site_id == settings.default_site_id,
                CloudMetricRollup.tent_id == tent_id,
                CloudMetricRollup.metric == storage_metric,
                CloudMetricRollup.bucket == bucket,
                CloudMetricRollup.bucket_start_at >= cutoff,
            )
            .order_by(CloudMetricRollup.bucket_start_at)
        )
    ).scalars()
    return MetricHistoryResponse(
        metric=metric,
        range=range,
        points=[
            MetricHistoryPointResponse(
                bucket=row.bucket,
                bucket_start_at=row.bucket_start_at,
                bucket_end_at=row.bucket_end_at,
                min=_display_metric_value(row.min_value, display_spec),
                avg=_display_metric_value(row.avg_value, display_spec),
                max=_display_metric_value(row.max_value, display_spec),
                sample_count=row.sample_count,
                unit=display_spec.display_unit if display_spec else row.unit,
            )
            for row in rows
        ],
    )


@router.get("/tents/{tent_id}/devices", response_model=list[DeviceResponse])
async def devices(
    tent_id: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> list[DeviceResponse]:
    rows = (
        await session.execute(
            select(CloudDevice)
            .where(
                CloudDevice.site_id == settings.default_site_id,
                CloudDevice.tent_id == tent_id,
            )
            .order_by(CloudDevice.device_id)
        )
    ).scalars()
    return [
        DeviceResponse(
            device_id=row.device_id,
            name=row.name,
            kind=row.kind,
            controller=row.controller,
            is_active=row.is_active,
            last_seen_at=row.last_seen_at,
        )
        for row in rows
    ]


@router.get(
    "/tents/{tent_id}/lights/schedules",
    response_model=LightSchedulesResponse,
)
async def light_schedules(
    tent_id: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> LightSchedulesResponse:
    rows = (
        await session.execute(
            select(CloudSchedule)
            .where(
                CloudSchedule.site_id == settings.default_site_id,
                CloudSchedule.tent_id == tent_id,
                CloudSchedule.kind == "lights",
            )
            .order_by(CloudSchedule.schedule_id)
        )
    ).scalars()
    schedules = []
    for row in rows:
        state = _light_state(
            row.starts_local,
            row.ends_local,
            clock(),
            timezone=row.timezone,
        )
        schedules.append(
            LightScheduleResponse(
                site_id=row.site_id,
                tent_id=row.tent_id,
                zone_id=row.zone_id,
                device_id=row.device_id,
                capability_id=row.capability_id,
                schedule_id=row.schedule_id,
                kind=row.kind,
                enabled=row.is_enabled,
                timezone=row.timezone,
                starts_local=row.starts_local.strftime("%H:%M:%S"),
                ends_local=row.ends_local.strftime("%H:%M:%S"),
                duration_hours=_duration_hours(
                    row.starts_local,
                    row.ends_local,
                ),
                is_on=state.is_on,
                minutes_until_off=state.minutes_until_off,
                minutes_until_on=state.minutes_until_on,
            )
        )
    return LightSchedulesResponse(
        site_id=settings.default_site_id,
        tent_id=tent_id,
        schedules=schedules,
    )


@router.get("/tents/{tent_id}/assets/latest", response_model=list[AssetResponse])
async def latest_assets(
    tent_id: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> list[AssetResponse]:
    rows = (
        await session.execute(
            select(CloudAsset)
            .where(
                CloudAsset.site_id == settings.default_site_id,
                CloudAsset.tent_id == tent_id,
            )
            .order_by(desc(CloudAsset.captured_at))
            .limit(10)
        )
    ).scalars()
    signer = UrlSigner(settings.session_secret)
    object_store = _object_store(settings)
    now = clock()
    return [
        _asset_response(
            row,
            settings=settings,
            signer=signer,
            object_store=object_store,
            now=now,
        )
        for row in rows
    ]


@router.get("/assets/{asset_id}/signed-url", response_model=AssetResponse)
async def asset_signed_url(
    asset_id: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> AssetResponse:
    asset = await session.get(CloudAsset, asset_id)
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "asset not found")
    signer = UrlSigner(settings.session_secret)
    return _asset_response(
        asset,
        settings=settings,
        signer=signer,
        object_store=_object_store(settings),
        now=clock(),
    )


@router.get("/sync/status", response_model=SyncStatusResponse)
async def sync_status(
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> SyncStatusResponse:
    site = await session.get(CloudSite, settings.default_site_id)
    command_backlog_depth = await _command_backlog_depth(
        session, site_id=settings.default_site_id
    )
    if site is None:
        return SyncStatusResponse(
            site_id=settings.default_site_id,
            gateway_last_seen_at=None,
            gateway_backlog_depth=0,
            last_catalog_sync_at=None,
            command_backlog_depth=command_backlog_depth,
            status="offline",
        )
    status_label = _sync_status_label(site.gateway_last_seen_at, now=clock())
    return SyncStatusResponse(
        site_id=site.site_id,
        gateway_last_seen_at=site.gateway_last_seen_at,
        gateway_backlog_depth=site.gateway_backlog_depth,
        last_catalog_sync_at=site.last_catalog_sync_at,
        command_backlog_depth=command_backlog_depth,
        status=status_label,
    )


@router.post(
    "/commands",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def create_command(
    body: CommandCreateRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    if not settings.command_creation_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "commands disabled")
    existing = (
        await session.execute(
            select(CloudCommand).where(
                CloudCommand.requested_by == user,
                CloudCommand.idempotency_key == body.idempotency_key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _command_response(existing)

    now = clock()
    site_id = body.site_id or settings.default_site_id
    if site_id != settings.default_site_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "unsupported site")
    command = CloudCommand(
        command_id=str(uuid.uuid4()),
        idempotency_key=body.idempotency_key,
        site_id=site_id,
        tent_id=body.tent_id,
        device_id=body.device_id,
        capability_id=body.capability_id,
        command_type=body.command_type,
        payload=body.payload,
        requested_by=user,
        status="queued",
        queued_at=now,
        expires_at=now + timedelta(seconds=COMMAND_EXPIRY_SECONDS),
        created_at=now,
        updated_at=now,
    )
    session.add(command)
    add_audit_event(
        session,
        now=now,
        event_type="command_created",
        actor_type="browser",
        actor_id=user,
        site_id=site_id,
        subject_type="cloud_command",
        subject_id=command.command_id,
        metadata={
            "command_type": command.command_type,
            "tent_id": command.tent_id,
            "device_id": command.device_id,
            "capability_id": command.capability_id,
        },
    )
    await session.commit()
    await session.refresh(command)
    return _command_response(command)


@router.post(
    "/admin/gateway-credentials/{credential_id}/rotate",
    response_model=GatewayCredentialRotateResponse,
)
async def rotate_gateway_credential(
    credential_id: str,
    body: GatewayCredentialRotateRequest,
    user: str = Depends(require_browser_user),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> GatewayCredentialRotateResponse:
    credential = await session.get(GatewayCredential, credential_id)
    if credential is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "gateway credential not found")
    now = clock()
    credential.token_sha256 = body.token_sha256
    credential.rotated_at = now
    credential.updated_at = now
    add_audit_event(
        session,
        now=now,
        event_type="gateway_credential_rotated",
        actor_type="browser",
        actor_id=user,
        site_id=credential.allowed_site_id,
        subject_type="gateway_credential",
        subject_id=credential.credential_id,
        metadata={"gateway_id": credential.gateway_id},
    )
    await session.commit()
    return GatewayCredentialRotateResponse(
        credential_id=credential.credential_id,
        gateway_id=credential.gateway_id,
        allowed_site_id=credential.allowed_site_id,
        rotated_at=credential.rotated_at,
    )


@router.post("/admin/assets/prune-expired", response_model=PruneAssetsResponse)
async def prune_assets(
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> PruneAssetsResponse:
    result = await prune_expired_assets(
        session,
        settings=settings,
        now=clock(),
        actor_type="browser",
        actor_id=user,
        site_id=settings.default_site_id,
    )
    return PruneAssetsResponse(
        cutoff=result.cutoff,
        matched=result.matched,
        objects_deleted=result.objects_deleted,
    )


@router.get("/commands/{command_id}", response_model=CommandResponse)
async def get_command(
    command_id: str,
    user: str = Depends(require_browser_user),
    session: AsyncSession = Depends(get_session),
) -> CommandResponse:
    command = await session.get(CloudCommand, command_id)
    if command is None or command.requested_by != user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "command not found")
    return _command_response(command)


@router.get("/commands", response_model=list[CommandResponse])
async def list_commands(
    status: str | None = None,
    user: str = Depends(require_browser_user),
    session: AsyncSession = Depends(get_session),
) -> list[CommandResponse]:
    stmt = select(CloudCommand).where(CloudCommand.requested_by == user)
    if status is not None:
        stmt = stmt.where(CloudCommand.status == status)
    rows = (
        await session.execute(stmt.order_by(desc(CloudCommand.queued_at)).limit(50))
    ).scalars()
    return [_command_response(command) for command in rows]


def _asset_response(
    asset: CloudAsset,
    *,
    settings: CloudSettings,
    signer: UrlSigner,
    object_store: S3ObjectStore | None,
    now: datetime,
) -> AssetResponse:
    expires_at = expires_from(now, settings.asset_url_ttl_s)
    if object_store is None:
        signed_url = signer.build_signed_url(
            base_url=settings.public_asset_base_url,
            subject=asset.object_key,
            expires_at=expires_at,
        )
    else:
        signed_url = object_store.presign_get(
            object_key=asset.object_key,
            expires_in_s=settings.asset_url_ttl_s,
        )
    return AssetResponse(
        asset_id=asset.asset_id,
        kind=asset.kind,
        content_type=asset.content_type,
        byte_size=asset.byte_size,
        sha256=asset.sha256,
        captured_at=asset.captured_at,
        uploaded_at=asset.uploaded_at,
        signed_url=signed_url,
        signed_url_expires_at=expires_at,
    )


def _object_store(settings: CloudSettings) -> S3ObjectStore | None:
    if not (
        settings.s3_endpoint
        and settings.s3_region
        and settings.s3_access_key_id
        and settings.s3_secret_access_key
    ):
        return None
    return S3ObjectStore(settings=settings)


def _command_response(command: CloudCommand) -> CommandResponse:
    return CommandResponse(
        command_id=command.command_id,
        idempotency_key=command.idempotency_key,
        site_id=command.site_id,
        tent_id=command.tent_id,
        device_id=command.device_id,
        capability_id=command.capability_id,
        command_type=command.command_type,
        payload=command.payload,
        status=command.status,
        queued_at=command.queued_at,
        expires_at=command.expires_at,
        claimed_by=command.claimed_by,
        claimed_at=command.claimed_at,
        started_at=command.started_at,
        finished_at=command.finished_at,
        result=command.result,
        error=command.error,
    )


def _sync_status_label(
    last_seen_at: datetime | None, *, now: datetime
) -> SyncStatusLabel:
    if last_seen_at is None:
        return "offline"
    age_s = (now - last_seen_at).total_seconds()
    if age_s > 300:
        return "offline"
    if age_s > 90:
        return "stale"
    return "live"


async def _audit_missing_device_liveness(
    session: AsyncSession,
    *,
    site_id: str,
    now: datetime,
) -> None:
    rows = (
        await session.execute(
            select(CloudDevice, CloudLatestMetric)
            .join(
                CloudLatestMetric,
                and_(
                    CloudLatestMetric.site_id == CloudDevice.site_id,
                    CloudLatestMetric.tent_id == CloudDevice.tent_id,
                    CloudLatestMetric.device_id == CloudDevice.device_id,
                ),
            )
            .where(
                CloudDevice.site_id == site_id,
                CloudDevice.is_active.is_(True),
                CloudDevice.last_seen_at.is_(None),
            )
            .order_by(CloudDevice.device_id, CloudLatestMetric.metric)
        )
    ).all()
    current_by_device: dict[str, tuple[CloudDevice, list[CloudLatestMetric]]] = {}
    for device, metric in rows:
        if not _metric_is_current(metric, now=now):
            continue
        _, metrics = current_by_device.setdefault(device.device_key, (device, []))
        metrics.append(metric)
    if not current_by_device:
        return

    recent_subject_ids = set(
        (
            await session.execute(
                select(CloudAuditEvent.subject_id).where(
                    CloudAuditEvent.site_id == site_id,
                    CloudAuditEvent.event_type
                    == "data_consistency_missing_device_liveness",
                    CloudAuditEvent.created_at >= now - timedelta(hours=1),
                )
            )
        )
        .scalars()
        .all()
    )
    emitted = False
    for device_key, (device, metrics) in current_by_device.items():
        if device_key in recent_subject_ids:
            continue
        emitted = True
        add_audit_event(
            session,
            now=now,
            event_type="data_consistency_missing_device_liveness",
            actor_type="system",
            site_id=site_id,
            subject_type="cloud_device",
            subject_id=device_key,
            metadata={
                "tent_id": device.tent_id,
                "device_id": device.device_id,
                "metrics": sorted({metric.metric for metric in metrics}),
                "capability_ids": sorted({metric.capability_id for metric in metrics}),
            },
        )
    if emitted:
        await session.commit()


def _metric_is_current(metric: CloudLatestMetric, *, now: datetime) -> bool:
    updated_at = _same_timezone(metric.source_updated_at, now)
    return updated_at + timedelta(seconds=metric.stale_after_s) >= now


def _same_timezone(value: datetime, reference: datetime) -> datetime:
    if value.tzinfo is None and reference.tzinfo is not None:
        return value.replace(tzinfo=reference.tzinfo)
    if value.tzinfo is not None and reference.tzinfo is None:
        return value.replace(tzinfo=None)
    return value


def _light_state(
    starts_local: time,
    ends_local: time,
    now: datetime,
    *,
    timezone: str,
) -> LightState:
    from zoneinfo import ZoneInfo

    now_local = now.astimezone(ZoneInfo(timezone))
    now_t = now_local.time()
    if starts_local < ends_local:
        is_on = starts_local <= now_t < ends_local
    else:
        is_on = now_t >= starts_local or now_t < ends_local

    off_dt = datetime.combine(now_local.date(), ends_local, tzinfo=now_local.tzinfo)
    if off_dt <= now_local:
        off_dt = datetime.combine(
            now_local.date() + timedelta(days=1),
            ends_local,
            tzinfo=now_local.tzinfo,
        )
    on_dt = datetime.combine(now_local.date(), starts_local, tzinfo=now_local.tzinfo)
    if on_dt <= now_local:
        on_dt = datetime.combine(
            now_local.date() + timedelta(days=1),
            starts_local,
            tzinfo=now_local.tzinfo,
        )
    return LightState(
        is_on=is_on,
        minutes_until_off=(off_dt - now_local).total_seconds() / 60.0,
        minutes_until_on=(on_dt - now_local).total_seconds() / 60.0,
    )


def _duration_hours(starts_local: time, ends_local: time) -> float:
    start_seconds = _seconds_since_midnight(starts_local)
    end_seconds = _seconds_since_midnight(ends_local)
    return ((end_seconds - start_seconds) % (24 * 60 * 60)) / (60 * 60)


def _seconds_since_midnight(value: time) -> float:
    return (
        value.hour * 60 * 60
        + value.minute * 60
        + value.second
        + value.microsecond / 1_000_000
    )


async def _command_backlog_depth(session: AsyncSession, *, site_id: str) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(CloudCommand)
            .where(
                CloudCommand.site_id == site_id,
                CloudCommand.status.in_(["queued", "claimed", "running"]),
            )
        )
    ) or 0
