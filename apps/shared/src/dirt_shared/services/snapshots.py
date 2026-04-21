from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.snapshot import Snapshot


class SnapshotsService:
    """Reads from the snapshot archive. Constructor-inject the engine.

    Wired into FastAPI via ``app.state.snapshots`` in
    ``dirt_web.app.create_app``; resolved by the ``get_snapshots``
    provider in ``dirt_web.deps``.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def latest(self) -> Snapshot | None:
        async with AsyncSession(self._engine) as session:
            result = await session.exec(
                select(Snapshot).order_by(Snapshot.ts.desc()).limit(1)
            )
            return result.first()


def get_snapshot_path(snapshot: Snapshot) -> Path | None:
    """Return the snapshot file path if it exists on disk, else None.

    Stateless helper — no engine needed; not on the service class.
    """
    path = Path(snapshot.file_path)
    if path.exists():
        return path
    return None
