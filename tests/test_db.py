import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.models.snapshot import Snapshot


@pytest.fixture
async def async_session(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    async with AsyncSession(engine) as session:
        yield session
    await engine.dispose()


async def test_snapshot_create_and_query(async_session: AsyncSession):
    snapshot = Snapshot(file_path="/tmp/test.jpg")
    async_session.add(snapshot)
    await async_session.commit()

    result = await async_session.exec(select(Snapshot))
    rows = result.all()
    assert len(rows) == 1
    assert rows[0].file_path == "/tmp/test.jpg"
    assert rows[0].timestamp is not None
