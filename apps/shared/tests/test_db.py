from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.snapshot import Snapshot


async def test_snapshot_create_and_query(pg_engine):
    async with AsyncSession(pg_engine) as session:
        snapshot = Snapshot(file_path="/tmp/test.jpg")
        session.add(snapshot)
        await session.commit()

        result = await session.exec(select(Snapshot))
        rows = result.all()

    assert len(rows) == 1
    assert rows[0].file_path == "/tmp/test.jpg"
    assert rows[0].ts is not None
