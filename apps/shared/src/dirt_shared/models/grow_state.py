"""The current grow — future-proofed for multi-grow history.

Singleton semantics enforced by a partial unique index on ``is_current``:
at most one row can have ``is_current=true`` at any time. Historical
grows live as ``is_current=false`` rows; the V1 app reads only the
current row.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Date,
    Identity,
    Index,
    SmallInteger,
    Text,
    Time,
    text,
)
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class GrowState(SQLModel, table=True):
    __tablename__ = "growstate"
    __table_args__ = (
        CheckConstraint(
            "plant_count BETWEEN 1 AND 16", name="ck_growstate_plant_count"
        ),
        Index(
            "ux_growstate_is_current",
            "is_current",
            unique=True,
            postgresql_where=text("is_current = true"),
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    germination_date: date = Field(sa_column=Column(Date, nullable=False))
    flower_start_date: date | None = Field(
        default=None, sa_column=Column(Date, nullable=True)
    )
    lights_on_local: time = Field(
        default=time(5, 0),
        sa_column=Column(Time, nullable=False, server_default=text("'05:00:00'")),
    )
    lights_off_local: time = Field(
        default=time(23, 0),
        sa_column=Column(Time, nullable=False, server_default=text("'23:00:00'")),
    )
    strain: str = Field(
        default="Sirius Black × BS01",
        sa_column=Column(
            Text,
            nullable=False,
            server_default=text("'Sirius Black × BS01'"),
        ),
    )
    location: str = Field(
        default="Denver, MT · closet tent",
        sa_column=Column(
            Text,
            nullable=False,
            server_default=text("'Denver, MT · closet tent'"),
        ),
    )
    plant_count: int = Field(
        default=4,
        sa_column=Column(SmallInteger, nullable=False, server_default=text("4")),
    )
    is_current: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    created_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )
