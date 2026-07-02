from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from dirt_shared.cloud_contract import (
    AssetCompleteRequest,
    AssetFailureRequest,
    AssetRetentionRequest,
    AssetSignUploadRequest,
    BreedingBulkCreateSexTestsPayload,
    BreedingBulkCullPayload,
    BreedingBulkMovePayload,
    BreedingBulkPlantFactsPayload,
    BreedingBulkPlantNotePayload,
    BreedingBulkResultSexTestsPayload,
    BreedingBulkSexPayload,
    BreedingClonePlantsPayload,
    BreedingCreatePlantNotePayload,
    BreedingCreateSeedLotPayload,
    BreedingGerminatePlantsPayload,
    BreedingUpdateSeedLotInventoryPayload,
    BreedingUpdateSexTestPayload,
    CapturePolicyResponse,
    CatalogCrossEvent,
    CatalogDevice,
    CatalogPlant,
    CatalogPlantEvent,
    CatalogPlantLine,
    CatalogPlantLocation,
    CatalogPlantMetricStream,
    CatalogPlantNote,
    CatalogPlantSexTest,
    CatalogRequest,
    CatalogSchedule,
    CatalogSeedLot,
    CatalogTent,
    CatalogZone,
    ClaimedCommand,
    CommandClaimResponse,
    CommandResultResponse,
    LatestMetricItem,
    PtzCommandTarget,
    PtzLookPayload,
    PtzPresetPayload,
    PtzZoomRelativePayload,
    RollupItem,
    SignUploadResponse,
    WikiProjectionPage,
    WikiProjectionRequest,
)


def test_catalog_device_accepts_last_seen_timestamp() -> None:
    last_seen = datetime(2026, 5, 9, 12, 30, tzinfo=UTC)

    device = CatalogDevice(
        source_tent_id=2,
        source_zone_id=10,
        device_id="breeding-env-node",
        name="Breeding environment",
        last_seen_at=last_seen,
    )

    assert device.last_seen_at == last_seen


def test_catalog_device_accepts_intentional_null_last_seen() -> None:
    device = CatalogDevice(
        source_tent_id=2,
        source_zone_id=None,
        device_id="breeding-env-node",
        name="Breeding environment",
        last_seen_at=None,
    )

    assert device.last_seen_at is None


def test_catalog_device_rejects_missing_last_seen() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CatalogDevice(
            source_tent_id=2,
            source_zone_id=None,
            device_id="breeding-env-node",
            name="Breeding environment",
        )

    assert exc_info.value.errors()[0]["loc"] == ("last_seen_at",)
    assert exc_info.value.errors()[0]["type"] == "missing"


def test_gateway_contract_models_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CatalogDevice(
            source_tent_id=2,
            source_zone_id=None,
            device_id="breeding-env-node",
            name="Breeding environment",
            last_seen_at=None,
            stale_field=True,
        )

    assert exc_info.value.errors()[0]["loc"] == ("stale_field",)
    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"


def test_catalog_scope_dtos_require_source_ids_and_reject_retired_id_fields() -> None:
    tent = CatalogTent.model_validate(
        {
            "source_tent_id": 2,
            "name": "Breeding",
            "role": "breeding",
        }
    )
    zone = CatalogZone.model_validate(
        {
            "source_tent_id": tent.source_tent_id,
            "source_zone_id": 10,
            "name": "Canopy",
            "kind": "environment",
        }
    )
    schedule = CatalogSchedule.model_validate(
        {
            "source_site_id": 1,
            "source_tent_id": tent.source_tent_id,
            "source_schedule_id": 4,
            "source_zone_id": zone.source_zone_id,
            "device_id": "kasa-breeding-lights",
            "capability_id": None,
            "starts_local": "06:00:00",
            "ends_local": "18:00:00",
        }
    )

    assert tent.source_tent_id == 2
    assert zone.source_zone_id == 10
    assert schedule.source_schedule_id == 4

    stale_payloads = (
        (
            CatalogTent,
            {**tent.model_dump(mode="json"), "legacy_tent_id": "breeding"},
        ),
        (CatalogTent, {**tent.model_dump(mode="json"), "tent_id": "breeding"}),
        (
            CatalogZone,
            {**zone.model_dump(mode="json"), "legacy_zone_id": "canopy"},
        ),
        (CatalogZone, {**zone.model_dump(mode="json"), "zone_id": "canopy"}),
        (
            CatalogSchedule,
            {
                **schedule.model_dump(mode="json"),
                "legacy_schedule_id": "breeding-lights-photoperiod",
            },
        ),
        (
            CatalogSchedule,
            {
                **schedule.model_dump(mode="json"),
                "schedule_id": "breeding-lights-photoperiod",
            },
        ),
    )
    for model, payload in stale_payloads:
        with pytest.raises(ValidationError) as exc_info:
            model.model_validate(payload)
        assert exc_info.value.errors()[0]["type"] == "extra_forbidden"


