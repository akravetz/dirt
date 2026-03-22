import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.models.sensor_reading import SensorReading
from dirt.services.seed import seed_sensor_data


@pytest.fixture
async def async_session(tmp_path):
    db_path = tmp_path / "test.db"
    eng = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(eng) as session:
        yield session
    await eng.dispose()


async def test_seed_creates_readings(async_session: AsyncSession):
    count = await seed_sensor_data(async_session)
    assert count > 0

    result = await async_session.exec(select(SensorReading))
    rows = result.all()
    assert len(rows) == count


async def test_seed_is_idempotent(async_session: AsyncSession):
    first = await seed_sensor_data(async_session)
    assert first > 0

    second = await seed_sensor_data(async_session)
    assert second == 0


async def test_seed_values_in_range(async_session: AsyncSession):
    await seed_sensor_data(async_session)

    result = await async_session.exec(select(SensorReading))
    for r in result.all():
        assert 55 <= r.temperature_f <= 95, f"Temp out of range: {r.temperature_f}"
        assert 0 <= r.humidity_pct <= 100, f"Humidity out of range: {r.humidity_pct}"
        assert r.source == "mock"
