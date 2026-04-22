"""Unit tests for GET /api/humidifier/history.

Thin FastAPI wrapper over ``HumidifierStateService.get_history``. Tests
drive the full ASGI stack with an isolated Postgres DB + seeded
``humidifier_on`` sensor readings and assert the JSON body deserializes
into the generated Pydantic ``HumidifierHistory`` model.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from dirt_contracts.webapp_v1.models import HumidifierHistory
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


async def test_humidifier_history_requires_auth(app_engine):
    app = create_app(engine=app_engine, run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.get("/api/humidifier/history", params={"range": "24h"})
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/json")


async def test_humidifier_history_rejects_invalid_range(client: AsyncClient):
    """Out-of-enum range is rejected at the query layer (422)."""
    response = await client.get("/api/humidifier/history", params={"range": "bogus"})
    assert response.status_code == 422


async def test_humidifier_history_requires_range(client: AsyncClient):
    """``range`` is required; missing → 422."""
    response = await client.get("/api/humidifier/history")
    assert response.status_code == 422


async def test_humidifier_history_cold_cluster(client: AsyncClient):
    """No readings → empty points list with the echoed range."""
    response = await client.get("/api/humidifier/history", params={"range": "24h"})
    assert response.status_code == 200
    model = HumidifierHistory.model_validate(response.json())
    assert model.range.value == "24h"
    assert model.points == []


async def test_humidifier_history_returns_only_transitions(
    client: AsyncClient, app_engine
):
    """Non-transition rows (value unchanged from previous) are filtered out."""
    now = datetime.now(UTC)
    # Seed 30s-interval samples: off, off, on, on, off. Only 3 rows are
    # state-change rows: the first (prev IS NULL), the off→on, the
    # on→off. The two "unchanged" rows must NOT appear.
    samples = [
        (now - timedelta(minutes=20), 0.0),
        (now - timedelta(minutes=19, seconds=30), 0.0),
        (now - timedelta(minutes=15), 1.0),
        (now - timedelta(minutes=14, seconds=30), 1.0),
        (now - timedelta(minutes=5), 0.0),
    ]
    await _seed_humidifier_readings(app_engine, samples)

    response = await client.get("/api/humidifier/history", params={"range": "1h"})
    assert response.status_code == 200
    model = HumidifierHistory.model_validate(response.json())
    assert model.range.value == "1h"
    assert len(model.points) == 3
    # Ordered oldest → newest, with the expected on/off sequence.
    assert [p.on for p in model.points] == [False, True, False]
    # Timestamps are strictly increasing and timezone-aware.
    ts_list = [p.ts for p in model.points]
    assert all(t.tzinfo is not None for t in ts_list)
    assert ts_list == sorted(ts_list)


async def test_humidifier_history_respects_range_cutoff(
    client: AsyncClient, app_engine
):
    """Transitions older than the range cutoff must not appear."""
    now = datetime.now(UTC)
    samples = [
        # Outside the 1h window — must be excluded.
        (now - timedelta(hours=3), 0.0),
        (now - timedelta(hours=3) + timedelta(minutes=5), 1.0),
        # Inside the 1h window — must appear.
        (now - timedelta(minutes=30), 0.0),
        (now - timedelta(minutes=10), 1.0),
    ]
    await _seed_humidifier_readings(app_engine, samples)

    response = await client.get("/api/humidifier/history", params={"range": "1h"})
    assert response.status_code == 200
    model = HumidifierHistory.model_validate(response.json())
    # Only the two in-window rows survive; the first row inside the window
    # is also a transition (``prev IS NULL`` inside the CTE).
    assert len(model.points) == 2
    assert [p.on for p in model.points] == [False, True]
