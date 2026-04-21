"""One row per plant, scoped to a specific grow.

FKs:
- ``growstate_id`` — which grow this plant belongs to.
- ``sensornode_id`` — UNIQUE, enforcing the 1:1 between a plant and its
  ESP32 moisture node.

Uniqueness: ``(growstate_id, code)`` — the stable 'a'/'b'/'c'/'d' label
is unique per grow, not globally. Grow #2 can reuse A–D with different
surrogate ids.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    Double,
    ForeignKey,
    Identity,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlmodel import Field, SQLModel

from dirt_shared.models.enums import (
    PLANT_STATUS_ENUM,
    PLANT_STICKER_ENUM,
    PlantStatus,
    PlantSticker,
)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Plant(SQLModel, table=True):
    __tablename__ = "plant"
    __table_args__ = (
        CheckConstraint("code ~ '^[a-z]$'", name="ck_plant_code_lowercase_letter"),
        CheckConstraint(
            "moisture_target_low >= 0 AND moisture_target_low < moisture_target_high",
            name="ck_plant_moisture_low_bounds",
        ),
        CheckConstraint(
            "moisture_target_high <= 100",
            name="ck_plant_moisture_high_bounds",
        ),
        UniqueConstraint("growstate_id", "code", name="uq_plant_grow_code"),
        Index("ix_plant_status", "status"),
        Index("ix_plant_growstate_id", "growstate_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    growstate_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("growstate.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    sensornode_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("sensornode.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        )
    )
    code: str = Field(sa_column=Column(Text, nullable=False))
    name: str = Field(sa_column=Column(Text, nullable=False))
    sticker_color: PlantSticker = Field(
        sa_column=Column(PLANT_STICKER_ENUM, nullable=False)
    )
    status: PlantStatus = Field(
        default=PlantStatus.SECONDARY,
        sa_column=Column(
            PLANT_STATUS_ENUM,
            nullable=False,
            server_default=text("'secondary'"),
        ),
    )
    purple: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
    label: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    moisture_target_low: float = Field(
        default=55.0,
        sa_column=Column(Double, nullable=False, server_default=text("55")),
    )
    moisture_target_high: float = Field(
        default=70.0,
        sa_column=Column(Double, nullable=False, server_default=text("70")),
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
