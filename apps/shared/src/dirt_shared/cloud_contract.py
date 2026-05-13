"""Shared Pydantic contracts for the cloud gateway protocol."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CloudContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


CommandRequestStatus = Literal["running", "succeeded", "failed", "rejected", "expired"]
CommandResponseStatus = Literal[
    "queued",
    "claimed",
    "running",
    "succeeded",
    "failed",
    "rejected",
    "expired",
]
CommandType = Literal["ptz_preset", "ptz_look", "ptz_zoom"]
CapturePolicyReason = Literal[
    "camera_not_found",
    "camera_disabled",
    "lights_schedule_not_found",
]


class HeartbeatRequest(CloudContractModel):
    site_id: str
    gateway_id: str
    backlog_depth: int = 0


class HeartbeatResponse(CloudContractModel):
    ok: bool
    site_id: str
    gateway_id: str
    backlog_depth: int
    received_at: datetime


class CatalogSite(CloudContractModel):
    site_id: str
    name: str
    timezone: str = "America/Denver"


class CatalogTent(CloudContractModel):
    tent_id: str
    name: str
    is_active: bool = True


class CatalogZone(CloudContractModel):
    tent_id: str
    zone_id: str
    name: str
    kind: str = "environment"
    is_active: bool = True


class CatalogDevice(CloudContractModel):
    tent_id: str
    device_id: str
    name: str
    last_seen_at: datetime | None = Field(...)
    zone_id: str | None = None
    kind: str = "sensor"
    controller: str | None = None
    is_active: bool = True


class CatalogCapability(CloudContractModel):
    tent_id: str
    device_id: str
    capability_id: str
    metric_name: str | None = None
    kind: str = "metric"
    unit: str | None = None
    is_enabled: bool = True


class CatalogSchedule(CloudContractModel):
    site_id: str
    tent_id: str
    schedule_id: str
    starts_local: time
    ends_local: time
    zone_id: str | None = None
    device_id: str | None = None
    capability_id: str | None = None
    kind: str = "lights"
    timezone: str = "America/Denver"
    is_enabled: bool = True


class CatalogRequest(CloudContractModel):
    site: CatalogSite
    tents: list[CatalogTent] = Field(default_factory=list)
    zones: list[CatalogZone] = Field(default_factory=list)
    devices: list[CatalogDevice] = Field(default_factory=list)
    capabilities: list[CatalogCapability] = Field(default_factory=list)
    schedules: list[CatalogSchedule] = Field(default_factory=list)


class CatalogResponse(CloudContractModel):
    sites: int
    tents: int
    zones: int
    devices: int
    capabilities: int
    schedules: int


class LatestMetricItem(CloudContractModel):
    site_id: str
    tent_id: str
    capability_id: str
    metric: str
    value: float
    source_updated_at: datetime
    unit: str | None = None
    zone_id: str | None = None
    device_id: str | None = None
    stale_after_s: int = 120


class LatestMetricsRequest(CloudContractModel):
    site_id: str
    metrics: list[LatestMetricItem]


class UpsertCountResponse(CloudContractModel):
    upserted: int


class RollupItem(CloudContractModel):
    site_id: str
    tent_id: str
    capability_id: str
    metric: str
    bucket: str
    bucket_start_at: datetime
    bucket_end_at: datetime
    min_value: float | None = None
    avg_value: float | None = None
    max_value: float | None = None
    sample_count: int = 0
    unit: str | None = None


class RollupsRequest(CloudContractModel):
    site_id: str
    rollups: list[RollupItem]


class AssetSignUploadRequest(CloudContractModel):
    site_id: str
    tent_id: str
    content_type: str
    byte_size: int = Field(gt=0)
    object_key: str
    asset_id: str | None = None
    sha256: str | None = None
    kind: str = "snapshot"


class SignUploadResponse(CloudContractModel):
    asset_id: str | None
    object_key: str
    upload_url: str
    method: Literal["PUT"]
    headers: dict[str, str]
    expires_at: datetime
    byte_size: int


class AssetCompleteRequest(AssetSignUploadRequest):
    captured_at: datetime
    zone_id: str | None = None
    device_id: str | None = None


class AssetCompleteResponse(CloudContractModel):
    asset_id: str
    object_key: str
    uploaded_at: datetime


class AssetFailureRequest(CloudContractModel):
    site_id: str
    stage: str = Field(max_length=80)
    error: str = Field(max_length=500)
    tent_id: str | None = None
    asset_id: str | None = None
    object_key: str | None = None


class AssetFailureResponse(CloudContractModel):
    ok: bool
    received_at: datetime


class CapturePolicyResponse(CloudContractModel):
    site_id: str
    tent_id: str | None
    camera_device_id: str
    enabled: bool
    require_lights_on: bool
    lights_on_local: time | None
    lights_off_local: time | None
    timezone: str
    source_schedule_id: str | None
    reason: CapturePolicyReason | None = Field(...)


class AssetRetentionRequest(CloudContractModel):
    site_id: str
    as_of_date: date


class PruneAssetsResponse(CloudContractModel):
    cutoff: datetime
    matched: int
    objects_deleted: int


class CommandClaimRequest(CloudContractModel):
    site_id: str
    limit: int = Field(default=1, ge=1, le=10)


class PtzPresetPayload(CloudContractModel):
    preset_id: str = Field(min_length=1)


class PtzLookPayload(CloudContractModel):
    x: float = Field(ge=-0.5, le=0.5)
    y: float = Field(ge=-0.5, le=0.5)


class PtzZoomAbsolutePayload(CloudContractModel):
    zoom: float = Field(ge=1.0, le=2.0)


class PtzZoomRelativePayload(CloudContractModel):
    delta: float = Field(ge=-1.0, le=1.0)


PtzZoomPayload: TypeAlias = PtzZoomAbsolutePayload | PtzZoomRelativePayload
PtzCommandPayload: TypeAlias = PtzPresetPayload | PtzLookPayload | PtzZoomPayload


class ClaimedCommand(CloudContractModel):
    command_id: str
    site_id: str
    tent_id: str
    device_id: str | None
    capability_id: str | None
    command_type: CommandType
    payload: PtzCommandPayload
    status: CommandResponseStatus
    queued_at: datetime
    expires_at: datetime
    claimed_by: str | None
    claimed_at: datetime | None
    requested_by: str
    started_at: datetime | None
    finished_at: datetime | None
    result: dict[str, Any] | None
    error: str | None

    @model_validator(mode="after")
    def _payload_matches_command_type(self) -> ClaimedCommand:
        if self.command_type == "ptz_preset" and not isinstance(
            self.payload, PtzPresetPayload
        ):
            raise ValueError("ptz_preset requires a preset payload")
        if self.command_type == "ptz_look" and not isinstance(
            self.payload, PtzLookPayload
        ):
            raise ValueError("ptz_look requires a look payload")
        if self.command_type == "ptz_zoom" and not isinstance(
            self.payload, PtzZoomAbsolutePayload | PtzZoomRelativePayload
        ):
            raise ValueError("ptz_zoom requires a zoom payload")
        return self


class CommandClaimResponse(CloudContractModel):
    commands: list[ClaimedCommand]


class CommandResultRequest(CloudContractModel):
    site_id: str
    status: CommandRequestStatus
    result: dict[str, Any] | None = None
    error: str | None = None


class CommandResultOutboxPayload(CloudContractModel):
    command_id: str
    result: CommandResultRequest


class CommandResultResponse(ClaimedCommand):
    pass