def test_catalog_plant_requires_nullable_wire_fields() -> None:
    plant_payload = {
        "source_plant_id": 1,
        "line_source_id": 1,
        "sex_key": "female",
        "source_seed_lot_id": None,
        "clone_source_plant_id": None,
        "key": "SBBS-R1-001",
        "name": "Plant A",
        "germinated_at": "2026-03-15T12:00:00Z",
        "taken_at": None,
        "rooted_at": None,
        "veg_started_at": None,
        "flower_started_at": None,
        "culled_at": None,
        "culled_reason": None,
        "harvested_at": None,
        "selected_for_breeding_at": None,
        "selected_for_breeding_reason": None,
        "is_active": True,
    }

    plant = CatalogPlant.model_validate(plant_payload)
    assert plant.source_plant_id == 1
    assert plant.key == "SBBS-R1-001"
    assert plant.sex_key == "female"

    for field_name in (
        "sex_key",
        "source_seed_lot_id",
        "clone_source_plant_id",
        "taken_at",
        "rooted_at",
        "culled_reason",
    ):
        invalid = dict(plant_payload)
        del invalid[field_name]
        with pytest.raises(ValidationError) as exc_info:
            CatalogPlant.model_validate(invalid)
        assert exc_info.value.errors()[0]["loc"] == (field_name,)
        assert exc_info.value.errors()[0]["type"] == "missing"


def test_catalog_plant_sex_test_requires_nullable_wire_fields() -> None:
    sex_test_payload = {
        "source_sex_test_id": 10,
        "source_plant_id": 1,
        "vendor_name": "Farmer Freeman",
        "assay_name": None,
        "vendor_test_code": "FF-001",
        "sample_collected_at": "2026-07-01T12:00:00Z",
        "sample_sent_at": None,
        "result_received_at": None,
        "result_sex_key": None,
        "is_inconclusive": False,
        "notes": None,
    }

    sex_test = CatalogPlantSexTest.model_validate(sex_test_payload)
    assert sex_test.source_sex_test_id == 10
    assert sex_test.source_plant_id == 1
    assert sex_test.vendor_test_code == "FF-001"
    assert sex_test.result_sex_key is None

    for field_name in (
        "assay_name",
        "sample_sent_at",
        "result_received_at",
        "result_sex_key",
        "notes",
    ):
        invalid = dict(sex_test_payload)
        del invalid[field_name]
        with pytest.raises(ValidationError) as exc_info:
            CatalogPlantSexTest.model_validate(invalid)
        assert exc_info.value.errors()[0]["loc"] == (field_name,)
        assert exc_info.value.errors()[0]["type"] == "missing"


def test_catalog_request_requires_sex_tests() -> None:
    payload = {
        "site_id": "homebox",
        "site": {"source_site_id": 1, "name": "Home Box"},
    }

    with pytest.raises(ValidationError) as exc_info:
        CatalogRequest.model_validate(payload)

    assert exc_info.value.errors()[0]["loc"] == ("sex_tests",)
    assert exc_info.value.errors()[0]["type"] == "missing"
    assert CatalogRequest.model_validate({**payload, "sex_tests": []}).sex_tests == []


def test_catalog_line_seed_lot_and_location_require_source_identity() -> None:
    line = CatalogPlantLine.model_validate(
        {
            "source_line_id": 1,
            "project_code": "SBBS",
            "generation_label": "R1",
            "strain": "Sirius Black x BS01",
            "cultivar": "SBBS R1",
            "description": None,
            "source_name": "Unknown vendor",
        }
    )
    seed_lot = CatalogSeedLot.model_validate(
        {
            "source_seed_lot_id": 1,
            "line_source_id": line.source_line_id,
            "sex_type_key": "regular",
            "is_purchased": True,
            "vendor_name": "Unknown vendor",
            "acquired_at": None,
            "produced_by_cross_event_source_id": None,
            "seed_count": None,
            "notes": None,
        }
    )
    location = CatalogPlantLocation.model_validate(
        {
            "source_location_id": 1,
            "source_plant_id": 1,
            "source_tent_id": 1,
            "grid_position": None,
            "start_at": "2026-03-15T12:00:00Z",
            "end_at": None,
        }
    )

    assert seed_lot.line_source_id == 1
    assert seed_lot.sex_type_key == "regular"
    assert location.source_plant_id == 1
    assert location.grid_position is None

    for model, payload, field_name in (
        (CatalogPlantLine, line.model_dump(mode="json"), "source_line_id"),
        (CatalogSeedLot, seed_lot.model_dump(mode="json"), "source_seed_lot_id"),
        (CatalogPlantLocation, location.model_dump(mode="json"), "source_location_id"),
    ):
        del payload[field_name]
        with pytest.raises(ValidationError) as exc_info:
            model.model_validate(payload)
        assert exc_info.value.errors()[0]["loc"] == (field_name,)
        assert exc_info.value.errors()[0]["type"] == "missing"


def test_catalog_location_requires_nullable_grid_position() -> None:
    payload = {
        "source_location_id": 1,
        "source_plant_id": 1,
        "source_tent_id": 1,
        "start_at": "2026-03-15T12:00:00Z",
        "end_at": None,
    }

    with pytest.raises(ValidationError) as exc_info:
        CatalogPlantLocation.model_validate(payload)

    assert exc_info.value.errors()[0]["loc"] == ("grid_position",)
    assert exc_info.value.errors()[0]["type"] == "missing"


