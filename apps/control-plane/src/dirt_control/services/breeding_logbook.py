from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dirt_control.api.browser_schemas.breeding_logbook import (
    BreedingBulkCullRequest,
    BreedingBulkMoveRequest,
    BreedingBulkSexRequest,
    BreedingClonePlantsRequest,
    BreedingCreatePlantNoteRequest,
    BreedingCreateSeedLotRequest,
    BreedingGerminatePlantsRequest,
    BreedingLogbookBootstrapResponse,
    BreedingLogbookGroupBy,
    BreedingLogbookLineageResponse,
    BreedingLogbookLocationOptionResponse,
    BreedingLogbookLookupResponse,
    BreedingLogbookPlantDetailResponse,
    BreedingLogbookPlantJournalEventResponse,
    BreedingLogbookPlantListResponse,
    BreedingLogbookPlantMetricSummaryResponse,
    BreedingLogbookPlantRowResponse,
    BreedingLogbookPlantStageKey,
    BreedingLogbookSeedLotListResponse,
    BreedingLogbookSeedLotSummaryResponse,
)
from dirt_control.api.browser_schemas.commands import CommandResponse
from dirt_control.api.browser_schemas.metrics import METRIC_HISTORY_RANGES
from dirt_control.api.browser_schemas.plants import (
    PlantMetricHistoryResponse,
    PlantMetricStreamResponse,
)
from dirt_control.models import (
    CloudCrossEvent,
    CloudPlant,
    CloudPlantEvent,
    CloudPlantLine,
    CloudPlantLocation,
    CloudPlantNote,
    CloudSeedLot,
    CloudTent,
)
from dirt_control.services.browser_commands import (
    BREEDING_SITE_WIDE_TENT_ID,
    enqueue_breeding_command,
    storage_compat_tent_id,
)
from dirt_control.services.browser_plants import (
    PlantProjection,
    active_plant_metric_streams,
    active_plant_stream_counts,
    latest_metrics_by_stream,
    metric_rollups_by_stream,
    metric_stream_key,
    plant_metric_history_stream_response,
    plant_metric_stream_responses,
)
from dirt_control.services.browser_tents import (
    cloud_tents_by_source_id,
    get_cloud_tent_by_source_id,
    required_location_source_tent_id,
    required_source_tent_id,
    tent_display_name,
)
from dirt_control.settings import CloudSettings
from dirt_shared.cloud_contract import (
    BreedingBulkCullPayload,
    BreedingBulkMovePayload,
    BreedingBulkSexPayload,
    BreedingClonePlantsPayload,
    BreedingCreatePlantNotePayload,
    BreedingCreateSeedLotPayload,
    BreedingGerminatePlantsPayload,
)


@dataclass(frozen=True)
class BreedingLogbookPlantProjection:
    plant: CloudPlant
    location: CloudPlantLocation
    tent: CloudTent | None
    line: CloudPlantLine | None
    seed_lot: CloudSeedLot | None
    seed_lot_line: CloudPlantLine | None


async def bootstrap(
    session: AsyncSession, *, site_id: str, today: date
) -> BreedingLogbookBootstrapResponse:
    tents = (
        await session.execute(
            select(CloudTent)
            .where(
                CloudTent.site_id == site_id,
                CloudTent.is_active.is_(True),
                CloudTent.source_tent_id.is_not(None),
            )
            .order_by(CloudTent.source_tent_id, CloudTent.name)
        )
    ).scalars()
    return BreedingLogbookBootstrapResponse(
        today=today,
        today_label=today.strftime("%m/%d/%y"),
        plant_sexes=[
            BreedingLogbookLookupResponse(
                key=key,
                display_name=display_name,
                display_order=display_order,
            )
            for key, display_name, display_order in (
                ("unknown", "Unknown", 10),
                ("male", "Male", 20),
                ("female", "Female", 30),
                ("herm", "Hermaphrodite", 40),
                ("reversed", "Reversed", 50),
            )
        ],
        seed_lot_sex_types=[
            BreedingLogbookLookupResponse(
                key=key,
                display_name=display_name,
                display_order=display_order,
            )
            for key, display_name, display_order in (
                ("unknown", "Unknown", 10),
                ("feminized", "Feminized", 20),
                ("regular", "Regular", 30),
            )
        ],
        stages=[
            BreedingLogbookLookupResponse(
                key=key,
                display_name=display_name,
                display_order=display_order,
            )
            for key, display_name, display_order in (
                ("germinating", "Germinating", 10),
                ("veg", "Veg", 20),
                ("flower", "Flower", 30),
                ("breeding", "Breeding", 40),
                ("harvested", "Harvested", 50),
                ("culled", "Culled", 60),
            )
        ],
        locations=[
            BreedingLogbookLocationOptionResponse(
                source_tent_id=required_source_tent_id(tent),
                display_name=tent.name,
                role=tent.role,
                grid_position=None,
            )
            for tent in tents
        ],
    )


