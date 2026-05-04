"""Scoped physical or logical zones within a site or tent."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    Column,
    ForeignKey,
    Identity,
    Index,
    Text,
    UniqueConstraint,
    text,
)
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Zone(SQLModel, table=True):
    __tablename__ = "zone"
    __table_args__ = (
        UniqueConstraint("site_id", "tent_id", "zone_id", name="uq_zone_scope_zone_id"),
        Index("ix_zone_site_id", "site_id"),
        Index("ix_zone_tent_id", "tent_id"),
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
    tent_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("tent.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    zone_id: str = Field(sa_column=Column(Text, nullable=False))
    name: str = Field(sa_column=Column(Text, nullable=False))
    zone_type: str = Field(sa_column=Column(Text, nullable=False))
    active: bool = Field(
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