def test_catalog_timeline_dtos_require_nullable_fields() -> None:
    cross_payload = {
        "source_cross_event_id": 10,
        "resulting_line_source_id": 2,
        "seed_parent_source_plant_id": 1,
        "pollen_parent_source_plant_id": 2,
        "pollinated_at": "2026-04-20T12:00:00Z",
        "pollen_parent_is_reversed": None,
        "notes": None,
    }
    note_payload = {
        "source_note_id": 20,
        "source_plant_id": 1,
        "observed_at": "2026-04-21T12:00:00Z",
        "body": "Branching improved.",
        "created_by": None,
    }
    event_payload = {
        "source_event_id": 30,
        "source_plant_id": 1,
        "is_pollen_collection": False,
        "is_seed_production": False,
        "is_clone_taken": False,
        "is_sex_observation": True,
        "is_reversal": False,
        "is_transplant": False,
        "is_selection_for_breeding": False,
        "occurred_at": "2026-04-22T12:00:00Z",
        "reason": None,
        "notes": None,
        "metadata": {},
    }

    assert CatalogCrossEvent.model_validate(cross_payload).notes is None
    assert CatalogPlantNote.model_validate(note_payload).created_by is None
    assert CatalogPlantEvent.model_validate(event_payload).metadata == {}

    for model, payload, field_name in (
        (CatalogCrossEvent, cross_payload, "pollen_parent_is_reversed"),
        (CatalogCrossEvent, cross_payload, "notes"),
        (CatalogPlantNote, note_payload, "created_by"),
        (CatalogPlantEvent, event_payload, "reason"),
        (CatalogPlantEvent, event_payload, "notes"),
        (CatalogPlantEvent, event_payload, "metadata"),
    ):
        invalid = dict(payload)
        del invalid[field_name]
        with pytest.raises(ValidationError) as exc_info:
            model.model_validate(invalid)
        assert exc_info.value.errors()[0]["loc"] == (field_name,)
        assert exc_info.value.errors()[0]["type"] == "missing"


def test_catalog_plant_metric_stream_requires_public_stream_identity() -> None:
    stream_payload = {
        "source_plant_id": 1,
        "device_id": "plant-a-substrate-node",
        "capability_id": "substrate_ph",
        "metric": "substrate_ph",
        "display_order": 4,
        "is_active": True,
    }

    stream = CatalogPlantMetricStream.model_validate(stream_payload)
    assert stream.source_plant_id == 1
    assert stream.device_id == "plant-a-substrate-node"
    assert stream.metric == "substrate_ph"

    for field_name in ("device_id", "capability_id", "metric"):
        invalid = dict(stream_payload)
        del invalid[field_name]
        with pytest.raises(ValidationError) as exc_info:
            CatalogPlantMetricStream.model_validate(invalid)
        assert exc_info.value.errors()[0]["loc"] == (field_name,)
        assert exc_info.value.errors()[0]["type"] == "missing"


def test_metric_stream_contracts_require_device_id() -> None:
    metric_payload = {
        "site_id": "homebox",
        "source_site_id": 1,
        "source_tent_id": 1,
        "source_zone_id": None,
        "capability_id": "soil_moisture_raw",
        "metric": "soil_moisture_raw",
        "value": 1850.0,
        "source_updated_at": "2026-05-09T12:00:00Z",
    }
    with pytest.raises(ValidationError) as latest_missing:
        LatestMetricItem.model_validate(metric_payload)
    with pytest.raises(ValidationError) as latest_null:
        LatestMetricItem.model_validate({**metric_payload, "device_id": None})

    rollup_payload = {
        **metric_payload,
        "bucket": "1h",
        "bucket_start_at": "2026-05-09T11:00:00Z",
        "bucket_end_at": "2026-05-09T12:00:00Z",
    }
    with pytest.raises(ValidationError) as rollup_missing:
        RollupItem.model_validate(rollup_payload)
    with pytest.raises(ValidationError) as rollup_null:
        RollupItem.model_validate({**rollup_payload, "device_id": None})

    assert latest_missing.value.errors()[0]["loc"] == ("device_id",)
    assert latest_null.value.errors()[0]["loc"] == ("device_id",)
    assert rollup_missing.value.errors()[0]["loc"] == ("device_id",)
    assert rollup_null.value.errors()[0]["loc"] == ("device_id",)

    with pytest.raises(ValidationError) as stale_latest:
        LatestMetricItem.model_validate(
            {
                **metric_payload,
                "device_id": "plant-a",
                "tent_id": "main",
            }
        )
    assert stale_latest.value.errors()[0]["type"] == "extra_forbidden"


def test_wiki_projection_contract_requires_page_content_and_forbids_extra() -> None:
    page_payload = {
        "path": "wiki/grows/main-2026-03-15/plants/plant-a.md",
        "title": "Plant A",
        "frontmatter": {"title": "Plant A", "sources": []},
        "body_markdown": "# Plant A\n",
        "sha256": "a" * 64,
        "source_updated_at": "2026-05-31T07:00:00Z",
    }

    request = WikiProjectionRequest(
        site_id="homebox",
        generated_at="2026-05-31T07:01:00Z",
        pages=[page_payload],
        excluded_paths=["wiki/AGENTS.md"],
        content_hash="b" * 64,
    )

    assert request.pages[0].path == page_payload["path"]
    assert request.excluded_paths == ["wiki/AGENTS.md"]

    missing = dict(page_payload)
    del missing["body_markdown"]
    with pytest.raises(ValidationError) as missing_exc:
        WikiProjectionPage.model_validate(missing)
    assert missing_exc.value.errors()[0]["loc"] == ("body_markdown",)
    assert missing_exc.value.errors()[0]["type"] == "missing"

    with pytest.raises(ValidationError) as extra_exc:
        WikiProjectionPage.model_validate({**page_payload, "stale": True})
    assert extra_exc.value.errors()[0]["loc"] == ("stale",)
    assert extra_exc.value.errors()[0]["type"] == "extra_forbidden"