async def list_plants(
    session: AsyncSession,
    *,
    site_id: str,
    include_culled: bool,
    group_by: BreedingLogbookGroupBy,
    today: date,
) -> BreedingLogbookPlantListResponse:
    plant_rows = await breeding_logbook_plants(
        session,
        site_id=site_id,
        include_culled=include_culled,
    )
    stream_counts = await breeding_logbook_stream_counts(
        session,
        site_id=site_id,
        plants=plant_rows,
    )
    plant_ids = [row.plant.source_plant_id for row in plant_rows]
    latest_notes = await breeding_logbook_latest_notes(
        session,
        site_id=site_id,
        plant_ids=plant_ids,
    )
    latest_events = await breeding_logbook_latest_events(
        session,
        site_id=site_id,
        plant_ids=plant_ids,
    )
    rows = [
        breeding_logbook_plant_row_response(
            row,
            telemetry_stream_count=stream_counts.get(row.plant.source_plant_id, 0),
            latest_note=latest_notes.get(row.plant.source_plant_id),
            latest_event=latest_events.get(row.plant.source_plant_id),
            today=today,
        )
        for row in plant_rows
    ]
    return BreedingLogbookPlantListResponse(
        active_count=sum(1 for row in rows if row.stage_key != "culled"),
        culled_count=sum(1 for row in rows if row.stage_key == "culled"),
        group_by=group_by,
        plants=rows,
    )


async def list_seed_lots(
    session: AsyncSession, *, site_id: str
) -> BreedingLogbookSeedLotListResponse:
    rows = (
        await session.execute(
            select(CloudSeedLot, CloudPlantLine)
            .outerjoin(
                CloudPlantLine,
                and_(
                    CloudPlantLine.site_id == CloudSeedLot.site_id,
                    CloudPlantLine.source_line_id == CloudSeedLot.line_source_id,
                ),
            )
            .where(CloudSeedLot.site_id == site_id)
            .order_by(
                CloudPlantLine.project_code,
                CloudPlantLine.generation_label,
                CloudSeedLot.source_seed_lot_id,
            )
        )
    ).all()
    return BreedingLogbookSeedLotListResponse(
        seed_lots=[
            breeding_logbook_seed_lot_summary_response(seed_lot, line)
            for seed_lot, line in rows
        ]
    )


async def plant_metric_history(
    session: AsyncSession,
    *,
    site_id: str,
    plant_key: str,
    range_key: str,
    now: datetime,
) -> PlantMetricHistoryResponse:
    range_spec = METRIC_HISTORY_RANGES.get(range_key)
    if range_spec is None:
        raise HTTPException(status_code=400, detail="invalid range")
    plant = await get_breeding_logbook_plant(
        session,
        site_id=site_id,
        plant_key=plant_key,
    )
    stream_rows = [
        row
        for row in await active_plant_metric_streams(
            session,
            site_id=site_id,
            plant=plant_projection_from_breeding_logbook(plant),
        )
        if row.presentation is not None and row.presentation.history_enabled
    ]
    bucket, window = range_spec
    history_by_stream = await metric_rollups_by_stream(
        session,
        site_id=site_id,
        source_tent_id=required_location_source_tent_id(plant.location),
        bucket=bucket,
        cutoff=now - window,
        streams=[row.stream for row in stream_rows],
    )
    return PlantMetricHistoryResponse(
        range=range_key,
        bucket=bucket,
        streams=[
            plant_metric_history_stream_response(
                row,
                history_by_stream.get(metric_stream_key(row.stream), []),
            )
            for row in stream_rows
        ],
    )


async def plant_detail(
    session: AsyncSession,
    *,
    site_id: str,
    plant_key: str,
    today: date,
) -> BreedingLogbookPlantDetailResponse:
    plant = await get_breeding_logbook_plant(
        session,
        site_id=site_id,
        plant_key=plant_key,
    )
    stream_rows = await active_plant_metric_streams(
        session,
        site_id=site_id,
        plant=plant_projection_from_breeding_logbook(plant),
    )
    latest_by_stream = await latest_metrics_by_stream(
        session,
        site_id=site_id,
        source_tent_id=required_location_source_tent_id(plant.location),
        streams=[row.stream for row in stream_rows],
    )
    notes = await breeding_logbook_plant_notes(
        session,
        site_id=site_id,
        source_plant_id=plant.plant.source_plant_id,
    )
    events = await breeding_logbook_plant_events(
        session,
        site_id=site_id,
        source_plant_id=plant.plant.source_plant_id,
    )
    lineage = await breeding_logbook_lineage(
        session,
        site_id=site_id,
        plant=plant,
    )
    telemetry = plant_metric_stream_responses(stream_rows, latest_by_stream)
    return BreedingLogbookPlantDetailResponse(
        plant=breeding_logbook_plant_row_response(
            plant,
            telemetry_stream_count=len(telemetry),
            latest_note=notes[0] if notes else None,
            latest_event=events[0] if events else None,
            today=today,
        ),
        lineage=lineage,
        metrics=breeding_logbook_metric_summaries(telemetry),
        events=breeding_logbook_journal_events(notes=notes, events=events),
        telemetry=telemetry,
        wiki_content=None,
    )


