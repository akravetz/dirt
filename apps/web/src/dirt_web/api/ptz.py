"""PTZ endpoints — thin wrapper over ``dirt_shared.services.ptz.PTZService``.

All four endpoints (state, preset, look, zoom) share one ``PTZService``
instance, resolved via ``Depends(get_ptz)`` from ``dirt_web.deps``.
"""

from __future__ import annotations

from dirt_contracts.webapp_v1.models import PTZState
from fastapi import APIRouter, Depends

from dirt_shared.services.ptz import PTZService
from dirt_web.deps import get_ptz

router = APIRouter(prefix="/api/ptz", tags=["ptz"])


@router.get("/state", response_model=PTZState)
async def ptz_state(ptz: PTZService = Depends(get_ptz)) -> PTZState:
    """Current motor position + preset list for the PTZ panel."""
    payload = await ptz.get_state()
    return PTZState.model_validate(payload)