def test_sign_upload_response_serializes_datetime_as_json() -> None:
    expires_at = datetime(2026, 5, 9, 12, 45, tzinfo=UTC)

    response = SignUploadResponse(
        asset_id=None,
        object_key="tents/1/snapshots/latest.jpg",
        upload_url="https://assets.test/upload",
        method="PUT",
        headers={"Content-Type": "image/jpeg"},
        expires_at=expires_at,
        byte_size=123,
    )

    assert response.model_dump(mode="json")["expires_at"] == "2026-05-09T12:45:00Z"


def test_asset_retention_request_matches_gateway_projection_shape() -> None:
    request = AssetRetentionRequest(site_id="homebox", as_of_date="2026-05-09")

    assert request.model_dump(mode="json") == {
        "site_id": "homebox",
        "as_of_date": "2026-05-09",
    }


def test_asset_request_retired_scope_fields_are_rejected() -> None:
    sign_payload = {
        "site_id": "homebox",
        "source_tent_id": 2,
        "content_type": "image/jpeg",
        "byte_size": 123,
        "object_key": "cameras/obsbot-breeding/snapshots/latest.jpg",
    }
    complete_payload = {
        **sign_payload,
        "captured_at": "2026-05-09T12:00:00Z",
        "source_zone_id": 10,
    }
    failure_payload = {
        "site_id": "homebox",
        "stage": "upload",
        "error": "network unavailable",
        "source_tent_id": 2,
    }

    assert AssetSignUploadRequest.model_validate(sign_payload).source_tent_id == 2
    assert AssetCompleteRequest.model_validate(complete_payload).source_zone_id == 10
    assert AssetFailureRequest.model_validate(failure_payload).source_tent_id == 2

    stale_payloads = (
        (AssetSignUploadRequest, {**sign_payload, "tent_id": "breeding"}),
        (AssetCompleteRequest, {**complete_payload, "tent_id": "breeding"}),
        (AssetCompleteRequest, {**complete_payload, "zone_id": "canopy"}),
        (AssetFailureRequest, {**failure_payload, "tent_id": "breeding"}),
    )
    for model, payload in stale_payloads:
        with pytest.raises(ValidationError) as exc_info:
            model.model_validate(payload)
        assert exc_info.value.errors()[0]["type"] == "extra_forbidden"


def test_capture_policy_retired_tent_id_is_rejected() -> None:
    payload = {
        "site_id": "homebox",
        "source_site_id": 1,
        "source_tent_id": 2,
        "tent_name": "Breeding Tent",
        "camera_device_id": "obsbot-breeding",
        "enabled": True,
        "require_lights_on": True,
        "lights_on_local": "06:00:00",
        "lights_off_local": "18:00:00",
        "timezone": "America/Denver",
        "source_schedule_id": 4,
        "reason": None,
    }

    assert CapturePolicyResponse.model_validate(payload).source_tent_id == 2
    with pytest.raises(ValidationError) as exc_info:
        CapturePolicyResponse.model_validate({**payload, "tent_id": "breeding"})
    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"


def test_command_claim_response_requires_nullable_wire_keys() -> None:
    command = {
        "command_id": "cmd_1",
        "site_id": "homebox",
        "target": {
            "kind": "ptz",
            "source_tent_id": 1,
            "device_id": "obsbot-main",
            "capability_id": "ptz_move",
        },
        "command_type": "ptz_zoom",
        "payload": {"zoom": 1.2},
        "status": "claimed",
        "queued_at": "2026-05-09T12:00:00Z",
        "expires_at": "2026-05-09T12:05:00Z",
        "claimed_by": None,
        "claimed_at": None,
        "requested_by": "browser",
        "started_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
    }

    assert CommandClaimResponse(commands=[command]).commands[0].claimed_at is None

    missing_nullable = dict(command)
    del missing_nullable["claimed_at"]
    with pytest.raises(ValidationError) as exc_info:
        CommandClaimResponse(commands=[missing_nullable])

    assert exc_info.value.errors()[0]["loc"] == ("commands", 0, "claimed_at")
    assert exc_info.value.errors()[0]["type"] == "missing"


def test_claimed_command_and_result_response_reject_retired_command_fields() -> None:
    command = _command_payload(
        command_type="ptz_preset",
        payload={"preset_id": "overview"},
    )
    result = {
        **command,
        "status": "succeeded",
        "finished_at": "2026-05-09T12:00:30Z",
        "result": {"ok": True},
    }

    for field_name, value in (
        ("tent_id", "main"),
        ("source_tent_id", 1),
        ("device_id", "obsbot-main"),
        ("capability_id", "ptz_move"),
    ):
        with pytest.raises(ValidationError) as claimed_exc:
            ClaimedCommand.model_validate({**command, field_name: value})
        assert claimed_exc.value.errors()[0]["type"] == "extra_forbidden"
        with pytest.raises(ValidationError) as result_exc:
            CommandResultResponse.model_validate({**result, field_name: value})
        assert result_exc.value.errors()[0]["type"] == "extra_forbidden"


def test_claimed_command_accepts_ptz_target_shape() -> None:
    command = _command_payload(
        command_type="ptz_preset",
        payload={"preset_id": "overview"},
    )

    claimed = ClaimedCommand.model_validate(command)

    assert isinstance(claimed.target, PtzCommandTarget)
    assert claimed.target.device_id == "obsbot-main"
    assert isinstance(claimed.payload, PtzPresetPayload)


