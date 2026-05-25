"""Irrigation pulse schedules and dispatch ledger rows."""

from __future__ import annotations

from datetime import UTC, datetime, time

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class IrrigationScheduleItem(SQLModel, table=True):
    __tablename__ = "irrigation_schedule_item"
    __table_args__ = (
        CheckConstraint(
            "duration_s > 0",
            name="ck_irrigation_schedule_item_duration_positive",
        ),
        UniqueConstraint(
            "schedule_id",
            "starts_local",
            name="uq_irrigation_schedule_item_schedule_start",
        ),
        Index("ix_irrigation_schedule_item_schedule_id", "schedule_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    schedule_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("schedule.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    starts_local: time = Field(sa_column=Column(Time, nullable=False))
    duration_s: int = Field(sa_column=Column(Integer, nullable=False))
    enabled: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default=text("true")),
    )
    label: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
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


class IrrigationRun(SQLModel, table=True):
    __tablename__ = "irrigation_run"
    __table_args__ = (
        CheckConstraint(
            "duration_s > 0",
            name="ck_irrigation_run_duration_positive",
        ),
        CheckConstraint(
            "status IN ('pending', 'dispatched', 'failed', 'skipped')",
            name="ck_irrigation_run_status",
        ),
        UniqueConstraint(
            "schedule_item_id",
            "intended_start_at",
            name="uq_irrigation_run_schedule_item_intended_start",
        ),
        Index("ix_irrigation_run_schedule_id", "schedule_id"),
        Index("ix_irrigation_run_schedule_item_id", "schedule_item_id"),
        Index("ix_irrigation_run_device_id", "device_id"),
        Index("ix_irrigation_run_capability_id", "capability_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    schedule_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("schedule.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    schedule_item_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("irrigation_schedule_item.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    device_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("device.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    capability_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("capability.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    intended_start_at: datetime = Field(
        sa_column=Column(TIMESTAMP(timezone=True), nullable=False)
    )
    started_at: datetime | None = Field(
        default=None,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=True),
    )
    finished_at: datetime | None = Field(
        default=None,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=True),
    )
    duration_s: int = Field(sa_column=Column(Integer, nullable=False))
    status: str = Field(sa_column=Column(Text, nullable=False))
    error: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
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
