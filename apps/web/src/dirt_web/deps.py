"""FastAPI dependency providers — resolve service instances from app.state.

Endpoints take their service via ``Depends(get_foo)``. Tests override
behaviour with ``app.dependency_overrides[get_foo] = lambda: FakeFoo()``
instead of ``mock.patch``.

Each provider is a one-liner. The wiring is in ``dirt_web.app.create_app``.

Only three providers exist today because only three services are
reached via ``Depends(...)``: Settings, SnapshotsService, ReadingsService.
The rest of the ``CoreServices`` bundle (plants, grow, plant_detail,
humidifier_state, system_status) is still constructed and placed on
``app.state`` by ``dirt_shared.app_wiring.build_core_services`` for
future webapp-rewrite endpoints — add a provider here when an endpoint
actually needs one. Don't pre-scaffold: unused providers drift out of
sync with the services they wrap.
"""

from fastapi import Request

from dirt_shared.config import Settings
from dirt_shared.services.grow_state import GrowStateService
from dirt_shared.services.humidifier_state import HumidifierStateService
from dirt_shared.services.plants import PlantsService
from dirt_shared.services.readings import ReadingsService
from dirt_shared.services.snapshots import SnapshotsService
from dirt_shared.services.system_status import SystemStatusService


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_snapshots(request: Request) -> SnapshotsService:
    return request.app.state.snapshots


def get_readings(request: Request) -> ReadingsService:
    return request.app.state.readings


def get_grow(request: Request) -> GrowStateService:
    return request.app.state.grow


def get_humidifier_state(request: Request) -> HumidifierStateService:
    return request.app.state.humidifier_state


def get_plants(request: Request) -> PlantsService:
    return request.app.state.plants


def get_system_status(request: Request) -> SystemStatusService:
    return request.app.state.system_status