async def create_seed_lot_command(
    body: BreedingCreateSeedLotRequest,
    *,
    user: str,
    settings: CloudSettings,
    session: AsyncSession,
    now: datetime,
) -> CommandResponse:
    payload = BreedingCreateSeedLotPayload(
        **body.model_dump(exclude={"idempotency_key"})
    )
    if payload.source == "cross":
        seed_parent_key = payload.seed_parent_plant_key
        pollen_parent_key = payload.pollen_parent_plant_key
        if seed_parent_key is None or pollen_parent_key is None:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "cross seed lots require seed and pollen parent plant keys",
            )
        await require_cloud_plant_key(
            session,
            site_id=settings.default_site_id,
            plant_key=seed_parent_key,
        )
        await require_cloud_plant_key(
            session,
            site_id=settings.default_site_id,
            plant_key=pollen_parent_key,
        )
    return await enqueue_breeding_command(
        body.idempotency_key,
        user=user,
        settings=settings,
        session=session,
        now=now,
        command_type="breeding_seed_lot_create",
        legacy_storage_tent_id=BREEDING_SITE_WIDE_TENT_ID,
        source_tent_id=None,
        payload=payload,
    )


async def germinate_plants_command(
    body: BreedingGerminatePlantsRequest,
    *,
    user: str,
    settings: CloudSettings,
    session: AsyncSession,
    now: datetime,
) -> CommandResponse:
    await get_cloud_tent_by_source_id(
        session, site_id=settings.default_site_id, source_tent_id=body.source_tent_id
    )
    seed_lot_source_id = seed_lot_source_id_from_request(body.seed_lot_id)
    await require_cloud_seed_lot_source_id(
        session,
        site_id=settings.default_site_id,
        seed_lot_source_id=seed_lot_source_id,
    )
    payload = BreedingGerminatePlantsPayload(
        seed_lot_source_id=seed_lot_source_id,
        count=body.count,
        source_tent_id=body.source_tent_id,
        grid_position=None,
        germinated_at=body.germinated_at,
    )
    return await enqueue_breeding_command(
        body.idempotency_key,
        user=user,
        settings=settings,
        session=session,
        now=now,
        command_type="breeding_plants_germinate",
        legacy_storage_tent_id=storage_compat_tent_id(body.source_tent_id),
        source_tent_id=body.source_tent_id,
        payload=payload,
    )


async def clone_plants_command(
    body: BreedingClonePlantsRequest,
    *,
    user: str,
    settings: CloudSettings,
    session: AsyncSession,
    now: datetime,
) -> CommandResponse:
    await get_cloud_tent_by_source_id(
        session, site_id=settings.default_site_id, source_tent_id=body.source_tent_id
    )
    mother = await require_cloud_plant_key(
        session, site_id=settings.default_site_id, plant_key=body.mother_plant_key
    )
    payload = BreedingClonePlantsPayload(
        mother_plant_key=mother.key,
        count=body.count,
        source_tent_id=body.source_tent_id,
        grid_position=None,
        taken_at=body.taken_at,
    )
    return await enqueue_breeding_command(
        body.idempotency_key,
        user=user,
        settings=settings,
        session=session,
        now=now,
        command_type="breeding_plants_clone",
        legacy_storage_tent_id=storage_compat_tent_id(body.source_tent_id),
        source_tent_id=body.source_tent_id,
        payload=payload,
    )


async def bulk_sex_plants_command(
    body: BreedingBulkSexRequest,
    *,
    user: str,
    settings: CloudSettings,
    session: AsyncSession,
    now: datetime,
) -> CommandResponse:
    await require_cloud_plant_keys(
        session, site_id=settings.default_site_id, plant_keys=body.plant_keys
    )
    payload = BreedingBulkSexPayload(plant_keys=body.plant_keys, sex_key=body.sex_key)
    return await enqueue_breeding_command(
        body.idempotency_key,
        user=user,
        settings=settings,
        session=session,
        now=now,
        command_type="breeding_plants_bulk_sex",
        legacy_storage_tent_id=BREEDING_SITE_WIDE_TENT_ID,
        source_tent_id=None,
        payload=payload,
    )


async def bulk_move_plants_command(
    body: BreedingBulkMoveRequest,
    *,
    user: str,
    settings: CloudSettings,
    session: AsyncSession,
    now: datetime,
) -> CommandResponse:
    await get_cloud_tent_by_source_id(
        session, site_id=settings.default_site_id, source_tent_id=body.source_tent_id
    )
    await require_cloud_plant_keys(
        session, site_id=settings.default_site_id, plant_keys=body.plant_keys
    )
    payload = BreedingBulkMovePayload(
        plant_keys=body.plant_keys,
        source_tent_id=body.source_tent_id,
        grid_position=None,
    )
    return await enqueue_breeding_command(
        body.idempotency_key,
        user=user,
        settings=settings,
        session=session,
        now=now,
        command_type="breeding_plants_bulk_move",
        legacy_storage_tent_id=storage_compat_tent_id(body.source_tent_id),
        source_tent_id=body.source_tent_id,
        payload=payload,
    )


