from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.sensor_reading import SensorReading


async def _seed_test_data(session: AsyncSession, hours: int = 48) -> None:
    """Insert a small set of readings across all metrics."""
    now = datetime.now(UTC)
    readings = []
    for i in range(hours * 4):  # one reading every 15 minutes
        ts = now - timedelta(minutes=15 * i)
        values = {
            "temperature_f": 72.0 + (i % 10) * 0.5,
            "humidity_pct": 50.0 + (i % 10) * 0.3,
            "pressure_hpa": 1013.0 + (i % 5) * 0.1,
            "vpd_kpa": 1.1 + (i % 10) * 0.01,
            "dew_point_f": 55.0 + (i % 10) * 0.2,
        }
        for metric, value in values.items():
            readings.append(
                SensorReading(
                    timestamp=ts,
                    location="tent",
                    metric=metric,
                    value=value,
                    source="test",
                )
            )
    session.add_all(readings)
    await session.commit()


@pytest.fixture
async def db_engine(tmp_path):
    db_path = tmp_path / "test.db"
    eng = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(eng) as session:
        await _seed_test_data(session)
    yield eng
    await eng.dispose()


@pytest.fixture
async def client(db_engine):
    with (
        patch("dirt_shared.services.capture.capture_loop"),
        patch("dirt_shared.db.engine", db_engine),
        patch("dirt_shared.services.readings.engine", db_engine),
    ):
        from dirt_web.app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=False
        ) as ac:
            login = await ac.post(
                "/login", data={"username": "admin", "password": "changeme"}
            )
            ac.cookies = login.cookies
            yield ac


async def test_readings_default_range(client: AsyncClient):
    response = await client.get("/api/sensors/readings")
    assert response.status_code == 200
    data = response.json()
    # Response shape: {metric: {labels, values}, ...}
    assert "temperature_f" in data
    assert "humidity_pct" in data
    assert "pressure_hpa" in data
    assert "vpd_kpa" in data
    assert "dew_point_f" in data
    for metric in data.values():
        assert "labels" in metric
        assert "values" in metric
        assert len(metric["labels"]) == len(metric["values"])


@pytest.mark.parametrize("range_param", ["1h", "24h", "7d", "30d"])
async def test_readings_range_params(client: AsyncClient, range_param: str):
    response = await client.get(f"/api/sensors/readings?range={range_param}")
    assert response.status_code == 200
    data = response.json()
    # At least temperature_f should have some points in any range
    assert len(data["temperature_f"]["labels"]) > 0


async def test_readings_invalid_range(client: AsyncClient):
    response = await client.get("/api/sensors/readings?range=99d")
    assert response.status_code == 422


async def test_current_readings(client: AsyncClient):
    response = await client.get("/sensors/current")
    assert response.status_code == 200
    assert "°F" in response.text
    assert "%" in response.text