def test_claimed_command_accepts_breeding_command_without_target() -> None:
    command = _command_payload(
        command_type="breeding_plants_bulk_sex",
        payload={"plant_keys": ["SBBS-R1-001"], "sex_key": "female"},
    )
    command["target"] = None

    claimed = ClaimedCommand.model_validate(command)

    assert claimed.target is None
    assert isinstance(claimed.payload, BreedingBulkSexPayload)


def test_command_claim_response_uses_explicit_ptz_payload_models() -> None:
    preset = _command_payload(
        command_type="ptz_preset",
        payload={"preset_id": "overview"},
    )
    look = _command_payload(command_type="ptz_look", payload={"x": 0.2, "y": -0.1})
    zoom = _command_payload(command_type="ptz_zoom", payload={"delta": 0.1})

    response = CommandClaimResponse(commands=[preset, look, zoom])

    assert isinstance(response.commands[0].payload, PtzPresetPayload)
    assert isinstance(response.commands[1].payload, PtzLookPayload)
    assert isinstance(response.commands[2].payload, PtzZoomRelativePayload)


def test_command_claim_response_rejects_mismatched_ptz_payload() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CommandClaimResponse(
            commands=[
                _command_payload(
                    command_type="ptz_preset",
                    payload={"x": 0.2, "y": -0.1},
                )
            ]
        )

    assert exc_info.value.errors()[0]["type"] == "value_error"


def test_command_claim_response_uses_explicit_breeding_payload_models() -> None:
    commands = [
        _command_payload(
            command_type="breeding_seed_lot_create",
            payload={
                "source": "purchased",
                "generation": "R1",
                "prefix": "SBBS",
                "strain": "Sirius Black",
                "cultivar": "BS01",
                "source_name": "pack label",
                "vendor_name": "Archive",
                "acquired_at": None,
                "seed_count": 12,
                "sex_type_key": "feminized",
                "notes": None,
            },
        ),
        _command_payload(
            command_type="breeding_seed_lot_update",
            payload={
                "seed_lot_source_id": 1,
                "sex_type_key": "regular",
                "seed_count": 8,
                "notes": None,
                "vendor_name": "Archive",
                "acquired_at": None,
            },
        ),
        _command_payload(
            command_type="breeding_plants_germinate",
            payload={
                "seed_lot_source_id": 1,
                "count": 2,
                "source_tent_id": 2,
                "grid_position": None,
                "germinated_at": None,
            },
        ),
        _command_payload(
            command_type="breeding_plants_clone",
            payload={
                "mother_plant_key": "SBBS-R1-001",
                "count": 2,
                "source_tent_id": 2,
                "grid_position": None,
                "taken_at": None,
            },
        ),
        _command_payload(
            command_type="breeding_plants_bulk_sex",
            payload={"plant_keys": ["SBBS-R1-001"], "sex_key": "female"},
        ),
        _command_payload(
            command_type="breeding_sex_tests_bulk_create",
            payload={
                "vendor_name": "Farmer Freeman",
                "assay_name": "EZ-XY",
                "sample_collected_at": "2026-07-01T12:00:00Z",
                "sample_sent_at": None,
                "tests": [
                    {
                        "plant_key": "SBBS-R1-001",
                        "vendor_test_code": "FF-001",
                        "notes": None,
                    }
                ],
            },
        ),
        _command_payload(
            command_type="breeding_sex_test_update",
            payload={
                "sex_test_source_id": 10,
                "vendor_name": "Farmer Freeman",
                "assay_name": "EZ-XY",
                "vendor_test_code": "FF-001",
                "sample_collected_at": "2026-07-01T12:00:00Z",
                "sample_sent_at": None,
                "result_received_at": None,
                "result_sex_key": None,
                "is_inconclusive": False,
                "notes": None,
            },
        ),
        _command_payload(
            command_type="breeding_sex_tests_bulk_result",
            payload={
                "result_received_at": "2026-07-05T12:00:00Z",
                "results": [
                    {
                        "sex_test_source_id": 10,
                        "result_sex_key": "female",
                        "is_inconclusive": False,
                    },
                    {
                        "sex_test_source_id": 11,
                        "result_sex_key": None,
                        "is_inconclusive": True,
                    },
                ],
            },
        ),
        _command_payload(
            command_type="breeding_plants_bulk_move",
            payload={
                "plant_keys": ["SBBS-R1-001"],
                "source_tent_id": 1,
                "grid_position": None,
            },
        ),
        _command_payload(
            command_type="breeding_plants_update_facts",
            payload={
                "plant_keys": ["SBBS-R1-001", "SBBS-R1-002"],
                "updates": [
                    {"field": "taken_at", "value": "2026-06-18T16:00:00Z"},
                    {"field": "rooted_at", "value": "2026-06-19T16:00:00Z"},
                    {"field": "veg_started_at", "value": "2026-06-20T16:00:00Z"},
                    {"field": "sex_key", "value": "female"},
                    {"field": "flower_started_at", "value": None},
                    {"field": "harvested_at", "value": None},
                    {
                        "field": "selected_for_breeding_reason",
                        "value": "keeper",
                    },
                ],
            },
        ),
        _command_payload(
            command_type="breeding_plants_bulk_cull",
            payload={
                "plant_keys": ["SBBS-R1-001"],
                "reason": "selected male",
                "culled_at": "2026-06-21T16:00:00Z",
            },
        ),
        _command_payload(
            command_type="breeding_plant_note_create",
            payload={
                "plant_key": "SBBS-R1-001",
                "body": "Stem rub improved.",
                "observed_at": None,
            },
        ),
        _command_payload(
            command_type="breeding_plants_bulk_note",
            payload={
                "plant_keys": ["SBBS-R1-001", "SBBS-R1-002"],
                "body": "Canopy improved.",
                "observed_at": None,
            },
        ),
    ]

    response = CommandClaimResponse(commands=commands)

    assert isinstance(response.commands[0].payload, BreedingCreateSeedLotPayload)
    assert isinstance(
        response.commands[1].payload, BreedingUpdateSeedLotInventoryPayload
    )
    assert isinstance(response.commands[2].payload, BreedingGerminatePlantsPayload)
    assert isinstance(response.commands[3].payload, BreedingClonePlantsPayload)
    assert isinstance(response.commands[4].payload, BreedingBulkSexPayload)
    assert isinstance(response.commands[5].payload, BreedingBulkCreateSexTestsPayload)
    assert isinstance(response.commands[6].payload, BreedingUpdateSexTestPayload)
    assert isinstance(response.commands[7].payload, BreedingBulkResultSexTestsPayload)
    assert isinstance(response.commands[8].payload, BreedingBulkMovePayload)
    assert isinstance(response.commands[9].payload, BreedingBulkPlantFactsPayload)
    assert isinstance(response.commands[10].payload, BreedingBulkCullPayload)
    assert isinstance(response.commands[11].payload, BreedingCreatePlantNotePayload)
    assert isinstance(response.commands[12].payload, BreedingBulkPlantNotePayload)
    assert response.commands[2].payload.grid_position is None


