"""Grow identity endpoint — drives the top-bar tag line."""

from datetime import time

from dirt_contracts.webapp_v1.models import (
    GrowCurrent,
    GrowFlowerFlipRequest,
    LightsState,
)
from fastapi import APIRouter, Depends, HTTPException

from dirt_shared.services.grow_state import GrowCurrentPayload, GrowStateService
from dirt_web.deps import get_grow

router = APIRouter(tags=["grow"])


def _grow_current_response(payload: GrowCurrentPayload) -> GrowCurrent:
    return GrowCurrent(
        germination_date=payload.germination_date,
        flower_start_date=payload.flower_start_date,
        day_number=payload.day_number,
        grow_week_number=payload.grow_week_number,
        flower_week_number=payload.flower_week_number,
        stage=payload.stage,
        strain=payload.strain,
        plant_count=payload.plant_count,
        lights=LightsState(
            on=payload.lights.on,
            on_local=payload.lights_on_local.strftime("%H:%M:%S"),
            off_local=payload.lights_off_local.strftime("%H:%M:%S"),
            minutes_until_off=payload.lights.minutes_until_off,
            minutes_until_on=payload.lights.minutes_until_on,
        ),
    )


@router.get("/api/grow/current", response_model=GrowCurrent)
async def grow_current(
    grow: GrowStateService = Depends(get_grow),
) -> GrowCurrent:
    """Return germination / day / stage / lights for the current grow."""
    payload = await grow.get_grow_current_payload()
    return _grow_current_response(payload)


@router.post("/api/grow/flower-flip", response_model=GrowCurrent)
async def grow_flower_flip(
    payload: GrowFlowerFlipRequest,
    grow: GrowStateService = Depends(get_grow),
) -> GrowCurrent:
    """Set first flower day and switch the current grow to a 12/12 schedule."""
    try:
        lights_on_local = time.fromisoformat(payload.lights_on_local)
        lights_off_local = time.fromisoformat(payload.lights_off_local)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid local time") from exc

    try:
        current = await grow.flip_to_flower(
            flower_start_date=payload.flower_start_date,
            lights_on_local=lights_on_local,
            lights_off_local=lights_off_local,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _grow_current_response(current)
