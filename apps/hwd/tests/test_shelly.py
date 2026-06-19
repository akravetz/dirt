from __future__ import annotations

import json

import httpx
import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_hwd.services.shelly import (
    ShellyIdentityMismatch,
    ShellyPlugClient,
    ShellyPlugTarget,
    load_shelly_plug_target,
)
from dirt_shared.testing import create_test_capability, create_test_device

TEST_MAC = "AA:BB:CC:DD:EE:01"


def _target() -> ShellyPlugTarget:
    return ShellyPlugTarget(
        source_site_id=1,
        source_tent_id=1,
        source_zone_id=None,
        device_pk=1,
        device_id="test-shelly-pump",
        capability_pk=2,
        capability_id="pump_power",
        hostname="pump.local",
        ip="192.0.2.10",
        provider_uid_kind="mac",
        provider_uid=TEST_MAC,
    )


async def test_shelly_client_tries_hostname_before_ip_and_falls_back() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.host == "pump.local":
            raise httpx.ConnectError("mdns lookup failed", request=request)
        if request.url.path.endswith("/Shelly.GetDeviceInfo"):
            return httpx.Response(200, request=request, json={"mac": TEST_MAC})
        return httpx.Response(200, request=request, json={"was_on": False})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ShellyPlugClient(http=http)

        endpoint = await client.timed_pulse(_target(), duration_s=5)

    assert endpoint == "192.0.2.10"
    assert [(request.url.host, request.url.path) for request in requests] == [
        ("pump.local", "/rpc/Shelly.GetDeviceInfo"),
        ("192.0.2.10", "/rpc/Shelly.GetDeviceInfo"),
        ("192.0.2.10", "/rpc/Switch.Set"),
    ]


async def test_shelly_client_refuses_identity_mismatch_before_control() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, request=request, json={"mac": "AA:BB:CC:DD:EE:99"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ShellyPlugClient(http=http)

        with pytest.raises(ShellyIdentityMismatch):
            await client.timed_pulse(_target(), duration_s=5)

    assert [(request.url.host, request.url.path) for request in requests] == [
        ("pump.local", "/rpc/Shelly.GetDeviceInfo")
    ]


async def test_shelly_timed_pulse_payload_uses_toggle_after() -> None:
    switch_payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/Shelly.GetDeviceInfo"):
            return httpx.Response(200, request=request, json={"mac": TEST_MAC})
        switch_payloads.append(json.loads(request.content.decode()))
        return httpx.Response(200, request=request, json={"was_on": False})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        client = ShellyPlugClient(http=http)

        await client.timed_pulse(_target(), duration_s=7)

    assert switch_payloads == [{"id": 0, "on": True, "toggle_after": 7}]


async def test_load_shelly_plug_target_reads_db_identity_and_reachability(
    app_engine,
) -> None:
    async with AsyncSession(app_engine) as session:
        device = await create_test_device(
            session,
            device_id="test-shelly-loader",
            tent_id="main",
            kind="actuator",
            controller="shelly",
        )
        device.hostname = "loader.local"
        device.ip = "192.0.2.44"
        device.provider_uid_kind = "mac"
        device.provider_uid = "AA:BB:CC:DD:EE:44"
        capability = await create_test_capability(
            session,
            device=device,
            capability_id="pump_power",
            kind="actuator",
            metric_name="pump_on",
            unit="bool",
            source="shelly",
        )
        capability.metadata_json = {"switch_id": 1}
        device_pk = device.id
        capability_pk = capability.id
        if device_pk is None or capability_pk is None:
            raise AssertionError("test fixture did not assign target primary keys")
        await session.commit()

        target = await load_shelly_plug_target(
            session,
            device_pk=device_pk,
            capability_pk=capability_pk,
        )

    assert target is not None
    assert target.device_id == "test-shelly-loader"
    assert target.capability_id == "pump_power"
    assert target.hostname == "loader.local"
    assert target.ip == "192.0.2.44"
    assert target.provider_uid_kind == "mac"
    assert target.provider_uid == "AA:BB:CC:DD:EE:44"
    assert target.switch_id == 1