def test_breeding_command_payloads_reject_bad_shapes() -> None:
    with pytest.raises(ValidationError) as mismatch_exc:
        CommandClaimResponse(
            commands=[
                _command_payload(
                    command_type="breeding_plants_bulk_cull",
                    payload={"plant_keys": ["SBBS-R1-001"], "sex_key": "female"},
                )
            ]
        )
    assert mismatch_exc.value.errors()[0]["type"] == "value_error"

    with pytest.raises(ValidationError) as update_mismatch_exc:
        CommandClaimResponse(
            commands=[
                _command_payload(
                    command_type="breeding_seed_lot_update",
                    payload={"plant_keys": ["SBBS-R1-001"], "sex_key": "female"},
                )
            ]
        )
    assert update_mismatch_exc.value.errors()[0]["type"] == "value_error"

    with pytest.raises(ValidationError) as extra_exc:
        BreedingBulkMovePayload.model_validate(
            {
                "plant_keys": ["SBBS-R1-001"],
                "source_tent_id": 1,
                "grid_position": None,
                "plant_names": ["Plant A"],
            }
        )
    assert extra_exc.value.errors()[0]["type"] == "extra_forbidden"

    with pytest.raises(ValidationError):
        BreedingBulkCullPayload(plant_keys=[], reason="culled", culled_at=None)
    with pytest.raises(ValidationError):
        BreedingBulkCullPayload(
            plant_keys=["SBBS-R1-001"], reason="   ", culled_at=None
        )
    with pytest.raises(ValidationError):
        BreedingCreatePlantNotePayload(plant_key="SBBS-R1-001", body="   ")
    with pytest.raises(ValidationError):
        BreedingBulkPlantNotePayload(plant_keys=[], body="Looks better.")
    with pytest.raises(ValidationError):
        BreedingBulkPlantNotePayload(
            plant_keys=["SBBS-R1-001", "SBBS-R1-001"], body="Looks better."
        )
    with pytest.raises(ValidationError):
        BreedingBulkPlantNotePayload(plant_keys=["SBBS-R1-001"], body="   ")
    with pytest.raises(ValidationError):
        BreedingBulkPlantFactsPayload(plant_keys=[], updates=[])
    with pytest.raises(ValidationError):
        BreedingBulkPlantFactsPayload(
            plant_keys=["SBBS-R1-001"],
            updates=[{"field": "sex_key", "value": None}],
        )
    with pytest.raises(ValidationError):
        BreedingBulkPlantFactsPayload(
            plant_keys=["SBBS-R1-001"],
            updates=[{"field": "veg_started_at", "value": "female"}],
        )
    with pytest.raises(ValidationError):
        BreedingBulkPlantFactsPayload(
            plant_keys=["SBBS-R1-001"],
            updates=[
                {"field": "veg_started_at", "value": None},
                {"field": "veg_started_at", "value": "2026-06-20T16:00:00Z"},
            ],
        )


