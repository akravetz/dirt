from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends

from dirt_control.api.browser_schemas.metrics import (
    CurrentMetricResponse,
    MetricHistoryResponse,
    MetricPresentationResponse,
)
from dirt_control.deps import get_clock, get_session, get_settings
from dirt_control.security import require_browser_user
from dirt_control.services.browser_metrics import (
    current_metrics as current_metrics_service,
)
from dirt_control.services.browser_metrics import (
    metric_history as metric_history_service,
)
from dirt_control.services.browser_metrics import (
    metric_presentation as metric_presentation_service,
)
from dirt_control.settings import CloudSettings

router = APIRouter()


@router.get(
    "/tents/{source_tent_id}/metrics/current",
    response_model=list[CurrentMetricResponse],
)
async def current_metrics(
    source_tent_id: int,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
) -> list[CurrentMetricResponse]:
    return await current_metrics_service(
        session, site_id=settings.default_site_id, source_tent_id=source_tent_id
    )


@router.get(
    "/tents/{source_tent_id}/metrics/presentation",
    response_model=MetricPresentationResponse,
)
async def metric_presentation(
    source_tent_id: int,
    _: str = Depends(require_browser_user),
    session=Depends(get_session),
) -> MetricPresentationResponse:
    _ = source_tent_id
    return await metric_presentation_service(session)


@router.get(
    "/tents/{source_tent_id}/metrics/history", response_model=MetricHistoryResponse
)
async def metric_history(  # noqa: PLR0913
    source_tent_id: int,
    metric: str,
    device_id: str | None = None,
    capability_id: str | None = None,
    range: str = "24h",
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> MetricHistoryResponse:
    return await metric_history_service(
        session,
        site_id=settings.default_site_id,
        source_tent_id=source_tent_id,
        metric=metric,
        range_key=range,
        device_id=device_id,
        capability_id=capability_id,
        now=clock(),
    )
