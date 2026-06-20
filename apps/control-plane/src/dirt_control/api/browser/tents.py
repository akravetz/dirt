from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends

from dirt_control.api.browser_schemas.tents import (
    DeviceResponse,
    LightSchedulesResponse,
    TentResponse,
    TentStateResponse,
)
from dirt_control.deps import get_clock, get_session, get_settings
from dirt_control.security import require_browser_user
from dirt_control.services.browser_tents import (
    get_tent_state,
    list_devices,
    list_light_schedules,
    list_tents,
)
from dirt_control.settings import CloudSettings

router = APIRouter()


@router.get("/tents", response_model=list[TentResponse])
async def tents(
    site_id: str | None = None,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
) -> list[TentResponse]:
    return await list_tents(session, site_id=site_id or settings.default_site_id)


@router.get("/tents/{source_tent_id}/state", response_model=TentStateResponse)
async def tent_state(
    source_tent_id: int,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
) -> TentStateResponse:
    return await get_tent_state(
        session, site_id=settings.default_site_id, source_tent_id=source_tent_id
    )


@router.get("/tents/{source_tent_id}/devices", response_model=list[DeviceResponse])
async def devices(
    source_tent_id: int,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
) -> list[DeviceResponse]:
    return await list_devices(
        session, site_id=settings.default_site_id, source_tent_id=source_tent_id
    )


@router.get(
    "/tents/{source_tent_id}/lights/schedules",
    response_model=LightSchedulesResponse,
)
async def light_schedules(
    source_tent_id: int,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> LightSchedulesResponse:
    return await list_light_schedules(
        session,
        site_id=settings.default_site_id,
        source_tent_id=source_tent_id,
        now=clock(),
    )
