from pathlib import Path

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.snapshot import Snapshot
from dirt_shared.services.scope import DEFAULT_SITE_ID, DEFAULT_TENT_ID, resolve_scope


class SnapshotsService:
    """Reads from the snapshot archive. Constructor-inject the engine.

    Wired into FastAPI via ``app.state.snapshots`` in
    ``dirt_web.app.create_app``; resolved by the ``get_snapshots``
    provider in ``dirt_web.deps``.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def latest(
        self,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
    ) -> Snapshot | None:
        async with AsyncSession(self._engine) as session:
            scope = await resolve_scope(session, site_id=site_id, tent_id=tent_id)
            stmt = select(Snapshot)
            if scope is not None:
                stmt = stmt.where(
                    or_(
                        (Snapshot.site_id == scope.site_pk)
                        & (Snapshot.tent_id == scope.tent_pk),
                        (Snapshot.site_id.is_(None)) & (Snapshot.tent_id.is_(None)),
                    )
                )
            result = await session.exec(stmt.order_by(Snapshot.ts.desc()).limit(1))
            return result.first()


def get_snapshot_path(snapshot: Snapshot) -> Path | None:
    """Return the snapshot file path if it exists on disk, else None.

    Stateless helper — no engine needed; not on the service class.
    """
    path = Path(snapshot.file_path)
    if path.exists():
        return path
    return None
