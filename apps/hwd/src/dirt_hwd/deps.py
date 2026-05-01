"""FastAPI dependency providers for dirt_hwd.

Mirrors ``dirt_web.deps`` — endpoints take services + config via
``Depends(get_*)`` and tests override with ``app.dependency_overrides``.
"""

from fastapi import Request

from dirt_hwd.services.sensor_quality import SensorQualityService
from dirt_shared.config import Settings
from dirt_shared.services.readings import ReadingsService


def get_readings(request: Request) -> ReadingsService:
    return request.app.state.readings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_sensor_quality(request: Request) -> SensorQualityService:
    return request.app.state.sensor_quality
