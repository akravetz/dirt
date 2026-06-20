from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends

from dirt_control.api.browser_schemas.plants import (
    PlantDetailResponse,
    PlantMetricHistoryResponse,
    PlantSummaryResponse,
)
from dirt_control.deps import get_clock, get_session, get_settings
from dirt_control.security import require_browser_user
from dirt_control.services.browser_plants import (
    get_plant_detail_response,
    get_plant_metric_history_response,
    list_plant_summaries,
)
from dirt_control.settings import CloudSettings

router = APIRouter()


@router.get("/tents/{source_tent_id}/plants", response_model=list[PlantSummaryResponse])
async def plants(
    source_tent_id: int,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
) -> list[PlantSummaryResponse]:
    return await list_plant_summaries(
        session, site_id=settings.default_site_id, source_tent_id=source_tent_id
    )


@router.get(
    "/tents/{source_tent_id}/plants/{plant_id}", response_model=PlantDetailResponse
)
async def plant_detail(
    source_tent_id: int,
    plant_id: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
) -> PlantDetailResponse:
    return await get_plant_detail_response(
        session,
        site_id=settings.default_site_id,
        source_tent_id=source_tent_id,
        plant_id=plant_id,
    )


@router.get(
    "/tents/{source_tent_id}/plants/{plant_id}/metrics/history",
    response_model=PlantMetricHistoryResponse,
)
async def plant_metric_history(  # noqa: PLR0913
    source_tent_id: int,
    plant_id: str,
    range: str = "24h",
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> PlantMetricHistoryResponse:
    return await get_plant_metric_history_response(
        session,
        site_id=settings.default_site_id,
        source_tent_id=source_tent_id,
        plant_id=plant_id,
        range_key=range,
        now=clock(),
    )
