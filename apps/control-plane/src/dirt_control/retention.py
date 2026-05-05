from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from dirt_control.audit import add_audit_event
from dirt_control.models import CloudAsset
from dirt_control.settings import CloudSettings


class ObjectStore(Protocol):
    def delete_objects(self, object_keys: Sequence[str]) -> int: ...


@dataclass(frozen=True)
class RetentionResult:
    cutoff: datetime
    matched: int
    objects_deleted: int


async def prune_expired_assets(  # noqa: PLR0913
    session: AsyncSession,
    *,
    settings: CloudSettings,
    now: datetime,
    actor_type: str,
    actor_id: str | None,
    site_id: str | None = None,
    object_store: ObjectStore | None = None,
) -> RetentionResult:
    cutoff = now - timedelta(days=settings.asset_retention_days)
    stmt = select(CloudAsset).where(CloudAsset.captured_at < cutoff)
    if site_id is not None:
        stmt = stmt.where(CloudAsset.site_id == site_id)
    rows = (await session.execute(stmt)).scalars().all()
    asset_ids = [row.asset_id for row in rows]
    object_keys = [row.object_key for row in rows]
    objects_deleted = 0
    if object_store is not None and object_keys:
        objects_deleted = await asyncio.to_thread(
            object_store.delete_objects, object_keys
        )
    if asset_ids:
        delete_stmt = delete(CloudAsset).where(CloudAsset.asset_id.in_(asset_ids))
        await session.execute(delete_stmt)
    add_audit_event(
        session,
        now=now,
        event_type="asset_retention_pruned",
        actor_type=actor_type,
        actor_id=actor_id,
        site_id=site_id,
        subject_type="cloud_asset",
        metadata={
            "retention_days": settings.asset_retention_days,
            "cutoff": cutoff.isoformat(),
            "matched": len(rows),
            "objects_deleted": objects_deleted,
        },
    )
    await session.commit()
    return RetentionResult(
        cutoff=cutoff,
        matched=len(rows),
        objects_deleted=objects_deleted,
    )
