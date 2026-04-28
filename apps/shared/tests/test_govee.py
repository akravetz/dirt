"""Tests for the Govee Public API v2 client.

httpx.MockTransport — no real network. The discovery fixture is a real
capture from the deployed H7142 (2026-04-27); the state / control fixtures
are hand-authored mirrors of the verified live shapes.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from dirt_shared.services.govee import (
    BASE_URL,
    GoveeClient,
    GoveeError,
    GoveeRateLimitError,
    StateSnapshot,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _client(handler) -> GoveeClient:
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport)
    return GoveeClient(api_key="TEST_KEY", http=http)


def _discovery_body() -> dict:
    return json.loads((FIXTURES / "govee_h7142_discovery.json").read_text())


# ============================================================
# discover
# ============================================================


async def test_discover_uses_get_with_auth_header():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Govee-API-Key")
        seen["body"] = request.read()
        return httpx.Response(200, json=_discovery_body())

    client = _client(handler)
    devices = await client.discover()

    assert seen["method"] == "GET"
    assert seen["url"] == f"{BASE_URL}/user/devices"
    assert seen["auth"] == "TEST_KEY"
    assert seen["body"] == b""
    assert len(devices) == 1
    assert devices[0].sku == "H7142"
    assert devices[0].device == "14:38:60:74:F4:DD:B9:46"
    assert devices[0].name == "dirt-humidifier"
    assert devices[0].type == "devices.types.humidifier"
    # Four capabilities exactly: powerSwitch, workMode, humidity, lackWaterEvent.
    instances = [c["instance"] for c in devices[0].raw_capabilities]
    assert instances == ["powerSwitch", "workMode", "humidity", "lackWaterEvent"]


async def test_discover_accepts_data_as_dict_with_devices_key():
    """Older readme.io renders showed `data: {devices: [...]}`. Tolerate both."""

    def handler(_request):
        return httpx.Response(
            200,
            json={
                "code": 200,
                "message": "ok",
                "data": {
                    "devices": [
                        {
                            "sku": "H7142",
                            "device": "AA:BB",
                            "deviceName": "x",
                            "type": "devices.types.humidifier",
                            "capabilities": [],
                        }
                    ]
                },
            },
        )

    devices = await _client(handler).discover()
    assert len(devices) == 1
    assert devices[0].sku == "H7142"


# ============================================================
# get_state — parsing
# ============================================================


async def test_get_state_parses_full_capability_response():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        body = json.loads(request.read())
        assert body["payload"] == {"sku": "H7142", "device": "AA:BB"}
        assert "requestId" in body
        return httpx.Response(
            200,
            json={
                "code": 200,
                "msg": "success",
                "payload": {
                    "sku": "H7142",
                    "device": "AA:BB",
                    "capabilities": [
                        {
                            "type": "devices.capabilities.online",
                            "instance": "online",
                            "state": {"value": True},
                        },
                        {
                            "type": "devices.capabilities.on_off",
                            "instance": "powerSwitch",
                            "state": {"value": 1},
                        },
                        {
                            "type": "devices.capabilities.work_mode",
                            "instance": "workMode",
                            "state": {"value": {"workMode": 1, "modeValue": 5}},
                        },
                    ],
                },
            },
        )

    snap = await _client(handler).get_state("H7142", "AA:BB")
    assert snap == StateSnapshot(
        online=True, power_on=True, work_mode=1, mode_value=5, lack_water=False
    )


async def test_get_state_lack_water_event_present():
    def handler(_request):
        return httpx.Response(
            200,
            json={
                "code": 200,
                "msg": "ok",
                "payload": {
                    "capabilities": [
                        {"instance": "online", "state": {"value": True}},
                        {"instance": "powerSwitch", "state": {"value": 1}},
                        {
                            "instance": "workMode",
                            "state": {"value": {"workMode": 1, "modeValue": 3}},
                        },
                        {
                            "instance": "lackWaterEvent",
                            "state": {"value": {"name": "lack"}},
                        },
                    ],
                },
            },
        )

    snap = await _client(handler).get_state("H7142", "AA:BB")
    assert snap.lack_water is True


async def test_get_state_offline_with_missing_caps():
    def handler(_request):
        return httpx.Response(
            200,
            json={
                "code": 200,
                "msg": "ok",
                "payload": {
                    "capabilities": [
                        {"instance": "online", "state": {"value": False}},
                    ]
                },
            },
        )

    snap = await _client(handler).get_state("H7142", "AA:BB")
    assert snap == StateSnapshot(
        online=False, power_on=None, work_mode=None, mode_value=None, lack_water=False
    )


async def test_get_state_accepts_data_envelope():
    """Tolerate `data: {...}` instead of `payload: {...}`."""

    def handler(_request):
        return httpx.Response(
            200,
            json={
                "code": 200,
                "msg": "ok",
                "data": {
                    "capabilities": [
                        {"instance": "online", "state": {"value": True}},
                        {"instance": "powerSwitch", "state": {"value": 0}},
                    ]
                },
            },
        )

    snap = await _client(handler).get_state("H7142", "AA:BB")
    assert snap.online is True
    assert snap.power_on is False


# ============================================================
# set_power / set_manual_level — wire format
# ============================================================


async def test_set_power_on_sends_correct_capability():
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.read())
        return httpx.Response(200, json={"code": 200, "msg": "success"})

    await _client(handler).set_power("H7142", "AA:BB", on=True)

    assert seen["url"] == f"{BASE_URL}/device/control"
    payload = seen["body"]["payload"]
    assert payload["sku"] == "H7142"
    assert payload["device"] == "AA:BB"
    assert payload["capability"] == {
        "type": "devices.capabilities.on_off",
        "instance": "powerSwitch",
        "value": 1,
    }
    assert "requestId" in seen["body"]


async def test_set_power_off_sends_zero():
    seen: dict = {}

    def handler(request):
        seen["body"] = json.loads(request.read())
        return httpx.Response(200, json={"code": 200, "msg": "ok"})

    await _client(handler).set_power("H7142", "AA:BB", on=False)
    assert seen["body"]["payload"]["capability"]["value"] == 0


async def test_set_manual_level_sends_struct():
    seen: dict = {}

    def handler(request):
        seen["body"] = json.loads(request.read())
        return httpx.Response(200, json={"code": 200, "msg": "ok"})

    await _client(handler).set_manual_level("H7142", "AA:BB", 7)
    cap = seen["body"]["payload"]["capability"]
    assert cap["type"] == "devices.capabilities.work_mode"
    assert cap["instance"] == "workMode"
    assert cap["value"] == {"workMode": 1, "modeValue": 7}


# ============================================================
# error mapping
# ============================================================


async def test_app_level_error_code_raises_govee_error():
    def handler(_request):
        return httpx.Response(200, json={"code": 400, "msg": "bad payload"})

    with pytest.raises(GoveeError) as exc:
        await _client(handler).get_state("H7142", "AA:BB")
    assert exc.value.code == 400
    assert "bad payload" in exc.value.message


async def test_rate_limit_app_code_raises_subclass():
    def handler(_request):
        return httpx.Response(200, json={"code": 429, "msg": "Too Many Requests"})

    with pytest.raises(GoveeRateLimitError):
        await _client(handler).set_power("H7142", "AA:BB", on=True)


async def test_rate_limit_http_status_raises_subclass():
    def handler(_request):
        return httpx.Response(429, json={"code": 429, "msg": "throttled"})

    with pytest.raises(GoveeRateLimitError):
        await _client(handler).set_power("H7142", "AA:BB", on=True)


async def test_transport_error_wrapped_as_govee_error():
    def handler(_request):
        raise httpx.ConnectError("nope")

    with pytest.raises(GoveeError, match="transport error"):
        await _client(handler).discover()


async def test_empty_api_key_rejected_at_construction():
    with pytest.raises(ValueError, match="api key"):
        GoveeClient(api_key="", http=httpx.AsyncClient())
