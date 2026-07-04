from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator

PROBE_ID_MIN = 1
PROBE_ID_MAX = 3
FORMULA_TEMPLATE = "100 * (raw_moisture_pct - dry_anchor_mean) / span"
DEFAULT_STATUS_INTERVAL_MS = 30000
PROBE_ID_BY_MODBUS_ADDRESS = {
    "0x02": 1,
    "0x03": 2,
    "0x04": 3,
}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FirmwareModel(BaseModel):
    # Firmware is an owned boundary, but the calibration adapter only consumes
    # a subset of the broader diagnostic surface. Ignore unrelated additions
    # while still validating the fields calibration logic uses.
    model_config = ConfigDict(extra="ignore")


class AnchorType(StrEnum):
    DRY = "dry"
    WET_CAPACITY = "wet_capacity"


class SessionStatus(StrEnum):
    DRAFT = "draft"
    COMPLETED = "completed"


class ProbeIdentity(StrictModel):
    probe_id: int = Field(ge=PROBE_ID_MIN, le=PROBE_ID_MAX)
    modbus_address: str = Field(pattern=r"^0x[0-9A-Fa-f]{2}$")
    device_id: str = Field(min_length=1)


class MetricStats(StrictModel):
    count: int = Field(ge=0)
    mean: float | None = None
    min: float | None = None
    max: float | None = None
    stddev: float | None = None


class CaptureStats(StrictModel):
    sample_count: int = Field(ge=0)
    valid_sample_count: int = Field(ge=0)
    soil_moisture_pct: MetricStats
    substrate_ec_us_cm: MetricStats
    substrate_ph: MetricStats
    substrate_temp_c: MetricStats


class ProbeSample(StrictModel):
    seq: int = Field(ge=0)
    read_ms: int = Field(ge=0)
    probe_id: int = Field(ge=PROBE_ID_MIN, le=PROBE_ID_MAX)
    modbus_address: str = Field(pattern=r"^0x[0-9A-Fa-f]{2}$")
    modbus_status: str = Field(min_length=1)
    valid: bool
    soil_moisture_pct: float | None = None
    substrate_temp_c: float | None = None
    substrate_ec_us_cm: float | None = None
    substrate_ph: float | None = None
    raw_modbus_frame_hex: str = ""


class CapturePreview(StrictModel):
    id: str = Field(min_length=1)
    anchor_type: AnchorType
    probe_id: int = Field(ge=PROBE_ID_MIN, le=PROBE_ID_MAX)
    modbus_address: str = Field(pattern=r"^0x[0-9A-Fa-f]{2}$")
    device_id: str = Field(min_length=1)
    placement_label: str | None = None
    note: str | None = None
    duration_s: float = Field(gt=0)
    started_at: datetime
    ended_at: datetime
    input_ec_ms_cm_override: float | None = Field(default=None, ge=0)
    input_ph_override: float | None = Field(default=None, ge=0, le=14)
    samples: list[ProbeSample]
    stats: CaptureStats


class Capture(CapturePreview):
    accepted_at: datetime


class ProbeCalibrationSummary(StrictModel):
    probe: ProbeIdentity
    dry_anchor_mean: float | None = None
    wet_anchor_mean: float | None = None
    span: float | None = None
    dry_capture_count: int = Field(ge=0)
    wet_capture_count: int = Field(ge=0)
    valid_dry_sample_count: int = Field(ge=0)
    valid_wet_sample_count: int = Field(ge=0)
    formula_template: str = FORMULA_TEMPLATE
    formula: str | None = None
    ready: bool
    warnings: list[str] = Field(default_factory=list)


class CalibrationSummary(StrictModel):
    formula_template: str = FORMULA_TEMPLATE
    probes: list[ProbeCalibrationSummary]
    warnings: list[str] = Field(default_factory=list)
    completed_at: datetime | None = None


class CalibrationSession(StrictModel):
    id: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime
    status: SessionStatus
    controller_url: str = Field(min_length=1)
    probe_map: list[ProbeIdentity]
    input_ec_ms_cm: float | None = Field(default=None, ge=0)
    input_ph: float | None = Field(default=None, ge=0, le=14)
    accepted_captures: list[Capture] = Field(default_factory=list)
    summary: CalibrationSummary | None = None


class LatestCompletedArtifact(StrictModel):
    session_id: str = Field(min_length=1)
    session_path: str = Field(min_length=1)
    completed_at: datetime
    summary: CalibrationSummary


class CreateSessionRequest(StrictModel):
    input_ec_ms_cm: float | None = Field(default=None, ge=0)
    input_ph: float | None = Field(default=None, ge=0, le=14)


class UpdateWetReferenceRequest(CreateSessionRequest):
    pass


class CapturePreviewRequest(StrictModel):
    probe_id: int = Field(ge=PROBE_ID_MIN, le=PROBE_ID_MAX)
    anchor_type: AnchorType
    duration_s: float = Field(default=60.0, gt=0, le=300)
    placement_label: str | None = None
    note: str | None = None
    input_ec_ms_cm_override: float | None = Field(default=None, ge=0)
    input_ph_override: float | None = Field(default=None, ge=0, le=14)
    poll_interval_s: float = Field(default=2.0, gt=0, le=10)


class AcceptCaptureRequest(StrictModel):
    capture: CapturePreview


class StartCalibrationRequest(StrictModel):
    duration_s: int = Field(default=900, ge=1, le=3600)
    interval_ms: int = Field(default=2000, ge=1000, le=30000)


class ToolInfoResponse(StrictModel):
    ok: bool
    controller_url: str
    storage_root: str


class LiveStatusResponse(StrictModel):
    controller_url: str
    status: ControllerStatus


class ControllerModeResponse(StrictModel):
    controller_url: str
    state: str
    calibration_mode: ControllerCalibrationMode


