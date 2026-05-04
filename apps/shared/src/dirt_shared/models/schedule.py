"""Scoped local schedules for tent devices and capabilities."""

from __future__ import annotations

from datetime import UTC, datetime, time

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Identity,
    Index,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Schedule(SQLModel, table=True):
    __tablename__ = "schedule"
    __table_args__ = (
        UniqueConstraint("tent_id", "schedule_id", name="uq_schedule_tent_schedule_id"),
        Index("ix_schedule_site_id", "site_id"),
        Index("ix_schedule_tent_id", "tent_id"),
        Index("ix_schedule_device_id", "device_id"),
        Index("ix_schedule_capability_id", "capability_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("site.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    tent_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("tent.id", ondelete="RESTRICT"),
            nullable=False,
        )
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
    schedule_id: str = Field(sa_column=Column(Text, nullable=False))
    kind: str = Field(sa_column=Column(Text, nullable=False))
    starts_local: time | None = Field(
        default=None, sa_column=Column(Time, nullable=True)
    )
    ends_local: time | None = Field(default=None, sa_column=Column(Time, nullable=True))
    timezone: str = Field(
        default="America/Denver",
        sa_column=Column(
            Text,
            nullable=False,
            server_default=text("'America/Denver'"),
        ),
    )
    enabled: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default=text("true")),
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
