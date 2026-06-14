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
from dirt_control.deps import get_asset_store, get_clock, get_session, get_settings
from dirt_control.models import (
    CloudAsset,
    CloudAuditEvent,
    CloudCommand,
    CloudDevice,
    CloudLatestMetric,
    CloudMetricPresentation,
    CloudMetricRollup,
    CloudPlant,
    CloudPlantLine,
    CloudPlantLocation,
    CloudPlantMetricStream,
    CloudSchedule,
    CloudSite,
    CloudTent,
    CloudWikiPage,
    GatewayCredential,
)
from dirt_control.retention import prune_expired_assets
from dirt_control.security import expires_from, require_browser_user, verify_password
from dirt_control.settings import CloudSettings
from dirt_control.storage import AssetStore
from dirt_shared.cloud_contract import PruneAssetsResponse

router = APIRouter(prefix="/api")
COMMAND_EXPIRY_SECONDS = 60
PTZ_COMMAND_TYPES = Literal["ptz_preset", "ptz_look", "ptz_zoom"]
METRIC_HISTORY_RANGES: dict[str, tuple[str, timedelta]] = {
    "1h": ("5m", timedelta(hours=1)),
    "24h": ("1h", timedelta(hours=24)),
    "7d": ("4h", timedelta(days=7)),
    "30d": ("4h", timedelta(days=30)),
    "90d": ("1d", timedelta(days=90)),
}
SOURCE_UNITS_BY_METRIC = {
    "soil_moisture_pct": "%",
    "substrate_temp_c": "degC",
    "substrate_ec_us_cm": "us/cm",
    "substrate_ph": "pH",
}
DISPLAY_UNITS_BY_METRIC = {
    "soil_moisture_pct": "%",
    "substrate_temp_c": "degF",
    "substrate_ec_us_cm": "mS/cm",
    "substrate_ph": "pH",
}
MetricStreamKey = tuple[str, str, str]


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
    device_id: str
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


class MetricPresentationRangeResponse(BrowserResponse):
    range: str
    bucket: str


class MetricPresentationMetricResponse(BrowserResponse):
    metric: str
    display_name: str
    unit: str
    accent: str
    value_precision: int
    y_min: float | None
    y_max: float | None
    display_order: int


class MetricPresentationHistoryGroupResponse(BrowserResponse):
    group: str
    label: str
    display_order: int
    metrics: list[MetricPresentationMetricResponse]


class MetricPresentationResponse(BrowserResponse):
    current_metrics: list[MetricPresentationMetricResponse]
    history_groups: list[MetricPresentationHistoryGroupResponse]
    supported_ranges: list[MetricPresentationRangeResponse]


class PlantSummaryResponse(BrowserResponse):
    site_id: str
    tent_id: str
    id: int
    key: str
    line_source_id: int
    line: PlantLineResponse | None
    name: str
    grid_position: str
    germinated_at: datetime | None
    rooted_at: datetime | None
    veg_started_at: datetime | None
    flower_started_at: datetime | None
    culled_at: datetime | None
    harvested_at: datetime | None
    is_active: bool
    telemetry_stream_count: int


class PlantLineResponse(BrowserResponse):
    id: int
    project_code: str | None
    generation_label: str | None
    strain: str
    cultivar: str
    source_name: str | None


class PlantCurrentLocationResponse(BrowserResponse):
    id: int
    tent_id: str
    grid_position: str
    start_at: datetime
    end_at: datetime | None


class PlantNoteResponse(BrowserResponse):
    id: int
    observed_at: datetime
    body: str
    created_by: str | None


class PlantEventResponse(BrowserResponse):
    id: int
    occurred_at: datetime
    kinds: list[str]
    reason: str | None
    notes: str | None
    metadata: dict[str, Any]


class PlantWikiContentResponse(BrowserResponse):
    path: str
    title: str
    frontmatter: dict[str, Any]
    body_markdown: str
    sha256: str
    source_updated_at: datetime


