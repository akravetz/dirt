"""Per-ESP32 metadata (and scratch rows for non-ESP32 locations).

One row per ``SensorLocation`` enum value, seeded by the initial Atlas
migration so that FKs from ``sensorreading`` / ``plant`` are satisfied
from day one. ESP32 nodes overwrite their own row via the ingest upsert;
``tent`` and ``reservoir`` rows stay minimally populated (NULL ip /
firmware) until real hardware owns them.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import TIMESTAMP, BigInteger, Column, Identity, Index, Text
from sqlalchemy.dialects.postgresql import INET
from sqlmodel import Field, SQLModel

from dirt_shared.models.enums import SENSOR_LOCATION_ENUM, SensorLocation


class SensorNode(SQLModel, table=True):
    __tablename__ = "sensornode"
    __table_args__ = (
        Index(
            "ix_sensornode_last_seen",
            "last_seen",
            postgresql_ops={"last_seen": "DESC"},
        ),
    )

    id: int | None = Field(
        default=None,
        sa_column=Column(BigInteger, Identity(always=True), primary_key=True),
    )
    location: SensorLocation = Field(
        sa_column=Column(SENSOR_LOCATION_ENUM, nullable=False, unique=True),
    )
    ip: str | None = Field(default=None, sa_column=Column(INET, nullable=True))
    firmware_version: str | None = Field(
        default=None, sa_column=Column(Text, nullable=True)
    )
    uptime_ms: int | None = Field(
        default=None, sa_column=Column(BigInteger, nullable=True)
    )
    last_seen: datetime | None = Field(
        default=None,
        sa_column=Column(TIMESTAMP(timezone=True), nullable=True),
    )
