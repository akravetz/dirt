"""Per-(sensornode, metric) two-point linear calibration.

Auto-widened at ingest: raw_low is the wettest ADC reading ever seen,
raw_high the driest. Calibrated percentage:
    pct = 100 * (raw_high - raw) / (raw_high - raw_low)
clamped to [0, 100]. Degenerate ranges (raw_high <= raw_low) return
None — protected here by CHECK constraint.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    TIMESTAMP,
    BigInteger,
    CheckConstraint,
    Column,
    Double,
    ForeignKey,
    Identity,
    Text,
    UniqueConstraint,
    text,
)
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SensorCalibration(SQLModel, table=True):
    __tablename__ = "sensorcalibration"
    __table_args__ = (
        # Allow raw_high == raw_low (initial state after a single observation).
        # compute_calibrated_pct() treats equal-range as degenerate and returns None.
        CheckConstraint("raw_high >= raw_low", name="ck_sensorcalibration_range"),
        UniqueConstraint(
            "sensornode_id",
            "metric",
            name="uq_sensorcalibration_node_metric",
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    sensornode_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("sensornode.id", ondelete="CASCADE"),
            nullable=False,
        )
    )
    metric: str = Field(sa_column=Column(Text, nullable=False))
    raw_low: float = Field(sa_column=Column(Double, nullable=False))
    raw_high: float = Field(sa_column=Column(Double, nullable=False))
    updated_at: datetime = Field(
        default_factory=_utcnow,
        sa_column=Column(
            TIMESTAMP(timezone=True),
            nullable=False,
            server_default=text("now()"),
        ),
    )
