"""Unit tests for GET /api/humidifier/state.

Thin FastAPI wrapper over ``HumidifierStateService.get_state``. Tests
drive the full ASGI stack with an isolated Postgres DB + seeded
``humidifier_on`` sensor readings and assert the JSON body deserializes
into the generated Pydantic ``HumidifierState`` model.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from dirt_contracts.webapp_v1.models import HumidifierState
from httpx import ASGITransport, AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.enums import SensorLocation, SensorSource
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_web.app import create_app


async def _seed_humidifier_readings(
    engine, samples: list[tuple[datetime, float]]
) -> None:
    """Insert ``(ts, value)`` rows under metric='humidifier_on'."""
    async with AsyncSession(engine) as s:
        tent_id = (
            await s.exec(
                select(SensorNode.id).where(SensorNode.location == SensorLocation.TENT)
            )
        ).first()
        assert tent_id is not None
        s.add_all(
            [
                SensorReading(
                    ts=ts,
                    sensornode_id=tent_id,
                    metric="humidifier_on",
                    value=value,
                    source=SensorSource.ARDUINO,
                )
                for ts, value in samples
            ]
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


async def test_humidifier_state_requires_auth(app_engine):
    app = create_app(engine=app_engine, run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.get("/api/humidifier/state")
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/json")


async def test_humidifier_state_cold_cluster(client: AsyncClient):
    """No readings at all → contract-shaped envelope with on=False."""
    response = await client.get("/api/humidifier/state")
    assert response.status_code == 200
    model = HumidifierState.model_validate(response.json())
    assert model.on is False
    assert model.cycles_24h == 0
    # Cold cluster anchors since/duration_s to ts/0 so the required
    # contract fields stay non-null.
    assert model.duration_s == 0
    assert model.since == model.ts


async def test_humidifier_state_returns_contract_shape(client: AsyncClient, app_engine):
    """Seed an off→on→off→on sequence and assert the derived envelope."""
    now = datetime.now(UTC)
    # Transitions over the last hour: off@-50m, on@-40m, off@-30m, on@-10m.
    # Current state (latest): on. Last transition: -10m. cycles_24h: 2.
    samples = [
        (now - timedelta(minutes=50), 0.0),
        (now - timedelta(minutes=40), 1.0),
        (now - timedelta(minutes=30), 0.0),
        (now - timedelta(minutes=10), 1.0),
    ]
    await _seed_humidifier_readings(app_engine, samples)

    response = await client.get("/api/humidifier/state")
    assert response.status_code == 200
    model = HumidifierState.model_validate(response.json())

    assert model.on is True
    assert model.cycles_24h == 2
    # ``since`` is the latest transition — the -10m sample.
    assert model.since.tzinfo is not None
    assert abs((model.ts - model.since).total_seconds() - 600) < 30
    # duration_s is a non-negative integer (contract: conint(ge=0)).
    assert model.duration_s >= 0
    assert 570 <= model.duration_s <= 630


async def test_humidifier_state_only_24h_window_for_cycles(
    client: AsyncClient, app_engine
):
    """Cycles older than 24h do not count toward ``cycles_24h``."""
    now = datetime.now(UTC)
    samples = [
        # Old cycle — 30h ago; must NOT contribute to cycles_24h.
        (now - timedelta(hours=30), 0.0),
        (now - timedelta(hours=30) + timedelta(minutes=5), 1.0),
        # Recent cycle — 2h ago; counts.
        (now - timedelta(hours=2), 0.0),
        (now - timedelta(hours=2) + timedelta(minutes=5), 1.0),
    ]
    await _seed_humidifier_readings(app_engine, samples)

    response = await client.get("/api/humidifier/state")
    assert response.status_code == 200
    model = HumidifierState.model_validate(response.json())
    assert model.on is True
    assert model.cycles_24h == 1