class PlantMetricReadingResponse(BrowserResponse):
    value: float
    source_value: float
    source_unit: str | None
    display_unit: str
    device_id: str
    capability_id: str
    source_updated_at: datetime
    received_at: datetime
    stale_after_s: int


class PlantMetricStreamResponse(BrowserResponse):
    metric: str
    display_name: str
    display_unit: str
    source_unit: str | None
    value_precision: int
    accent: str
    y_min: float | None
    y_max: float | None
    display_order: int
    history_enabled: bool
    device_id: str
    capability_id: str
    latest_reading: PlantMetricReadingResponse | None


class PlantDetailResponse(BrowserResponse):
    site_id: str
    tent_id: str
    id: int
    key: str
    line_source_id: int
    line: PlantLineResponse | None
    name: str
    grid_position: str
    current_location: PlantCurrentLocationResponse
    germinated_at: datetime | None
    rooted_at: datetime | None
    veg_started_at: datetime | None
    flower_started_at: datetime | None
    culled_at: datetime | None
    culled_reason: str | None
    harvested_at: datetime | None
    selected_for_breeding_at: datetime | None
    selected_for_breeding_reason: str | None
    is_active: bool
    telemetry_stream_count: int
    telemetry: list[PlantMetricStreamResponse]
    notes: list[PlantNoteResponse]
    events: list[PlantEventResponse]
    wiki_content: PlantWikiContentResponse | None


class PlantMetricHistoryPointResponse(BrowserResponse):
    bucket: str
    bucket_start_at: datetime
    bucket_end_at: datetime
    min: float | None
    avg: float | None
    max: float | None
    source_min: float | None
    source_avg: float | None
    source_max: float | None
    sample_count: int
    source_unit: str | None
    display_unit: str


class PlantMetricHistoryStreamResponse(BrowserResponse):
    metric: str
    display_name: str
    display_unit: str
    source_unit: str | None
    value_precision: int
    accent: str
    y_min: float | None
    y_max: float | None
    display_order: int
    device_id: str
    capability_id: str
    points: list[PlantMetricHistoryPointResponse]


class PlantMetricHistoryResponse(BrowserResponse):
    range: str
    bucket: str
    streams: list[PlantMetricHistoryStreamResponse]


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


@dataclass(frozen=True)
class PlantMetricStreamProjection:
    stream: CloudPlantMetricStream
    presentation: CloudMetricPresentation | None


@dataclass(frozen=True)
class PlantProjection:
    plant: CloudPlant
    location: CloudPlantLocation
    line: CloudPlantLine | None


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


def _current_metric_response(row: CloudLatestMetric) -> CurrentMetricResponse:
    return CurrentMetricResponse(
        metric=row.metric,
        value=row.value,
        unit=row.unit,
        capability_id=row.capability_id,
        device_id=row.device_id,
        source_updated_at=row.source_updated_at,
        received_at=row.received_at,
        stale_after_s=row.stale_after_s,
    )


def _presentation_metric_response(
    row: CloudMetricPresentation,
) -> MetricPresentationMetricResponse:
    return MetricPresentationMetricResponse(
        metric=row.metric,
        display_name=row.display_name,
        unit=row.unit,
        accent=row.accent,
        value_precision=row.value_precision,
        y_min=row.y_min,
        y_max=row.y_max,
        display_order=row.display_order,
    )


def _supported_metric_ranges_response() -> list[MetricPresentationRangeResponse]:
    return [
        MetricPresentationRangeResponse(range=range_key, bucket=bucket)
        for range_key, (bucket, _) in METRIC_HISTORY_RANGES.items()
    ]


def _history_group_parts(row: CloudMetricPresentation) -> tuple[str, str, int]:
    if (
        row.dashboard_group is None
        or row.dashboard_group_label is None
        or row.dashboard_group_order is None
    ):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "history metric presentation row missing dashboard group",
        )
    return row.dashboard_group, row.dashboard_group_label, row.dashboard_group_order


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
    site = (
        await session.execute(
            select(CloudSite).where(CloudSite.site_id == settings.default_site_id)
        )
    ).scalar_one_or_none()
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
    site = (
        await session.execute(
            select(CloudSite).where(CloudSite.site_id == settings.default_site_id)
        )
    ).scalar_one_or_none()
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
            .order_by(
                CloudLatestMetric.metric,
                CloudLatestMetric.device_id,
                CloudLatestMetric.capability_id,
            )
        )
    ).scalars()
    return [_current_metric_response(row) for row in rows]


