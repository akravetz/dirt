"""Archive of timestamped JPEG snapshots on disk with scoped ownership."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Column,
    ForeignKey,
    Identity,
    Index,
    Text,
    text,
)
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Snapshot(SQLModel, table=True):
    __tablename__ = "snapshot"
    __table_args__ = (
        Index("ix_snapshot_ts", "ts", postgresql_ops={"ts": "DESC"}),
        Index(
            "ix_snapshot_scope_ts",
            "site_id",
            "tent_id",
            "ts",
            postgresql_ops={"ts": "DESC"},
        ),
        Index("ix_snapshot_device_id", "device_id"),
        Index("ix_snapshot_growrun_id", "growrun_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    ts: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )
    file_path: str = Field(sa_column=Column(Text, nullable=False, unique=True))
    site_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("site.id", ondelete="RESTRICT"),
            nullable=True,
        ),
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
    growrun_id: int | None = Field(
        default=None,
        sa_column=Column(
            BigInteger,
            ForeignKey("growrun.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    view_id: str = Field(
        default="periodic",
        sa_column=Column(Text, nullable=False, server_default=text("'periodic'")),
    )
    kind: str = Field(
        default="periodic",
        sa_column=Column(Text, nullable=False, server_default=text("'periodic'")),
    )