def test_breeding_sex_test_payloads_require_nullable_fields() -> None:
    create_payload = {
        "vendor_name": "Farmer Freeman",
        "assay_name": None,
        "sample_collected_at": "2026-07-01T12:00:00Z",
        "sample_sent_at": None,
        "tests": [
            {
                "plant_key": "SBBS-R1-001",
                "vendor_test_code": "FF-001",
                "notes": None,
            }
        ],
    }
    update_payload = {
        "sex_test_source_id": 10,
        "vendor_name": "Farmer Freeman",
        "assay_name": None,
        "vendor_test_code": "FF-001",
        "sample_collected_at": "2026-07-01T12:00:00Z",
        "sample_sent_at": None,
        "result_received_at": None,
        "result_sex_key": None,
        "is_inconclusive": False,
        "notes": None,
    }
    result_payload = {
        "result_received_at": "2026-07-05T12:00:00Z",
        "results": [
            {
                "sex_test_source_id": 10,
                "result_sex_key": "female",
                "is_inconclusive": False,
            }
        ],
    }

    assert BreedingBulkCreateSexTestsPayload.model_validate(create_payload)
    assert BreedingUpdateSexTestPayload.model_validate(update_payload)
    assert BreedingBulkResultSexTestsPayload.model_validate(result_payload)

    for field_name in ("assay_name", "sample_sent_at"):
        invalid = dict(create_payload)
        del invalid[field_name]
        with pytest.raises(ValidationError) as exc_info:
            BreedingBulkCreateSexTestsPayload.model_validate(invalid)
        assert exc_info.value.errors()[0]["loc"] == (field_name,)
        assert exc_info.value.errors()[0]["type"] == "missing"

    for field_name in (
        "assay_name",
        "sample_sent_at",
        "result_received_at",
        "result_sex_key",
        "notes",
    ):
        invalid = dict(update_payload)
        del invalid[field_name]
        with pytest.raises(ValidationError) as exc_info:
            BreedingUpdateSexTestPayload.model_validate(invalid)
        assert exc_info.value.errors()[0]["loc"] == (field_name,)
        assert exc_info.value.errors()[0]["type"] == "missing"

    invalid_result = dict(result_payload)
    del invalid_result["result_received_at"]
    with pytest.raises(ValidationError) as exc_info:
        BreedingBulkResultSexTestsPayload.model_validate(invalid_result)
    assert exc_info.value.errors()[0]["loc"] == ("result_received_at",)
    assert exc_info.value.errors()[0]["type"] == "missing"

    invalid_row = {
        **result_payload,
        "results": [{"sex_test_source_id": 10, "is_inconclusive": False}],
    }
    with pytest.raises(ValidationError) as row_exc:
        BreedingBulkResultSexTestsPayload.model_validate(invalid_row)
    assert row_exc.value.errors()[0]["loc"] == ("results", 0, "result_sex_key")
    assert row_exc.value.errors()[0]["type"] == "missing"


def test_breeding_sex_test_payloads_reject_bad_text_and_duplicates() -> None:
    payload = {
        "vendor_name": " Farmer Freeman ",
        "assay_name": " EZ-XY ",
        "sample_collected_at": "2026-07-01T12:00:00Z",
        "sample_sent_at": None,
        "tests": [
            {
                "plant_key": " SBBS-R1-001 ",
                "vendor_test_code": " FF-001 ",
                "notes": " sample ok ",
            }
        ],
    }

    parsed = BreedingBulkCreateSexTestsPayload.model_validate(payload)

    assert parsed.vendor_name == "Farmer Freeman"
    assert parsed.assay_name == "EZ-XY"
    assert parsed.tests[0].plant_key == "SBBS-R1-001"
    assert parsed.tests[0].vendor_test_code == "FF-001"
    assert parsed.tests[0].notes == "sample ok"

    for invalid in (
        {**payload, "vendor_name": "   "},
        {**payload, "assay_name": "   "},
        {
            **payload,
            "tests": [
                {
                    "plant_key": "   ",
                    "vendor_test_code": "FF-001",
                    "notes": None,
                }
            ],
        },
        {
            **payload,
            "tests": [
                {
                    "plant_key": "SBBS-R1-001",
                    "vendor_test_code": "   ",
                    "notes": None,
                }
            ],
        },
        {
            **payload,
            "tests": [
                {
                    "plant_key": "SBBS-R1-001",
                    "vendor_test_code": "FF-001",
                    "notes": "   ",
                }
            ],
        },
        {
            **payload,
            "tests": [
                {"plant_key": "SBBS-R1-001", "vendor_test_code": "FF-001"},
                {"plant_key": "SBBS-R1-002", "vendor_test_code": "FF-001"},
            ],
        },
    ):
        with pytest.raises(ValidationError):
            BreedingBulkCreateSexTestsPayload.model_validate(invalid)


def test_breeding_sex_test_result_payloads_reject_bad_result_shapes() -> None:
    for row in (
        {"sex_test_source_id": 10, "result_sex_key": None, "is_inconclusive": False},
        {
            "sex_test_source_id": 10,
            "result_sex_key": "female",
            "is_inconclusive": True,
        },
    ):
        with pytest.raises(ValidationError):
            BreedingBulkResultSexTestsPayload.model_validate(
                {
                    "result_received_at": "2026-07-05T12:00:00Z",
                    "results": [row],
                }
            )

    with pytest.raises(ValidationError):
        BreedingBulkResultSexTestsPayload.model_validate(
            {
                "result_received_at": "2026-07-05T12:00:00Z",
                "results": [
                    {
                        "sex_test_source_id": 10,
                        "result_sex_key": "female",
                        "is_inconclusive": False,
                    },
                    {
                        "sex_test_source_id": 10,
                        "result_sex_key": None,
                        "is_inconclusive": True,
                    },
                ],
            }
        )

    with pytest.raises(ValidationError):
        BreedingUpdateSexTestPayload.model_validate(
            {
                "sex_test_source_id": 10,
                "vendor_name": "Farmer Freeman",
                "assay_name": "EZ-XY",
                "vendor_test_code": "FF-001",
                "sample_collected_at": "2026-07-01T12:00:00Z",
                "sample_sent_at": None,
                "result_received_at": None,
                "result_sex_key": "female",
                "is_inconclusive": False,
                "notes": None,
            }
        )


