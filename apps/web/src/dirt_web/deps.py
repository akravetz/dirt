"""FastAPI dependency providers — resolve service instances from app.state.

Endpoints take their service via ``Depends(get_foo)``. Tests override
behaviour with ``app.dependency_overrides[get_foo] = lambda: FakeFoo()``
instead of ``mock.patch``.

Each provider is a one-liner. The wiring is in ``dirt_web.app.create_app``.

Only three providers exist today because only three services are
reached via ``Depends(...)``: Settings, SnapshotsService, ReadingsService.
The rest of the ``CoreServices`` bundle (plants, grow, plant_detail,
system_status) is still constructed and placed on ``app.state`` by
``dirt_shared.app_wiring.build_core_services`` for future webapp-rewrite
endpoints — add a provider here when an endpoint actually needs one.
Don't pre-scaffold: unused providers drift out of sync with the
services they wrap.
"""

from fastapi import Request

from dirt_shared.camera import CameraCaptureError, ObsbotDaemonCameraSource
from dirt_shared.config import Settings
from dirt_shared.services.capture import FrameCapturer
from dirt_shared.services.commands import CommandService
from dirt_shared.services.grow_state import GrowStateService
from dirt_shared.services.light_schedules import LightScheduleService
from dirt_shared.services.plants import PlantsService
from dirt_shared.services.ptz import PTZService
from dirt_shared.services.readings import ReadingsService
from dirt_shared.services.scope_catalog import ScopeCatalogService
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


def get_light_schedules(request: Request) -> LightScheduleService:
    return request.app.state.light_schedules


def get_plants(request: Request) -> PlantsService:
    return request.app.state.plants


def get_system_status(request: Request) -> SystemStatusService:
    return request.app.state.system_status


def get_commands(request: Request) -> CommandService:
    return request.app.state.commands


def get_scope_catalog(request: Request) -> ScopeCatalogService:
    return request.app.state.scope_catalog


def get_ptz(request: Request) -> PTZService:
    return request.app.state.ptz


def get_frame_capturer(request: Request) -> FrameCapturer:
    """Camera-daemon frame capture through the shared camera source.

    Tests override with ``app.dependency_overrides[get_frame_capturer]
    = lambda: fake_capturer`` to avoid touching the camera socket.
    """
    source = ObsbotDaemonCameraSource(
        socket_path=get_settings(request).capture().camera_socket_path
    )

    async def capture() -> bytes | None:
        try:
            return (await source.capture()).jpeg_bytes
        except CameraCaptureError:
            return None

    return capture
