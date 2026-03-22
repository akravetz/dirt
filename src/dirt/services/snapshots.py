from pathlib import Path

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.models.snapshot import Snapshot


async def get_latest_snapshot(session: AsyncSession) -> Snapshot | None:
    result = await session.exec(
        select(Snapshot).order_by(Snapshot.timestamp.desc()).limit(1)
    )
    return result.first()


def get_snapshot_path(snapshot: Snapshot) -> Path | None:
    """Return the snapshot file path if it exists on disk, else None."""
    path = Path(snapshot.file_path)
    if path.exists():
        return path
    return None
