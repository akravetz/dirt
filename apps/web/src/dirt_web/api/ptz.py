"""PTZ endpoints — thin wrapper over ``dirt_shared.services.ptz.PTZService``.

All four endpoints (state, preset, look, zoom) share one ``PTZService``
instance, resolved via ``Depends(get_ptz)`` from ``dirt_web.deps``.
"""

from __future__ import annotations

from dirt_contracts.webapp_v1.models import (
    PTZApplied,
    PTZLookRequest,
    PTZState,
    PTZZoomRequest,
    PTZZoomResponse,
)
from fastapi import APIRouter, Depends, HTTPException

from dirt_shared.services.ptz import PTZService, UnknownPresetError
from dirt_web.deps import get_ptz

router = APIRouter(prefix="/api/ptz", tags=["ptz"])


@router.get("/state", response_model=PTZState)
async def ptz_state(ptz: PTZService = Depends(get_ptz)) -> PTZState:
    """Current motor position + preset list for the PTZ panel."""
    payload = await ptz.get_state()
    return PTZState.model_validate(payload)


@router.post("/preset/{id}", response_model=PTZApplied)
async def ptz_preset(
    id: str,
    ptz: PTZService = Depends(get_ptz),
) -> PTZApplied:
    """Move to the named preset. 404 when the id is not in camera.json."""
    try:
        payload = await ptz.apply_preset(id)
    except UnknownPresetError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return PTZApplied.model_validate(payload)


@router.post("/look", response_model=PTZApplied)
async def ptz_look(
    req: PTZLookRequest,
    ptz: PTZService = Depends(get_ptz),
) -> PTZApplied:
    """Click-to-look. Normalized frame coords x/y ∈ [-0.5, 0.5]."""
    payload = await ptz.look_at_normalized(req.x, req.y)
    return PTZApplied.model_validate(payload)


@router.post("/zoom", response_model=PTZZoomResponse)
async def ptz_zoom(
    req: PTZZoomRequest,
    ptz: PTZService = Depends(get_ptz),
) -> PTZZoomResponse:
    """Set zoom absolutely (``zoom``) or relatively (``delta``). XOR required."""
    has_zoom = req.zoom is not None
    has_delta = req.delta is not None
    if has_zoom == has_delta:
        raise HTTPException(
            status_code=400,
            detail="provide exactly one of 'zoom' or 'delta'",
        )
    payload = await ptz.zoom_to(req.zoom) if has_zoom else await ptz.zoom_by(req.delta)
    return PTZZoomResponse.model_validate(payload)
