from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from dirt_shared.cloud_contract import (
    AssetRetentionRequest,
    CatalogDevice,
    CommandClaimResponse,
    PtzLookPayload,
    PtzPresetPayload,
    PtzZoomRelativePayload,
    SignUploadResponse,
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
