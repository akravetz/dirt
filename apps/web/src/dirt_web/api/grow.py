"""Grow identity endpoint — drives the top-bar tag line."""

from dirt_contracts.webapp_v1.models import GrowCurrent, LightsState
from fastapi import APIRouter, Depends

from dirt_shared.services.grow_state import GrowStateService
from dirt_web.deps import get_grow

router = APIRouter(tags=["grow"])


@router.get("/api/grow/current", response_model=GrowCurrent)
async def grow_current(
    grow: GrowStateService = Depends(get_grow),
) -> GrowCurrent:
    """Return germination / day / stage / lights for the current grow."""
    payload = await grow.get_grow_current_payload()
    return GrowCurrent(
        germination_date=payload.germination_date,
        flower_start_date=payload.flower_start_date,
        day_number=payload.day_number,
        grow_week_number=payload.grow_week_number,
        flower_week_number=payload.flower_week_number,
        stage=payload.stage,
        strain=payload.strain,
        location=payload.location,
        plant_count=payload.plant_count,
        lights=LightsState(
            on=payload.lights.on,
            on_local=payload.lights_on_local.strftime("%H:%M:%S"),
            off_local=payload.lights_off_local.strftime("%H:%M:%S"),
            minutes_until_off=payload.lights.minutes_until_off,
            minutes_until_on=payload.lights.minutes_until_on,
        ),
    )
