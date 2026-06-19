from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dirt_control.audit import add_audit_event
from dirt_control.deps import get_asset_store, get_clock, get_session, get_settings
from dirt_control.models import (
    CloudAsset,
    CloudAuditEvent,
    CloudCommand,
    CloudCrossEvent,
    CloudDevice,
    CloudLatestMetric,
    CloudMetricPresentation,
    CloudMetricRollup,
    CloudPlant,
    CloudPlantEvent,
    CloudPlantLine,
    CloudPlantLocation,
    CloudPlantMetricStream,
    CloudPlantNote,
    CloudSchedule,
    CloudSeedLot,
    CloudSite,
    CloudTent,
    CloudWikiPage,
    GatewayCredential,
)
from dirt_control.retention import prune_expired_assets
from dirt_control.security import expires_from, require_browser_user, verify_password
from dirt_control.settings import CloudSettings
from dirt_control.storage import AssetStore
from dirt_shared.cloud_contract import (
    BreedingBulkCullPayload,
    BreedingBulkMovePayload,
    BreedingBulkSexPayload,
    BreedingClonePlantsPayload,
    BreedingCommandPayload,
    BreedingCreatePlantNotePayload,
    BreedingCreateSeedLotPayload,
    BreedingGerminatePlantsPayload,
    CommandType,
    PlantSexKey,
    PruneAssetsResponse,
)

router = APIRouter(prefix="/api")
COMMAND_EXPIRY_SECONDS = 60
BREEDING_COMMAND_EXPIRY_SECONDS = 3600
BREEDING_SITE_WIDE_TENT_ID = "breeding-logbook"
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
    source_tent_id: int = Field(gt=0)
    device_id: Literal["obsbot-main"]
    capability_id: Literal["ptz_move"]
    command_type: PTZ_COMMAND_TYPES
    payload: dict[str, Any] = Field(default_factory=dict)


class BrowserRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BreedingCommandRequest(BrowserRequest):
    idempotency_key: str = Field(min_length=1, max_length=160)


class BreedingCreateSeedLotRequest(BreedingCreateSeedLotPayload):
    idempotency_key: str = Field(min_length=1, max_length=160)


class BreedingGerminatePlantsRequest(BreedingCommandRequest):
    seed_lot_id: str = Field(min_length=1)
    count: int = Field(gt=0)
    source_tent_id: int = Field(gt=0)
    grid_position: Literal[None] = Field(...)
    germinated_at: datetime | None = None


class BreedingClonePlantsRequest(BreedingCommandRequest):
    mother_plant_key: str = Field(min_length=1, max_length=120)
    count: int = Field(gt=0)
    source_tent_id: int = Field(gt=0)
    grid_position: Literal[None] = Field(...)
    taken_at: datetime | None = None


class BreedingBulkSexRequest(BreedingCommandRequest):
    plant_keys: list[str] = Field(min_length=1)
    sex_key: PlantSexKey

    @field_validator("plant_keys")
    @classmethod
    def _clean_plant_keys(cls, value: list[str]) -> list[str]:
        return _clean_nonblank_list(value, field_name="plant_keys")


class BreedingBulkMoveRequest(BreedingCommandRequest):
    plant_keys: list[str] = Field(min_length=1)
    source_tent_id: int = Field(gt=0)
    grid_position: Literal[None] = Field(...)

    @field_validator("plant_keys")
    @classmethod
    def _clean_plant_keys(cls, value: list[str]) -> list[str]:
        return _clean_nonblank_list(value, field_name="plant_keys")


class BreedingBulkCullRequest(BreedingCommandRequest):
    plant_keys: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)

    @field_validator("plant_keys")
    @classmethod
    def _clean_plant_keys(cls, value: list[str]) -> list[str]:
        return _clean_nonblank_list(value, field_name="plant_keys")

    @field_validator("reason")
    @classmethod
    def _clean_reason(cls, value: str) -> str:
        return _clean_nonblank(value, field_name="reason")


class BreedingCreatePlantNoteRequest(BreedingCommandRequest):
    body: str = Field(min_length=1)
    observed_at: datetime | None = None

    @field_validator("body")
    @classmethod
    def _clean_body(cls, value: str) -> str:
        return _clean_nonblank(value, field_name="body")


class GatewayCredentialRotateRequest(BaseModel):
    token_sha256: str = Field(min_length=64, max_length=64)


class BrowserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")


SyncStatusLabel = Literal["live", "stale", "offline"]
BreedingLogbookPlantStageKey = Literal[
    "germinating",
    "veg",
    "flower",
    "breeding",
    "harvested",
    "culled",
]
BreedingLogbookSeedLotSexTypeKey = Literal["unknown", "feminized", "regular"]
BreedingLogbookSeedLotSource = Literal["cross", "purchased"]
BreedingLogbookGroupBy = Literal["stage"]


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
    source_tent_id: int
    name: str
    role: str | None
    is_active: bool
    synced_at: datetime


class TentStateResponse(BrowserResponse):
    site_id: str
    source_tent_id: int
    name: str
    role: str | None
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


class BreedingLogbookLookupResponse(BrowserResponse):
    key: str
    display_name: str
    display_order: int


class BreedingLogbookLocationOptionResponse(BrowserResponse):
    source_tent_id: int
    display_name: str
    role: str | None
    grid_position: str | None


class BreedingLogbookBootstrapResponse(BrowserResponse):
    today: date
    today_label: str
    plant_sexes: list[BreedingLogbookLookupResponse]
    seed_lot_sex_types: list[BreedingLogbookLookupResponse]
    stages: list[BreedingLogbookLookupResponse]
    locations: list[BreedingLogbookLocationOptionResponse]


class BreedingLogbookSeedLotSummaryResponse(BrowserResponse):
    id: str
    label: str
    prefix: str
    strain: str
    cultivar: str
    generation: str
    source: BreedingLogbookSeedLotSource
    source_label: str
    parents_label: str
    sex_type_key: BreedingLogbookSeedLotSexTypeKey
    seed_count: int | None


class BreedingLogbookSeedLotListResponse(BrowserResponse):
    seed_lots: list[BreedingLogbookSeedLotSummaryResponse]


class BreedingLogbookPlantRowResponse(BrowserResponse):
    id: str
    key: str
    name: str
    generation: str
    parents_label: str
    sex_key: PlantSexKey
    stage_key: BreedingLogbookPlantStageKey
    stage_day: int
    germinated_on: date | None
    veg_started_on: date | None
    flower_started_on: date | None
    culled_on: date | None
    current_tent_id: int
    current_tent_name: str
    grid_position: str | None
    seed_lot_label: str
    last_note: str
    telemetry_summary: str


class BreedingLogbookPlantListResponse(BrowserResponse):
    active_count: int
    culled_count: int
    group_by: BreedingLogbookGroupBy
    plants: list[BreedingLogbookPlantRowResponse]


class BreedingLogbookPlantMetricSummaryResponse(BrowserResponse):
    label: str
    value: str
    tone: Literal["ok", "warn"]


class BreedingLogbookLineageResponse(BrowserResponse):
    parents: str
    offspring: str


class BreedingLogbookPlantJournalEventResponse(BrowserResponse):
    id: str
    occurred_at: datetime | None
    date_label: str
    tag: Literal["cross", "note", "stage", "sex", "germ"]
    body: str
    has_photo: bool


