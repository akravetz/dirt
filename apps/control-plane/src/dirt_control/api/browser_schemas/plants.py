from __future__ import annotations

from datetime import datetime
from typing import Any

from dirt_control.api.browser_schemas.common import BrowserResponse
from dirt_shared.cloud_contract import PlantSexKey


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
    taken_at: datetime | None
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
