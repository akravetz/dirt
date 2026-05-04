"""Physical controller sites managed by this Dirt installation."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Boolean,
    Column,
    Identity,
    Index,
    Text,
    text,
)
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Site(SQLModel, table=True):
    __tablename__ = "site"
    __table_args__ = (
        Index(
            "ux_site_is_default",
            "is_default",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    site_id: str = Field(sa_column=Column(Text, nullable=False, unique=True))
    name: str = Field(sa_column=Column(Text, nullable=False))
    location: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    timezone: str = Field(
        default="America/Denver",
        sa_column=Column(
            Text,
            nullable=False,
            server_default=text("'America/Denver'"),
        ),
    )
    is_default: bool = Field(
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
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )
