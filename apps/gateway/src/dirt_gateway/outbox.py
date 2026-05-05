"""SQL-backed local outbox for gateway cloud side effects."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models import CloudOutbox, CloudSyncCursor


@dataclass(frozen=True)
class EnqueueResult:
    row: CloudOutbox
    created: bool


class OutboxRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def enqueue(
        self,
        *,
        event_type: str,
        idempotency_key: str,
        payload: Mapping[str, Any],
        now: datetime,
    ) -> EnqueueResult:
        json_payload = _jsonable(dict(payload))
        async with AsyncSession(self._engine) as session:
            existing = (
                await session.exec(
                    select(CloudOutbox).where(
                        CloudOutbox.idempotency_key == idempotency_key
                    )
                )
            ).first()
            if existing is not None:
                return EnqueueResult(row=existing, created=False)

            row = CloudOutbox(
                event_type=event_type,
                idempotency_key=idempotency_key,
                payload=json_payload,
                status="pending",
                attempt_count=0,
                next_retry_at=now,
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
            return EnqueueResult(row=row, created=True)

    async def due(self, *, now: datetime, limit: int = 50) -> list[CloudOutbox]:
        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(CloudOutbox)
                    .where(CloudOutbox.status == "pending")
                    .where(CloudOutbox.next_retry_at <= now)
                    .order_by(CloudOutbox.created_at, CloudOutbox.id)
                    .limit(limit)
                )
            ).all()
            return list(rows)

    async def pending_count(self) -> int:
        async with AsyncSession(self._engine) as session:
            count = (
                await session.exec(
                    select(func.count())
                    .select_from(CloudOutbox)
                    .where(CloudOutbox.status == "pending")
                )
            ).one()
            return int(count)

    async def mark_delivered(self, row_id: int, *, now: datetime) -> None:
        async with AsyncSession(self._engine) as session:
            row = await session.get(CloudOutbox, row_id)
            if row is None:
                return
            row.status = "delivered"
            row.delivered_at = now
            row.last_error = None
            row.updated_at = now
            await session.commit()

    async def mark_failed(
        self,
        row_id: int,
        *,
        error: str,
        now: datetime,
        retry_delay_s: float,
    ) -> None:
        async with AsyncSession(self._engine) as session:
            row = await session.get(CloudOutbox, row_id)
            if row is None:
                return
            row.status = "pending"
            row.attempt_count += 1
            row.last_error = error[:1000]
            row.next_retry_at = now + timedelta(seconds=retry_delay_s)
            row.updated_at = now
            await session.commit()

    async def set_cursor(
        self,
        *,
        cursor_key: str,
        cursor_value: Mapping[str, Any],
        now: datetime,
    ) -> None:
        async with AsyncSession(self._engine) as session:
            row = await session.get(CloudSyncCursor, cursor_key)
            if row is None:
                row = CloudSyncCursor(
                    cursor_key=cursor_key,
                    cursor_value=_jsonable(dict(cursor_value)),
                    updated_at=now,
                )
                session.add(row)
            else:
                row.cursor_value = _jsonable(dict(cursor_value))
                row.updated_at = now
            await session.commit()


def stable_json_hash(payload: Mapping[str, Any]) -> str:
    text = json.dumps(_jsonable(dict(payload)), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode()).hexdigest()


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_jsonable(item) for item in value]
    return value
