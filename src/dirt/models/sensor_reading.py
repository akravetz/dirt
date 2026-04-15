from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SensorReading(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=_utcnow, index=True)
    location: str = Field(index=True)  # "tent", "plant-a", "plant-b", ...
    metric: str = Field(index=True)
    value: float
    source: str = "arduino"