async def bulk_cull_plants_command(
    body: BreedingBulkCullRequest,
    *,
    user: str,
    settings: CloudSettings,
    session: AsyncSession,
    now: datetime,
) -> CommandResponse:
    await require_cloud_plant_keys(
        session, site_id=settings.default_site_id, plant_keys=body.plant_keys
    )
    payload = BreedingBulkCullPayload(plant_keys=body.plant_keys, reason=body.reason)
    return await enqueue_breeding_command(
        body.idempotency_key,
        user=user,
        settings=settings,
        session=session,
        now=now,
        command_type="breeding_plants_bulk_cull",
        legacy_storage_tent_id=BREEDING_SITE_WIDE_TENT_ID,
        source_tent_id=None,
        payload=payload,
    )


async def create_plant_note_command(  # noqa: PLR0913
    plant_key: str,
    body: BreedingCreatePlantNoteRequest,
    *,
    user: str,
    settings: CloudSettings,
    session: AsyncSession,
    now: datetime,
) -> CommandResponse:
    plant = await require_cloud_plant_key(
        session, site_id=settings.default_site_id, plant_key=plant_key
    )
    payload = BreedingCreatePlantNotePayload(
        plant_key=plant.key,
        body=body.body,
        observed_at=body.observed_at,
    )
    return await enqueue_breeding_command(
        body.idempotency_key,
        user=user,
        settings=settings,
        session=session,
        now=now,
        command_type="breeding_plant_note_create",
        legacy_storage_tent_id=BREEDING_SITE_WIDE_TENT_ID,
        source_tent_id=None,
        payload=payload,
    )


async def breeding_logbook_plants(
    session: AsyncSession,
    *,
    site_id: str,
    include_culled: bool,
    plant_key: str | None = None,
) -> list[BreedingLogbookPlantProjection]:
    active_filters = (
        ()
        if include_culled
        else (CloudPlant.is_active.is_(True), CloudPlant.culled_at.is_(None))
    )
    key_filters = () if plant_key is None else (CloudPlant.key == plant_key,)
    plant_rows = (
        await session.execute(
            select(
                CloudPlant,
                CloudPlantLine,
                CloudSeedLot,
            )
            .outerjoin(
                CloudPlantLine,
                and_(
                    CloudPlantLine.site_id == CloudPlant.site_id,
                    CloudPlantLine.source_line_id == CloudPlant.line_source_id,
                ),
            )
            .outerjoin(
                CloudSeedLot,
                and_(
                    CloudSeedLot.site_id == CloudPlant.site_id,
                    CloudSeedLot.source_seed_lot_id == CloudPlant.source_seed_lot_id,
                ),
            )
            .where(
                CloudPlant.site_id == site_id,
                *active_filters,
                *key_filters,
            )
            .order_by(CloudPlant.key)
        )
    ).all()
    plant_ids = [plant.source_plant_id for plant, _line, _seed_lot in plant_rows]
    if not plant_ids:
        return []
    location_rows = (
        await session.execute(
            select(CloudPlantLocation)
            .where(
                CloudPlantLocation.site_id == site_id,
                CloudPlantLocation.source_plant_id.in_(plant_ids),
            )
            .order_by(
                CloudPlantLocation.source_plant_id,
                CloudPlantLocation.start_at,
            )
        )
    ).scalars()
    locations = breeding_logbook_locations_by_plant(location_rows)
    tents = await cloud_tents_by_source_id(
        session,
        site_id=site_id,
        source_tent_ids={
            location.source_tent_id
            for location in locations.values()
            if location.source_tent_id is not None
        },
    )
    projections = [
        BreedingLogbookPlantProjection(
            plant=plant,
            location=location,
            tent=tent,
            line=line,
            seed_lot=seed_lot,
            seed_lot_line=line,
        )
        for plant, line, seed_lot in plant_rows
        if (location := locations.get(plant.source_plant_id)) is not None
        for tent in [tents.get(required_location_source_tent_id(location))]
    ]
    return sorted(
        projections,
        key=lambda row: (
            required_location_source_tent_id(row.location),
            row.location.grid_position or "",
            row.plant.key,
        ),
    )


def breeding_logbook_locations_by_plant(
    locations: Iterable[CloudPlantLocation],
) -> dict[int, CloudPlantLocation]:
    selected: dict[int, CloudPlantLocation] = {}
    for location in locations:
        current = selected.get(location.source_plant_id)
        if current is None or is_preferred_breeding_logbook_location(
            location,
            current,
        ):
            selected[location.source_plant_id] = location
    return selected


