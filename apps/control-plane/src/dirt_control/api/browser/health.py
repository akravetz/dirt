from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends

from dirt_control.api.browser_schemas.health import HealthResponse, SyncStatusResponse
from dirt_control.deps import get_clock, get_session, get_settings
from dirt_control.security import require_browser_user
from dirt_control.services.browser_health import (
    health_status,
    sync_status_response,
)
from dirt_control.settings import CloudSettings

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health(
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> HealthResponse:
    return await health_status(session, settings=settings, now=clock())


@router.get("/sync/status", response_model=SyncStatusResponse)
async def sync_status(
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> SyncStatusResponse:
    return await sync_status_response(session, settings=settings, now=clock())
