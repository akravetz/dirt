from __future__ import annotations

from datetime import datetime
from typing import Any

from dirt_control.api.browser_schemas.common import BrowserResponse
from dirt_control.api.browser_schemas.metrics import MetricAccent
from dirt_shared.cloud_contract import PlantSexKey
from dirt_shared.metric_history import MetricHistoryBucket, MetricHistoryRange


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
    taken_at: datetime | None
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


class PlantWikiContentResponse(BrowserResponse):
    path: str
    title: str
    frontmatter: dict[str, Any]
    body_markdown: str
    sha256: str
    source_updated_at: datetime


class PlantMetricReadingResponse(BrowserResponse):
    value: float


class PlantMetricStreamResponse(BrowserResponse):
    metric: str
    device_id: str
    capability_id: str
    latest_reading: PlantMetricReadingResponse | None


class PlantMetricHistoryPointResponse(BrowserResponse):
    ts: datetime
    value: float | None


class PlantMetricHistoryStreamResponse(BrowserResponse):
    metric: str
    display_name: str
    display_unit: str
    source_unit: str | None
    value_precision: int
    accent: MetricAccent
    y_min: float | None
    y_max: float | None
    display_order: int
    device_id: str
    capability_id: str
    points: list[PlantMetricHistoryPointResponse]


class PlantMetricHistoryResponse(BrowserResponse):
    range: MetricHistoryRange
    bucket: MetricHistoryBucket
    streams: list[PlantMetricHistoryStreamResponse]


class PlantMetricHistoryPlantResponse(BrowserResponse):
    id: int
    key: str
    name: str
    grid_position: str | None
    streams: list[PlantMetricHistoryStreamResponse]


class PlantMetricHistoryCollectionResponse(BrowserResponse):
    range: MetricHistoryRange
    bucket: MetricHistoryBucket
    plants: list[PlantMetricHistoryPlantResponse]
