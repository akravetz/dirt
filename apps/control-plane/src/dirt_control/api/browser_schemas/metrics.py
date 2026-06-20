from __future__ import annotations

from datetime import datetime, timedelta

from dirt_control.api.browser_schemas.common import BrowserResponse

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
