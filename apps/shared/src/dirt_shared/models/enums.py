"""Python enums that map to Postgres native enum types."""

from __future__ import annotations

from enum import StrEnum

from sqlalchemy import Enum as SAEnum


class SensorSource(StrEnum):
    AC_INFINITY = "ac_infinity"
    ARDUINO = "arduino"
    ESP32 = "esp32"
    KASA = "kasa"
    GOVEE = "govee"
    MOCK = "mock"


def _lowercase_values(enum_cls: type[StrEnum]) -> list[str]:
    return [e.value for e in enum_cls]


SENSOR_SOURCE_ENUM = SAEnum(
    SensorSource, name="sensor_source", values_callable=_lowercase_values
)