def is_preferred_breeding_logbook_location(
    candidate: CloudPlantLocation,
    current: CloudPlantLocation,
) -> bool:
    if candidate.end_at is None and current.end_at is not None:
        return True
    if candidate.end_at is not None and current.end_at is None:
        return False
    return candidate.start_at > current.start_at


async def get_breeding_logbook_plant(
    session: AsyncSession,
    *,
    site_id: str,
    plant_key: str,
) -> BreedingLogbookPlantProjection:
    rows = await breeding_logbook_plants(
        session,
        site_id=site_id,
        include_culled=True,
        plant_key=plant_key,
    )
    if rows:
        return rows[0]
    raise HTTPException(status.HTTP_404_NOT_FOUND, "plant not found")


def plant_projection_from_breeding_logbook(
    projection: BreedingLogbookPlantProjection,
) -> PlantProjection:
    return PlantProjection(
        plant=projection.plant,
        location=projection.location,
        tent=projection.tent,
        line=projection.line,
    )


async def breeding_logbook_latest_notes(
    session: AsyncSession,
    *,
    site_id: str,
    plant_ids: list[int],
) -> dict[int, CloudPlantNote]:
    if not plant_ids:
        return {}
    rows = (
        await session.execute(
            select(CloudPlantNote)
            .where(
                CloudPlantNote.site_id == site_id,
                CloudPlantNote.source_plant_id.in_(plant_ids),
            )
            .order_by(
                CloudPlantNote.source_plant_id,
                desc(CloudPlantNote.observed_at),
                desc(CloudPlantNote.source_note_id),
            )
        )
    ).scalars()
    latest: dict[int, CloudPlantNote] = {}
    for note in rows:
        latest.setdefault(note.source_plant_id, note)
    return latest


async def breeding_logbook_latest_events(
    session: AsyncSession,
    *,
    site_id: str,
    plant_ids: list[int],
) -> dict[int, CloudPlantEvent]:
    if not plant_ids:
        return {}
    rows = (
        await session.execute(
            select(CloudPlantEvent)
            .where(
                CloudPlantEvent.site_id == site_id,
                CloudPlantEvent.source_plant_id.in_(plant_ids),
            )
            .order_by(
                CloudPlantEvent.source_plant_id,
                desc(CloudPlantEvent.occurred_at),
                desc(CloudPlantEvent.source_event_id),
            )
        )
    ).scalars()
    latest: dict[int, CloudPlantEvent] = {}
    for event in rows:
        latest.setdefault(event.source_plant_id, event)
    return latest


async def breeding_logbook_plant_notes(
    session: AsyncSession,
    *,
    site_id: str,
    source_plant_id: int,
) -> list[CloudPlantNote]:
    return list(
        (
            await session.execute(
                select(CloudPlantNote)
                .where(
                    CloudPlantNote.site_id == site_id,
                    CloudPlantNote.source_plant_id == source_plant_id,
                )
                .order_by(
                    desc(CloudPlantNote.observed_at),
                    desc(CloudPlantNote.source_note_id),
                )
            )
        ).scalars()
    )


async def breeding_logbook_plant_events(
    session: AsyncSession,
    *,
    site_id: str,
    source_plant_id: int,
) -> list[CloudPlantEvent]:
    return list(
        (
            await session.execute(
                select(CloudPlantEvent)
                .where(
                    CloudPlantEvent.site_id == site_id,
                    CloudPlantEvent.source_plant_id == source_plant_id,
                )
                .order_by(
                    desc(CloudPlantEvent.occurred_at),
                    desc(CloudPlantEvent.source_event_id),
                )
            )
        ).scalars()
    )


async def breeding_logbook_stream_counts(
    session: AsyncSession,
    *,
    site_id: str,
    plants: list[BreedingLogbookPlantProjection],
) -> dict[int, int]:
    return await active_plant_stream_counts(
        session,
        site_id=site_id,
        plants=[plant_projection_from_breeding_logbook(row) for row in plants],
    )


async def breeding_logbook_lineage(
    session: AsyncSession,
    *,
    site_id: str,
    plant: BreedingLogbookPlantProjection,
) -> BreedingLogbookLineageResponse:
    return BreedingLogbookLineageResponse(
        parents=await breeding_logbook_parent_label(
            session,
            site_id=site_id,
            plant=plant,
        ),
        offspring=await breeding_logbook_offspring_label(
            session,
            site_id=site_id,
            source_plant_id=plant.plant.source_plant_id,
        ),
    )


