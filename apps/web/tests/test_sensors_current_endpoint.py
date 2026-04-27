"""Unit tests for GET /api/sensors/current.

The endpoint composes ``ReadingsService.get_latest_reading``,
``grow_state.STAGE_TARGETS``, and ``grow_state.band_status``. The
reservoir is now real: ``reservoir_in`` is read from the ``reservoir``
sensornode (firmware does the cm → in conversion at publish time, so
the persisted unit matches the contract). Tests drive the full ASGI
stack with an isolated Postgres DB and assert the JSON body
deserializes into the generated Pydantic ``SensorsCurrent`` model.
"""

from __future__ import annotations

import inspect
from datetime import UTC, datetime, timedelta

import pytest
from dirt_contracts.webapp_v1.models import SensorsCurrent
from httpx import ASGITransport, AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.enums import SensorLocation, SensorSource
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.readings import ReadingsService
from dirt_web.app import create_app


async def _node_id(engine, location: SensorLocation) -> int:
    """Find-or-create the SensorNode for ``location`` and return its id."""
    async with AsyncSession(engine) as s:
        result = await s.exec(
            select(SensorNode.id).where(SensorNode.location == location)
        )
        node_id = result.first()
        if node_id is None:
            node = SensorNode(location=location)
            s.add(node)
            await s.commit()
            await s.refresh(node)
            node_id = node.id
        return node_id


async def _seed_readings(
    engine,
    *,
    temperature_f: float = 72.0,
    humidity_pct: float = 50.0,
    vpd_kpa: float = 1.0,
    reservoir_in: float = 23.62,
    stale: bool = False,
) -> None:
    """Seed a single batch of fresh readings at "now" for the five metrics.

    When ``stale=True`` we also backfill ``threshold`` identical
    temperature_f readings so ``is_sensor_stale()`` flips to True. The
    threshold is read from ``ReadingsService.is_sensor_stale``'s own
    default (the implementation's source of truth) rather than hardcoded
    here — if the default changes, this test still exercises the true
    boundary.
    """
    tent_id = await _node_id(engine, SensorLocation.TENT)
    reservoir_id = await _node_id(engine, SensorLocation.RESERVOIR)
    now = datetime.now(UTC)
    rows: list[SensorReading] = []

    def add(metric: str, value: float, ts: datetime, node_id: int = tent_id) -> None:
        rows.append(
            SensorReading(
                ts=ts,
                sensornode_id=node_id,
                metric=metric,
                value=value,
                source=SensorSource.ARDUINO,
            )
        )

    # One fresh reading per metric. Tent metrics ride on the tent node;
    # reservoir_in rides on the reservoir node (different sensornode_id —
    # must be present for the API's get_latest_reading lookup to find it).
    for metric, value in {
        "temperature_f": temperature_f,
        "humidity_pct": humidity_pct,
        "vpd_kpa": vpd_kpa,
        "dew_point_f": 55.0,
        "fan_duty_pct": 30.0,
    }.items():
        add(metric, value, now)
    add("reservoir_in", reservoir_in, now, node_id=reservoir_id)

    if stale:
        threshold = (
            inspect.signature(ReadingsService.is_sensor_stale)
            .parameters["threshold"]
            .default
        )
        # Backfill identical temperature_f readings so the last N are
        # all the same value — the staleness signal the service defines.
        for i in range(1, threshold + 2):
            add("temperature_f", temperature_f, now - timedelta(minutes=i))

    async with AsyncSession(engine) as s:
        s.add_all(rows)
        await s.commit()


@pytest.fixture
async def client(app_engine):
    app = create_app(engine=app_engine, run_mcp=False)
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


async def test_sensors_current_requires_auth(app_engine):
    app = create_app(engine=app_engine, run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.get("/api/sensors/current")
        # AuthMiddleware returns 401 JSON for unauthenticated /api/* —
        # the SPA handles /login routing client-side.
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/json")


async def test_sensors_current_returns_contract_shape(client: AsyncClient, app_engine):
    await _seed_readings(app_engine, temperature_f=72.0, humidity_pct=50.0, vpd_kpa=1.0)
    response = await client.get("/api/sensors/current")
    assert response.status_code == 200
    model = SensorsCurrent.model_validate(response.json())

    # All five metrics populated.
    assert model.metrics.temperature_f.value == pytest.approx(72.0)
    assert model.metrics.humidity_pct.value == pytest.approx(50.0)
    assert model.metrics.vpd_kpa.value == pytest.approx(1.0)
    assert model.metrics.fan_pct.value == pytest.approx(30.0)
    # Reservoir: firmware emits inches natively, server stores as-is.
    assert model.metrics.reservoir_in.value == pytest.approx(23.62)

    # Target bands present for every metric defined in STAGE_TARGETS;
    # absent for fan_pct and reservoir_in (no per-stage band declared).
    assert model.metrics.temperature_f.target is not None
    assert model.metrics.humidity_pct.target is not None
    assert model.metrics.vpd_kpa.target is not None
    assert model.metrics.fan_pct.target is not None
    assert model.metrics.reservoir_in.target is None

    # Veg-stage bands: temp 70-82, humidity 45-55, VPD 0.8-1.2, fan 20-80.
    # Seeded values sit inside each band → status "ok".
    assert model.metrics.temperature_f.status.value == "ok"
    assert model.metrics.humidity_pct.status.value == "ok"
    assert model.metrics.vpd_kpa.status.value == "ok"
    assert model.metrics.fan_pct.status.value == "ok"

    # Fresh seed → not stale.
    assert model.stale is False


async def test_sensors_current_stale_flag(client: AsyncClient, app_engine):
    # Seed a run of identical temperature_f readings long enough to
    # satisfy ReadingsService.is_sensor_stale's default threshold.
    await _seed_readings(app_engine, stale=True)
    response = await client.get("/api/sensors/current")
    assert response.status_code == 200
    model = SensorsCurrent.model_validate(response.json())
    assert model.stale is True
