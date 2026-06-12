from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from dirt_shared.cloud_contract import (
    AssetRetentionRequest,
    CatalogDevice,
    CatalogPlant,
    CatalogPlantMetricStream,
    CommandClaimResponse,
    LatestMetricItem,
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
        tent_id="breeding",
        device_id="breeding-env-node",
        name="Breeding environment",
        last_seen_at=last_seen,
    )

    assert device.last_seen_at == last_seen


def test_catalog_device_accepts_intentional_null_last_seen() -> None:
    device = CatalogDevice(
        tent_id="breeding",
        device_id="breeding-env-node",
        name="Breeding environment",
        last_seen_at=None,
    )

    assert device.last_seen_at is None


def test_catalog_device_rejects_missing_last_seen() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CatalogDevice(
            tent_id="breeding",
            device_id="breeding-env-node",
            name="Breeding environment",
        )

    assert exc_info.value.errors()[0]["loc"] == ("last_seen_at",)
    assert exc_info.value.errors()[0]["type"] == "missing"


def test_gateway_contract_models_forbid_extra_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        CatalogDevice(
            tent_id="breeding",
            device_id="breeding-env-node",
            name="Breeding environment",
            last_seen_at=None,
            stale_field=True,
        )

    assert exc_info.value.errors()[0]["loc"] == ("stale_field",)
    assert exc_info.value.errors()[0]["type"] == "extra_forbidden"


def test_catalog_plant_requires_nullable_wire_fields() -> None:
    plant_payload = {
        "tent_id": "main",
        "grow_run_id": "main-2026-03-15",
        "plant_id": "a",
        "name": "Plant A",
        "display_order": 1,
        "sticker_color": None,
        "status": "primary",
        "purple": True,
        "moisture_target_low": 55.0,
        "moisture_target_high": 70.0,
        "wiki_path": None,
        "is_active": True,
    }

    plant = CatalogPlant.model_validate(plant_payload)
    assert plant.wiki_path is None

    for field_name in ("sticker_color", "wiki_path"):
        invalid = dict(plant_payload)
        del invalid[field_name]
        with pytest.raises(ValidationError) as exc_info:
            CatalogPlant.model_validate(invalid)
        assert exc_info.value.errors()[0]["loc"] == (field_name,)
        assert exc_info.value.errors()[0]["type"] == "missing"


def test_catalog_plant_metric_stream_requires_public_stream_identity() -> None:
    stream_payload = {
        "tent_id": "main",
        "grow_run_id": "main-2026-03-15",
        "plant_id": "a",
        "device_id": "plant-a-substrate-node",
        "capability_id": "substrate_ph",
        "metric": "substrate_ph",
        "display_order": 4,
        "is_active": True,
    }

    stream = CatalogPlantMetricStream.model_validate(stream_payload)
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
        "tent_id": "main",
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
        object_key="homebox/main/snapshots/latest.jpg",
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


def test_command_claim_response_requires_nullable_wire_keys() -> None:
    command = {
        "command_id": "cmd_1",
        "site_id": "homebox",
        "tent_id": "main",
        "device_id": None,
        "capability_id": None,
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


def _command_payload(
    *, command_type: str, payload: dict[str, object]
) -> dict[str, object]:
    return {
        "command_id": f"cmd_{command_type}",
        "site_id": "homebox",
        "tent_id": "main",
        "device_id": "obsbot-main",
        "capability_id": "ptz_move",
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
