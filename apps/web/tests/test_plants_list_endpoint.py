"""Unit tests for GET /api/plants.

Thin FastAPI wrapper around ``PlantsService.list_plants`` joined with
``GrowStateService.get_grow_current_payload`` for the top-level ``day``
number. Tests drive the full ASGI stack with an isolated Postgres DB
seeded by the template migrations and assert the JSON body deserializes
into the generated ``PlantsResponse`` model.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from dirt_contracts.webapp_v1.models import PlantsResponse, PlantStickerColor
from httpx import ASGITransport, AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.enums import SensorSource
from dirt_shared.models.grow_run import GrowRun
from dirt_shared.models.plant import Plant
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_reading import SensorReading
from dirt_web.app import create_app


async def _moisture_capability_id(engine, device_id: str) -> int:
    async with AsyncSession(engine) as s:
        result = await s.exec(
            select(Capability.id)
            .join(Device, Device.id == Capability.device_id)
            .where(Device.device_id == device_id)
            .where(Capability.capability_id == "soil_moisture_raw")
        )
        capability_id = result.first()
        assert capability_id is not None
        return capability_id


async def _seed_moisture(
    engine,
    *,
    device_id: str,
    raw: float,
    raw_low: float = 0.0,
    raw_high: float = 1000.0,
) -> None:
    """Seed one calibration + one soil_moisture_raw reading for a plant node.

    With raw_low=0 and raw_high=1000 the calibration maps raw→pct by
    ``100 * (1000 - raw) / 1000``, giving us a predictable pct in tests
    without hardcoding the compute function's implementation.
    """
    capability_id = await _moisture_capability_id(engine, device_id)
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
                capability_id=capability_id,
                metric="soil_moisture_raw",
                value=raw,
                source=SensorSource.ESP32,
            )
        )
        await s.commit()


async def _clear_sticker_color(engine, plant_id: str) -> None:
    async with AsyncSession(engine) as s:
        plant = (
            await s.exec(
                select(Plant)
                .join(GrowRun, GrowRun.id == Plant.growrun_id)
                .where(GrowRun.grow_run_id == "main-2026-03-15")
                .where(Plant.plant_id == plant_id)
            )
        ).one()
        plant.sticker_color = None
        s.add(plant)
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
    await _seed_moisture(app_engine, device_id="plant-a-node", raw=380.0)
    await _clear_sticker_color(app_engine, "b")

    response = await client.get("/api/plants")
    assert response.status_code == 200
    body = response.json()

    model = PlantsResponse.model_validate(body)
    assert model.day >= 1

    plant_ids = [p.plant_id for p in model.plants]
    assert plant_ids == ["a", "b", "c", "d"]
    assert all("code" not in plant for plant in body["plants"])
    assert all("label" not in plant for plant in body["plants"])

    # Template migrations seed A with sticker yellow + status primary +
    # purple=true.
    plant_a = next(p for p in model.plants if p.plant_id == "a")
    assert plant_a.name == "Plant A"
    assert plant_a.sticker_color == PlantStickerColor.yellow
    assert plant_a.purple is True
    assert plant_a.moisture_pct == pytest.approx(62.0, abs=0.01)
    assert plant_a.moisture_ts is not None

    # Plants without calibration return moisture_pct=None; sticker_color may be null.
    plant_b = next(p for p in model.plants if p.plant_id == "b")
    assert plant_b.sticker_color is None
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
    assert [plant.plant_id for plant in model.plants] == ["r1", "r2", "r3", "r4", "r5"]
    assert [plant.name for plant in model.plants] == [
        "Track A R1",
        "Track A R2",
        "Track A R3",
        "Track A R4",
        "Track A R5",
    ]
    assert [plant.sticker_color for plant in model.plants] == [
        PlantStickerColor.pink,
        PlantStickerColor.yellow,
        PlantStickerColor.brown,
        PlantStickerColor.blue,
        PlantStickerColor.orange,
    ]