class BreedingLogbookPlantDetailResponse(BrowserResponse):
    plant: BreedingLogbookPlantRowResponse
    lineage: BreedingLogbookLineageResponse
    metrics: list[BreedingLogbookPlantMetricSummaryResponse]
    events: list[BreedingLogbookPlantJournalEventResponse]
    telemetry: list[PlantMetricStreamResponse]
    wiki_content: PlantWikiContentResponse | None


class PlantSummaryResponse(BrowserResponse):
    site_id: str
    current_tent_id: int
    current_tent_name: str
    id: int
    key: str
    line_source_id: int
    line: PlantLineResponse | None
    sex_key: PlantSexKey
    name: str
    grid_position: str | None
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
    current_tent_id: int
    current_tent_name: str
    grid_position: str | None
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
    current_tent_id: int
    current_tent_name: str
    id: int
    key: str
    line_source_id: int
    line: PlantLineResponse | None
    sex_key: PlantSexKey
    name: str
    grid_position: str | None
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
    tent: CloudTent | None
    line: CloudPlantLine | None


@dataclass(frozen=True)
class BreedingLogbookPlantProjection:
    plant: CloudPlant
    location: CloudPlantLocation
    tent: CloudTent | None
    line: CloudPlantLine | None
    seed_lot: CloudSeedLot | None
    seed_lot_line: CloudPlantLine | None


class LightScheduleResponse(BrowserResponse):
    site_id: str
    source_tent_id: int
    tent_name: str
    source_zone_id: int | None
    device_id: str | None
    capability_id: str | None
    source_schedule_id: int
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
    source_tent_id: int
    tent_name: str
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
    source_tent_id: int | None
    legacy_target_tent_id: str
    device_id: str | None
    capability_id: str | None
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
            .order_by(CloudTent.source_tent_id, CloudTent.name)
        )
    ).scalars()
    return [
        TentResponse(
            site_id=row.site_id,
            source_tent_id=_required_source_tent_id(row),
            name=row.name,
            role=row.role,
            is_active=row.is_active,
            synced_at=row.synced_at,
        )
        for row in rows
    ]