async def breeding_logbook_parent_label(
    session: AsyncSession,
    *,
    site_id: str,
    plant: BreedingLogbookPlantProjection,
) -> str:
    cross_event_id = (
        None
        if plant.seed_lot is None
        else plant.seed_lot.produced_by_cross_event_source_id
    )
    if cross_event_id is None:
        return lineage_label(plant.line)

    cross = (
        await session.execute(
            select(CloudCrossEvent).where(
                CloudCrossEvent.site_id == site_id,
                CloudCrossEvent.source_cross_event_id == cross_event_id,
            )
        )
    ).scalar_one_or_none()
    if cross is None:
        return lineage_label(plant.line)

    seed_parent_id = cross.seed_parent_source_plant_id
    pollen_parent_id = cross.pollen_parent_source_plant_id
    parents = {
        row.source_plant_id: row
        for row in (
            await session.execute(
                select(CloudPlant).where(
                    CloudPlant.site_id == site_id,
                    CloudPlant.source_plant_id.in_([seed_parent_id, pollen_parent_id]),
                )
            )
        ).scalars()
    }
    seed_parent = breeding_logbook_parent_plant_label(
        parents.get(seed_parent_id),
        fallback=f"plant #{seed_parent_id}",
    )
    pollen_parent = breeding_logbook_parent_plant_label(
        parents.get(pollen_parent_id),
        fallback=f"plant #{pollen_parent_id}",
    )
    if cross.pollen_parent_is_reversed:
        pollen_parent = f"{pollen_parent} (reversed)"
    return f"{seed_parent} x {pollen_parent}"


async def breeding_logbook_offspring_label(
    session: AsyncSession,
    *,
    site_id: str,
    source_plant_id: int,
) -> str:
    cross_events = list(
        (
            await session.execute(
                select(CloudCrossEvent)
                .where(
                    CloudCrossEvent.site_id == site_id,
                    (
                        (CloudCrossEvent.seed_parent_source_plant_id == source_plant_id)
                        | (
                            CloudCrossEvent.pollen_parent_source_plant_id
                            == source_plant_id
                        )
                    ),
                )
                .order_by(
                    desc(CloudCrossEvent.pollinated_at),
                    desc(CloudCrossEvent.source_cross_event_id),
                )
            )
        ).scalars()
    )
    if not cross_events:
        return "No offspring logged"

    cross_event_ids = [event.source_cross_event_id for event in cross_events]
    seed_lot_rows = (
        await session.execute(
            select(CloudSeedLot, CloudPlantLine)
            .outerjoin(
                CloudPlantLine,
                and_(
                    CloudPlantLine.site_id == CloudSeedLot.site_id,
                    CloudPlantLine.source_line_id == CloudSeedLot.line_source_id,
                ),
            )
            .where(
                CloudSeedLot.site_id == site_id,
                CloudSeedLot.produced_by_cross_event_source_id.in_(cross_event_ids),
            )
            .order_by(CloudSeedLot.source_seed_lot_id)
        )
    ).all()
    seed_lots_by_cross: dict[int, list[tuple[CloudSeedLot, CloudPlantLine | None]]] = {}
    seed_lot_ids: list[int] = []
    for seed_lot, line in seed_lot_rows:
        if seed_lot.produced_by_cross_event_source_id is None:
            continue
        seed_lots_by_cross.setdefault(
            seed_lot.produced_by_cross_event_source_id,
            [],
        ).append((seed_lot, line))
        seed_lot_ids.append(seed_lot.source_seed_lot_id)

    plant_counts: dict[int, int] = {}
    if seed_lot_ids:
        count_rows = (
            await session.execute(
                select(CloudPlant.source_seed_lot_id, func.count())
                .where(
                    CloudPlant.site_id == site_id,
                    CloudPlant.source_seed_lot_id.in_(seed_lot_ids),
                )
                .group_by(CloudPlant.source_seed_lot_id)
            )
        ).all()
        plant_counts = {
            seed_lot_id: int(count)
            for seed_lot_id, count in count_rows
            if seed_lot_id is not None
        }

    summaries: list[str] = []
    for cross_event in cross_events:
        seed_lots = seed_lots_by_cross.get(cross_event.source_cross_event_id, [])
        if not seed_lots:
            summaries.append(
                f"Cross #{cross_event.source_cross_event_id}: no seed lots projected"
            )
            continue
        lot_summaries: list[str] = []
        for seed_lot, line in seed_lots:
            count_label = plant_count_label(
                plant_counts.get(seed_lot.source_seed_lot_id, 0)
            )
            lot_summaries.append(f"{seed_lot_label(seed_lot, line)} ({count_label})")
        summaries.append(
            f"Cross #{cross_event.source_cross_event_id}: {', '.join(lot_summaries)}"
        )
    return "; ".join(summaries)


