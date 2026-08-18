from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from dirt_control.api.browser_schemas.plants import (
    PlantMetricHistoryCollectionResponse,
    PlantSummaryResponse,
)
from dirt_control.deps import get_clock, get_session, get_settings
from dirt_control.security import require_browser_user
from dirt_control.services.browser_plants import (
    list_plant_summaries,
)
from dirt_control.services.plant_metrics import (
    get_plant_metric_history_collection_response,
)
from dirt_control.settings import CloudSettings
from dirt_shared.metric_history import MetricHistoryRange

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
    "/tents/{source_tent_id}/plants/metrics/history",
    response_model=PlantMetricHistoryCollectionResponse,
)
async def plant_metric_history_collection(
    source_tent_id: int,
    range_key: Annotated[MetricHistoryRange, Query(alias="range")] = "24h",
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> PlantMetricHistoryCollectionResponse:
    return await get_plant_metric_history_collection_response(
        session,
        site_id=settings.default_site_id,
        source_tent_id=source_tent_id,
        range_key=range_key,
        now=clock(),
    )