@router.get("/tents/{source_tent_id}/state", response_model=TentStateResponse)
async def tent_state(
    source_tent_id: int,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> TentStateResponse:
    site = (
        await session.execute(
            select(CloudSite).where(CloudSite.site_id == settings.default_site_id)
        )
    ).scalar_one_or_none()
    tent = await _get_cloud_tent_by_source_id(
        session, site_id=settings.default_site_id, source_tent_id=source_tent_id
    )
    return TentStateResponse(
        site_id=tent.site_id,
        source_tent_id=_required_source_tent_id(tent),
        name=tent.name,
        role=tent.role,
        is_active=tent.is_active,
        gateway_last_seen_at=site.gateway_last_seen_at if site else None,
        last_catalog_sync_at=site.last_catalog_sync_at if site else None,
    )


@router.get(
    "/tents/{source_tent_id}/metrics/current",
    response_model=list[CurrentMetricResponse],
)
async def current_metrics(
    source_tent_id: int,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> list[CurrentMetricResponse]:
    rows = (
        await session.execute(
            select(CloudLatestMetric)
            .where(
                CloudLatestMetric.site_id == settings.default_site_id,
                CloudLatestMetric.source_tent_id == source_tent_id,
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
    "/tents/{source_tent_id}/metrics/presentation",
    response_model=MetricPresentationResponse,
)
async def metric_presentation(
    source_tent_id: int,
    _: str = Depends(require_browser_user),
    session: AsyncSession = Depends(get_session),
) -> MetricPresentationResponse:
    _ = source_tent_id
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


@router.get(
    "/tents/{source_tent_id}/metrics/history", response_model=MetricHistoryResponse
)
async def metric_history(  # noqa: PLR0913
    source_tent_id: int,
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
                CloudMetricRollup.source_tent_id == source_tent_id,
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


@router.get(
    "/breeding-logbook/bootstrap",
    response_model=BreedingLogbookBootstrapResponse,
)
async def breeding_logbook_bootstrap(
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> BreedingLogbookBootstrapResponse:
    today = clock().date()
    tents = (
        await session.execute(
            select(CloudTent)
            .where(
                CloudTent.site_id == settings.default_site_id,
                CloudTent.is_active.is_(True),
                CloudTent.source_tent_id.is_not(None),
            )
            .order_by(CloudTent.source_tent_id, CloudTent.name)
        )
    ).scalars()
    return BreedingLogbookBootstrapResponse(
        today=today,
        today_label=today.strftime("%m/%d/%y"),
        plant_sexes=[
            BreedingLogbookLookupResponse(
                key=key,
                display_name=display_name,
                display_order=display_order,
            )
            for key, display_name, display_order in (
                ("unknown", "Unknown", 10),
                ("male", "Male", 20),
                ("female", "Female", 30),
                ("herm", "Hermaphrodite", 40),
                ("reversed", "Reversed", 50),
            )
        ],
        seed_lot_sex_types=[
            BreedingLogbookLookupResponse(
                key=key,
                display_name=display_name,
                display_order=display_order,
            )
            for key, display_name, display_order in (
                ("unknown", "Unknown", 10),
                ("feminized", "Feminized", 20),
                ("regular", "Regular", 30),
            )
        ],
        stages=[
            BreedingLogbookLookupResponse(
                key=key,
                display_name=display_name,
                display_order=display_order,
            )
            for key, display_name, display_order in (
                ("germinating", "Germinating", 10),
                ("veg", "Veg", 20),
                ("flower", "Flower", 30),
                ("breeding", "Breeding", 40),
                ("harvested", "Harvested", 50),
                ("culled", "Culled", 60),
            )
        ],
        locations=[
            BreedingLogbookLocationOptionResponse(
                source_tent_id=_required_source_tent_id(tent),
                display_name=tent.name,
                role=tent.role,
                grid_position=None,
            )
            for tent in tents
        ],
    )


@router.get(
    "/breeding-logbook/plants",
    response_model=BreedingLogbookPlantListResponse,
)
async def breeding_logbook_plants(
    include_culled: bool = False,
    group_by: BreedingLogbookGroupBy = "stage",
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> BreedingLogbookPlantListResponse:
    plant_rows = await _breeding_logbook_plants(
        session,
        site_id=settings.default_site_id,
        include_culled=include_culled,
    )
    stream_counts = await _breeding_logbook_stream_counts(
        session,
        site_id=settings.default_site_id,
        plants=plant_rows,
    )
    plant_ids = [row.plant.source_plant_id for row in plant_rows]
    latest_notes = await _breeding_logbook_latest_notes(
        session,
        site_id=settings.default_site_id,
        plant_ids=plant_ids,
    )
    latest_events = await _breeding_logbook_latest_events(
        session,
        site_id=settings.default_site_id,
        plant_ids=plant_ids,
    )
    today = clock().date()
    rows = [
        _breeding_logbook_plant_row_response(
            row,
            telemetry_stream_count=stream_counts.get(row.plant.source_plant_id, 0),
            latest_note=latest_notes.get(row.plant.source_plant_id),
            latest_event=latest_events.get(row.plant.source_plant_id),
            today=today,
        )
        for row in plant_rows
    ]
    return BreedingLogbookPlantListResponse(
        active_count=sum(1 for row in rows if row.stage_key != "culled"),
        culled_count=sum(1 for row in rows if row.stage_key == "culled"),
        group_by=group_by,
        plants=rows,
    )


@router.get(
    "/breeding-logbook/seed-lots",
    response_model=BreedingLogbookSeedLotListResponse,
)
async def breeding_logbook_seed_lots(
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> BreedingLogbookSeedLotListResponse:
    rows = (
        await session.execute(
            select(CloudSeedLot, CloudPlantLine)
            .outerjoin(
                CloudPlantLine,
                and_(
                    CloudPlantLine.site_id == CloudSeedLot.site_id,
                    CloudPlantLine.source_line_id == CloudSeedLot.line_source_id,
                ),
            )
            .where(CloudSeedLot.site_id == settings.default_site_id)
            .order_by(
                CloudPlantLine.project_code,
                CloudPlantLine.generation_label,
                CloudSeedLot.source_seed_lot_id,
            )
        )
    ).all()
    return BreedingLogbookSeedLotListResponse(
        seed_lots=[
            _breeding_logbook_seed_lot_summary_response(seed_lot, line)
            for seed_lot, line in rows
        ]
    )


@router.get(
    "/breeding-logbook/plants/{plant_key}/metrics/history",
    response_model=PlantMetricHistoryResponse,
)
async def breeding_logbook_plant_metric_history(
    plant_key: str,
    range: str = "24h",
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> PlantMetricHistoryResponse:
    range_spec = METRIC_HISTORY_RANGES.get(range)
    if range_spec is None:
        raise HTTPException(status_code=400, detail="invalid range")
    plant = await _get_breeding_logbook_plant(
        session,
        site_id=settings.default_site_id,
        plant_key=plant_key,
    )
    stream_rows = [
        row
        for row in await _active_plant_metric_streams(
            session,
            site_id=settings.default_site_id,
            plant=_plant_projection_from_breeding_logbook(plant),
        )
        if row.presentation is not None and row.presentation.history_enabled
    ]
    bucket, window = range_spec
    history_by_stream = await _metric_rollups_by_stream(
        session,
        site_id=settings.default_site_id,
        source_tent_id=_required_location_source_tent_id(plant.location),
        bucket=bucket,
        cutoff=clock() - window,
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


@router.get(
    "/breeding-logbook/plants/{plant_key}",
    response_model=BreedingLogbookPlantDetailResponse,
)
async def breeding_logbook_plant_detail(
    plant_key: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> BreedingLogbookPlantDetailResponse:
    plant = await _get_breeding_logbook_plant(
        session,
        site_id=settings.default_site_id,
        plant_key=plant_key,
    )
    stream_rows = await _active_plant_metric_streams(
        session,
        site_id=settings.default_site_id,
        plant=_plant_projection_from_breeding_logbook(plant),
    )
    latest_by_stream = await _latest_metrics_by_stream(
        session,
        site_id=settings.default_site_id,
        source_tent_id=_required_location_source_tent_id(plant.location),
        streams=[row.stream for row in stream_rows],
    )
    notes = await _breeding_logbook_plant_notes(
        session,
        site_id=settings.default_site_id,
        source_plant_id=plant.plant.source_plant_id,
    )
    events = await _breeding_logbook_plant_events(
        session,
        site_id=settings.default_site_id,
        source_plant_id=plant.plant.source_plant_id,
    )
    lineage = await _breeding_logbook_lineage(
        session,
        site_id=settings.default_site_id,
        plant=plant,
    )
    telemetry = _plant_metric_stream_responses(stream_rows, latest_by_stream)
    return BreedingLogbookPlantDetailResponse(
        plant=_breeding_logbook_plant_row_response(
            plant,
            telemetry_stream_count=len(telemetry),
            latest_note=notes[0] if notes else None,
            latest_event=events[0] if events else None,
            today=clock().date(),
        ),
        lineage=lineage,
        metrics=_breeding_logbook_metric_summaries(telemetry),
        events=_breeding_logbook_journal_events(notes=notes, events=events),
        telemetry=telemetry,
        wiki_content=None,
    )


@router.get("/tents/{source_tent_id}/plants", response_model=list[PlantSummaryResponse])
async def plants(
    source_tent_id: int,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> list[PlantSummaryResponse]:
    latest_rows = await _latest_plants(
        session,
        site_id=settings.default_site_id,
        source_tent_id=source_tent_id,
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


@router.get(
    "/tents/{source_tent_id}/plants/{plant_id}", response_model=PlantDetailResponse
)
async def plant_detail(
    source_tent_id: int,
    plant_id: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> PlantDetailResponse:
    plant = await _get_plant(
        session,
        site_id=settings.default_site_id,
        source_tent_id=source_tent_id,
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
        source_tent_id=source_tent_id,
        streams=[row.stream for row in stream_rows],
    )
    return _plant_detail_response(
        plant,
        telemetry=_plant_metric_stream_responses(stream_rows, latest_by_stream),
        wiki_page=None,
    )


@router.get(
    "/tents/{source_tent_id}/plants/{plant_id}/metrics/history",
    response_model=PlantMetricHistoryResponse,
)
async def plant_metric_history(  # noqa: PLR0913
    source_tent_id: int,
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
        source_tent_id=source_tent_id,
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
        source_tent_id=source_tent_id,
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


@router.get("/tents/{source_tent_id}/devices", response_model=list[DeviceResponse])
async def devices(
    source_tent_id: int,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> list[DeviceResponse]:
    rows = (
        await session.execute(
            select(CloudDevice)
            .where(
                CloudDevice.site_id == settings.default_site_id,
                CloudDevice.source_tent_id == source_tent_id,
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
    "/tents/{source_tent_id}/lights/schedules",
    response_model=LightSchedulesResponse,
)
async def light_schedules(
    source_tent_id: int,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> LightSchedulesResponse:
    tent = await _get_cloud_tent_by_source_id(
        session, site_id=settings.default_site_id, source_tent_id=source_tent_id
    )
    rows = (
        await session.execute(
            select(CloudSchedule)
            .where(
                CloudSchedule.site_id == settings.default_site_id,
                CloudSchedule.source_tent_id == source_tent_id,
                CloudSchedule.kind == "lights",
                CloudSchedule.source_schedule_id.is_not(None),
            )
            .order_by(CloudSchedule.source_schedule_id)
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
                source_tent_id=_required_schedule_source_tent_id(row),
                tent_name=tent.name,
                source_zone_id=row.source_zone_id,
                device_id=row.device_id,
                capability_id=row.capability_id,
                source_schedule_id=_required_source_schedule_id(row),
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
        source_tent_id=source_tent_id,
        tent_name=tent.name,
        schedules=schedules,
    )


@router.get("/tents/{source_tent_id}/assets/latest", response_model=list[AssetResponse])
async def latest_assets(
    source_tent_id: int,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    asset_store: AssetStore = Depends(get_asset_store),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> list[AssetResponse]:
    tent = await _get_cloud_tent_by_source_id(
        session, site_id=settings.default_site_id, source_tent_id=source_tent_id
    )
    rows = (
        await session.execute(
            select(CloudAsset)
            .where(
                CloudAsset.site_id == settings.default_site_id,
                CloudAsset.tent_id == tent.tent_id,
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
    "/breeding-logbook/seed-lots",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def create_breeding_seed_lot(
    body: BreedingCreateSeedLotRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    payload = BreedingCreateSeedLotPayload(
        **body.model_dump(exclude={"idempotency_key"})
    )
    if payload.source == "cross":
        seed_parent_key = payload.seed_parent_plant_key
        pollen_parent_key = payload.pollen_parent_plant_key
        if seed_parent_key is None or pollen_parent_key is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "cross seed lots require seed and pollen parent plant keys",
            )
        await _require_cloud_plant_key(
            session,
            site_id=settings.default_site_id,
            plant_key=seed_parent_key,
        )
        await _require_cloud_plant_key(
            session,
            site_id=settings.default_site_id,
            plant_key=pollen_parent_key,
        )
    return await _enqueue_breeding_command(
        body.idempotency_key,
        user=user,
        settings=settings,
        session=session,
        clock=clock,
        command_type="breeding_seed_lot_create",
        target_tent_id=BREEDING_SITE_WIDE_TENT_ID,
        source_tent_id=None,
        payload=payload,
    )


@router.post(
    "/breeding-logbook/plants:germinate",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def germinate_breeding_plants(
    body: BreedingGerminatePlantsRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    target_tent_id = await _legacy_tent_id_for_browser_source_tent_id(
        session,
        site_id=settings.default_site_id,
        source_tent_id=body.source_tent_id,
    )
    seed_lot_source_id = _seed_lot_source_id_from_request(body.seed_lot_id)
    await _require_cloud_seed_lot_source_id(
        session,
        site_id=settings.default_site_id,
        seed_lot_source_id=seed_lot_source_id,
    )
    payload = BreedingGerminatePlantsPayload(
        seed_lot_source_id=seed_lot_source_id,
        count=body.count,
        source_tent_id=body.source_tent_id,
        grid_position=None,
        germinated_at=body.germinated_at,
    )
    return await _enqueue_breeding_command(
        body.idempotency_key,
        user=user,
        settings=settings,
        session=session,
        clock=clock,
        command_type="breeding_plants_germinate",
        target_tent_id=target_tent_id,
        source_tent_id=body.source_tent_id,
        payload=payload,
    )


@router.post(
    "/breeding-logbook/plants:clone",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def clone_breeding_plants(
    body: BreedingClonePlantsRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    target_tent_id = await _legacy_tent_id_for_browser_source_tent_id(
        session,
        site_id=settings.default_site_id,
        source_tent_id=body.source_tent_id,
    )
    mother = await _require_cloud_plant_key(
        session, site_id=settings.default_site_id, plant_key=body.mother_plant_key
    )
    payload = BreedingClonePlantsPayload(
        mother_plant_key=mother.key,
        count=body.count,
        source_tent_id=body.source_tent_id,
        grid_position=None,
        taken_at=body.taken_at,
    )
    return await _enqueue_breeding_command(
        body.idempotency_key,
        user=user,
        settings=settings,
        session=session,
        clock=clock,
        command_type="breeding_plants_clone",
        target_tent_id=target_tent_id,
        source_tent_id=body.source_tent_id,
        payload=payload,
    )


@router.post(
    "/breeding-logbook/plants:bulk-sex",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def bulk_sex_breeding_plants(
    body: BreedingBulkSexRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    await _require_cloud_plant_keys(
        session, site_id=settings.default_site_id, plant_keys=body.plant_keys
    )
    payload = BreedingBulkSexPayload(plant_keys=body.plant_keys, sex_key=body.sex_key)
    return await _enqueue_breeding_command(
        body.idempotency_key,
        user=user,
        settings=settings,
        session=session,
        clock=clock,
        command_type="breeding_plants_bulk_sex",
        target_tent_id=BREEDING_SITE_WIDE_TENT_ID,
        source_tent_id=None,
        payload=payload,
    )


@router.post(
    "/breeding-logbook/plants:bulk-move",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def bulk_move_breeding_plants(
    body: BreedingBulkMoveRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    target_tent_id = await _legacy_tent_id_for_browser_source_tent_id(
        session,
        site_id=settings.default_site_id,
        source_tent_id=body.source_tent_id,
    )
    await _require_cloud_plant_keys(
        session, site_id=settings.default_site_id, plant_keys=body.plant_keys
    )
    payload = BreedingBulkMovePayload(
        plant_keys=body.plant_keys,
        source_tent_id=body.source_tent_id,
        grid_position=None,
    )
    return await _enqueue_breeding_command(
        body.idempotency_key,
        user=user,
        settings=settings,
        session=session,
        clock=clock,
        command_type="breeding_plants_bulk_move",
        target_tent_id=target_tent_id,
        source_tent_id=body.source_tent_id,
        payload=payload,
    )


@router.post(
    "/breeding-logbook/plants:bulk-cull",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def bulk_cull_breeding_plants(
    body: BreedingBulkCullRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    await _require_cloud_plant_keys(
        session, site_id=settings.default_site_id, plant_keys=body.plant_keys
    )
    payload = BreedingBulkCullPayload(plant_keys=body.plant_keys, reason=body.reason)
    return await _enqueue_breeding_command(
        body.idempotency_key,
        user=user,
        settings=settings,
        session=session,
        clock=clock,
        command_type="breeding_plants_bulk_cull",
        target_tent_id=BREEDING_SITE_WIDE_TENT_ID,
        source_tent_id=None,
        payload=payload,
    )


@router.post(
    "/breeding-logbook/plants/{plant_key}/notes",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def create_breeding_plant_note(  # noqa: PLR0913
    plant_key: str,
    body: BreedingCreatePlantNoteRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    plant = await _require_cloud_plant_key(
        session, site_id=settings.default_site_id, plant_key=plant_key
    )
    payload = BreedingCreatePlantNotePayload(
        plant_key=plant.key,
        body=body.body,
        observed_at=body.observed_at,
    )
    return await _enqueue_breeding_command(
        body.idempotency_key,
        user=user,
        settings=settings,
        session=session,
        clock=clock,
        command_type="breeding_plant_note_create",
        target_tent_id=BREEDING_SITE_WIDE_TENT_ID,
        source_tent_id=None,
        payload=payload,
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
    target_tent_id = await _legacy_tent_id_for_browser_source_tent_id(
        session, site_id=site_id, source_tent_id=body.source_tent_id
    )
    command = CloudCommand(
        command_id=str(uuid.uuid4()),
        idempotency_key=body.idempotency_key,
        site_id=site_id,
        tent_id=target_tent_id,
        source_tent_id=body.source_tent_id,
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


async def _breeding_logbook_plants(
    session: AsyncSession,
    *,
    site_id: str,
    include_culled: bool,
    plant_key: str | None = None,
) -> list[BreedingLogbookPlantProjection]:
    active_filters = (
        ()
        if include_culled
        else (CloudPlant.is_active.is_(True), CloudPlant.culled_at.is_(None))
    )
    key_filters = () if plant_key is None else (CloudPlant.key == plant_key,)
    plant_rows = (
        await session.execute(
            select(
                CloudPlant,
                CloudPlantLine,
                CloudSeedLot,
            )
            .outerjoin(
                CloudPlantLine,
                and_(
                    CloudPlantLine.site_id == CloudPlant.site_id,
                    CloudPlantLine.source_line_id == CloudPlant.line_source_id,
                ),
            )
            .outerjoin(
                CloudSeedLot,
                and_(
                    CloudSeedLot.site_id == CloudPlant.site_id,
                    CloudSeedLot.source_seed_lot_id == CloudPlant.source_seed_lot_id,
                ),
            )
            .where(
                CloudPlant.site_id == site_id,
                *active_filters,
                *key_filters,
            )
            .order_by(CloudPlant.key)
        )
    ).all()
    plant_ids = [plant.source_plant_id for plant, _line, _seed_lot in plant_rows]
    if not plant_ids:
        return []
    location_rows = (
        await session.execute(
            select(CloudPlantLocation)
            .where(
                CloudPlantLocation.site_id == site_id,
                CloudPlantLocation.source_plant_id.in_(plant_ids),
            )
            .order_by(
                CloudPlantLocation.source_plant_id,
                CloudPlantLocation.start_at,
            )
        )
    ).scalars()
    locations = _breeding_logbook_locations_by_plant(location_rows)
    tents = await _cloud_tents_by_source_id(
        session,
        site_id=site_id,
        source_tent_ids={
            location.source_tent_id
            for location in locations.values()
            if location.source_tent_id is not None
        },
    )
    projections = [
        BreedingLogbookPlantProjection(
            plant=plant,
            location=location,
            tent=tent,
            line=line,
            seed_lot=seed_lot,
            seed_lot_line=line,
        )
        for plant, line, seed_lot in plant_rows
        if (location := locations.get(plant.source_plant_id)) is not None
        for tent in [tents.get(_required_location_source_tent_id(location))]
    ]
    return sorted(
        projections,
        key=lambda row: (
            _required_location_source_tent_id(row.location),
            row.location.grid_position or "",
            row.plant.key,
        ),
    )


def _breeding_logbook_locations_by_plant(
    locations: Iterable[CloudPlantLocation],
) -> dict[int, CloudPlantLocation]:
    selected: dict[int, CloudPlantLocation] = {}
    for location in locations:
        current = selected.get(location.source_plant_id)
        if current is None or _is_preferred_breeding_logbook_location(
            location,
            current,
        ):
            selected[location.source_plant_id] = location
    return selected


def _is_preferred_breeding_logbook_location(
    candidate: CloudPlantLocation,
    current: CloudPlantLocation,
) -> bool:
    if candidate.end_at is None and current.end_at is not None:
        return True
    if candidate.end_at is not None and current.end_at is None:
        return False
    return candidate.start_at > current.start_at


async def _get_breeding_logbook_plant(
    session: AsyncSession,
    *,
    site_id: str,
    plant_key: str,
) -> BreedingLogbookPlantProjection:
    rows = await _breeding_logbook_plants(
        session,
        site_id=site_id,
        include_culled=True,
        plant_key=plant_key,
    )
    if rows:
        return rows[0]
    raise HTTPException(status.HTTP_404_NOT_FOUND, "plant not found")


def _plant_projection_from_breeding_logbook(
    projection: BreedingLogbookPlantProjection,
) -> PlantProjection:
    return PlantProjection(
        plant=projection.plant,
        location=projection.location,
        tent=projection.tent,
        line=projection.line,
    )


async def _breeding_logbook_latest_notes(
    session: AsyncSession,
    *,
    site_id: str,
    plant_ids: list[int],
) -> dict[int, CloudPlantNote]:
    if not plant_ids:
        return {}
    rows = (
        await session.execute(
            select(CloudPlantNote)
            .where(
                CloudPlantNote.site_id == site_id,
                CloudPlantNote.source_plant_id.in_(plant_ids),
            )
            .order_by(
                CloudPlantNote.source_plant_id,
                desc(CloudPlantNote.observed_at),
                desc(CloudPlantNote.source_note_id),
            )
        )
    ).scalars()
    latest: dict[int, CloudPlantNote] = {}
    for note in rows:
        latest.setdefault(note.source_plant_id, note)
    return latest


async def _breeding_logbook_latest_events(
    session: AsyncSession,
    *,
    site_id: str,
    plant_ids: list[int],
) -> dict[int, CloudPlantEvent]:
    if not plant_ids:
        return {}
    rows = (
        await session.execute(
            select(CloudPlantEvent)
            .where(
                CloudPlantEvent.site_id == site_id,
                CloudPlantEvent.source_plant_id.in_(plant_ids),
            )
            .order_by(
                CloudPlantEvent.source_plant_id,
                desc(CloudPlantEvent.occurred_at),
                desc(CloudPlantEvent.source_event_id),
            )
        )
    ).scalars()
    latest: dict[int, CloudPlantEvent] = {}
    for event in rows:
        latest.setdefault(event.source_plant_id, event)
    return latest


async def _breeding_logbook_plant_notes(
    session: AsyncSession,
    *,
    site_id: str,
    source_plant_id: int,
) -> list[CloudPlantNote]:
    return list(
        (
            await session.execute(
                select(CloudPlantNote)
                .where(
                    CloudPlantNote.site_id == site_id,
                    CloudPlantNote.source_plant_id == source_plant_id,
                )
                .order_by(
                    desc(CloudPlantNote.observed_at),
                    desc(CloudPlantNote.source_note_id),
                )
            )
        ).scalars()
    )


async def _breeding_logbook_plant_events(
    session: AsyncSession,
    *,
    site_id: str,
    source_plant_id: int,
) -> list[CloudPlantEvent]:
    return list(
        (
            await session.execute(
                select(CloudPlantEvent)
                .where(
                    CloudPlantEvent.site_id == site_id,
                    CloudPlantEvent.source_plant_id == source_plant_id,
                )
                .order_by(
                    desc(CloudPlantEvent.occurred_at),
                    desc(CloudPlantEvent.source_event_id),
                )
            )
        ).scalars()
    )


async def _breeding_logbook_stream_counts(
    session: AsyncSession,
    *,
    site_id: str,
    plants: list[BreedingLogbookPlantProjection],
) -> dict[int, int]:
    return await _active_plant_stream_counts(
        session,
        site_id=site_id,
        plants=[_plant_projection_from_breeding_logbook(row) for row in plants],
    )


async def _breeding_logbook_lineage(
    session: AsyncSession,
    *,
    site_id: str,
    plant: BreedingLogbookPlantProjection,
) -> BreedingLogbookLineageResponse:
    return BreedingLogbookLineageResponse(
        parents=await _breeding_logbook_parent_label(
            session,
            site_id=site_id,
            plant=plant,
        ),
        offspring=await _breeding_logbook_offspring_label(
            session,
            site_id=site_id,
            source_plant_id=plant.plant.source_plant_id,
        ),
    )


async def _breeding_logbook_parent_label(
    session: AsyncSession,
    *,
    site_id: str,
    plant: BreedingLogbookPlantProjection,
) -> str:
    cross_event_id = (
        None
        if plant.seed_lot is None
        else plant.seed_lot.produced_by_cross_event_source_id
    )
    if cross_event_id is None:
        return _lineage_label(plant.line)

    cross = (
        await session.execute(
            select(CloudCrossEvent).where(
                CloudCrossEvent.site_id == site_id,
                CloudCrossEvent.source_cross_event_id == cross_event_id,
            )
        )
    ).scalar_one_or_none()
    if cross is None:
        return _lineage_label(plant.line)

    seed_parent_id = cross.seed_parent_source_plant_id
    pollen_parent_id = cross.pollen_parent_source_plant_id
    parents = {
        row.source_plant_id: row
        for row in (
            await session.execute(
                select(CloudPlant).where(
                    CloudPlant.site_id == site_id,
                    CloudPlant.source_plant_id.in_([seed_parent_id, pollen_parent_id]),
                )
            )
        ).scalars()
    }
    seed_parent = _breeding_logbook_parent_plant_label(
        parents.get(seed_parent_id),
        fallback=f"plant #{seed_parent_id}",
    )
    pollen_parent = _breeding_logbook_parent_plant_label(
        parents.get(pollen_parent_id),
        fallback=f"plant #{pollen_parent_id}",
    )
    if cross.pollen_parent_is_reversed:
        pollen_parent = f"{pollen_parent} (reversed)"
    return f"{seed_parent} x {pollen_parent}"


async def _breeding_logbook_offspring_label(
    session: AsyncSession,
    *,
    site_id: str,
    source_plant_id: int,
) -> str:
    cross_events = list(
        (
            await session.execute(
                select(CloudCrossEvent)
                .where(
                    CloudCrossEvent.site_id == site_id,
                    (
                        (CloudCrossEvent.seed_parent_source_plant_id == source_plant_id)
                        | (
                            CloudCrossEvent.pollen_parent_source_plant_id
                            == source_plant_id
                        )
                    ),
                )
                .order_by(
                    desc(CloudCrossEvent.pollinated_at),
                    desc(CloudCrossEvent.source_cross_event_id),
                )
            )
        ).scalars()
    )
    if not cross_events:
        return "No offspring logged"

    cross_event_ids = [event.source_cross_event_id for event in cross_events]
    seed_lot_rows = (
        await session.execute(
            select(CloudSeedLot, CloudPlantLine)
            .outerjoin(
                CloudPlantLine,
                and_(
                    CloudPlantLine.site_id == CloudSeedLot.site_id,
                    CloudPlantLine.source_line_id == CloudSeedLot.line_source_id,
                ),
            )
            .where(
                CloudSeedLot.site_id == site_id,
                CloudSeedLot.produced_by_cross_event_source_id.in_(cross_event_ids),
            )
            .order_by(CloudSeedLot.source_seed_lot_id)
        )
    ).all()
    seed_lots_by_cross: dict[int, list[tuple[CloudSeedLot, CloudPlantLine | None]]] = {}
    seed_lot_ids: list[int] = []
    for seed_lot, line in seed_lot_rows:
        if seed_lot.produced_by_cross_event_source_id is None:
            continue
        seed_lots_by_cross.setdefault(
            seed_lot.produced_by_cross_event_source_id,
            [],
        ).append((seed_lot, line))
        seed_lot_ids.append(seed_lot.source_seed_lot_id)

    plant_counts: dict[int, int] = {}
    if seed_lot_ids:
        count_rows = (
            await session.execute(
                select(CloudPlant.source_seed_lot_id, func.count())
                .where(
                    CloudPlant.site_id == site_id,
                    CloudPlant.source_seed_lot_id.in_(seed_lot_ids),
                )
                .group_by(CloudPlant.source_seed_lot_id)
            )
        ).all()
        plant_counts = {
            seed_lot_id: int(count)
            for seed_lot_id, count in count_rows
            if seed_lot_id is not None
        }

    summaries: list[str] = []
    for cross_event in cross_events:
        seed_lots = seed_lots_by_cross.get(cross_event.source_cross_event_id, [])
        if not seed_lots:
            summaries.append(
                f"Cross #{cross_event.source_cross_event_id}: no seed lots projected"
            )
            continue
        lot_summaries: list[str] = []
        for seed_lot, line in seed_lots:
            count_label = _plant_count_label(
                plant_counts.get(seed_lot.source_seed_lot_id, 0)
            )
            lot_summaries.append(f"{_seed_lot_label(seed_lot, line)} ({count_label})")
        summaries.append(
            f"Cross #{cross_event.source_cross_event_id}: {', '.join(lot_summaries)}"
        )
    return "; ".join(summaries)


def _breeding_logbook_plant_row_response(
    projection: BreedingLogbookPlantProjection,
    *,
    telemetry_stream_count: int,
    today: date,
    latest_note: CloudPlantNote | None = None,
    latest_event: CloudPlantEvent | None = None,
) -> BreedingLogbookPlantRowResponse:
    plant = projection.plant
    stage_key = _breeding_logbook_stage_key(projection)
    return BreedingLogbookPlantRowResponse(
        id=str(plant.source_plant_id),
        key=plant.key,
        name=plant.name,
        generation=_generation_label(projection.line),
        parents_label=_lineage_label(projection.line),
        sex_key=plant.sex_key,
        stage_key=stage_key,
        stage_day=_stage_day(plant, projection.location, stage_key, today=today),
        germinated_on=_date_or_none(plant.germinated_at),
        veg_started_on=_date_or_none(plant.veg_started_at or plant.rooted_at),
        flower_started_on=_date_or_none(plant.flower_started_at),
        culled_on=_date_or_none(plant.culled_at),
        current_tent_id=_required_location_source_tent_id(projection.location),
        current_tent_name=_tent_display_name(projection.tent, projection.location),
        grid_position=projection.location.grid_position,
        seed_lot_label=_seed_lot_label(projection.seed_lot, projection.seed_lot_line),
        last_note=_breeding_logbook_last_note(
            plant,
            latest_note=latest_note,
            latest_event=latest_event,
        ),
        telemetry_summary=_telemetry_summary(telemetry_stream_count),
    )


def _breeding_logbook_seed_lot_summary_response(
    seed_lot: CloudSeedLot,
    line: CloudPlantLine | None,
) -> BreedingLogbookSeedLotSummaryResponse:
    return BreedingLogbookSeedLotSummaryResponse(
        id=str(seed_lot.source_seed_lot_id),
        label=_seed_lot_label(seed_lot, line),
        prefix=line.project_code if line is not None and line.project_code else "",
        strain=line.strain if line is not None else "Unknown strain",
        cultivar=line.cultivar if line is not None else "Unknown cultivar",
        generation=_generation_label(line),
        source="purchased" if seed_lot.is_purchased else "cross",
        source_label=_seed_lot_source_label(seed_lot),
        parents_label=_lineage_label(line),
        sex_type_key=seed_lot.sex_type_key,
        seed_count=seed_lot.seed_count,
    )


def _breeding_logbook_last_note(
    plant: CloudPlant,
    *,
    latest_note: CloudPlantNote | None,
    latest_event: CloudPlantEvent | None,
) -> str:
    if latest_note is not None:
        return latest_note.body
    if latest_event is not None:
        event_body = _breeding_logbook_event_body(latest_event)
        if event_body:
            return event_body
    return plant.culled_reason or plant.selected_for_breeding_reason or ""


def _breeding_logbook_journal_events(
    *,
    notes: list[CloudPlantNote],
    events: list[CloudPlantEvent],
) -> list[BreedingLogbookPlantJournalEventResponse]:
    journal_events = [
        *_breeding_logbook_note_journal_events(notes),
        *_breeding_logbook_plant_journal_events(events),
    ]
    return sorted(
        journal_events,
        key=lambda event: (
            event.occurred_at or datetime.min,
            event.id,
        ),
        reverse=True,
    )


def _breeding_logbook_note_journal_events(
    notes: list[CloudPlantNote],
) -> list[BreedingLogbookPlantJournalEventResponse]:
    return [
        BreedingLogbookPlantJournalEventResponse(
            id=f"note-{note.source_note_id}",
            occurred_at=note.observed_at,
            date_label=_journal_date_label(note.observed_at),
            tag="note",
            body=note.body,
            has_photo=False,
        )
        for note in notes
    ]


def _breeding_logbook_plant_journal_events(
    events: list[CloudPlantEvent],
) -> list[BreedingLogbookPlantJournalEventResponse]:
    return [
        BreedingLogbookPlantJournalEventResponse(
            id=f"event-{event.source_event_id}",
            occurred_at=event.occurred_at,
            date_label=_journal_date_label(event.occurred_at),
            tag=_breeding_logbook_event_tag(event),
            body=_breeding_logbook_event_body(event),
            has_photo=False,
        )
        for event in events
    ]


def _breeding_logbook_event_tag(
    event: CloudPlantEvent,
) -> Literal["cross", "note", "stage", "sex", "germ"]:
    if event.is_seed_production or event.is_pollen_collection:
        return "cross"
    if event.is_sex_observation or event.is_reversal:
        return "sex"
    if event.is_transplant or event.is_selection_for_breeding:
        return "stage"
    if event.is_clone_taken:
        return "germ"
    return "note"


def _breeding_logbook_event_body(event: CloudPlantEvent) -> str:
    for value in (event.notes, event.reason):
        if value is not None and value.strip():
            return value.strip()
    labels = [
        label
        for is_present, label in (
            (event.is_pollen_collection, "Pollen collected"),
            (event.is_seed_production, "Seed production logged"),
            (event.is_clone_taken, "Clone taken"),
            (event.is_sex_observation, "Sex observation logged"),
            (event.is_reversal, "Reversal logged"),
            (event.is_transplant, "Transplant logged"),
            (event.is_selection_for_breeding, "Selected for breeding"),
        )
        if is_present
    ]
    return "; ".join(labels)


def _journal_date_label(value: datetime) -> str:
    return f"{value.strftime('%b')} {value.day}"


def _breeding_logbook_parent_plant_label(
    plant: CloudPlant | None,
    *,
    fallback: str,
) -> str:
    if plant is None:
        return fallback
    return f"{plant.name} ({plant.key})"


def _plant_count_label(count: int) -> str:
    if count == 1:
        return "1 plant"
    return f"{count} plants"


def _breeding_logbook_stage_key(
    projection: BreedingLogbookPlantProjection,
) -> BreedingLogbookPlantStageKey:
    plant = projection.plant
    if plant.culled_at is not None:
        return "culled"
    if plant.harvested_at is not None:
        return "harvested"
    if not plant.is_active:
        return "culled"
    if plant.selected_for_breeding_at is not None:
        return "breeding"
    if plant.flower_started_at is not None:
        return "flower"
    if plant.veg_started_at is not None or plant.rooted_at is not None:
        return "veg"
    return "germinating"


def _stage_day(
    plant: CloudPlant,
    location: CloudPlantLocation,
    stage_key: BreedingLogbookPlantStageKey,
    *,
    today: date,
) -> int:
    starts_at = {
        "germinating": plant.germinated_at,
        "veg": plant.veg_started_at or plant.rooted_at,
        "flower": plant.flower_started_at,
        "breeding": plant.selected_for_breeding_at or plant.flower_started_at,
        "harvested": plant.harvested_at,
        "culled": plant.culled_at,
    }[stage_key]
    start_date = _date_or_none(starts_at) or location.start_at.date()
    return max(0, (today - start_date).days)


def _seed_lot_label(
    seed_lot: CloudSeedLot | None,
    line: CloudPlantLine | None,
) -> str:
    if seed_lot is None:
        return "Unassigned seed lot"
    label_parts = [
        part
        for part in (
            line.project_code if line is not None else None,
            line.generation_label if line is not None else None,
        )
        if part
    ]
    if not label_parts and line is not None:
        label_parts = [line.strain, line.cultivar]
    label = " ".join(label_parts) if label_parts else "Seed lot"
    return f"{label} #{seed_lot.source_seed_lot_id}"


def _seed_lot_source_label(seed_lot: CloudSeedLot) -> str:
    if seed_lot.is_purchased:
        return seed_lot.vendor_name or "unknown vendor"
    return "in-house cross"


def _lineage_label(line: CloudPlantLine | None) -> str:
    if line is None:
        return "Unknown lineage"
    return " x ".join(part for part in (line.strain, line.cultivar) if part)


def _generation_label(line: CloudPlantLine | None) -> str:
    if line is None:
        return ""
    return line.generation_label or line.cultivar


def _telemetry_summary(stream_count: int) -> str:
    if stream_count == 0:
        return "tent context"
    if stream_count == 1:
        return "1 plant stream"
    return f"{stream_count} plant streams"


def _breeding_logbook_metric_summaries(
    telemetry: list[PlantMetricStreamResponse],
) -> list[BreedingLogbookPlantMetricSummaryResponse]:
    summaries: list[BreedingLogbookPlantMetricSummaryResponse] = []
    for stream in telemetry:
        reading = stream.latest_reading
        value = "no reading"
        if reading is not None:
            value = f"{reading.value:g}{stream.display_unit}"
        summaries.append(
            BreedingLogbookPlantMetricSummaryResponse(
                label=stream.display_name,
                value=value,
                tone="ok",
            )
        )
    return summaries


def _date_or_none(value: datetime | None) -> date | None:
    return None if value is None else value.date()


async def _latest_plants(
    session: AsyncSession,
    *,
    site_id: str,
    source_tent_id: int,
) -> list[PlantProjection]:
    rows = (
        await session.execute(
            select(CloudPlant, CloudPlantLocation, CloudTent, CloudPlantLine)
            .join(
                CloudPlantLocation,
                and_(
                    CloudPlantLocation.site_id == CloudPlant.site_id,
                    CloudPlantLocation.source_plant_id == CloudPlant.source_plant_id,
                ),
            )
            .outerjoin(
                CloudTent,
                and_(
                    CloudTent.site_id == CloudPlantLocation.site_id,
                    CloudTent.source_tent_id == CloudPlantLocation.source_tent_id,
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
                CloudPlantLocation.source_tent_id == source_tent_id,
                CloudPlantLocation.end_at.is_(None),
            )
            .order_by(CloudPlantLocation.grid_position, CloudPlant.key)
        )
    ).all()
    return [
        PlantProjection(plant=plant, location=location, tent=tent, line=line)
        for plant, location, tent, line in rows
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
        current_tent_id=_required_location_source_tent_id(location),
        current_tent_name=_tent_display_name(projection.tent, location),
        id=plant.source_plant_id,
        key=plant.key,
        line_source_id=plant.line_source_id,
        line=_plant_line_response(projection.line),
        sex_key=plant.sex_key,
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
    source_tent_id: int,
    plant_id: str,
) -> PlantProjection:
    row = (
        await session.execute(
            select(CloudPlant, CloudPlantLocation, CloudTent, CloudPlantLine)
            .join(
                CloudPlantLocation,
                and_(
                    CloudPlantLocation.site_id == CloudPlant.site_id,
                    CloudPlantLocation.source_plant_id == CloudPlant.source_plant_id,
                ),
            )
            .outerjoin(
                CloudTent,
                and_(
                    CloudTent.site_id == CloudPlantLocation.site_id,
                    CloudTent.source_tent_id == CloudPlantLocation.source_tent_id,
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
                CloudPlantLocation.source_tent_id == source_tent_id,
                CloudPlantLocation.end_at.is_(None),
            )
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "plant not found")
    plant, location, tent, line = row
    return PlantProjection(plant=plant, location=location, tent=tent, line=line)


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
    source_tent_id: int,
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
                CloudLatestMetric.source_tent_id == source_tent_id,
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
    source_tent_id: int,
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
                    CloudMetricRollup.source_tent_id == source_tent_id,
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
        current_tent_id=_required_location_source_tent_id(location),
        current_tent_name=_tent_display_name(plant.tent, location),
        id=cloud_plant.source_plant_id,
        key=cloud_plant.key,
        line_source_id=cloud_plant.line_source_id,
        line=_plant_line_response(plant.line),
        sex_key=cloud_plant.sex_key,
        name=cloud_plant.name,
        grid_position=location.grid_position,
        current_location=_plant_current_location_response(location, plant.tent),
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
    tent: CloudTent | None,
) -> PlantCurrentLocationResponse:
    return PlantCurrentLocationResponse(
        id=location.source_location_id,
        current_tent_id=_required_location_source_tent_id(location),
        current_tent_name=_tent_display_name(tent, location),
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
        source_tent_id=command.source_tent_id,
        legacy_target_tent_id=command.tent_id,
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


def _clean_nonblank(value: str, *, field_name: str) -> str:
    stripped = value.strip()
    if stripped == "":
        raise ValueError(f"{field_name} must not be blank")
    return stripped


def _clean_nonblank_list(values: list[str], *, field_name: str) -> list[str]:
    cleaned = [_clean_nonblank(value, field_name=field_name) for value in values]
    if len(set(cleaned)) != len(cleaned):
        raise ValueError(f"{field_name} must not contain duplicates")
    return cleaned


def _seed_lot_source_id_from_request(seed_lot_id: str) -> int:
    try:
        value = int(seed_lot_id)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "seed_lot_id must be a source seed lot id",
        ) from exc
    if value <= 0:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "seed_lot_id must be positive",
        )
    return value


async def _get_cloud_tent_by_source_id(
    session: AsyncSession, *, site_id: str, source_tent_id: int
) -> CloudTent:
    tent = (
        await session.execute(
            select(CloudTent).where(
                CloudTent.site_id == site_id,
                CloudTent.source_tent_id == source_tent_id,
            )
        )
    ).scalar_one_or_none()
    if tent is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "tent not found")
    return tent


async def _require_cloud_tent_by_source_id(
    session: AsyncSession, *, site_id: str, source_tent_id: int
) -> CloudTent:
    tent = (
        await session.execute(
            select(CloudTent).where(
                CloudTent.site_id == site_id,
                CloudTent.source_tent_id == source_tent_id,
                CloudTent.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if tent is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "unknown target tent",
        )
    return tent


async def _cloud_tents_by_source_id(
    session: AsyncSession, *, site_id: str, source_tent_ids: set[int]
) -> dict[int, CloudTent]:
    if not source_tent_ids:
        return {}
    rows = (
        await session.execute(
            select(CloudTent).where(
                CloudTent.site_id == site_id,
                CloudTent.source_tent_id.in_(source_tent_ids),
            )
        )
    ).scalars()
    return {_required_source_tent_id(row): row for row in rows}


def _required_source_tent_id(tent: CloudTent) -> int:
    if tent.source_tent_id is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "cloud tent missing source_tent_id",
        )
    return tent.source_tent_id


def _required_location_source_tent_id(location: CloudPlantLocation) -> int:
    if location.source_tent_id is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "cloud plant location missing source_tent_id",
        )
    return location.source_tent_id


def _tent_display_name(tent: CloudTent | None, location: CloudPlantLocation) -> str:
    if tent is not None:
        return tent.name
    # Temporary bridge for older additive cloud projections until Milestone 7
    # makes source tent identity mandatory everywhere.
    return location.tent_id


def _required_schedule_source_tent_id(schedule: CloudSchedule) -> int:
    if schedule.source_tent_id is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "cloud schedule missing source_tent_id",
        )
    return schedule.source_tent_id


def _required_source_schedule_id(schedule: CloudSchedule) -> int:
    if schedule.source_schedule_id is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "cloud schedule missing source_schedule_id",
        )
    return schedule.source_schedule_id


async def _legacy_tent_id_for_browser_source_tent_id(
    session: AsyncSession, *, site_id: str, source_tent_id: int
) -> str:
    tent = (
        await session.execute(
            select(CloudTent).where(
                CloudTent.site_id == site_id,
                CloudTent.source_tent_id == source_tent_id,
                CloudTent.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if tent is not None:
        return tent.tent_id
    # Temporary bridge until command payload/storage no longer carries tent text.
    fallback = {1: "main", 2: "breeding", 3: "clones"}.get(source_tent_id)
    if fallback is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "unknown target tent",
        )
    return fallback


async def _require_cloud_seed_lot_source_id(
    session: AsyncSession, *, site_id: str, seed_lot_source_id: int
) -> CloudSeedLot:
    seed_lot = (
        await session.execute(
            select(CloudSeedLot).where(
                CloudSeedLot.site_id == site_id,
                CloudSeedLot.source_seed_lot_id == seed_lot_source_id,
            )
        )
    ).scalar_one_or_none()
    if seed_lot is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "unknown seed lot",
        )
    return seed_lot


async def _require_cloud_plant_key(
    session: AsyncSession, *, site_id: str, plant_key: str
) -> CloudPlant:
    plant = (
        await session.execute(
            select(CloudPlant).where(
                CloudPlant.site_id == site_id,
                CloudPlant.key == plant_key,
            )
        )
    ).scalar_one_or_none()
    if plant is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "unknown plant key",
        )
    return plant


async def _require_cloud_plant_keys(
    session: AsyncSession, *, site_id: str, plant_keys: list[str]
) -> list[CloudPlant]:
    rows = (
        (
            await session.execute(
                select(CloudPlant).where(
                    CloudPlant.site_id == site_id,
                    CloudPlant.key.in_(plant_keys),
                )
            )
        )
        .scalars()
        .all()
    )
    found = {plant.key for plant in rows}
    missing = [plant_key for plant_key in plant_keys if plant_key not in found]
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"unknown plant key: {missing[0]}",
        )
    return rows


async def _enqueue_breeding_command(  # noqa: PLR0913
    idempotency_key: str,
    *,
    user: str,
    settings: CloudSettings,
    session: AsyncSession,
    clock: Callable[[], datetime],
    command_type: CommandType,
    target_tent_id: str,
    source_tent_id: int | None,
    payload: BreedingCommandPayload,
) -> CommandResponse:
    if not settings.command_creation_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "commands disabled")
    existing = (
        await session.execute(
            select(CloudCommand).where(
                CloudCommand.requested_by == user,
                CloudCommand.idempotency_key == idempotency_key,
            )
        )
    ).scalar_one_or_none()
    if existing is not None:
        return _command_response(existing)

    now = clock()
    command = CloudCommand(
        command_id=str(uuid.uuid4()),
        idempotency_key=idempotency_key,
        site_id=settings.default_site_id,
        tent_id=target_tent_id,
        source_tent_id=source_tent_id,
        device_id=None,
        capability_id=None,
        command_type=command_type,
        payload=payload.model_dump(mode="json"),
        requested_by=user,
        status="queued",
        queued_at=now,
        expires_at=now + timedelta(seconds=BREEDING_COMMAND_EXPIRY_SECONDS),
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
        site_id=settings.default_site_id,
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