class SessionSummaryResponse(StrictModel):
    session_id: str
    status: SessionStatus
    summary: CalibrationSummary


class LatestCompletedResponse(StrictModel):
    artifact: LatestCompletedArtifact | None
    session: CalibrationSession | None


class ControllerCalibrationCounters(FirmwareModel):
    start_count: int = Field(ge=0)
    stop_count: int = Field(ge=0)
    auto_expire_count: int = Field(ge=0)
    measurement_cycle_count: int = Field(ge=0)
    sample_success_count: int = Field(ge=0)
    sample_failure_count: int = Field(ge=0)


class ControllerCalibrationMode(FirmwareModel):
    active: bool
    started_ms: int = Field(ge=0)
    expires_ms: int = Field(ge=0)
    remaining_ms: int = Field(ge=0)
    interval_ms: int = Field(ge=0)
    normal_measurement_interval_ms: int = Field(ge=0)
    ingest_interval_ms: int = Field(ge=0)
    counters: ControllerCalibrationCounters


def _inactive_calibration_mode_payload() -> dict[str, object]:
    return {
        "active": False,
        "started_ms": 0,
        "expires_ms": 0,
        "remaining_ms": 0,
        "interval_ms": 0,
        "normal_measurement_interval_ms": DEFAULT_STATUS_INTERVAL_MS,
        "ingest_interval_ms": DEFAULT_STATUS_INTERVAL_MS,
        "counters": {
            "start_count": 0,
            "stop_count": 0,
            "auto_expire_count": 0,
            "measurement_cycle_count": 0,
            "sample_success_count": 0,
            "sample_failure_count": 0,
        },
    }


class StatusLatestSample(FirmwareModel):
    soil_moisture_pct: float
    substrate_temp_c: float
    substrate_ec_us_cm: float
    substrate_ph: float
    age_ms: int = Field(ge=0)


class ControllerStatusSlot(FirmwareModel):
    probe_id: int = Field(ge=PROBE_ID_MIN, le=PROBE_ID_MAX)
    device_id: str = Field(min_length=1)
    modbus_address: str = Field(pattern=r"^0x[0-9A-Fa-f]{2}$")
    enabled: bool
    sample_ring_count: int = Field(ge=0)
    latest_sample: StatusLatestSample | None = None
    latest_raw_modbus_frame_hex: str = ""
    last_modbus_status: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def _adapt_pre_calibration_status_slot(cls, data):
        if not isinstance(data, dict):
            return data
        adapted = dict(data)
        address = adapted.get("modbus_address")
        if "probe_id" not in adapted and isinstance(address, str):
            probe_id = PROBE_ID_BY_MODBUS_ADDRESS.get(address.lower())
            if probe_id is not None:
                adapted["probe_id"] = probe_id
        adapted.setdefault("sample_ring_count", 0)
        return adapted


class ControllerInfo(FirmwareModel):
    device_id: str = Field(min_length=1)
    hostname: str = Field(min_length=1)
    slot_count: int = Field(ge=0)
    enabled_slot_count: int = Field(ge=0)
    any_enabled_slot_failing: bool
    normal_measurement_interval_ms: int = Field(ge=0)
    ingest_interval_ms: int = Field(ge=0)

    @model_validator(mode="before")
    @classmethod
    def _adapt_pre_calibration_status_controller(cls, data):
        if not isinstance(data, dict):
            return data
        adapted = dict(data)
        adapted.setdefault("normal_measurement_interval_ms", DEFAULT_STATUS_INTERVAL_MS)
        adapted.setdefault("ingest_interval_ms", DEFAULT_STATUS_INTERVAL_MS)
        return adapted


class ControllerStatus(FirmwareModel):
    controller: ControllerInfo
    firmware_version: str = Field(min_length=1)
    calibration_mode: ControllerCalibrationMode
    slots: list[ControllerStatusSlot]

    @model_validator(mode="before")
    @classmethod
    def _adapt_pre_calibration_status(cls, data):
        if not isinstance(data, dict):
            return data
        adapted = dict(data)
        adapted.setdefault("calibration_mode", _inactive_calibration_mode_payload())
        return adapted


class ControllerCommandResponse(FirmwareModel):
    ok: bool
    state: str = Field(min_length=1)
    calibration_mode: ControllerCalibrationMode


class FirmwareSample(ProbeSample, FirmwareModel):
    @model_validator(mode="after")
    def _valid_samples_include_metric_values(self) -> FirmwareSample:
        if not self.valid:
            return self
        missing = [
            name
            for name in (
                "soil_moisture_pct",
                "substrate_temp_c",
                "substrate_ec_us_cm",
                "substrate_ph",
            )
            if getattr(self, name) is None
        ]
        if missing:
            message = "valid firmware sample missing " + ", ".join(missing)
            raise ValueError(message)
        return self


class SamplesSlot(FirmwareModel):
    probe_id: int = Field(ge=PROBE_ID_MIN, le=PROBE_ID_MAX)
    device_id: str = Field(min_length=1)
    modbus_address: str = Field(pattern=r"^0x[0-9A-Fa-f]{2}$")
    enabled: bool
    ring_capacity: int = Field(ge=0)
    ring_sample_count: int = Field(ge=0)
    returned_sample_count: int = Field(ge=0)
    samples: list[FirmwareSample]


class SamplesController(FirmwareModel):
    device_id: str = Field(min_length=1)
    hostname: str = Field(min_length=1)
    firmware_version: str = Field(min_length=1)
    read_ms: int = Field(ge=0)
    window_s: int = Field(ge=1)
    calibration_mode: ControllerCalibrationMode


class SamplesResponse(FirmwareModel):
    controller: SamplesController
    slots: list[SamplesSlot]
