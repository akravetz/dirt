from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.config import settings
from dirt.models.snapshot import Snapshot  # noqa: F401 — registers table with SQLModel

engine = create_async_engine(settings.database_url)


async def get_session():
    async with AsyncSession(engine) as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
