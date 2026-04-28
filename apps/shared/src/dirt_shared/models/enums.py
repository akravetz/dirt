"""Python enums that map to Postgres native enum types.

Two parallel declarations per concept:

- A ``StrEnum`` subclass (e.g. ``PlantStatus``) — the Python type used in
  SQLModel field annotations, API responses, and log messages. Subclassing
  ``StrEnum`` makes JSON / logging / bind-param serialization transparent.

- A shared ``SAEnum`` instance (e.g. ``PLANT_STATUS_ENUM``) — the SQLAlchemy
  type that models reference via ``sa_column``. Centralizing these here
  means Atlas sees one ``CREATE TYPE`` DDL per enum (not N), and name
  collisions are impossible.

``values_callable`` is required because StrEnum's ``.name`` is the
UPPERCASE constant but the Postgres enum label must be the lowercase
``.value``.
"""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum


class GrowStage(StrEnum):
    VEG = "veg"
    FLOWER_EARLY = "flower_early"
    FLOWER_LATE = "flower_late"


class PlantStatus(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"
    RETIRED = "retired"


class PlantSticker(StrEnum):
    YELLOW = "yellow"
    ORANGE = "orange"
    PINK = "pink"
    BLUE = "blue"


class SensorLocation(StrEnum):
    TENT = "tent"
    PLANT_A = "plant-a"
    PLANT_B = "plant-b"
    PLANT_C = "plant-c"
    PLANT_D = "plant-d"
    RESERVOIR = "reservoir"


class SensorSource(StrEnum):
    ARDUINO = "arduino"
    ESP32 = "esp32"
    KASA = "kasa"
    GOVEE = "govee"
    MOCK = "mock"


def _lowercase_values(enum_cls: type[StrEnum]) -> list[str]:
    return [e.value for e in enum_cls]


GROW_STAGE_ENUM = SAEnum(
    GrowStage, name="grow_stage", values_callable=_lowercase_values
)
PLANT_STATUS_ENUM = SAEnum(
    PlantStatus, name="plant_status", values_callable=_lowercase_values
)
PLANT_STICKER_ENUM = SAEnum(
    PlantSticker, name="plant_sticker", values_callable=_lowercase_values
)
SENSOR_LOCATION_ENUM = SAEnum(
    SensorLocation, name="sensor_location", values_callable=_lowercase_values
)
SENSOR_SOURCE_ENUM = SAEnum(
    SensorSource, name="sensor_source", values_callable=_lowercase_values
)
