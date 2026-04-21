"""Append-only sensor reading fact table.

One row per (ts, sensornode_id, metric, value, source). The hot table —
grows by ~20 rows per 20s cycle. Append-only, never updated; no
``updated_at``.

Indexes: BRIN on ``ts`` (append-only monotonic timestamps are the
textbook BRIN use case); composite B-trees on ``(metric, ts DESC)`` and
``(sensornode_id, ts DESC)`` for the "latest value per metric/node"
query pattern.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    Column,
    Double,
    ForeignKey,
    Identity,
    Index,
    Text,
    text,
)
from sqlmodel import Field, SQLModel

from dirt_shared.models.enums import SENSOR_SOURCE_ENUM, SensorSource


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SensorReading(SQLModel, table=True):
    __tablename__ = "sensorreading"
    __table_args__ = (
        Index(
            "ix_sensorreading_ts",
            "ts",
            postgresql_using="brin",
        ),
        Index(
            "ix_sensorreading_metric_ts",
            "metric",
            "ts",
            postgresql_ops={"ts": "DESC"},
        ),
        Index(
            "ix_sensorreading_node_ts",
            "sensornode_id",
            "ts",
            postgresql_ops={"ts": "DESC"},
        ),
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
    sensornode_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("sensornode.id", ondelete="RESTRICT"),
            nullable=False,
        )
    )
    metric: str = Field(sa_column=Column(Text, nullable=False))
    value: float = Field(sa_column=Column(Double, nullable=False))
    source: SensorSource = Field(sa_column=Column(SENSOR_SOURCE_ENUM, nullable=False))
