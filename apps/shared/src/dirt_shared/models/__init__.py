"""All SQLModel table classes + enum types.

Imported side-effect-only by ``dirt_shared.db`` and by
``scripts/atlas-load-sqlmodel.py`` so that SQLModel metadata is populated
before it's inspected.
"""
from __future__ import annotations

from dirt_shared.models.enums import (
    GROW_STAGE_ENUM,
    PLANT_STATUS_ENUM,
    PLANT_STICKER_ENUM,
    SENSOR_LOCATION_ENUM,
    SENSOR_SOURCE_ENUM,
    GrowStage,
    PlantStatus,
    PlantSticker,
    SensorLocation,
    SensorSource,
)
from dirt_shared.models.grow_state import GrowState
from dirt_shared.models.plant import Plant
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.models.snapshot import Snapshot

__all__ = [
    "GROW_STAGE_ENUM",
    "PLANT_STATUS_ENUM",
    "PLANT_STICKER_ENUM",
    "SENSOR_LOCATION_ENUM",
    "SENSOR_SOURCE_ENUM",
    "GrowStage",
    "GrowState",
    "Plant",
    "PlantStatus",
    "PlantSticker",
    "SensorCalibration",
    "SensorLocation",
    "SensorNode",
    "SensorReading",
    "SensorSource",
    "Snapshot",
]
