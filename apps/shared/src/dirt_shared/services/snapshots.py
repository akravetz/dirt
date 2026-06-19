from pathlib import Path

from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.snapshot import Snapshot
from dirt_shared.services.scope import resolve_scope


class SnapshotsService:
    """Reads from the snapshot archive. Constructor-inject the engine."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def latest(
        self,
        *,
        site_pk: int | None = None,
        tent_pk: int | None = None,
    ) -> Snapshot | None:
        async with AsyncSession(self._engine) as session:
            scope = await resolve_scope(session, site_pk=site_pk, tent_pk=tent_pk)
            if scope is None:
                return None
            stmt = select(Snapshot)
            scoped_match = (Snapshot.site_id == scope.site_pk) & (
                Snapshot.tent_id == scope.tent_pk
            )
            if site_pk is None and tent_pk is None:
                stmt = stmt.where(
                    or_(
                        scoped_match,
                        (Snapshot.site_id.is_(None)) & (Snapshot.tent_id.is_(None)),
                    )
                )
            else:
                stmt = stmt.where(scoped_match)
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
