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


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine) as session:
        if await session.get(GrowState, 1) is None:
            session.add(GrowState(id=1, germination_date=GROW_START))
            await session.commit()