def test_breeding_sex_test_result_payloads_reject_non_lab_sex_keys() -> None:
    for sex_key in ("unknown", "herm", "reversed"):
        with pytest.raises(ValidationError):
            BreedingBulkResultSexTestsPayload.model_validate(
                {
                    "result_received_at": "2026-07-05T12:00:00Z",
                    "results": [
                        {
                            "sex_test_source_id": 10,
                            "result_sex_key": sex_key,
                            "is_inconclusive": False,
                        }
                    ],
                }
            )
        with pytest.raises(ValidationError):
            BreedingUpdateSexTestPayload.model_validate(
                {
                    "sex_test_source_id": 10,
                    "vendor_name": "Farmer Freeman",
                    "assay_name": "EZ-XY",
                    "vendor_test_code": "FF-001",
                    "sample_collected_at": "2026-07-01T12:00:00Z",
                    "sample_sent_at": None,
                    "result_received_at": "2026-07-05T12:00:00Z",
                    "result_sex_key": sex_key,
                    "is_inconclusive": False,
                    "notes": None,
                }
            )


def test_breeding_seed_lot_update_payload_requires_complete_inventory_state() -> None:
    payload = {
        "seed_lot_source_id": 1,
        "sex_type_key": "regular",
        "seed_count": 8,
        "notes": None,
        "vendor_name": " Archive ",
        "acquired_at": None,
    }

    update = BreedingUpdateSeedLotInventoryPayload.model_validate(payload)

    assert update.vendor_name == "Archive"
    assert update.notes is None

    for field_name in ("seed_count", "notes", "vendor_name", "acquired_at"):
        invalid = dict(payload)
        del invalid[field_name]
        with pytest.raises(ValidationError) as exc_info:
            BreedingUpdateSeedLotInventoryPayload.model_validate(invalid)
        assert exc_info.value.errors()[0]["loc"] == (field_name,)
        assert exc_info.value.errors()[0]["type"] == "missing"

    with pytest.raises(ValidationError):
        BreedingUpdateSeedLotInventoryPayload.model_validate(
            {**payload, "seed_count": -1}
        )
    with pytest.raises(ValidationError):
        BreedingUpdateSeedLotInventoryPayload.model_validate(
            {**payload, "vendor_name": "   "}
        )
    with pytest.raises(ValidationError) as extra_exc:
        BreedingUpdateSeedLotInventoryPayload.model_validate(
            {**payload, "line_source_id": 1}
        )
    assert extra_exc.value.errors()[0]["type"] == "extra_forbidden"


def test_breeding_grid_position_payloads_require_explicit_null() -> None:
    payloads = [
        (
            BreedingGerminatePlantsPayload,
            {
                "seed_lot_source_id": 1,
                "count": 2,
                "source_tent_id": 2,
                "grid_position": None,
            },
        ),
        (
            BreedingClonePlantsPayload,
            {
                "mother_plant_key": "SBBS-R1-001",
                "count": 2,
                "source_tent_id": 2,
                "grid_position": None,
            },
        ),
        (
            BreedingBulkMovePayload,
            {
                "plant_keys": ["SBBS-R1-001"],
                "source_tent_id": 1,
                "grid_position": None,
            },
        ),
    ]

    for model, payload in payloads:
        assert model.model_validate(payload).grid_position is None

        missing = dict(payload)
        del missing["grid_position"]
        with pytest.raises(ValidationError) as missing_exc:
            model.model_validate(missing)
        assert missing_exc.value.errors()[0]["loc"] == ("grid_position",)
        assert missing_exc.value.errors()[0]["type"] == "missing"

        with pytest.raises(ValidationError) as non_null_exc:
            model.model_validate({**payload, "grid_position": "A1"})
        assert non_null_exc.value.errors()[0]["loc"] == ("grid_position",)


def test_breeding_seed_lot_payload_validates_source_specific_fields() -> None:
    cross = BreedingCreateSeedLotPayload(
        source="cross",
        generation="F1",
        prefix="SBX",
        seed_parent_plant_key="SBBS-R1-001",
        pollen_parent_plant_key="SBBS-R1-002",
        sex_type_key="regular",
    )

    assert cross.source == "cross"
    assert cross.seed_parent_plant_key == "SBBS-R1-001"

    with pytest.raises(ValidationError):
        BreedingCreateSeedLotPayload(
            source="purchased",
            generation="R1",
            prefix="SBBS",
            sex_type_key="feminized",
        )
    with pytest.raises(ValidationError):
        BreedingCreateSeedLotPayload(
            source="cross",
            generation="F1",
            prefix="SBX",
            seed_parent_plant_key="SBBS-R1-001",
            pollen_parent_plant_key="SBBS-R1-001",
            sex_type_key="regular",
        )


def _command_payload(
    *, command_type: str, payload: dict[str, object]
) -> dict[str, object]:
    target = None
    if command_type.startswith("ptz_"):
        target = {
            "kind": "ptz",
            "source_tent_id": 1,
            "device_id": "obsbot-main",
            "capability_id": "ptz_move",
        }
    return {
        "command_id": f"cmd_{command_type}",
        "site_id": "homebox",
        "target": target,
        "command_type": command_type,
        "payload": payload,
        "status": "claimed",
        "queued_at": "2026-05-09T12:00:00Z",
        "expires_at": "2026-05-09T12:05:00Z",
        "claimed_by": None,
        "claimed_at": None,
        "requested_by": "browser",
        "started_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
    }
