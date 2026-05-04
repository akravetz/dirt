"""Scoped grow cycles for each tent."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Identity,
    Index,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class GrowRun(SQLModel, table=True):
    __tablename__ = "growrun"
    __table_args__ = (
        CheckConstraint("plant_count BETWEEN 0 AND 64", name="ck_growrun_plant_count"),
        UniqueConstraint("tent_id", "grow_run_id", name="uq_growrun_tent_grow_run_id"),
        Index("ix_growrun_site_id", "site_id"),
        Index("ix_growrun_tent_id", "tent_id"),
        Index(
            "ux_growrun_current_per_tent",
            "tent_id",
            unique=True,
            postgresql_where=text("is_current = true"),
        ),
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
    grow_run_id: str = Field(sa_column=Column(Text, nullable=False))
    name: str = Field(sa_column=Column(Text, nullable=False))
    purpose: str = Field(sa_column=Column(Text, nullable=False))
    germination_date: date | None = Field(
        default=None, sa_column=Column(Date, nullable=True)
    )
    flower_start_date: date | None = Field(
        default=None, sa_column=Column(Date, nullable=True)
    )
    strain: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    timezone: str = Field(
        default="America/Denver",
        sa_column=Column(
            Text,
            nullable=False,
            server_default=text("'America/Denver'"),
        ),
    )
    plant_count: int = Field(
        default=0,
        sa_column=Column(SmallInteger, nullable=False, server_default=text("0")),
    )
    is_current: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    started_at: datetime | None = Field(
        default=None, sa_column=Column(TIMESTAMP(timezone=True), nullable=True)
    )
    ended_at: datetime | None = Field(
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
