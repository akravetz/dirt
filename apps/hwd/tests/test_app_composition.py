from __future__ import annotations

from pathlib import Path

from dirt_hwd.app import create_app
from dirt_hwd.services.kasa_schedule import ScheduledKasaActuatorService
from dirt_hwd.services.thermoforge import ScheduledThermoForgeService
from dirt_shared.config import Settings


def test_default_background_services_include_scheduled_thermoforge(
    app_engine,
    tmp_path: Path,
) -> None:
    app = create_app(
        engine=app_engine,
        settings=Settings(_env_file=None, DIRT_DATA_DIR=tmp_path),
        background_services=None,
    )

    service_types = [type(service) for service in app.state.background_services]

    assert ScheduledThermoForgeService in service_types
    assert service_types.index(ScheduledKasaActuatorService) < service_types.index(
        ScheduledThermoForgeService
    )
