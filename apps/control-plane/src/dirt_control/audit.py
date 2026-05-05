from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from dirt_control.models import CloudAuditEvent


def add_audit_event(  # noqa: PLR0913
    session: AsyncSession,
    *,
    now: datetime,
    event_type: str,
    actor_type: str,
    actor_id: str | None = None,
    site_id: str | None = None,
    subject_type: str | None = None,
    subject_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CloudAuditEvent:
    event = CloudAuditEvent(
        event_id=str(uuid.uuid4()),
        site_id=site_id,
        actor_type=actor_type,
        actor_id=actor_id,
        event_type=event_type,
        subject_type=subject_type,
        subject_id=subject_id,
        event_metadata=metadata or {},
        created_at=now,
    )
    session.add(event)
    return event
