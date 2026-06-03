from __future__ import annotations

from pathlib import Path

from dirt_hwd.app import create_app
from dirt_hwd.services.climate_controller import ClimateControllerService
from dirt_hwd.services.fan_controller import FanTrimLoopService
from dirt_hwd.services.humidifier import HumidifierLoopService
from dirt_hwd.services.kasa_schedule import ScheduledKasaActuatorService
from dirt_shared.config import Settings


def test_default_background_services_use_unified_climate_authority(
    app_engine,
    tmp_path: Path,
) -> None:
    app = create_app(
        engine=app_engine,
        settings=Settings(_env_file=None, DIRT_DATA_DIR=tmp_path),
        background_services=None,
    )

    service_types = [type(service) for service in app.state.background_services]

    assert ClimateControllerService in service_types
    assert HumidifierLoopService not in service_types
    assert FanTrimLoopService not in service_types
    assert ScheduledKasaActuatorService in service_types
