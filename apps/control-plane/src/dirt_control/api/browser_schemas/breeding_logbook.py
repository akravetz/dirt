from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator

from dirt_control.api.browser_schemas.common import (
    BrowserRequest,
    BrowserResponse,
    clean_nonblank,
    clean_nonblank_list,
)
from dirt_control.api.browser_schemas.plants import (
    PlantMetricStreamResponse,
    PlantWikiContentResponse,
)
from dirt_shared.cloud_contract import (
    BreedingBulkPlantFactsPayload,
    BreedingCreateSeedLotPayload,
    BreedingUpdateSeedLotInventoryPayload,
    PlantSexKey,
)

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


class BreedingCommandRequest(BrowserRequest):
    idempotency_key: str = Field(min_length=1, max_length=160)


class BreedingCreateSeedLotRequest(BreedingCreateSeedLotPayload):
    idempotency_key: str = Field(min_length=1, max_length=160)


class BreedingUpdateSeedLotInventoryRequest(BreedingUpdateSeedLotInventoryPayload):
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
        return clean_nonblank_list(value, field_name="plant_keys")


class BreedingBulkMoveRequest(BreedingCommandRequest):
    plant_keys: list[str] = Field(min_length=1)
    source_tent_id: int = Field(gt=0)
    grid_position: Literal[None] = Field(...)

    @field_validator("plant_keys")
    @classmethod
    def _clean_plant_keys(cls, value: list[str]) -> list[str]:
        return clean_nonblank_list(value, field_name="plant_keys")


class BreedingUpdatePlantFactsRequest(BreedingBulkPlantFactsPayload):
    idempotency_key: str = Field(min_length=1, max_length=160)


class BreedingBulkCullRequest(BreedingCommandRequest):
    plant_keys: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)

    @field_validator("plant_keys")
    @classmethod
    def _clean_plant_keys(cls, value: list[str]) -> list[str]:
        return clean_nonblank_list(value, field_name="plant_keys")

    @field_validator("reason")
    @classmethod
    def _clean_reason(cls, value: str) -> str:
        return clean_nonblank(value, field_name="reason")


class BreedingCreatePlantNoteRequest(BreedingCommandRequest):
    body: str = Field(min_length=1)
    observed_at: datetime | None = None

    @field_validator("body")
    @classmethod
    def _clean_body(cls, value: str) -> str:
        return clean_nonblank(value, field_name="body")


class BreedingBulkPlantNoteRequest(BreedingCommandRequest):
    plant_keys: list[str] = Field(min_length=1)
    body: str = Field(min_length=1)
    observed_at: datetime | None = None

    @field_validator("plant_keys")
    @classmethod
    def _clean_plant_keys(cls, value: list[str]) -> list[str]:
        return clean_nonblank_list(value, field_name="plant_keys")

    @field_validator("body")
    @classmethod
    def _clean_body(cls, value: str) -> str:
        return clean_nonblank(value, field_name="body")


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


class BreedingLogbookSeedLotLineResponse(BrowserResponse):
    source_line_id: int
    prefix: str
    generation: str
    strain: str
    cultivar: str
    source_name: str | None = Field(...)
    description: str | None = Field(...)


class BreedingLogbookSeedLotCrossContextResponse(BrowserResponse):
    source_cross_event_id: int
    pollinated_at: datetime
    pollen_parent_is_reversed: bool | None = Field(...)
    seed_parent_source_plant_id: int
    seed_parent_key: str | None = Field(...)
    seed_parent_name: str | None = Field(...)
    seed_parent_label: str
    pollen_parent_source_plant_id: int
    pollen_parent_key: str | None = Field(...)
    pollen_parent_name: str | None = Field(...)
    pollen_parent_label: str
    parents_label: str
    notes: str | None = Field(...)


class BreedingLogbookSeedLotDetailResponse(BreedingLogbookSeedLotSummaryResponse):
    source_seed_lot_id: int
    source_line_id: int
    line: BreedingLogbookSeedLotLineResponse | None = Field(...)
    is_purchased: bool
    vendor_name: str | None = Field(...)
    acquired_at: datetime | None = Field(...)
    produced_by_cross_event_source_id: int | None = Field(...)
    cross: BreedingLogbookSeedLotCrossContextResponse | None = Field(...)
    notes: str | None = Field(...)
    created_plant_count: int


class BreedingLogbookPlantRowResponse(BrowserResponse):
    id: str
    key: str
    name: str
    generation: str
    parents_label: str
    sex_key: PlantSexKey
    stage_key: BreedingLogbookPlantStageKey
    stage_day: int
    is_clone: bool
    germinated_at: datetime | None
    germinated_on: date | None
    taken_at: datetime | None
    taken_on: date | None
    rooted_at: datetime | None
    rooted_on: date | None
    veg_started_at: datetime | None
    veg_started_on: date | None
    flower_started_at: datetime | None
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
