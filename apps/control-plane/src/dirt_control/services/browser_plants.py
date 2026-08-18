from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dirt_control.api.browser_schemas.plants import (
    PlantLineResponse,
    PlantSummaryResponse,
)
from dirt_control.models import (
    CloudPlant,
    CloudPlantLine,
    CloudPlantLocation,
    CloudPlantMetricStream,
    CloudTent,
)
from dirt_control.services.browser_tents import (
    location_tent_name,
    required_location_source_tent_id,
)


@dataclass(frozen=True)
class PlantProjection:
    plant: CloudPlant
    location: CloudPlantLocation
    tent: CloudTent | None
    line: CloudPlantLine | None


async def list_plant_summaries(
    session: AsyncSession, *, site_id: str, source_tent_id: int
) -> list[PlantSummaryResponse]:
    latest_rows = await latest_plants(
        session,
        site_id=site_id,
        source_tent_id=source_tent_id,
    )
    stream_counts = await active_plant_stream_counts(
        session,
        site_id=site_id,
        plants=latest_rows,
    )
    return [
        plant_summary_response(
            row,
            telemetry_stream_count=stream_counts.get(row.plant.source_plant_id, 0),
        )
        for row in latest_rows
    ]


async def latest_plants(
    session: AsyncSession,
    *,
    site_id: str,
    source_tent_id: int,
) -> list[PlantProjection]:
    rows = (
        await session.execute(
            select(CloudPlant, CloudPlantLocation, CloudTent, CloudPlantLine)
            .join(
                CloudPlantLocation,
                and_(
                    CloudPlantLocation.site_id == CloudPlant.site_id,
                    CloudPlantLocation.source_plant_id == CloudPlant.source_plant_id,
                ),
            )
            .outerjoin(
                CloudTent,
                and_(
                    CloudTent.site_id == CloudPlantLocation.site_id,
                    CloudTent.source_tent_id == CloudPlantLocation.source_tent_id,
                ),
            )
            .outerjoin(
                CloudPlantLine,
                and_(
                    CloudPlantLine.site_id == CloudPlant.site_id,
                    CloudPlantLine.source_line_id == CloudPlant.line_source_id,
                ),
            )
            .where(
                CloudPlant.site_id == site_id,
                CloudPlantLocation.site_id == site_id,
                CloudPlantLocation.source_tent_id == source_tent_id,
                CloudPlantLocation.end_at.is_(None),
            )
            .order_by(CloudPlantLocation.grid_position, CloudPlant.key)
        )
    ).all()
    return [
        PlantProjection(plant=plant, location=location, tent=tent, line=line)
        for plant, location, tent, line in rows
    ]


def plant_summary_response(
    projection: PlantProjection,
    *,
    telemetry_stream_count: int,
) -> PlantSummaryResponse:
    plant = projection.plant
    location = projection.location
    return PlantSummaryResponse(
        site_id=plant.site_id,
        current_tent_id=required_location_source_tent_id(location),
        current_tent_name=location_tent_name(projection.tent, location),
        id=plant.source_plant_id,
        key=plant.key,
        line_source_id=plant.line_source_id,
        line=plant_line_response(projection.line),
        sex_key=plant.sex_key,
        name=plant.name,
        grid_position=location.grid_position,
        germinated_at=plant.germinated_at,
        taken_at=plant.taken_at,
        rooted_at=plant.rooted_at,
        veg_started_at=plant.veg_started_at,
        flower_started_at=plant.flower_started_at,
        culled_at=plant.culled_at,
        harvested_at=plant.harvested_at,
        is_active=plant.is_active,
        telemetry_stream_count=telemetry_stream_count,
    )


async def active_plant_stream_counts(
    session: AsyncSession,
    *,
    site_id: str,
    plants: list[PlantProjection],
) -> dict[int, int]:
    source_plant_ids = {plant.plant.source_plant_id for plant in plants}
    if not source_plant_ids:
        return {}
    rows = (
        await session.execute(
            select(
                CloudPlantMetricStream.source_plant_id,
                func.count(CloudPlantMetricStream.id),
            )
            .where(
                CloudPlantMetricStream.site_id == site_id,
                CloudPlantMetricStream.is_active.is_(True),
                CloudPlantMetricStream.source_plant_id.in_(tuple(source_plant_ids)),
            )
            .group_by(CloudPlantMetricStream.source_plant_id)
        )
    ).all()
    return {
        source_plant_id: count
        for source_plant_id, count in rows
        if source_plant_id in source_plant_ids
    }


def plant_line_response(line: CloudPlantLine | None) -> PlantLineResponse | None:
    if line is None:
        return None
    return PlantLineResponse(
        id=line.source_line_id,
        project_code=line.project_code,
        generation_label=line.generation_label,
        strain=line.strain,
        cultivar=line.cultivar,
        source_name=line.source_name,
    )
