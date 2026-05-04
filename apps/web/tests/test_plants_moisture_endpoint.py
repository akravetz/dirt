"""Unit tests for GET /api/plants/{code}/moisture.

Thin wrapper over ``PlantsService.get_plant_moisture_history`` plus the
``count_irrigation_events`` heuristic (upward jumps >= 5% between
adjacent samples). Tests drive the full ASGI stack with the template-
seeded Postgres DB and assert the JSON body deserializes into the
generated ``PlantMoistureHistory`` model.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from dirt_contracts.webapp_v1.models import (
    PlantCode,
    PlantMoistureHistory,
    Range,
)
from httpx import ASGITransport, AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.enums import SensorLocation, SensorSource
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.sensor_contract import device_id_for_legacy_location
from dirt_web.app import create_app


async def _sensornode_id(engine, location: SensorLocation) -> int:
    async with AsyncSession(engine) as s:
        result = await s.exec(
            select(SensorNode.id).where(SensorNode.location == location)
        )
        node_id = result.first()
        assert node_id is not None
        return node_id


async def _moisture_capability_id(engine, location: SensorLocation) -> int:
    async with AsyncSession(engine) as s:
        device_id = device_id_for_legacy_location(location)
        assert device_id is not None
        result = await s.exec(
            select(Capability.id)
            .join(Device, Device.id == Capability.device_id)
            .where(Device.device_id == device_id)
            .where(Capability.capability_id == "soil_moisture_raw")
        )
        capability_id = result.first()
        assert capability_id is not None
        return capability_id


async def _seed_moisture_series(
    engine,
    *,
    location: SensorLocation,
    raws: list[tuple[datetime, float]],
    raw_low: float = 0.0,
    raw_high: float = 1000.0,
) -> None:
    """Seed a calibration + a list of (ts, raw) readings for one plant.

    With raw_low=0 and raw_high=1000 the calibration maps raw→pct by
    ``100 * (1000 - raw) / 1000``, so ``raw=500`` → 50% and ``raw=100`` → 90%.
    """
    node_id = await _sensornode_id(engine, location)
    capability_id = await _moisture_capability_id(engine, location)
    async with AsyncSession(engine) as s:
        s.add(
            SensorCalibration(
                capability_id=capability_id,
                metric="soil_moisture_raw",
                raw_low=raw_low,
                raw_high=raw_high,
            )
        )
        for ts, raw in raws:
            s.add(
                SensorReading(
                    ts=ts,
                    sensornode_id=node_id,
                    capability_id=capability_id,
                    metric="soil_moisture_raw",
                    value=raw,
                    source=SensorSource.ESP32,
                )
            )
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


async def test_plants_moisture_requires_auth():
    app = create_app(run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.get("/api/plants/a/moisture?range=24h")
        assert response.status_code == 401


async def test_plants_moisture_unknown_code_is_404(client: AsyncClient):
    response = await client.get("/api/plants/z/moisture?range=24h")
    assert response.status_code == 404


async def test_plants_moisture_invalid_range_is_422(client: AsyncClient):
    """FastAPI Query validation rejects out-of-enum range before handler."""
    response = await client.get("/api/plants/a/moisture?range=garbage")
    assert response.status_code == 422


async def test_plants_moisture_empty_series(client: AsyncClient):
    """No calibration or readings → empty points list, zero events."""
    response = await client.get("/api/plants/a/moisture?range=24h")
    assert response.status_code == 200
    model = PlantMoistureHistory.model_validate(response.json())
    assert model.code == PlantCode.a
    assert model.range == Range.field_24h
    assert model.points == []
    assert model.irrigation_events_24h == 0
    # Even without readings the target band is carried from the Plant row
    # (template seeds moisture_target_low=55, _high=70 by default).
    assert model.target is not None


async def test_plants_moisture_series_with_irrigation_events(
    client: AsyncClient, app_engine
):
    """Drying trend punctuated by three ``upward jump >= 5%`` events."""
    now = datetime.now(UTC)

    # Alternate drying + watering ramps: each "watering" step raises raw
    # by more than the 5%-pct jump threshold (raws 500→100 = 50%→90%,
    # i.e. +40pct). Three watering events total.
    raws = [
        (now - timedelta(hours=23), 500.0),  # 50%
        (now - timedelta(hours=22), 550.0),  # 45% (drying)
        (now - timedelta(hours=21), 100.0),  # 90% (event 1)
        (now - timedelta(hours=18), 600.0),  # 40% (drying)
        (now - timedelta(hours=15), 100.0),  # 90% (event 2)
        (now - timedelta(hours=10), 700.0),  # 30% (drying)
        (now - timedelta(hours=5), 100.0),  # 90% (event 3)
        (now - timedelta(minutes=30), 600.0),  # 40% (drying)
    ]
    await _seed_moisture_series(app_engine, location=SensorLocation.PLANT_A, raws=raws)

    response = await client.get("/api/plants/a/moisture?range=24h")
    assert response.status_code == 200
    model = PlantMoistureHistory.model_validate(response.json())
    assert model.code == PlantCode.a
    assert model.range == Range.field_24h
    assert model.irrigation_events_24h == 3
    # Non-empty series comes back in chronological order.
    assert len(model.points) == len(raws)
    assert all(
        model.points[i].ts <= model.points[i + 1].ts
        for i in range(len(model.points) - 1)
    )
    # Points are pct values in [0, 100].
    assert all(0.0 <= p.value <= 100.0 for p in model.points)


async def test_plants_moisture_1h_range_preserves_24h_event_count(
    client: AsyncClient, app_engine
):
    """Switching range=1h must not affect the 24h event count."""
    now = datetime.now(UTC)
    raws = [
        (now - timedelta(hours=20), 500.0),  # event (earlier in 24h, outside 1h)
        (now - timedelta(hours=19), 100.0),
        (now - timedelta(hours=15), 600.0),  # event
        (now - timedelta(hours=14), 100.0),
        (now - timedelta(minutes=45), 500.0),  # within 1h, no jump
        (now - timedelta(minutes=30), 480.0),
    ]
    await _seed_moisture_series(app_engine, location=SensorLocation.PLANT_B, raws=raws)

    response = await client.get("/api/plants/b/moisture?range=1h")
    assert response.status_code == 200
    model = PlantMoistureHistory.model_validate(response.json())
    assert model.range == Range.field_1h
    # 1h window catches only the last two readings — no upward jump there.
    assert len(model.points) == 2
    # But the 24h event count covers the whole day: 2 upward jumps.
    assert model.irrigation_events_24h == 2


async def test_plants_moisture_7d_range_bucketed_hourly(
    client: AsyncClient, app_engine
):
    """7d responses bucket to ~hourly resolution so the JSON stays bounded.

    A dense series (20 readings spread across 90 minutes) should collapse
    to ≤2 points for 7d, matching the hourly bucket width the FE expects.
    """
    now = datetime.now(UTC)
    raws = [(now - timedelta(minutes=90 - i * 5), 400.0) for i in range(20)]
    await _seed_moisture_series(app_engine, location=SensorLocation.PLANT_A, raws=raws)

    response = await client.get("/api/plants/a/moisture?range=7d")
    assert response.status_code == 200
    model = PlantMoistureHistory.model_validate(response.json())
    assert model.range == Range.field_7d
    # 90 minutes of readings crosses at most 3 hourly bucket boundaries.
    assert len(model.points) <= 3
    assert len(model.points) < len(raws)
    # 1h on the same data stays raw (no bucketing).
    response_1h = await client.get("/api/plants/a/moisture?range=1h")
    model_1h = PlantMoistureHistory.model_validate(response_1h.json())
    assert len(model_1h.points) > len(model.points)
