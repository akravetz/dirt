"""Archive of timestamped JPEG snapshots on disk."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import TIMESTAMP, BigInteger, Column, Identity, Index, Text, text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Snapshot(SQLModel, table=True):
    __tablename__ = "snapshot"
    __table_args__ = (Index("ix_snapshot_ts", "ts", postgresql_ops={"ts": "DESC"}),)

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
