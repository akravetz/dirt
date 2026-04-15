from datetime import datetime

from sqlmodel import Field, SQLModel


class SensorNode(SQLModel, table=True):
    """Per-node metadata. One row per sensor node, keyed by location.

    Upserted when a node POSTs a reading. Rows are not created eagerly —
    only after a node has reported at least once.
    """

    location: str = Field(primary_key=True)  # "tent" | "plant-a" | "plant-b" | ...
    ip: str | None = None
    firmware_version: str | None = None
    uptime_ms: int | None = None
    last_seen: datetime | None = Field(default=None, index=True)