def breeding_logbook_plant_row_response(
    projection: BreedingLogbookPlantProjection,
    *,
    telemetry_stream_count: int,
    today: date,
    latest_note: CloudPlantNote | None = None,
    latest_event: CloudPlantEvent | None = None,
) -> BreedingLogbookPlantRowResponse:
    plant = projection.plant
    stage_key = breeding_logbook_stage_key(projection)
    return BreedingLogbookPlantRowResponse(
        id=str(plant.source_plant_id),
        key=plant.key,
        name=plant.name,
        generation=generation_label(projection.line),
        parents_label=lineage_label(projection.line),
        sex_key=plant.sex_key,
        stage_key=stage_key,
        stage_day=stage_day(plant, projection.location, stage_key, today=today),
        germinated_on=date_or_none(plant.germinated_at),
        veg_started_on=date_or_none(plant.veg_started_at or plant.rooted_at),
        flower_started_on=date_or_none(plant.flower_started_at),
        culled_on=date_or_none(plant.culled_at),
        current_tent_id=required_location_source_tent_id(projection.location),
        current_tent_name=tent_display_name(projection.tent, projection.location),
        grid_position=projection.location.grid_position,
        seed_lot_label=seed_lot_label(projection.seed_lot, projection.seed_lot_line),
        last_note=breeding_logbook_last_note(
            plant,
            latest_note=latest_note,
            latest_event=latest_event,
        ),
        telemetry_summary=telemetry_summary(telemetry_stream_count),
    )


def breeding_logbook_seed_lot_summary_response(
    seed_lot: CloudSeedLot,
    line: CloudPlantLine | None,
) -> BreedingLogbookSeedLotSummaryResponse:
    return BreedingLogbookSeedLotSummaryResponse(
        id=str(seed_lot.source_seed_lot_id),
        label=seed_lot_label(seed_lot, line),
        prefix=line.project_code if line is not None and line.project_code else "",
        strain=line.strain if line is not None else "Unknown strain",
        cultivar=line.cultivar if line is not None else "Unknown cultivar",
        generation=generation_label(line),
        source="purchased" if seed_lot.is_purchased else "cross",
        source_label=seed_lot_source_label(seed_lot),
        parents_label=lineage_label(line),
        sex_type_key=seed_lot.sex_type_key,
        seed_count=seed_lot.seed_count,
    )


def breeding_logbook_last_note(
    plant: CloudPlant,
    *,
    latest_note: CloudPlantNote | None,
    latest_event: CloudPlantEvent | None,
) -> str:
    if latest_note is not None:
        return latest_note.body
    if latest_event is not None:
        event_body = breeding_logbook_event_body(latest_event)
        if event_body:
            return event_body
    return plant.culled_reason or plant.selected_for_breeding_reason or ""


def breeding_logbook_journal_events(
    *,
    notes: list[CloudPlantNote],
    events: list[CloudPlantEvent],
) -> list[BreedingLogbookPlantJournalEventResponse]:
    journal_events = [
        *breeding_logbook_note_journal_events(notes),
        *breeding_logbook_plant_journal_events(events),
    ]
    return sorted(
        journal_events,
        key=lambda event: (
            event.occurred_at or datetime.min,
            event.id,
        ),
        reverse=True,
    )


def breeding_logbook_note_journal_events(
    notes: list[CloudPlantNote],
) -> list[BreedingLogbookPlantJournalEventResponse]:
    return [
        BreedingLogbookPlantJournalEventResponse(
            id=f"note-{note.source_note_id}",
            occurred_at=note.observed_at,
            date_label=journal_date_label(note.observed_at),
            tag="note",
            body=note.body,
            has_photo=False,
        )
        for note in notes
    ]


def breeding_logbook_plant_journal_events(
    events: list[CloudPlantEvent],
) -> list[BreedingLogbookPlantJournalEventResponse]:
    return [
        BreedingLogbookPlantJournalEventResponse(
            id=f"event-{event.source_event_id}",
            occurred_at=event.occurred_at,
            date_label=journal_date_label(event.occurred_at),
            tag=breeding_logbook_event_tag(event),
            body=breeding_logbook_event_body(event),
            has_photo=False,
        )
        for event in events
    ]


def breeding_logbook_event_tag(
    event: CloudPlantEvent,
) -> Literal["cross", "note", "stage", "sex", "germ"]:
    if event.is_seed_production or event.is_pollen_collection:
        return "cross"
    if event.is_sex_observation or event.is_reversal:
        return "sex"
    if event.is_transplant or event.is_selection_for_breeding:
        return "stage"
    if event.is_clone_taken:
        return "germ"
    return "note"


def breeding_logbook_event_body(event: CloudPlantEvent) -> str:
    for value in (event.notes, event.reason):
        if value is not None and value.strip():
            return value.strip()
    labels = [
        label
        for is_present, label in (
            (event.is_pollen_collection, "Pollen collected"),
            (event.is_seed_production, "Seed production logged"),
            (event.is_clone_taken, "Clone taken"),
            (event.is_sex_observation, "Sex observation logged"),
            (event.is_reversal, "Reversal logged"),
            (event.is_transplant, "Transplant logged"),
            (event.is_selection_for_breeding, "Selected for breeding"),
        )
        if is_present
    ]
    return "; ".join(labels)


def journal_date_label(value: datetime) -> str:
    return f"{value.strftime('%b')} {value.day}"


def breeding_logbook_parent_plant_label(
    plant: CloudPlant | None,
    *,
    fallback: str,
) -> str:
    if plant is None:
        return fallback
    return f"{plant.name} ({plant.key})"


