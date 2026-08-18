"""Shared Pydantic contracts for the cloud gateway protocol."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from dirt_shared.metric_history import MetricHistoryBucket


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
CommandType = Literal[
    "ptz_preset",
    "ptz_look",
    "ptz_zoom",
    "breeding_seed_lot_create",
    "breeding_seed_lot_update",
    "breeding_plants_germinate",
    "breeding_plants_clone",
    "breeding_plants_bulk_sex",
    "breeding_sex_tests_bulk_create",
    "breeding_sex_test_update",
    "breeding_sex_tests_bulk_result",
    "breeding_plants_bulk_move",
    "breeding_plants_update_facts",
    "breeding_plants_bulk_cull",
    "breeding_plant_note_create",
    "breeding_plants_bulk_note",
]
CapturePolicyReason = Literal[
    "camera_not_found",
    "camera_disabled",
    "lights_schedule_not_found",
]
PlantSexKey = Literal["unknown", "male", "female", "herm", "reversed"]
PlantSexTestResultSexKey = Literal["male", "female"]
SeedLotSexTypeKey = Literal["unknown", "feminized", "regular"]
BreedingPlantFactField = Literal[
    "sex_key",
    "germinated_at",
    "taken_at",
    "rooted_at",
    "veg_started_at",
    "flower_started_at",
    "culled_at",
    "culled_reason",
    "harvested_at",
    "selected_for_breeding_at",
    "selected_for_breeding_reason",
]
BREEDING_PLANT_DATE_FACT_FIELDS = {
    "germinated_at",
    "taken_at",
    "rooted_at",
    "veg_started_at",
    "flower_started_at",
    "culled_at",
    "harvested_at",
    "selected_for_breeding_at",
}
BREEDING_PLANT_TEXT_FACT_FIELDS = {
    "culled_reason",
    "selected_for_breeding_reason",
}


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
    source_site_id: int
    name: str
    timezone: str = "America/Denver"


class CatalogTent(CloudContractModel):
    source_tent_id: int
    name: str
    role: str
    is_active: bool = True


class CatalogZone(CloudContractModel):
    source_tent_id: int
    source_zone_id: int
    name: str
    kind: str = "environment"
    is_active: bool = True


class CatalogDevice(CloudContractModel):
    source_tent_id: int
    device_id: str
    name: str
    last_seen_at: datetime | None = Field(...)
    source_zone_id: int | None = Field(...)
    kind: str = "sensor"
    controller: str | None = None
    is_active: bool = True


class CatalogCapability(CloudContractModel):
    source_tent_id: int
    device_id: str
    capability_id: str
    metric_name: str | None = None
    kind: str = "metric"
    unit: str | None = None
    is_enabled: bool = True


class CatalogSchedule(CloudContractModel):
    source_site_id: int
    source_tent_id: int
    source_schedule_id: int
    starts_local: time
    ends_local: time
    source_zone_id: int | None = Field(...)
    device_id: str | None = None
    capability_id: str | None = None
    kind: str = "lights"
    timezone: str = "America/Denver"
    is_enabled: bool = True


class CatalogPlantLine(CloudContractModel):
    source_line_id: int
    project_code: str | None = Field(...)
    generation_label: str | None = Field(...)
    strain: str
    cultivar: str
    description: str | None = Field(...)
    source_name: str | None = Field(...)


class CatalogSeedLot(CloudContractModel):
    source_seed_lot_id: int
    line_source_id: int
    sex_type_key: SeedLotSexTypeKey
    is_purchased: bool
    vendor_name: str | None = Field(...)
    acquired_at: datetime | None = Field(...)
    produced_by_cross_event_source_id: int | None = Field(...)
    seed_count: int | None = Field(...)
    notes: str | None = Field(...)


class CatalogPlant(CloudContractModel):
    source_plant_id: int
    line_source_id: int
    sex_key: PlantSexKey
    source_seed_lot_id: int | None = Field(...)
    clone_source_plant_id: int | None = Field(...)
    key: str
    name: str
    germinated_at: datetime | None = Field(...)
    taken_at: datetime | None = Field(...)
    rooted_at: datetime | None = Field(...)
    veg_started_at: datetime | None = Field(...)
    flower_started_at: datetime | None = Field(...)
    culled_at: datetime | None = Field(...)
    culled_reason: str | None = Field(...)
    harvested_at: datetime | None = Field(...)
    selected_for_breeding_at: datetime | None = Field(...)
    selected_for_breeding_reason: str | None = Field(...)
    is_active: bool


class CatalogPlantSexTest(CloudContractModel):
    source_sex_test_id: int
    source_plant_id: int
    vendor_name: str
    assay_name: str | None = Field(...)
    vendor_test_code: str
    sample_collected_at: datetime
    sample_sent_at: datetime | None = Field(...)
    result_received_at: datetime | None = Field(...)
    result_sex_key: PlantSexTestResultSexKey | None = Field(...)
    is_inconclusive: bool
    notes: str | None = Field(...)

    @model_validator(mode="after")
    def _result_state_is_complete(self) -> CatalogPlantSexTest:
        _validate_sex_test_result_state(
            result_received_at=self.result_received_at,
            result_sex_key=self.result_sex_key,
            is_inconclusive=self.is_inconclusive,
        )
        return self


class CatalogPlantLocation(CloudContractModel):
    source_location_id: int
    source_plant_id: int
    source_tent_id: int
    grid_position: str | None = Field(...)
    start_at: datetime
    end_at: datetime | None = Field(...)


class CatalogCrossEvent(CloudContractModel):
    source_cross_event_id: int
    resulting_line_source_id: int
    seed_parent_source_plant_id: int
    pollen_parent_source_plant_id: int
    pollinated_at: datetime
    pollen_parent_is_reversed: bool | None = Field(...)
    notes: str | None = Field(...)


class CatalogPlantNote(CloudContractModel):
    source_note_id: int
    source_plant_id: int
    observed_at: datetime
    body: str
    created_by: str | None = Field(...)


class CatalogPlantEvent(CloudContractModel):
    source_event_id: int
    source_plant_id: int
    is_pollen_collection: bool
    is_seed_production: bool
    is_clone_taken: bool
    is_sex_observation: bool
    is_reversal: bool
    is_transplant: bool
    is_selection_for_breeding: bool
    occurred_at: datetime
    reason: str | None = Field(...)
    notes: str | None = Field(...)
    metadata: dict[str, Any]


class CatalogPlantMetricStream(CloudContractModel):
    source_plant_id: int
    device_id: str
    capability_id: str
    metric: str
    display_order: int
    is_active: bool


class CatalogRequest(CloudContractModel):
    site_id: str
    site: CatalogSite
    tents: list[CatalogTent] = Field(default_factory=list)
    zones: list[CatalogZone] = Field(default_factory=list)
    devices: list[CatalogDevice] = Field(default_factory=list)
    capabilities: list[CatalogCapability] = Field(default_factory=list)
    schedules: list[CatalogSchedule] = Field(default_factory=list)
    plant_lines: list[CatalogPlantLine] = Field(default_factory=list)
    seed_lots: list[CatalogSeedLot] = Field(default_factory=list)
    plants: list[CatalogPlant] = Field(default_factory=list)
    sex_tests: list[CatalogPlantSexTest]
    plant_locations: list[CatalogPlantLocation] = Field(default_factory=list)
    cross_events: list[CatalogCrossEvent] = Field(default_factory=list)
    plant_notes: list[CatalogPlantNote] = Field(default_factory=list)
    plant_events: list[CatalogPlantEvent] = Field(default_factory=list)
    plant_metric_streams: list[CatalogPlantMetricStream] = Field(default_factory=list)


class CatalogResponse(CloudContractModel):
    sites: int
    tents: int
    zones: int
    devices: int
    capabilities: int
    schedules: int
    plant_lines: int
    seed_lots: int
    plants: int
    sex_tests: int
    plant_locations: int
    cross_events: int
    plant_notes: int
    plant_events: int
    plant_metric_streams: int


class LatestMetricItem(CloudContractModel):
    site_id: str
    source_site_id: int
    source_tent_id: int
    device_id: str
    capability_id: str
    metric: str
    value: float
    source_updated_at: datetime
    unit: str | None = None
    source_zone_id: int | None = Field(...)
    stale_after_s: int = 120


class LatestMetricsRequest(CloudContractModel):
    site_id: str
    metrics: list[LatestMetricItem]


class UpsertCountResponse(CloudContractModel):
    upserted: int


class RollupItem(CloudContractModel):
    site_id: str
    source_site_id: int
    source_tent_id: int
    device_id: str
    capability_id: str
    metric: str
    bucket: MetricHistoryBucket
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


class WikiProjectionPage(CloudContractModel):
    path: str
    title: str
    frontmatter: dict[str, Any]
    body_markdown: str
    sha256: str
    source_updated_at: datetime


class WikiProjectionRequest(CloudContractModel):
    site_id: str
    generated_at: datetime
    pages: list[WikiProjectionPage]
    excluded_paths: list[str] = Field(default_factory=list)
    content_hash: str


class WikiProjectionResponse(CloudContractModel):
    upserted: int
    deleted: int
    synced_at: datetime


class AssetSignUploadRequest(CloudContractModel):
    site_id: str
    source_tent_id: int | None = Field(...)
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
    source_zone_id: int | None = Field(...)
    device_id: str | None = None


class AssetCompleteResponse(CloudContractModel):
    asset_id: str
    object_key: str
    uploaded_at: datetime


class AssetFailureRequest(CloudContractModel):
    site_id: str
    stage: str = Field(max_length=80)
    error: str = Field(max_length=500)
    source_tent_id: int | None = Field(default=None)
    asset_id: str | None = None
    object_key: str | None = None


class AssetFailureResponse(CloudContractModel):
    ok: bool
    received_at: datetime


class CapturePolicyResponse(CloudContractModel):
    site_id: str
    source_site_id: int | None = Field(...)
    source_tent_id: int | None = Field(...)
    tent_name: str | None = Field(...)
    camera_device_id: str
    enabled: bool
    require_lights_on: bool
    lights_on_local: time | None
    lights_off_local: time | None
    timezone: str
    source_schedule_id: int | None
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


def _strip_required_text(value: str) -> str:
    stripped = value.strip()
    if stripped == "":
        raise ValueError("must not be blank")
    return stripped


def _strip_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    return _strip_required_text(value)


def _strip_required_text_list(values: list[str]) -> list[str]:
    stripped = [_strip_required_text(value) for value in values]
    if len(set(stripped)) != len(stripped):
        raise ValueError("must not contain duplicates")
    return stripped


def _reject_duplicate_values(values: list[object], message: str) -> None:
    if len(set(values)) != len(values):
        raise ValueError(message)


def _validate_sex_test_result_state(
    *,
    result_received_at: datetime | None,
    result_sex_key: PlantSexTestResultSexKey | None,
    is_inconclusive: bool,
) -> None:
    has_result = result_sex_key is not None
    if result_received_at is None:
        if has_result or is_inconclusive:
            raise ValueError("pending sex tests must not include a result")
        return
    if has_result == is_inconclusive:
        raise ValueError(
            "received sex tests require exactly one conclusive result_sex_key "
            "or is_inconclusive=true"
        )


class BreedingCreateSeedLotPayload(CloudContractModel):
    source: Literal["purchased", "cross"]
    generation: str = Field(min_length=1)
    prefix: str = Field(min_length=1)
    sex_type_key: SeedLotSexTypeKey
    strain: str | None = None
    cultivar: str | None = None
    source_name: str | None = None
    vendor_name: str | None = None
    acquired_at: datetime | None = None
    seed_parent_plant_key: str | None = None
    pollen_parent_plant_key: str | None = None
    pollinated_at: datetime | None = None
    pollen_parent_is_reversed: bool | None = None
    seed_count: int | None = Field(default=None, ge=0)
    notes: str | None = None

    @field_validator(
        "generation",
        "prefix",
        "strain",
        "cultivar",
        "source_name",
        "vendor_name",
        "seed_parent_plant_key",
        "pollen_parent_plant_key",
        "notes",
    )
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)

    @model_validator(mode="after")
    def _source_fields_match(self) -> BreedingCreateSeedLotPayload:
        if self.source == "purchased":
            missing = [
                field_name
                for field_name in ("strain", "cultivar", "source_name")
                if getattr(self, field_name) is None
            ]
            if missing:
                raise ValueError(
                    "purchased seed lots require strain, cultivar, and source_name"
                )
            if self.seed_parent_plant_key is not None:
                raise ValueError(
                    "purchased seed lots must not include seed_parent_plant_key"
                )
            if self.pollen_parent_plant_key is not None:
                raise ValueError(
                    "purchased seed lots must not include pollen_parent_plant_key"
                )
        else:
            if (
                self.seed_parent_plant_key is None
                or self.pollen_parent_plant_key is None
            ):
                raise ValueError(
                    "cross seed lots require seed and pollen parent plant keys"
                )
            if self.seed_parent_plant_key == self.pollen_parent_plant_key:
                raise ValueError("cross parents must be distinct plants")
        return self


class BreedingUpdateSeedLotInventoryPayload(CloudContractModel):
    seed_lot_source_id: int = Field(gt=0)
    sex_type_key: SeedLotSexTypeKey
    seed_count: int | None = Field(..., ge=0)
    notes: str | None = Field(...)
    vendor_name: str | None = Field(...)
    acquired_at: datetime | None = Field(...)

    @field_validator("notes", "vendor_name")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)


class BreedingGerminatePlantsPayload(CloudContractModel):
    seed_lot_source_id: int = Field(gt=0)
    count: int = Field(gt=0)
    source_tent_id: int = Field(gt=0)
    grid_position: None = Field(...)
    germinated_at: datetime | None = None


class BreedingClonePlantsPayload(CloudContractModel):
    mother_plant_key: str = Field(min_length=1)
    count: int = Field(gt=0)
    source_tent_id: int = Field(gt=0)
    grid_position: None = Field(...)
    taken_at: datetime | None = None

    @field_validator("mother_plant_key")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return _strip_required_text(value)


class BreedingBulkSexPayload(CloudContractModel):
    plant_keys: list[str] = Field(min_length=1)
    sex_key: PlantSexKey

    @field_validator("plant_keys")
    @classmethod
    def _strip_plant_keys(cls, value: list[str]) -> list[str]:
        return _strip_required_text_list(value)


class BreedingBulkCreateSexTestItem(CloudContractModel):
    plant_key: str = Field(min_length=1)
    vendor_test_code: str = Field(min_length=1)
    notes: str | None = None

    @field_validator("plant_key", "vendor_test_code")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _strip_required_text(value)

    @field_validator("notes")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)


class BreedingBulkCreateSexTestsPayload(CloudContractModel):
    vendor_name: str = Field(min_length=1)
    assay_name: str | None = Field(...)
    sample_collected_at: datetime
    sample_sent_at: datetime | None = Field(...)
    tests: list[BreedingBulkCreateSexTestItem] = Field(min_length=1)

    @field_validator("vendor_name")
    @classmethod
    def _strip_vendor_name(cls, value: str) -> str:
        return _strip_required_text(value)

    @field_validator("assay_name")
    @classmethod
    def _strip_assay_name(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)

    @model_validator(mode="after")
    def _tests_are_unique(self) -> BreedingBulkCreateSexTestsPayload:
        _reject_duplicate_values(
            [test.plant_key for test in self.tests],
            "tests must not contain duplicate plant_key values",
        )
        _reject_duplicate_values(
            [test.vendor_test_code for test in self.tests],
            "tests must not contain duplicate vendor_test_code values",
        )
        return self


class BreedingUpdateSexTestPayload(CloudContractModel):
    sex_test_source_id: int = Field(gt=0)
    vendor_name: str = Field(min_length=1)
    assay_name: str | None = Field(...)
    vendor_test_code: str = Field(min_length=1)
    sample_collected_at: datetime
    sample_sent_at: datetime | None = Field(...)
    result_received_at: datetime | None = Field(...)
    result_sex_key: PlantSexTestResultSexKey | None = Field(...)
    is_inconclusive: bool
    notes: str | None = Field(...)

    @field_validator("vendor_name", "vendor_test_code")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _strip_required_text(value)

    @field_validator("assay_name", "notes")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _strip_optional_text(value)

    @model_validator(mode="after")
    def _result_state_is_complete(self) -> BreedingUpdateSexTestPayload:
        _validate_sex_test_result_state(
            result_received_at=self.result_received_at,
            result_sex_key=self.result_sex_key,
            is_inconclusive=self.is_inconclusive,
        )
        return self


class BreedingSexTestResultRow(CloudContractModel):
    sex_test_source_id: int = Field(gt=0)
    result_sex_key: PlantSexTestResultSexKey | None = Field(...)
    is_inconclusive: bool

    @model_validator(mode="after")
    def _result_is_unambiguous(self) -> BreedingSexTestResultRow:
        has_result_sex = self.result_sex_key is not None
        if has_result_sex == self.is_inconclusive:
            raise ValueError(
                "sex-test result rows require exactly one conclusive "
                "result_sex_key or is_inconclusive=true"
            )
        return self


class BreedingBulkResultSexTestsPayload(CloudContractModel):
    result_received_at: datetime
    results: list[BreedingSexTestResultRow] = Field(min_length=1)

    @model_validator(mode="after")
    def _results_are_unique(self) -> BreedingBulkResultSexTestsPayload:
        _reject_duplicate_values(
            [row.sex_test_source_id for row in self.results],
            "results must not contain duplicate sex_test_source_id values",
        )
        return self


class BreedingBulkMovePayload(CloudContractModel):
    plant_keys: list[str] = Field(min_length=1)
    source_tent_id: int = Field(gt=0)
    grid_position: None = Field(...)

    @field_validator("plant_keys")
    @classmethod
    def _strip_plant_keys(cls, value: list[str]) -> list[str]:
        return _strip_required_text_list(value)


class BreedingPlantFactUpdate(CloudContractModel):
    field: BreedingPlantFactField
    value: datetime | str | None

    @model_validator(mode="after")
    def _value_matches_field(self) -> BreedingPlantFactUpdate:
        if self.field == "sex_key":
            if self.value not in ("unknown", "male", "female", "herm", "reversed"):
                raise ValueError("sex_key updates require a plant sex key")
            return self
        if self.field in BREEDING_PLANT_TEXT_FACT_FIELDS:
            if self.value is None:
                return self
            if not isinstance(self.value, str) or self.value.strip() == "":
                raise ValueError(f"{self.field} updates require nonblank text or null")
            self.value = self.value.strip()
            return self
        if self.field in BREEDING_PLANT_DATE_FACT_FIELDS:
            if self.value is None or isinstance(self.value, datetime):
                return self
            if isinstance(self.value, str):
                try:
                    self.value = datetime.fromisoformat(
                        self.value.replace("Z", "+00:00")
                    )
                except ValueError as exc:
                    raise ValueError(
                        f"{self.field} updates require a datetime or null"
                    ) from exc
                return self
            raise ValueError(f"{self.field} updates require a datetime or null")
        raise ValueError(f"unsupported plant fact field: {self.field}")


class BreedingBulkPlantFactsPayload(CloudContractModel):
    plant_keys: list[str] = Field(min_length=1)
    updates: list[BreedingPlantFactUpdate] = Field(min_length=1)

    @field_validator("plant_keys")
    @classmethod
    def _strip_plant_keys(cls, value: list[str]) -> list[str]:
        return _strip_required_text_list(value)

    @model_validator(mode="after")
    def _updates_are_unambiguous(self) -> BreedingBulkPlantFactsPayload:
        fields = [update.field for update in self.updates]
        if len(set(fields)) != len(fields):
            raise ValueError("updates must not contain duplicate fields")
        return self


class BreedingBulkCullPayload(CloudContractModel):
    plant_keys: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)
    culled_at: datetime | None = Field(...)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        return _strip_required_text(value)

    @field_validator("plant_keys")
    @classmethod
    def _strip_plant_keys(cls, value: list[str]) -> list[str]:
        return _strip_required_text_list(value)


class BreedingCreatePlantNotePayload(CloudContractModel):
    plant_key: str = Field(min_length=1)
    body: str = Field(min_length=1)
    observed_at: datetime | None = None

    @field_validator("plant_key", "body")
    @classmethod
    def _strip_text(cls, value: str) -> str:
        return _strip_required_text(value)


class BreedingBulkPlantNotePayload(CloudContractModel):
    plant_keys: list[str] = Field(min_length=1)
    body: str = Field(min_length=1)
    observed_at: datetime | None = None

    @field_validator("plant_keys")
    @classmethod
    def _strip_plant_keys(cls, value: list[str]) -> list[str]:
        return _strip_required_text_list(value)

    @field_validator("body")
    @classmethod
    def _strip_body(cls, value: str) -> str:
        return _strip_required_text(value)


PtzZoomPayload: TypeAlias = PtzZoomAbsolutePayload | PtzZoomRelativePayload
PtzCommandPayload: TypeAlias = PtzPresetPayload | PtzLookPayload | PtzZoomPayload


class PtzCommandTarget(CloudContractModel):
    kind: Literal["ptz"]
    source_tent_id: int | None = None
    device_id: Literal["obsbot-main"]
    capability_id: Literal["ptz_move"]


CommandTarget: TypeAlias = PtzCommandTarget


BreedingCommandPayload: TypeAlias = (
    BreedingCreateSeedLotPayload
    | BreedingUpdateSeedLotInventoryPayload
    | BreedingGerminatePlantsPayload
    | BreedingClonePlantsPayload
    | BreedingBulkSexPayload
    | BreedingBulkCreateSexTestsPayload
    | BreedingUpdateSexTestPayload
    | BreedingBulkResultSexTestsPayload
    | BreedingBulkMovePayload
    | BreedingBulkPlantFactsPayload
    | BreedingBulkCullPayload
    | BreedingCreatePlantNotePayload
    | BreedingBulkPlantNotePayload
)


class ClaimedCommand(CloudContractModel):
    command_id: str
    site_id: str
    command_type: CommandType
    target: CommandTarget | None = None
    payload: PtzCommandPayload | BreedingCommandPayload
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
        expected_payloads: dict[CommandType, type[CloudContractModel]] = {
            "breeding_seed_lot_create": BreedingCreateSeedLotPayload,
            "breeding_seed_lot_update": BreedingUpdateSeedLotInventoryPayload,
            "breeding_plants_germinate": BreedingGerminatePlantsPayload,
            "breeding_plants_clone": BreedingClonePlantsPayload,
            "breeding_plants_bulk_sex": BreedingBulkSexPayload,
            "breeding_sex_tests_bulk_create": BreedingBulkCreateSexTestsPayload,
            "breeding_sex_test_update": BreedingUpdateSexTestPayload,
            "breeding_sex_tests_bulk_result": BreedingBulkResultSexTestsPayload,
            "breeding_plants_bulk_move": BreedingBulkMovePayload,
            "breeding_plants_update_facts": BreedingBulkPlantFactsPayload,
            "breeding_plants_bulk_cull": BreedingBulkCullPayload,
            "breeding_plant_note_create": BreedingCreatePlantNotePayload,
            "breeding_plants_bulk_note": BreedingBulkPlantNotePayload,
        }
        expected = expected_payloads.get(self.command_type)
        if expected is not None and not isinstance(self.payload, expected):
            raise ValueError(f"{self.command_type} requires {expected.__name__}")
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
