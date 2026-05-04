"""Per sensor capability two-point linear calibration.

Auto-widened at ingest: raw_low is the wettest ADC reading ever seen,
raw_high the driest. Calibrated percentage:
    pct = 100 * (raw_high - raw) / (raw_high - raw_low)
clamped to [0, 100]. Degenerate ranges (raw_high <= raw_low) return
None — protected here by CHECK constraint.

``capability_id`` is the canonical scoped owner for new and backfilled rows.
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
    Index,
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
            "capability_id",
            "metric",
            name="uq_sensorcalibration_capability_metric",
        ),
        Index("ix_sensorcalibration_capability_id", "capability_id"),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    capability_id: int = Field(
        sa_column=Column(
            BigInteger,
            ForeignKey("capability.id", ondelete="RESTRICT"),
            nullable=False,
        ),
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
