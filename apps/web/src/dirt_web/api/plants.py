"""Plant endpoints — dashboard strip + drawer + moisture history.

``GET /api/plants`` lists A–D for the dashboard strip with each plant's
latest calibrated moisture. ``PlantsService.list_plants`` already
returns the per-plant summary with the DB-joined moisture pct; this
module converts the dataclass values into the generated Pydantic
``PlantsResponse`` model the contract freezes.
"""

from __future__ import annotations

from dirt_contracts.webapp_v1.models import (
    Plant,
    PlantCode,
    PlantsResponse,
    PlantStatus,
    PlantStickerColor,
)
from fastapi import APIRouter, Depends

from dirt_shared.services.grow_state import GrowStateService
from dirt_shared.services.plants import PlantsService, PlantSummary
from dirt_web.deps import get_grow, get_plants

router = APIRouter(tags=["plants"])


def _plant_from_summary(s: PlantSummary) -> Plant:
    return Plant(
        code=PlantCode(s.code),
        name=s.name,
        sticker_color=PlantStickerColor(s.sticker_color.value),
        status=PlantStatus(s.status.value),
        purple=s.purple,
        moisture_pct=s.moisture_pct,
        moisture_ts=s.moisture_ts,
    )


@router.get("/api/plants", response_model=PlantsResponse)
async def plants_list(
    plants: PlantsService = Depends(get_plants),
    grow: GrowStateService = Depends(get_grow),
) -> PlantsResponse:
    """Dashboard plants strip: A–D with latest calibrated moisture."""
    summaries = await plants.list_plants()
    payload = await grow.get_grow_current_payload()
    return PlantsResponse(
        day=payload.day_number,
        plants=[_plant_from_summary(s) for s in summaries],
    )