def plant_count_label(count: int) -> str:
    if count == 1:
        return "1 plant"
    return f"{count} plants"


def breeding_logbook_stage_key(
    projection: BreedingLogbookPlantProjection,
) -> BreedingLogbookPlantStageKey:
    plant = projection.plant
    if plant.culled_at is not None:
        return "culled"
    if plant.harvested_at is not None:
        return "harvested"
    if not plant.is_active:
        return "culled"
    if plant.selected_for_breeding_at is not None:
        return "breeding"
    if plant.flower_started_at is not None:
        return "flower"
    if plant.veg_started_at is not None or plant.rooted_at is not None:
        return "veg"
    return "germinating"


def stage_day(
    plant: CloudPlant,
    location: CloudPlantLocation,
    stage_key: BreedingLogbookPlantStageKey,
    *,
    today: date,
) -> int:
    starts_at = {
        "germinating": plant.germinated_at,
        "veg": plant.veg_started_at or plant.rooted_at,
        "flower": plant.flower_started_at,
        "breeding": plant.selected_for_breeding_at or plant.flower_started_at,
        "harvested": plant.harvested_at,
        "culled": plant.culled_at,
    }[stage_key]
    start_date = date_or_none(starts_at) or location.start_at.date()
    return max(0, (today - start_date).days)


def seed_lot_label(
    seed_lot: CloudSeedLot | None,
    line: CloudPlantLine | None,
) -> str:
    if seed_lot is None:
        return "Unassigned seed lot"
    label_parts = [
        part
        for part in (
            line.project_code if line is not None else None,
            line.generation_label if line is not None else None,
        )
        if part
    ]
    if not label_parts and line is not None:
        label_parts = [line.strain, line.cultivar]
    label = " ".join(label_parts) if label_parts else "Seed lot"
    return f"{label} #{seed_lot.source_seed_lot_id}"


def seed_lot_source_label(seed_lot: CloudSeedLot) -> str:
    if seed_lot.is_purchased:
        return seed_lot.vendor_name or "unknown vendor"
    return "in-house cross"


def lineage_label(line: CloudPlantLine | None) -> str:
    if line is None:
        return "Unknown lineage"
    return " x ".join(part for part in (line.strain, line.cultivar) if part)


def generation_label(line: CloudPlantLine | None) -> str:
    if line is None:
        return ""
    return line.generation_label or line.cultivar


def telemetry_summary(stream_count: int) -> str:
    if stream_count == 0:
        return "tent context"
    if stream_count == 1:
        return "1 plant stream"
    return f"{stream_count} plant streams"


def breeding_logbook_metric_summaries(
    telemetry: list[PlantMetricStreamResponse],
) -> list[BreedingLogbookPlantMetricSummaryResponse]:
    summaries: list[BreedingLogbookPlantMetricSummaryResponse] = []
    for stream in telemetry:
        reading = stream.latest_reading
        value = "no reading"
        if reading is not None:
            value = f"{reading.value:g}{stream.display_unit}"
        summaries.append(
            BreedingLogbookPlantMetricSummaryResponse(
                label=stream.display_name,
                value=value,
                tone="ok",
            )
        )
    return summaries


def date_or_none(value: datetime | None) -> date | None:
    return None if value is None else value.date()


def seed_lot_source_id_from_request(seed_lot_id: str) -> int:
    try:
        value = int(seed_lot_id)
    except ValueError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "seed_lot_id must be a source seed lot id",
        ) from exc
    if value <= 0:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "seed_lot_id must be positive",
        )
    return value


async def require_cloud_seed_lot_source_id(
    session: AsyncSession, *, site_id: str, seed_lot_source_id: int
) -> CloudSeedLot:
    seed_lot = (
        await session.execute(
            select(CloudSeedLot).where(
                CloudSeedLot.site_id == site_id,
                CloudSeedLot.source_seed_lot_id == seed_lot_source_id,
            )
        )
    ).scalar_one_or_none()
    if seed_lot is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "unknown seed lot",
        )
    return seed_lot


async def require_cloud_plant_key(
    session: AsyncSession, *, site_id: str, plant_key: str
) -> CloudPlant:
    plant = (
        await session.execute(
            select(CloudPlant).where(
                CloudPlant.site_id == site_id,
                CloudPlant.key == plant_key,
            )
        )
    ).scalar_one_or_none()
    if plant is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "unknown plant key",
        )
    return plant


async def require_cloud_plant_keys(
    session: AsyncSession, *, site_id: str, plant_keys: list[str]
) -> list[CloudPlant]:
    rows = (
        (
            await session.execute(
                select(CloudPlant).where(
                    CloudPlant.site_id == site_id,
                    CloudPlant.key.in_(plant_keys),
                )
            )
        )
        .scalars()
        .all()
    )
    found = {plant.key for plant in rows}
    missing = [plant_key for plant_key in plant_keys if plant_key not in found]
    if missing:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"unknown plant key: {missing[0]}",
        )
    return rows