@router.get(
    "/tents/{tent_id}/metrics/presentation",
    response_model=MetricPresentationResponse,
)
async def metric_presentation(
    tent_id: str,
    _: str = Depends(require_browser_user),
    session: AsyncSession = Depends(get_session),
) -> MetricPresentationResponse:
    rows = (
        (
            await session.execute(
                select(CloudMetricPresentation).order_by(
                    CloudMetricPresentation.display_order,
                    CloudMetricPresentation.metric,
                )
            )
        )
        .scalars()
        .all()
    )
    history_rows = sorted(
        (row for row in rows if row.history_enabled),
        key=lambda row: (
            row.dashboard_group_order if row.dashboard_group_order is not None else 0,
            row.display_order,
            row.metric,
        ),
    )
    history_groups: list[MetricPresentationHistoryGroupResponse] = []
    history_groups_by_key: dict[str, MetricPresentationHistoryGroupResponse] = {}
    for row in history_rows:
        group_key, group_label, group_order = _history_group_parts(row)
        existing_group = history_groups_by_key.get(group_key)
        if existing_group is None:
            existing_group = MetricPresentationHistoryGroupResponse(
                group=group_key,
                label=group_label,
                display_order=group_order,
                metrics=[],
            )
            history_groups_by_key[group_key] = existing_group
            history_groups.append(existing_group)
        existing_group.metrics.append(_presentation_metric_response(row))

    return MetricPresentationResponse(
        current_metrics=[
            _presentation_metric_response(row) for row in rows if row.current_enabled
        ],
        history_groups=history_groups,
        supported_ranges=_supported_metric_ranges_response(),
    )


@router.get("/tents/{tent_id}/metrics/history", response_model=MetricHistoryResponse)
async def metric_history(  # noqa: PLR0913
    tent_id: str,
    metric: str,
    device_id: str | None = None,
    capability_id: str | None = None,
    range: str = "24h",
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> MetricHistoryResponse:
    range_spec = METRIC_HISTORY_RANGES.get(range)
    if range_spec is None:
        raise HTTPException(status_code=400, detail="invalid range")
    if (device_id is None) != (capability_id is None):
        raise HTTPException(
            status_code=400,
            detail="device_id and capability_id must be supplied together",
        )
    bucket, window = range_spec
    cutoff = clock() - window
    stream_filters = (
        (
            CloudMetricRollup.device_id == device_id,
            CloudMetricRollup.capability_id == capability_id,
        )
        if device_id is not None and capability_id is not None
        else ()
    )
    rows = (
        await session.execute(
            select(CloudMetricRollup)
            .where(
                CloudMetricRollup.site_id == settings.default_site_id,
                CloudMetricRollup.tent_id == tent_id,
                CloudMetricRollup.metric == metric,
                CloudMetricRollup.bucket == bucket,
                CloudMetricRollup.bucket_start_at >= cutoff,
            )
            .where(*stream_filters)
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
                min=row.min_value,
                avg=row.avg_value,
                max=row.max_value,
                sample_count=row.sample_count,
                unit=row.unit,
            )
            for row in rows
        ],
    )


