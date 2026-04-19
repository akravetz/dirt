from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.config import GROW_START, settings
from dirt_shared.models.grow_state import GrowState
from dirt_shared.models.sensor_calibration import SensorCalibration  # noqa: F401
from dirt_shared.models.sensor_node import SensorNode  # noqa: F401
from dirt_shared.models.sensor_reading import SensorReading  # noqa: F401
from dirt_shared.models.snapshot import Snapshot  # noqa: F401

engine = create_async_engine(settings.database_url)


async def get_session():
    async with AsyncSession(engine) as session:
        yield session


# SQLModel.metadata.create_all only creates missing tables — it does not ALTER
# existing ones. These one-shot idempotent migrations are for columns added to
# live tables after the first deploy. They're safe to run every boot.
_COLUMN_MIGRATIONS: tuple[tuple[str, str, str], ...] = (
    ("growstate", "lights_on_local", "TEXT NOT NULL DEFAULT '05:00:00'"),
    ("growstate", "lights_off_local", "TEXT NOT NULL DEFAULT '23:00:00'"),
)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        for table, column, definition in _COLUMN_MIGRATIONS:
            existing = await conn.execute(text(f"PRAGMA table_info({table})"))
            if column not in {row[1] for row in existing}:
                await conn.execute(text(
                    f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                ))
    async with AsyncSession(engine) as session:
        if await session.get(GrowState, 1) is None:
            session.add(GrowState(id=1, germination_date=GROW_START))
            await session.commit()
