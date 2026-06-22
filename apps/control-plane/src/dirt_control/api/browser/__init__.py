from __future__ import annotations

from fastapi import APIRouter

from dirt_control.api.browser_schemas.admin import GatewayCredentialRotateResponse
from dirt_control.api.browser_schemas.assets import AssetResponse
from dirt_control.api.browser_schemas.auth import UserResponse
from dirt_control.api.browser_schemas.breeding_logbook import (
    BreedingLogbookBootstrapResponse,
    BreedingLogbookPlantDetailResponse,
    BreedingLogbookPlantListResponse,
    BreedingLogbookPlantRowResponse,
    BreedingLogbookSeedLotDetailResponse,
    BreedingLogbookSeedLotListResponse,
)
from dirt_control.api.browser_schemas.commands import CommandResponse
from dirt_control.api.browser_schemas.health import HealthResponse, SyncStatusResponse
from dirt_control.api.browser_schemas.metrics import (
    CurrentMetricResponse,
    MetricHistoryResponse,
    MetricPresentationMetricResponse,
    MetricPresentationResponse,
)
from dirt_control.api.browser_schemas.plants import (
    PlantDetailResponse,
    PlantMetricHistoryResponse,
    PlantSummaryResponse,
)
from dirt_control.api.browser_schemas.sites import SiteResponse
from dirt_control.api.browser_schemas.tents import (
    DeviceResponse,
    LightSchedulesResponse,
    TentResponse,
    TentStateResponse,
)

from . import (
    admin,
    assets,
    auth,
    breeding_logbook,
    commands,
    health,
    metrics,
    plants,
    sites,
    tents,
)

router = APIRouter(prefix="/api")
router.include_router(health.router)
router.include_router(auth.router)
router.include_router(sites.router)
router.include_router(tents.router)
router.include_router(metrics.router)
router.include_router(breeding_logbook.router)
router.include_router(plants.router)
router.include_router(assets.router)
router.include_router(commands.router)
router.include_router(admin.router)

__all__ = [
    "AssetResponse",
    "BreedingLogbookBootstrapResponse",
    "BreedingLogbookPlantDetailResponse",
    "BreedingLogbookPlantListResponse",
    "BreedingLogbookPlantRowResponse",
    "BreedingLogbookSeedLotDetailResponse",
    "BreedingLogbookSeedLotListResponse",
    "CommandResponse",
    "CurrentMetricResponse",
    "DeviceResponse",
    "GatewayCredentialRotateResponse",
    "HealthResponse",
    "LightSchedulesResponse",
    "MetricHistoryResponse",
    "MetricPresentationMetricResponse",
    "MetricPresentationResponse",
    "PlantDetailResponse",
    "PlantMetricHistoryResponse",
    "PlantSummaryResponse",
    "SiteResponse",
    "SyncStatusResponse",
    "TentResponse",
    "TentStateResponse",
    "UserResponse",
    "router",
]
