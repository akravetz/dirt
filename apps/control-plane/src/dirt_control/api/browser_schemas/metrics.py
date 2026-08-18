from __future__ import annotations

from datetime import datetime
from typing import Literal

from dirt_control.api.browser_schemas.common import BrowserResponse
from dirt_shared.metric_history import MetricHistoryBucket, MetricHistoryRange

MetricAccent = Literal["temp", "humidity", "vpd", "neutral", "reservoir", "moisture"]


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
    bucket: MetricHistoryBucket
    bucket_start_at: datetime
    bucket_end_at: datetime
    min: float | None
    avg: float | None
    max: float | None
    sample_count: int
    unit: str | None


class MetricHistoryResponse(BrowserResponse):
    metric: str
    range: MetricHistoryRange
    points: list[MetricHistoryPointResponse]


class MetricPresentationMetricResponse(BrowserResponse):
    metric: str
    display_name: str
    unit: str
    accent: MetricAccent
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
