"""Unit tests for GET /api/plants/{code}.

Thin wrapper over ``PlantsService.get_plant_detail_payload`` which
composes the plant's DB row + live moisture + parsed
``wiki/plants/plant-{code}.md`` frontmatter / Timeline / Current State.
Tests drive the full ASGI stack with the template-seeded Postgres DB
and assert the JSON body deserializes into the generated
``PlantDetail`` model.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from dirt_contracts.webapp_v1.models import PlantCode, PlantDetail, PlantStickerColor
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


async def _seed_moisture(engine, *, location: SensorLocation, raw: float) -> None:
    node_id = await _sensornode_id(engine, location)
    capability_id = await _moisture_capability_id(engine, location)
    async with AsyncSession(engine) as s:
        s.add(
            SensorCalibration(
                capability_id=capability_id,
                metric="soil_moisture_raw",
                raw_low=0.0,
                raw_high=1000.0,
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


async def test_plants_detail_requires_auth():
    app = create_app(run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.get("/api/plants/a")
        assert response.status_code == 401


async def test_plants_detail_unknown_code_is_404(client: AsyncClient):
    response = await client.get("/api/plants/z")
    assert response.status_code == 404
    assert response.json() == {"detail": "unknown plant"}


async def test_plants_detail_returns_contract_shape(
    client: AsyncClient, app_engine
) -> None:
    # Seed moisture so the envelope has a value rather than null pct.
    await _seed_moisture(app_engine, location=SensorLocation.PLANT_A, raw=380.0)

    response = await client.get("/api/plants/a")
    assert response.status_code == 200
    model = PlantDetail.model_validate(response.json())

    assert model.code == PlantCode.a
    assert model.name == "Plant A"
    assert model.sticker_color == PlantStickerColor.yellow
    assert model.purple is True
    assert model.wiki_path == "wiki/plants/plant-a.md"
    # The plant-a wiki has a non-empty Current State paragraph + an
    # ``updated`` frontmatter date, so the note must be populated.
    assert model.note is not None
    assert model.note.text
    # Timeline entries from the wiki include 'date', 'day', 'text' —
    # the endpoint filters to the contract-valid subset.
    assert len(model.timeline) >= 1
    assert all(t.day >= 1 for t in model.timeline)
    # Moisture envelope uses the seeded reading (raw=380 → pct=62).
    assert model.moisture.current_pct == pytest.approx(62.0, abs=0.01)
    assert model.moisture.target is not None
    assert model.day >= 1


async def test_plants_detail_cold_cluster_no_moisture(
    client: AsyncClient,
) -> None:
    """No readings → moisture pct is null but the envelope is still well-formed."""
    response = await client.get("/api/plants/b")
    assert response.status_code == 200
    model = PlantDetail.model_validate(response.json())
    assert model.code == PlantCode.b
    assert model.moisture.current_pct is None
    assert model.moisture.ts is None
    assert model.wiki_path == "wiki/plants/plant-b.md"
