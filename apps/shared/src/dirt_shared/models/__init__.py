"""All SQLModel table classes + enum types.

Imported side-effect-only by ``dirt_shared.db`` and by
``scripts/atlas-load-sqlmodel.py`` so that SQLModel metadata is populated
before it's inspected.
"""

from __future__ import annotations

from dirt_shared.models.cloud_gateway import CloudOutbox, CloudSyncCursor
from dirt_shared.models.command import Command
from dirt_shared.models.device import Capability, Device
from dirt_shared.models.enums import (
    SENSOR_SOURCE_ENUM,
    SensorSource,
)
from dirt_shared.models.irrigation import IrrigationRun, IrrigationScheduleItem
from dirt_shared.models.metric_presentation import MetricPresentation
from dirt_shared.models.plant import (
    CrossEvent,
    Plant,
    PlantEvent,
    PlantLine,
    PlantLocationHistory,
    PlantMetricStream,
    PlantNote,
    SeedLot,
)
from dirt_shared.models.schedule import Schedule
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.models.site import Site
from dirt_shared.models.snapshot import Snapshot
from dirt_shared.models.tent import Tent
from dirt_shared.models.zone import Zone

__all__ = [
    "SENSOR_SOURCE_ENUM",
    "Capability",
    "CloudOutbox",
    "CloudSyncCursor",
    "Command",
    "CrossEvent",
    "Device",
    "IrrigationRun",
    "IrrigationScheduleItem",
    "MetricPresentation",
    "Plant",
    "PlantEvent",
    "PlantLine",
    "PlantLocationHistory",
    "PlantMetricStream",
    "PlantNote",
    "Schedule",
    "SeedLot",
    "SensorCalibration",
    "SensorReading",
    "SensorSource",
    "Site",
    "Snapshot",
    "Tent",
    "Zone",
]