@router.get("/tents/{tent_id}/plants", response_model=list[PlantSummaryResponse])
async def plants(
    tent_id: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> list[PlantSummaryResponse]:
    latest_rows = await _latest_plants(
        session,
        site_id=settings.default_site_id,
        tent_id=tent_id,
    )
    stream_counts = await _active_plant_stream_counts(
        session,
        site_id=settings.default_site_id,
        plants=latest_rows,
    )
    return [
        _plant_summary_response(
            row,
            telemetry_stream_count=stream_counts.get(row.plant.source_plant_id, 0),
        )
        for row in latest_rows
    ]


@router.get("/tents/{tent_id}/plants/{plant_id}", response_model=PlantDetailResponse)
async def plant_detail(
    tent_id: str,
    plant_id: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> PlantDetailResponse:
    plant = await _get_plant(
        session,
        site_id=settings.default_site_id,
        tent_id=tent_id,
        plant_id=plant_id,
    )
    stream_rows = await _active_plant_metric_streams(
        session,
        site_id=settings.default_site_id,
        plant=plant,
    )
    latest_by_stream = await _latest_metrics_by_stream(
        session,
        site_id=settings.default_site_id,
        tent_id=tent_id,
        streams=[row.stream for row in stream_rows],
    )
    return _plant_detail_response(
        plant,
        telemetry=_plant_metric_stream_responses(stream_rows, latest_by_stream),
        wiki_page=None,
    )


@router.get(
    "/tents/{tent_id}/plants/{plant_id}/metrics/history",
    response_model=PlantMetricHistoryResponse,
)
async def plant_metric_history(  # noqa: PLR0913
    tent_id: str,
    plant_id: str,
    range: str = "24h",
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> PlantMetricHistoryResponse:
    range_spec = METRIC_HISTORY_RANGES.get(range)
    if range_spec is None:
        raise HTTPException(status_code=400, detail="invalid range")
    plant = await _get_plant(
        session,
        site_id=settings.default_site_id,
        tent_id=tent_id,
        plant_id=plant_id,
    )
    stream_rows = [
        row
        for row in await _active_plant_metric_streams(
            session,
            site_id=settings.default_site_id,
            plant=plant,
        )
        if row.presentation is not None and row.presentation.history_enabled
    ]
    bucket, window = range_spec
    cutoff = clock() - window
    history_by_stream = await _metric_rollups_by_stream(
        session,
        site_id=settings.default_site_id,
        tent_id=tent_id,
        bucket=bucket,
        cutoff=cutoff,
        streams=[row.stream for row in stream_rows],
    )
    return PlantMetricHistoryResponse(
        range=range,
        bucket=bucket,
        streams=[
            _plant_metric_history_stream_response(
                row,
                history_by_stream.get(_metric_stream_key(row.stream), []),
            )
            for row in stream_rows
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
    asset_store: AssetStore = Depends(get_asset_store),
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
    now = clock()
    return [
        _asset_response(
            row,
            settings=settings,
            asset_store=asset_store,
            now=now,
        )
        for row in rows
    ]


@router.get("/assets/{asset_id}/signed-url", response_model=AssetResponse)
async def asset_signed_url(
    asset_id: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    asset_store: AssetStore = Depends(get_asset_store),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> AssetResponse:
    asset = (
        await session.execute(select(CloudAsset).where(CloudAsset.asset_id == asset_id))
    ).scalar_one_or_none()
    if asset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "asset not found")
    return _asset_response(
        asset,
        settings=settings,
        asset_store=asset_store,
        now=clock(),
    )


@router.get("/sync/status", response_model=SyncStatusResponse)
async def sync_status(
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> SyncStatusResponse:
    site = (
        await session.execute(
            select(CloudSite).where(CloudSite.site_id == settings.default_site_id)
        )
    ).scalar_one_or_none()
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
    credential = (
        await session.execute(
            select(GatewayCredential).where(
                GatewayCredential.credential_id == credential_id
            )
        )
    ).scalar_one_or_none()
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
    asset_store: AssetStore = Depends(get_asset_store),
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
        object_store=asset_store,
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
    command = (
        await session.execute(
            select(CloudCommand).where(CloudCommand.command_id == command_id)
        )
    ).scalar_one_or_none()
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


async def _latest_plants(
    session: AsyncSession,
    *,
    site_id: str,
    tent_id: str,
) -> list[PlantProjection]:
    rows = (
        await session.execute(
            select(CloudPlant, CloudPlantLocation, CloudPlantLine)
            .join(
                CloudPlantLocation,
                and_(
                    CloudPlantLocation.site_id == CloudPlant.site_id,
                    CloudPlantLocation.source_plant_id == CloudPlant.source_plant_id,
                ),
            )
            .outerjoin(
                CloudPlantLine,
                and_(
                    CloudPlantLine.site_id == CloudPlant.site_id,
                    CloudPlantLine.source_line_id == CloudPlant.line_source_id,
                ),
            )
            .where(
                CloudPlant.site_id == site_id,
                CloudPlantLocation.site_id == site_id,
                CloudPlantLocation.tent_id == tent_id,
                CloudPlantLocation.end_at.is_(None),
            )
            .order_by(CloudPlantLocation.grid_position, CloudPlant.key)
        )
    ).all()
    return [
        PlantProjection(plant=plant, location=location, line=line)
        for plant, location, line in rows
    ]


def _plant_summary_response(
    projection: PlantProjection,
    *,
    telemetry_stream_count: int,
) -> PlantSummaryResponse:
    plant = projection.plant
    location = projection.location
    return PlantSummaryResponse(
        site_id=plant.site_id,
        tent_id=location.tent_id,
        id=plant.source_plant_id,
        key=plant.key,
        line_source_id=plant.line_source_id,
        line=_plant_line_response(projection.line),
        name=plant.name,
        grid_position=location.grid_position,
        germinated_at=plant.germinated_at,
        rooted_at=plant.rooted_at,
        veg_started_at=plant.veg_started_at,
        flower_started_at=plant.flower_started_at,
        culled_at=plant.culled_at,
        harvested_at=plant.harvested_at,
        is_active=plant.is_active,
        telemetry_stream_count=telemetry_stream_count,
    )


async def _get_plant(
    session: AsyncSession,
    *,
    site_id: str,
    tent_id: str,
    plant_id: str,
) -> PlantProjection:
    row = (
        await session.execute(
            select(CloudPlant, CloudPlantLocation, CloudPlantLine)
            .join(
                CloudPlantLocation,
                and_(
                    CloudPlantLocation.site_id == CloudPlant.site_id,
                    CloudPlantLocation.source_plant_id == CloudPlant.source_plant_id,
                ),
            )
            .outerjoin(
                CloudPlantLine,
                and_(
                    CloudPlantLine.site_id == CloudPlant.site_id,
                    CloudPlantLine.source_line_id == CloudPlant.line_source_id,
                ),
            )
            .where(
                CloudPlant.site_id == site_id,
                CloudPlant.key == plant_id,
                CloudPlantLocation.site_id == site_id,
                CloudPlantLocation.tent_id == tent_id,
                CloudPlantLocation.end_at.is_(None),
            )
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "plant not found")
    plant, location, line = row
    return PlantProjection(plant=plant, location=location, line=line)


async def _active_plant_stream_counts(
    session: AsyncSession,
    *,
    site_id: str,
    plants: list[PlantProjection],
) -> dict[int, int]:
    source_plant_ids = {plant.plant.source_plant_id for plant in plants}
    if not source_plant_ids:
        return {}
    rows = (
        await session.execute(
            select(
                CloudPlantMetricStream.source_plant_id,
                func.count(CloudPlantMetricStream.id),
            )
            .where(
                CloudPlantMetricStream.site_id == site_id,
                CloudPlantMetricStream.is_active.is_(True),
                CloudPlantMetricStream.source_plant_id.in_(tuple(source_plant_ids)),
            )
            .group_by(CloudPlantMetricStream.source_plant_id)
        )
    ).all()
    return {
        source_plant_id: count
        for source_plant_id, count in rows
        if source_plant_id in source_plant_ids
    }


async def _active_plant_metric_streams(
    session: AsyncSession,
    *,
    site_id: str,
    plant: PlantProjection,
) -> list[PlantMetricStreamProjection]:
    rows = (
        await session.execute(
            select(CloudPlantMetricStream, CloudMetricPresentation)
            .outerjoin(
                CloudMetricPresentation,
                CloudMetricPresentation.metric == CloudPlantMetricStream.metric,
            )
            .where(
                CloudPlantMetricStream.site_id == site_id,
                CloudPlantMetricStream.source_plant_id == plant.plant.source_plant_id,
                CloudPlantMetricStream.is_active.is_(True),
            )
            .order_by(
                CloudPlantMetricStream.display_order,
                CloudMetricPresentation.display_order,
                CloudPlantMetricStream.metric,
                CloudPlantMetricStream.device_id,
                CloudPlantMetricStream.capability_id,
            )
        )
    ).all()
    return [
        PlantMetricStreamProjection(stream=stream, presentation=presentation)
        for stream, presentation in rows
    ]


async def _latest_metrics_by_stream(
    session: AsyncSession,
    *,
    site_id: str,
    tent_id: str,
    streams: list[CloudPlantMetricStream],
) -> dict[MetricStreamKey, CloudLatestMetric]:
    stream_keys = {_metric_stream_key(stream) for stream in streams}
    if not stream_keys:
        return {}
    device_ids, capability_ids, metrics = _metric_stream_filter_values(stream_keys)
    rows = (
        await session.execute(
            select(CloudLatestMetric).where(
                CloudLatestMetric.site_id == site_id,
                CloudLatestMetric.tent_id == tent_id,
                CloudLatestMetric.device_id.in_(device_ids),
                CloudLatestMetric.capability_id.in_(capability_ids),
                CloudLatestMetric.metric.in_(metrics),
            )
        )
    ).scalars()
    latest_by_stream: dict[MetricStreamKey, CloudLatestMetric] = {}
    for row in rows:
        row_key = _latest_metric_key(row)
        if row_key in stream_keys:
            latest_by_stream[row_key] = row
    return latest_by_stream


async def _metric_rollups_by_stream(  # noqa: PLR0913
    session: AsyncSession,
    *,
    site_id: str,
    tent_id: str,
    bucket: str,
    cutoff: datetime,
    streams: list[CloudPlantMetricStream],
) -> dict[MetricStreamKey, list[CloudMetricRollup]]:
    stream_keys = {_metric_stream_key(stream) for stream in streams}
    if not stream_keys:
        return {}
    device_ids, capability_ids, metrics = _metric_stream_filter_values(stream_keys)
    rows = (
        (
            await session.execute(
                select(CloudMetricRollup)
                .where(
                    CloudMetricRollup.site_id == site_id,
                    CloudMetricRollup.tent_id == tent_id,
                    CloudMetricRollup.bucket == bucket,
                    CloudMetricRollup.bucket_start_at >= cutoff,
                    CloudMetricRollup.device_id.in_(device_ids),
                    CloudMetricRollup.capability_id.in_(capability_ids),
                    CloudMetricRollup.metric.in_(metrics),
                )
                .order_by(CloudMetricRollup.bucket_start_at)
            )
        )
        .scalars()
        .all()
    )
    by_stream: dict[MetricStreamKey, list[CloudMetricRollup]] = {}
    for row in rows:
        row_key = _rollup_key(row)
        if row_key in stream_keys:
            by_stream.setdefault(row_key, []).append(row)
    return by_stream


def _plant_detail_response(
    plant: PlantProjection,
    *,
    telemetry: list[PlantMetricStreamResponse],
    wiki_page: CloudWikiPage | None,
) -> PlantDetailResponse:
    cloud_plant = plant.plant
    location = plant.location
    return PlantDetailResponse(
        site_id=cloud_plant.site_id,
        tent_id=location.tent_id,
        id=cloud_plant.source_plant_id,
        key=cloud_plant.key,
        line_source_id=cloud_plant.line_source_id,
        line=_plant_line_response(plant.line),
        name=cloud_plant.name,
        grid_position=location.grid_position,
        current_location=_plant_current_location_response(location),
        germinated_at=cloud_plant.germinated_at,
        rooted_at=cloud_plant.rooted_at,
        veg_started_at=cloud_plant.veg_started_at,
        flower_started_at=cloud_plant.flower_started_at,
        culled_at=cloud_plant.culled_at,
        culled_reason=cloud_plant.culled_reason,
        harvested_at=cloud_plant.harvested_at,
        selected_for_breeding_at=cloud_plant.selected_for_breeding_at,
        selected_for_breeding_reason=cloud_plant.selected_for_breeding_reason,
        is_active=cloud_plant.is_active,
        telemetry_stream_count=len(telemetry),
        telemetry=telemetry,
        notes=[],
        events=[],
        wiki_content=(
            None
            if wiki_page is None
            else PlantWikiContentResponse(
                path=wiki_page.path,
                title=wiki_page.title,
                frontmatter=wiki_page.frontmatter,
                body_markdown=wiki_page.body_markdown,
                sha256=wiki_page.sha256,
                source_updated_at=wiki_page.source_updated_at,
            )
        ),
    )


def _plant_line_response(line: CloudPlantLine | None) -> PlantLineResponse | None:
    if line is None:
        return None
    return PlantLineResponse(
        id=line.source_line_id,
        project_code=line.project_code,
        generation_label=line.generation_label,
        strain=line.strain,
        cultivar=line.cultivar,
        source_name=line.source_name,
    )


def _plant_current_location_response(
    location: CloudPlantLocation,
) -> PlantCurrentLocationResponse:
    return PlantCurrentLocationResponse(
        id=location.source_location_id,
        tent_id=location.tent_id,
        grid_position=location.grid_position,
        start_at=location.start_at,
        end_at=location.end_at,
    )


def _plant_metric_stream_responses(
    rows: list[PlantMetricStreamProjection],
    latest_by_stream: dict[MetricStreamKey, CloudLatestMetric],
) -> list[PlantMetricStreamResponse]:
    return [
        _plant_metric_stream_response(
            row,
            latest_by_stream.get(_metric_stream_key(row.stream)),
        )
        for row in rows
    ]


def _plant_metric_stream_response(
    row: PlantMetricStreamProjection,
    latest: CloudLatestMetric | None,
) -> PlantMetricStreamResponse:
    stream = row.stream
    source_unit = _source_unit_for_metric(
        stream.metric, latest.unit if latest else None
    )
    display_unit = _display_unit_for_metric(
        stream.metric, row.presentation, source_unit
    )
    return PlantMetricStreamResponse(
        metric=stream.metric,
        display_name=_display_name_for_metric(stream.metric, row.presentation),
        display_unit=display_unit,
        source_unit=source_unit,
        value_precision=_value_precision_for_metric(row.presentation),
        accent=_accent_for_metric(row.presentation),
        y_min=row.presentation.y_min if row.presentation else None,
        y_max=row.presentation.y_max if row.presentation else None,
        display_order=stream.display_order,
        history_enabled=bool(row.presentation and row.presentation.history_enabled),
        device_id=stream.device_id,
        capability_id=stream.capability_id,
        latest_reading=(
            None
            if latest is None
            else PlantMetricReadingResponse(
                value=_display_metric_value(stream.metric, latest.value),
                source_value=latest.value,
                source_unit=source_unit,
                display_unit=display_unit,
                device_id=latest.device_id,
                capability_id=latest.capability_id,
                source_updated_at=latest.source_updated_at,
                received_at=latest.received_at,
                stale_after_s=latest.stale_after_s,
            )
        ),
    )


def _plant_metric_history_stream_response(
    row: PlantMetricStreamProjection,
    rollups: list[CloudMetricRollup],
) -> PlantMetricHistoryStreamResponse:
    stream = row.stream
    source_unit = _source_unit_for_metric(
        stream.metric, rollups[0].unit if rollups else None
    )
    display_unit = _display_unit_for_metric(
        stream.metric, row.presentation, source_unit
    )
    return PlantMetricHistoryStreamResponse(
        metric=stream.metric,
        display_name=_display_name_for_metric(stream.metric, row.presentation),
        display_unit=display_unit,
        source_unit=source_unit,
        value_precision=_value_precision_for_metric(row.presentation),
        accent=_accent_for_metric(row.presentation),
        y_min=row.presentation.y_min if row.presentation else None,
        y_max=row.presentation.y_max if row.presentation else None,
        display_order=stream.display_order,
        device_id=stream.device_id,
        capability_id=stream.capability_id,
        points=[
            PlantMetricHistoryPointResponse(
                bucket=rollup.bucket,
                bucket_start_at=rollup.bucket_start_at,
                bucket_end_at=rollup.bucket_end_at,
                min=_display_optional_metric_value(stream.metric, rollup.min_value),
                avg=_display_optional_metric_value(stream.metric, rollup.avg_value),
                max=_display_optional_metric_value(stream.metric, rollup.max_value),
                source_min=rollup.min_value,
                source_avg=rollup.avg_value,
                source_max=rollup.max_value,
                sample_count=rollup.sample_count,
                source_unit=_source_unit_for_metric(stream.metric, rollup.unit),
                display_unit=display_unit,
            )
            for rollup in rollups
        ],
    )


def _metric_stream_key(stream: CloudPlantMetricStream) -> MetricStreamKey:
    return stream.device_id, stream.capability_id, stream.metric


def _latest_metric_key(row: CloudLatestMetric) -> MetricStreamKey:
    return row.device_id, row.capability_id, row.metric


def _rollup_key(row: CloudMetricRollup) -> MetricStreamKey:
    return row.device_id, row.capability_id, row.metric


def _metric_stream_filter_values(
    stream_keys: set[MetricStreamKey],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    return (
        tuple({device_id for device_id, _, _ in stream_keys}),
        tuple({capability_id for _, capability_id, _ in stream_keys}),
        tuple({metric for _, _, metric in stream_keys}),
    )


def _display_metric_value(metric: str, value: float) -> float:
    if metric == "substrate_temp_c":
        return value * 9 / 5 + 32
    if metric == "substrate_ec_us_cm":
        return value / 1000
    return value


def _display_optional_metric_value(metric: str, value: float | None) -> float | None:
    if value is None:
        return None
    return _display_metric_value(metric, value)


def _source_unit_for_metric(metric: str, source_unit: str | None) -> str | None:
    return source_unit or SOURCE_UNITS_BY_METRIC.get(metric)


def _display_unit_for_metric(
    metric: str,
    presentation: CloudMetricPresentation | None,
    source_unit: str | None,
) -> str:
    if presentation is not None:
        return presentation.unit
    return DISPLAY_UNITS_BY_METRIC.get(metric) or source_unit or ""


def _display_name_for_metric(
    metric: str, presentation: CloudMetricPresentation | None
) -> str:
    if presentation is not None:
        return presentation.display_name
    return metric.replace("_", " ").title()


def _value_precision_for_metric(presentation: CloudMetricPresentation | None) -> int:
    return presentation.value_precision if presentation is not None else 1


def _accent_for_metric(presentation: CloudMetricPresentation | None) -> str:
    return presentation.accent if presentation is not None else "neutral"


def _asset_response(
    asset: CloudAsset,
    *,
    settings: CloudSettings,
    asset_store: AssetStore,
    now: datetime,
) -> AssetResponse:
    expires_at = expires_from(now, settings.asset_url_ttl_s)
    signed_url = asset_store.presign_get(
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
        subject_id = _device_audit_subject_id(device)
        _, metrics = current_by_device.setdefault(subject_id, (device, []))
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
    for subject_id, (device, metrics) in current_by_device.items():
        if subject_id in recent_subject_ids:
            continue
        emitted = True
        add_audit_event(
            session,
            now=now,
            event_type="data_consistency_missing_device_liveness",
            actor_type="system",
            site_id=site_id,
            subject_type="cloud_device",
            subject_id=subject_id,
            metadata={
                "tent_id": device.tent_id,
                "device_id": device.device_id,
                "metrics": sorted({metric.metric for metric in metrics}),
                "capability_ids": sorted({metric.capability_id for metric in metrics}),
            },
        )
    if emitted:
        await session.commit()


def _device_audit_subject_id(device: CloudDevice) -> str:
    return f"site={device.site_id};tent={device.tent_id};device={device.device_id}"


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
