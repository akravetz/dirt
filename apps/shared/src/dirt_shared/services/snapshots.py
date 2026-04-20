from pathlib import Path

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.db import engine
from dirt_shared.models.snapshot import Snapshot


async def get_latest_snapshot() -> Snapshot | None:
    async with AsyncSession(engine) as session:
        result = await session.exec(
            select(Snapshot).order_by(Snapshot.ts.desc()).limit(1)
        )
        return result.first()


def get_snapshot_path(snapshot: Snapshot) -> Path | None:
    """Return the snapshot file path if it exists on disk, else None."""
    path = Path(snapshot.file_path)
    if path.exists():
        return path
    return None
