"""Unit tests for GET /api/plants.

Thin FastAPI wrapper around ``PlantsService.list_plants`` joined with
``GrowStateService.get_grow_current_payload`` for the top-level ``day``
number. Tests drive the full ASGI stack with an isolated Postgres DB
seeded by the template migration (4 plants A–D, one sensornode per
plant, no readings or calibrations) and assert the JSON body
deserializes into the generated ``PlantsResponse`` model.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from dirt_contracts.webapp_v1.models import PlantCode, PlantsResponse
from httpx import ASGITransport, AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.enums import SensorLocation, SensorSource
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.sensor_contract import LEGACY_LOCATION_DEVICE_IDS
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
        result = await s.exec(
            select(Capability.id)
            .join(Device, Device.id == Capability.device_id)
            .where(Device.device_id == LEGACY_LOCATION_DEVICE_IDS[location])
            .where(Capability.capability_id == "soil_moisture_raw")
        )
        capability_id = result.first()
        assert capability_id is not None
        return capability_id


async def _seed_moisture(
    engine,
    *,
    location: SensorLocation,
    raw: float,
    raw_low: float = 0.0,
    raw_high: float = 1000.0,
) -> None:
    """Seed one calibration + one soil_moisture_raw reading for a plant node.

    With raw_low=0 and raw_high=1000 the calibration maps raw→pct by
    ``100 * (1000 - raw) / 1000``, giving us a predictable pct in tests
    without hardcoding the compute function's implementation.
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
        s.add(
            SensorReading(
                ts=datetime.now(UTC),
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


async def test_plants_list_requires_auth():
    app = create_app(run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.get("/api/plants")
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/json")


async def test_plants_list_returns_contract_shape(client: AsyncClient, app_engine):
    # Seed plant-a with a calibrated reading (raw=380 + [0,1000] → 62%).
    await _seed_moisture(app_engine, location=SensorLocation.PLANT_A, raw=380.0)

    response = await client.get("/api/plants")
    assert response.status_code == 200

    model = PlantsResponse.model_validate(response.json())
    assert model.day >= 1

    codes = [p.code for p in model.plants]
    assert codes == [PlantCode.a, PlantCode.b, PlantCode.c, PlantCode.d]

    # Template migration seeds A with sticker yellow + status primary +
    # purple=true + label "Purple Keeper Candidate".
    plant_a = next(p for p in model.plants if p.code == PlantCode.a)
    assert plant_a.name == "Plant A"
    assert plant_a.purple is True
    assert plant_a.moisture_pct == pytest.approx(62.0, abs=0.01)
    assert plant_a.moisture_ts is not None

    # Plants without calibration return moisture_pct=None.
    plant_b = next(p for p in model.plants if p.code == PlantCode.b)
    assert plant_b.moisture_pct is None
    assert plant_b.moisture_ts is None


async def test_plants_list_cold_cluster(client: AsyncClient):
    """No calibrations or readings yet — every plant has null moisture."""
    response = await client.get("/api/plants")
    assert response.status_code == 200
    model = PlantsResponse.model_validate(response.json())
    assert all(p.moisture_pct is None for p in model.plants)
    assert all(p.moisture_ts is None for p in model.plants)


async def test_plants_list_accepts_tent_scope(client: AsyncClient):
    response = await client.get("/api/plants", params={"tent_id": "breeding"})
    assert response.status_code == 200
    model = PlantsResponse.model_validate(response.json())
    assert model.day >= 1
    assert model.plants == []
