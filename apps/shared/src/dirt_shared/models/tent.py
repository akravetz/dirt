"""Logical grow tents within a physical controller site."""

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


class Tent(SQLModel, table=True):
    __tablename__ = "tent"
    __table_args__ = (
        UniqueConstraint("site_id", "tent_id", name="uq_tent_site_tent_id"),
        Index("ix_tent_site_id", "site_id"),
        Index(
            "ux_tent_default_per_site",
            "site_id",
            unique=True,
            postgresql_where=text("is_default = true"),
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
    tent_id: str = Field(sa_column=Column(Text, nullable=False))
    name: str = Field(sa_column=Column(Text, nullable=False))
    role: str = Field(sa_column=Column(Text, nullable=False))
    is_default: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, server_default=text("false")),
    )
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
