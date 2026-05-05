"""Local durability for outbound cloud gateway sync."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Column,
    Identity,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class CloudSyncCursor(SQLModel, table=True):
    """Per-stream local cloud sync cursors."""

    __tablename__ = "cloud_sync_cursor"

    cursor_key: str = Field(sa_column=Column(Text, primary_key=True))
    cursor_value: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )


class CloudOutbox(SQLModel, table=True):
    """Durable queue of cloud side effects awaiting acknowledgement."""

    __tablename__ = "cloud_outbox"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_cloud_outbox_idempotency_key"),
        Index("ix_cloud_outbox_status_next_retry", "status", "next_retry_at"),
        Index("ix_cloud_outbox_event_type", "event_type"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    event_type: str = Field(sa_column=Column(Text, nullable=False))
    idempotency_key: str = Field(sa_column=Column(Text, nullable=False))
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    )
    status: str = Field(
        default="pending",
        sa_column=Column(Text, nullable=False, server_default=text("'pending'")),
    )
    attempt_count: int = Field(
        default=0,
        sa_column=Column(BigInteger, nullable=False, server_default=text("0")),
    )
    next_retry_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )
    last_error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    delivered_at: datetime | None = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True), nullable=True)
    )
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )
