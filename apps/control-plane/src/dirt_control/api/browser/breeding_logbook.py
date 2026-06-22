from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, status

from dirt_control.api.browser_schemas.breeding_logbook import (
    BreedingBulkCullRequest,
    BreedingBulkMoveRequest,
    BreedingBulkPlantNoteRequest,
    BreedingBulkSexRequest,
    BreedingClonePlantsRequest,
    BreedingCreatePlantNoteRequest,
    BreedingCreateSeedLotRequest,
    BreedingGerminatePlantsRequest,
    BreedingLogbookBootstrapResponse,
    BreedingLogbookGroupBy,
    BreedingLogbookPlantDetailResponse,
    BreedingLogbookPlantListResponse,
    BreedingLogbookSeedLotDetailResponse,
    BreedingLogbookSeedLotListResponse,
    BreedingUpdatePlantFactsRequest,
    BreedingUpdateSeedLotInventoryRequest,
)
from dirt_control.api.browser_schemas.commands import CommandResponse
from dirt_control.api.browser_schemas.plants import PlantMetricHistoryResponse
from dirt_control.deps import get_clock, get_session, get_settings
from dirt_control.security import require_browser_user
from dirt_control.services.breeding_logbook import (
    bootstrap,
    bulk_create_plant_notes_command,
    bulk_cull_plants_command,
    bulk_move_plants_command,
    bulk_sex_plants_command,
    bulk_update_plant_facts_command,
    clone_plants_command,
    create_plant_note_command,
    create_seed_lot_command,
    germinate_plants_command,
    list_plants,
    list_seed_lots,
    plant_detail,
    plant_metric_history,
    seed_lot_detail,
    update_seed_lot_inventory_command,
)
from dirt_control.settings import CloudSettings

router = APIRouter()


@router.get(
    "/breeding-logbook/bootstrap",
    response_model=BreedingLogbookBootstrapResponse,
)
async def breeding_logbook_bootstrap(
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> BreedingLogbookBootstrapResponse:
    return await bootstrap(
        session, site_id=settings.default_site_id, today=clock().date()
    )


@router.get(
    "/breeding-logbook/plants",
    response_model=BreedingLogbookPlantListResponse,
)
async def breeding_logbook_plants(
    include_culled: bool = False,
    group_by: BreedingLogbookGroupBy = "stage",
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> BreedingLogbookPlantListResponse:
    return await list_plants(
        session,
        site_id=settings.default_site_id,
        include_culled=include_culled,
        group_by=group_by,
        today=clock().date(),
    )


@router.get(
    "/breeding-logbook/seed-lots",
    response_model=BreedingLogbookSeedLotListResponse,
)
async def breeding_logbook_seed_lots(
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
) -> BreedingLogbookSeedLotListResponse:
    return await list_seed_lots(session, site_id=settings.default_site_id)


@router.get(
    "/breeding-logbook/seed-lots/{seed_lot_id}",
    response_model=BreedingLogbookSeedLotDetailResponse,
)
async def breeding_logbook_seed_lot_detail(
    seed_lot_id: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
) -> BreedingLogbookSeedLotDetailResponse:
    return await seed_lot_detail(
        session,
        site_id=settings.default_site_id,
        seed_lot_id=seed_lot_id,
    )


@router.get(
    "/breeding-logbook/plants/{plant_key}/metrics/history",
    response_model=PlantMetricHistoryResponse,
)
async def breeding_logbook_plant_metric_history(
    plant_key: str,
    range: str = "24h",
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> PlantMetricHistoryResponse:
    return await plant_metric_history(
        session,
        site_id=settings.default_site_id,
        plant_key=plant_key,
        range_key=range,
        now=clock(),
    )


@router.get(
    "/breeding-logbook/plants/{plant_key}",
    response_model=BreedingLogbookPlantDetailResponse,
)
async def breeding_logbook_plant_detail(
    plant_key: str,
    _: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> BreedingLogbookPlantDetailResponse:
    return await plant_detail(
        session,
        site_id=settings.default_site_id,
        plant_key=plant_key,
        today=clock().date(),
    )


@router.post(
    "/breeding-logbook/seed-lots",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def create_breeding_seed_lot(
    body: BreedingCreateSeedLotRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    return await create_seed_lot_command(
        body,
        user=user,
        settings=settings,
        session=session,
        now=clock(),
    )


@router.post(
    "/breeding-logbook/seed-lots/{seed_lot_id}:update",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def update_breeding_seed_lot_inventory(  # noqa: PLR0913
    seed_lot_id: str,
    body: BreedingUpdateSeedLotInventoryRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    return await update_seed_lot_inventory_command(
        seed_lot_id,
        body,
        user=user,
        settings=settings,
        session=session,
        now=clock(),
    )


@router.post(
    "/breeding-logbook/plants:germinate",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def germinate_breeding_plants(
    body: BreedingGerminatePlantsRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    return await germinate_plants_command(
        body,
        user=user,
        settings=settings,
        session=session,
        now=clock(),
    )


@router.post(
    "/breeding-logbook/plants:clone",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def clone_breeding_plants(
    body: BreedingClonePlantsRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    return await clone_plants_command(
        body,
        user=user,
        settings=settings,
        session=session,
        now=clock(),
    )


@router.post(
    "/breeding-logbook/plants:bulk-sex",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def bulk_sex_breeding_plants(
    body: BreedingBulkSexRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    return await bulk_sex_plants_command(
        body,
        user=user,
        settings=settings,
        session=session,
        now=clock(),
    )


@router.post(
    "/breeding-logbook/plants:bulk-move",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def bulk_move_breeding_plants(
    body: BreedingBulkMoveRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    return await bulk_move_plants_command(
        body,
        user=user,
        settings=settings,
        session=session,
        now=clock(),
    )


@router.post(
    "/breeding-logbook/plants:update-facts",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def update_breeding_plant_facts(
    body: BreedingUpdatePlantFactsRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    return await bulk_update_plant_facts_command(
        body,
        user=user,
        settings=settings,
        session=session,
        now=clock(),
    )


@router.post(
    "/breeding-logbook/plants:bulk-cull",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def bulk_cull_breeding_plants(
    body: BreedingBulkCullRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    return await bulk_cull_plants_command(
        body,
        user=user,
        settings=settings,
        session=session,
        now=clock(),
    )


@router.post(
    "/breeding-logbook/plants/{plant_key}/notes",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def create_breeding_plant_note(  # noqa: PLR0913
    plant_key: str,
    body: BreedingCreatePlantNoteRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    return await create_plant_note_command(
        plant_key,
        body,
        user=user,
        settings=settings,
        session=session,
        now=clock(),
    )


@router.post(
    "/breeding-logbook/plants:bulk-note",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def bulk_create_breeding_plant_notes(
    body: BreedingBulkPlantNoteRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    return await bulk_create_plant_notes_command(
        body,
        user=user,
        settings=settings,
        session=session,
        now=clock(),
    )
