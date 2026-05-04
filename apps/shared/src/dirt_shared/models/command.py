"""Local command-intent ledger for hardware actions."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Column,
    ForeignKey,
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


class Command(SQLModel, table=True):
    __tablename__ = "command"
    __table_args__ = (
        UniqueConstraint("command_id", name="uq_command_command_id"),
        UniqueConstraint("idempotency_key", name="uq_command_idempotency_key"),
        Index("ix_command_site_id", "site_id"),
        Index("ix_command_tent_id", "tent_id"),
        Index("ix_command_status", "status"),
        Index(
            "ix_command_queued_at", "queued_at", postgresql_ops={"queued_at": "DESC"}
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    command_id: str = Field(sa_column=Column(Text, nullable=False))
    idempotency_key: str = Field(sa_column=Column(Text, nullable=False))
    site_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("site.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    tent_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("tent.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    zone_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("zone.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    device_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("device.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    capability_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("capability.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    command_type: str = Field(sa_column=Column(Text, nullable=False))
    payload: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(JSONB, nullable=False, server_default=text("'{}'::jsonb")),
    )
    requested_by: str = Field(sa_column=Column(Text, nullable=False))
    source: str = Field(sa_column=Column(Text, nullable=False))
    status: str = Field(
        default="queued",
        sa_column=Column(Text, nullable=False, server_default=text("'queued'")),
    )
    queued_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )
    started_at: datetime | None = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True), nullable=True)
    )
    succeeded_at: datetime | None = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True), nullable=True)
    )
    failed_at: datetime | None = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True), nullable=True)
    )
    cancelled_at: datetime | None = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True), nullable=True)
    )
    result: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
    error: dict[str, Any] | None = Field(
        default=None, sa_column=Column(JSONB, nullable=True)
    )
