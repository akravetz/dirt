"""Stable identities for local hardware and service-controlled devices."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

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
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Device(SQLModel, table=True):
    __tablename__ = "device"
    __table_args__ = (
        UniqueConstraint("site_id", "device_id", name="uq_device_site_device_id"),
        Index("ix_device_site_id", "site_id"),
        Index("ix_device_tent_id", "tent_id"),
        Index("ix_device_zone_id", "zone_id"),
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
    zone_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("zone.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    device_id: str = Field(sa_column=Column(Text, nullable=False))
    name: str = Field(sa_column=Column(Text, nullable=False))
    kind: str = Field(sa_column=Column(Text, nullable=False))
    controller: str = Field(sa_column=Column(Text, nullable=False))
    enabled: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default=text("true")),
    )
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
        ),
    )
    last_seen: datetime | None = Field(
        default=None,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=True),
    )
    ip: str | None = Field(default=None, sa_column=Column(INET, nullable=True))
    firmware_version: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    uptime_ms: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
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


class Capability(SQLModel, table=True):
    __tablename__ = "capability"
    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "capability_id",
            name="uq_capability_device_capability_id",
        ),
        Index("ix_capability_device_id", "device_id"),
        Index("ix_capability_metric_name", "metric_name"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    device_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("device.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    capability_id: str = Field(sa_column=Column(Text, nullable=False))
    name: str = Field(sa_column=Column(Text, nullable=False))
    kind: str = Field(sa_column=Column(Text, nullable=False))
    metric_name: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    unit: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    source: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    enabled: bool = Field(
        default=True,
        sa_column=Column(Boolean, nullable=False, server_default=text("true")),
    )
    metadata_json: dict[str, Any] = Field(
        default_factory=dict,
        sa_column=Column(
            "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
        ),
    )
