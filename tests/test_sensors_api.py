from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.services.seed import seed_sensor_data


@pytest.fixture
async def db_engine(tmp_path):
    db_path = tmp_path / "test.db"
    eng = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(eng) as session:
        await seed_sensor_data(session)
    yield eng
    await eng.dispose()


@pytest.fixture
async def client(db_engine):
    with (
        patch("dirt.services.capture.capture_loop"),
        patch("dirt.db.engine", db_engine),
        patch("dirt.services.readings.engine", db_engine),
    ):
        from dirt.app import app

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
    assert "labels" in data
    assert "temperature" in data
    assert "humidity" in data
    assert len(data["labels"]) == len(data["temperature"]) == len(data["humidity"])


@pytest.mark.parametrize("range_param", ["1h", "24h", "7d", "30d"])
async def test_readings_range_params(client: AsyncClient, range_param: str):
    response = await client.get(f"/api/sensors/readings?range={range_param}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["labels"]) > 0


async def test_readings_invalid_range(client: AsyncClient):
    response = await client.get("/api/sensors/readings?range=99d")
    assert response.status_code == 422


async def test_current_readings(client: AsyncClient):
    response = await client.get("/sensors/current")
    assert response.status_code == 200
    assert "°F" in response.text
    assert "%" in response.text
