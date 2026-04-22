"""Unit tests for GET /api/system/devices.

Thin FastAPI wrapper over :class:`SystemStatusService.get_device_statuses`.
The real service probes heterogenous sources (DB rows, a unix socket for
the camera daemon, ``systemctl --user is-active`` for the Jabra mock) —
those are integration concerns owned by ``SystemStatusService``'s own
tests. Here we pin the endpoint behaviour by overriding
``get_system_status`` with a fake that returns a known 8-row fixture,
and assert:

- unauth → 401
- happy path → 200, contract-shaped payload, 8 rows with statuses drawn
  from the ``DeviceStatusKind`` enum.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from dirt_contracts.webapp_v1.models import DevicesResponse, DeviceStatusKind
from httpx import ASGITransport, AsyncClient

from dirt_shared.services.system_status import DeviceStatus
from dirt_web.app import create_app
from dirt_web.deps import get_system_status


class _FakeSystemStatusService:
    """Return a deterministic 8-row fixture shaped like the mockup.

    Mirrors the render order in ``SystemStatusService.get_device_statuses``:
    tent Arduino, four plant nodes, humidifier, camera, Jabra.
    """

    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now

    async def get_device_statuses(self) -> list[DeviceStatus]:
        return [
            DeviceStatus(
                name="Arduino Nano + BME280",
                kind="env_sensor",
                status="ok",
                last_seen=self._now,
            ),
            DeviceStatus(
                name="ESP32-C3 · plant_a",
                kind="moisture_node",
                status="ok",
                last_seen=self._now,
            ),
            DeviceStatus(
                name="ESP32-C3 · plant_b",
                kind="moisture_node",
                status="warn",
                last_seen=self._now,
            ),
            DeviceStatus(
                name="ESP32-C3 · plant_c",
                kind="moisture_node",
                status="offline",
                last_seen=None,
            ),
            DeviceStatus(
                name="ESP32-C3 · plant_d",
                kind="moisture_node",
                status="ok",
                last_seen=self._now,
            ),
            DeviceStatus(
                name="Humidifier (Kasa EP10)",
                kind="actuator",
                status="warn",
                last_seen=self._now,
                note="not deployed",
            ),
            DeviceStatus(
                name="OBSBOT Tiny 2 Lite",
                kind="camera",
                status="ok",
                last_seen=self._now,
            ),
            DeviceStatus(
                name="Jabra Speak 410 (Claudia)",
                kind="voice",
                status="listening",
                last_seen=self._now,
            ),
        ]


@pytest.fixture
async def client(app_engine):
    app = create_app(engine=app_engine, run_mcp=False)
    fake = _FakeSystemStatusService(datetime.now(UTC))
    app.dependency_overrides[get_system_status] = lambda: fake
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        login = await ac.post(
            "/api/auth/login",
            json={"username": "admin", "password": "changeme"},
        )
        ac.cookies = login.cookies
        yield ac


async def test_system_devices_requires_auth(app_engine):
    """No session cookie → 401 before the handler runs."""
    app = create_app(engine=app_engine, run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.get("/api/system/devices")
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/json")


async def test_system_devices_returns_eight_rows(client: AsyncClient):
    """Happy path: 8 rows, each status is a valid DeviceStatusKind."""
    response = await client.get("/api/system/devices")
    assert response.status_code == 200

    model = DevicesResponse.model_validate(response.json())
    assert len(model.devices) == 8

    # Every row's ``status`` is one of the taxonomy values. Pydantic's
    # enum coercion would have rejected anything else in model_validate
    # above, but pin the expectation explicitly so a regression that
    # widens the taxonomy surfaces here, not at the SPA.
    allowed = set(DeviceStatusKind)
    for device in model.devices:
        assert device.status in allowed

    # The ``ts`` envelope must be timezone-aware (contract is
    # ``AwareDatetime``). model_validate would reject naive strings, so
    # asserting tzinfo here is belt-and-suspenders against a future
    # refactor that swaps ``datetime.now(UTC)`` for a naive clock.
    assert model.ts.tzinfo is not None

    # Mockup order: env sensor first, Jabra last. Pin the endpoints to
    # that order so the FE can rely on positional rendering without
    # re-sorting. Status values per row exercise every taxonomy member.
    kinds = [d.kind.value for d in model.devices]
    assert kinds == [
        "env_sensor",
        "moisture_node",
        "moisture_node",
        "moisture_node",
        "moisture_node",
        "actuator",
        "camera",
        "voice",
    ]
    statuses = [d.status.value for d in model.devices]
    assert "listening" in statuses
    assert "offline" in statuses
    assert "warn" in statuses
    assert "ok" in statuses
