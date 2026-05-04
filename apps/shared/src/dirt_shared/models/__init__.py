"""All SQLModel table classes + enum types.

Imported side-effect-only by ``dirt_shared.db`` and by
``scripts/atlas-load-sqlmodel.py`` so that SQLModel metadata is populated
before it's inspected.
"""

from __future__ import annotations

from dirt_shared.models.command import Command
from dirt_shared.models.device import Capability, Device
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
from dirt_shared.models.grow_run import GrowRun
from dirt_shared.models.grow_state import GrowState
from dirt_shared.models.plant import Plant
from dirt_shared.models.schedule import Schedule
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.models.site import Site
from dirt_shared.models.snapshot import Snapshot
from dirt_shared.models.tent import Tent
from dirt_shared.models.zone import Zone

__all__ = [
    "GROW_STAGE_ENUM",
    "PLANT_STATUS_ENUM",
    "PLANT_STICKER_ENUM",
    "SENSOR_LOCATION_ENUM",
    "SENSOR_SOURCE_ENUM",
    "Capability",
    "Command",
    "Device",
    "GrowRun",
    "GrowStage",
    "GrowState",
    "Plant",
    "PlantStatus",
    "PlantSticker",
    "Schedule",
    "SensorCalibration",
    "SensorLocation",
    "SensorNode",
    "SensorReading",
    "SensorSource",
    "Site",
    "Snapshot",
    "Tent",
    "Zone",
]
