from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dirt_control.api.browser_schemas.metrics import (
    METRIC_HISTORY_RANGES,
    MetricStreamKey,
)
from dirt_control.api.browser_schemas.plants import (
    PlantCurrentLocationResponse,
    PlantDetailResponse,
    PlantLineResponse,
    PlantMetricHistoryPointResponse,
    PlantMetricHistoryResponse,
    PlantMetricHistoryStreamResponse,
    PlantMetricReadingResponse,
    PlantMetricStreamResponse,
    PlantSummaryResponse,
    PlantWikiContentResponse,
)
from dirt_control.models import (
    CloudLatestMetric,
    CloudMetricPresentation,
    CloudMetricRollup,
    CloudPlant,
    CloudPlantLine,
    CloudPlantLocation,
    CloudPlantMetricStream,
    CloudTent,
    CloudWikiPage,
)
from dirt_control.services.browser_metrics import (
    accent_for_metric,
    display_metric_value,
    display_name_for_metric,
    display_optional_metric_value,
    display_unit_for_metric,
    metric_stream_filter_values,
    source_unit_for_metric,
    value_precision_for_metric,
)
from dirt_control.services.browser_tents import (
    location_tent_name,
    required_location_source_tent_id,
)


@dataclass(frozen=True)
class PlantMetricStreamProjection:
    stream: CloudPlantMetricStream
    presentation: CloudMetricPresentation | None


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


async def get_plant_detail_response(
    session: AsyncSession, *, site_id: str, source_tent_id: int, plant_id: str
) -> PlantDetailResponse:
    plant = await get_plant(
        session,
        site_id=site_id,
        source_tent_id=source_tent_id,
        plant_id=plant_id,
    )
    stream_rows = await active_plant_metric_streams(
        session,
        site_id=site_id,
        plant=plant,
    )
    latest_by_stream = await latest_metrics_by_stream(
        session,
        site_id=site_id,
        source_tent_id=source_tent_id,
        streams=[row.stream for row in stream_rows],
    )
    return plant_detail_response(
        plant,
        telemetry=plant_metric_stream_responses(stream_rows, latest_by_stream),
        wiki_page=None,
    )


async def get_plant_metric_history_response(  # noqa: PLR0913
    session: AsyncSession,
    *,
    site_id: str,
    source_tent_id: int,
    plant_id: str,
    range_key: str,
    now: datetime,
) -> PlantMetricHistoryResponse:
    range_spec = METRIC_HISTORY_RANGES.get(range_key)
    if range_spec is None:
        raise HTTPException(status_code=400, detail="invalid range")
    plant = await get_plant(
        session,
        site_id=site_id,
        source_tent_id=source_tent_id,
        plant_id=plant_id,
    )
    stream_rows = [
        row
        for row in await active_plant_metric_streams(
            session,
            site_id=site_id,
            plant=plant,
        )
        if row.presentation is not None and row.presentation.history_enabled
    ]
    bucket, window = range_spec
    history_by_stream = await metric_rollups_by_stream(
        session,
        site_id=site_id,
        source_tent_id=source_tent_id,
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
        rooted_at=plant.rooted_at,
        veg_started_at=plant.veg_started_at,
        flower_started_at=plant.flower_started_at,
        culled_at=plant.culled_at,
        harvested_at=plant.harvested_at,
        is_active=plant.is_active,
        telemetry_stream_count=telemetry_stream_count,
    )


async def get_plant(
    session: AsyncSession,
    *,
    site_id: str,
    source_tent_id: int,
    plant_id: str,
) -> PlantProjection:
    row = (
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
                CloudPlant.key == plant_id,
                CloudPlantLocation.site_id == site_id,
                CloudPlantLocation.source_tent_id == source_tent_id,
                CloudPlantLocation.end_at.is_(None),
            )
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="plant not found")
    plant, location, tent, line = row
    return PlantProjection(plant=plant, location=location, tent=tent, line=line)


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


async def active_plant_metric_streams(
    session: AsyncSession,
    *,
    site_id: str,
    plant: PlantProjection,
) -> list[PlantMetricStreamProjection]:
    rows = (
        await session.execute(
            select(CloudPlantMetricStream, CloudMetricPresentation)
            .outerjoin(
                CloudMetricPresentation,
                CloudMetricPresentation.metric == CloudPlantMetricStream.metric,
            )
            .where(
                CloudPlantMetricStream.site_id == site_id,
                CloudPlantMetricStream.source_plant_id == plant.plant.source_plant_id,
                CloudPlantMetricStream.is_active.is_(True),
            )
            .order_by(
                CloudPlantMetricStream.display_order,
                CloudMetricPresentation.display_order,
                CloudPlantMetricStream.metric,
                CloudPlantMetricStream.device_id,
                CloudPlantMetricStream.capability_id,
            )
        )
    ).all()
    return [
        PlantMetricStreamProjection(stream=stream, presentation=presentation)
        for stream, presentation in rows
    ]


async def latest_metrics_by_stream(
    session: AsyncSession,
    *,
    site_id: str,
    source_tent_id: int,
    streams: list[CloudPlantMetricStream],
) -> dict[MetricStreamKey, CloudLatestMetric]:
    stream_keys = {metric_stream_key(stream) for stream in streams}
    if not stream_keys:
        return {}
    device_ids, capability_ids, metrics = metric_stream_filter_values(stream_keys)
    rows = (
        await session.execute(
            select(CloudLatestMetric).where(
                CloudLatestMetric.site_id == site_id,
                CloudLatestMetric.source_tent_id == source_tent_id,
                CloudLatestMetric.device_id.in_(device_ids),
                CloudLatestMetric.capability_id.in_(capability_ids),
                CloudLatestMetric.metric.in_(metrics),
            )
        )
    ).scalars()
    latest_by_stream: dict[MetricStreamKey, CloudLatestMetric] = {}
    for row in rows:
        row_key = latest_metric_key(row)
        if row_key in stream_keys:
            latest_by_stream[row_key] = row
    return latest_by_stream


async def metric_rollups_by_stream(  # noqa: PLR0913
    session: AsyncSession,
    *,
    site_id: str,
    source_tent_id: int,
    bucket: str,
    cutoff: datetime,
    streams: list[CloudPlantMetricStream],
) -> dict[MetricStreamKey, list[CloudMetricRollup]]:
    stream_keys = {metric_stream_key(stream) for stream in streams}
    if not stream_keys:
        return {}
    device_ids, capability_ids, metrics = metric_stream_filter_values(stream_keys)
    rows = (
        (
            await session.execute(
                select(CloudMetricRollup)
                .where(
                    CloudMetricRollup.site_id == site_id,
                    CloudMetricRollup.source_tent_id == source_tent_id,
                    CloudMetricRollup.bucket == bucket,
                    CloudMetricRollup.bucket_start_at >= cutoff,
                    CloudMetricRollup.device_id.in_(device_ids),
                    CloudMetricRollup.capability_id.in_(capability_ids),
                    CloudMetricRollup.metric.in_(metrics),
                )
                .order_by(CloudMetricRollup.bucket_start_at)
            )
        )
        .scalars()
        .all()
    )
    by_stream: dict[MetricStreamKey, list[CloudMetricRollup]] = {}
    for row in rows:
        row_key = rollup_key(row)
        if row_key in stream_keys:
            by_stream.setdefault(row_key, []).append(row)
    return by_stream


def plant_detail_response(
    plant: PlantProjection,
    *,
    telemetry: list[PlantMetricStreamResponse],
    wiki_page: CloudWikiPage | None,
) -> PlantDetailResponse:
    cloud_plant = plant.plant
    location = plant.location
    return PlantDetailResponse(
        site_id=cloud_plant.site_id,
        current_tent_id=required_location_source_tent_id(location),
        current_tent_name=location_tent_name(plant.tent, location),
        id=cloud_plant.source_plant_id,
        key=cloud_plant.key,
        line_source_id=cloud_plant.line_source_id,
        line=plant_line_response(plant.line),
        sex_key=cloud_plant.sex_key,
        name=cloud_plant.name,
        grid_position=location.grid_position,
        current_location=plant_current_location_response(location, plant.tent),
        germinated_at=cloud_plant.germinated_at,
        rooted_at=cloud_plant.rooted_at,
        veg_started_at=cloud_plant.veg_started_at,
        flower_started_at=cloud_plant.flower_started_at,
        culled_at=cloud_plant.culled_at,
        culled_reason=cloud_plant.culled_reason,
        harvested_at=cloud_plant.harvested_at,
        selected_for_breeding_at=cloud_plant.selected_for_breeding_at,
        selected_for_breeding_reason=cloud_plant.selected_for_breeding_reason,
        is_active=cloud_plant.is_active,
        telemetry_stream_count=len(telemetry),
        telemetry=telemetry,
        notes=[],
        events=[],
        wiki_content=(
            None
            if wiki_page is None
            else PlantWikiContentResponse(
                path=wiki_page.path,
                title=wiki_page.title,
                frontmatter=wiki_page.frontmatter,
                body_markdown=wiki_page.body_markdown,
                sha256=wiki_page.sha256,
                source_updated_at=wiki_page.source_updated_at,
            )
        ),
    )


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


def plant_current_location_response(
    location: CloudPlantLocation,
    tent: CloudTent | None,
) -> PlantCurrentLocationResponse:
    return PlantCurrentLocationResponse(
        id=location.source_location_id,
        current_tent_id=required_location_source_tent_id(location),
        current_tent_name=location_tent_name(tent, location),
        grid_position=location.grid_position,
        start_at=location.start_at,
        end_at=location.end_at,
    )


def plant_metric_stream_responses(
    rows: list[PlantMetricStreamProjection],
    latest_by_stream: dict[MetricStreamKey, CloudLatestMetric],
) -> list[PlantMetricStreamResponse]:
    return [
        plant_metric_stream_response(
            row,
            latest_by_stream.get(metric_stream_key(row.stream)),
        )
        for row in rows
    ]


def plant_metric_stream_response(
    row: PlantMetricStreamProjection,
    latest: CloudLatestMetric | None,
) -> PlantMetricStreamResponse:
    stream = row.stream
    source_unit = source_unit_for_metric(stream.metric, latest.unit if latest else None)
    display_unit = display_unit_for_metric(stream.metric, row.presentation, source_unit)
    return PlantMetricStreamResponse(
        metric=stream.metric,
        display_name=display_name_for_metric(stream.metric, row.presentation),
        display_unit=display_unit,
        source_unit=source_unit,
        value_precision=value_precision_for_metric(row.presentation),
        accent=accent_for_metric(row.presentation),
        y_min=row.presentation.y_min if row.presentation else None,
        y_max=row.presentation.y_max if row.presentation else None,
        display_order=stream.display_order,
        history_enabled=bool(row.presentation and row.presentation.history_enabled),
        device_id=stream.device_id,
        capability_id=stream.capability_id,
        latest_reading=(
            None
            if latest is None
            else PlantMetricReadingResponse(
                value=display_metric_value(stream.metric, latest.value),
                source_value=latest.value,
                source_unit=source_unit,
                display_unit=display_unit,
                device_id=latest.device_id,
                capability_id=latest.capability_id,
                source_updated_at=latest.source_updated_at,
                received_at=latest.received_at,
                stale_after_s=latest.stale_after_s,
            )
        ),
    )


def plant_metric_history_stream_response(
    row: PlantMetricStreamProjection,
    rollups: list[CloudMetricRollup],
) -> PlantMetricHistoryStreamResponse:
    stream = row.stream
    source_unit = source_unit_for_metric(
        stream.metric, rollups[0].unit if rollups else None
    )
    display_unit = display_unit_for_metric(stream.metric, row.presentation, source_unit)
    return PlantMetricHistoryStreamResponse(
        metric=stream.metric,
        display_name=display_name_for_metric(stream.metric, row.presentation),
        display_unit=display_unit,
        source_unit=source_unit,
        value_precision=value_precision_for_metric(row.presentation),
        accent=accent_for_metric(row.presentation),
        y_min=row.presentation.y_min if row.presentation else None,
        y_max=row.presentation.y_max if row.presentation else None,
        display_order=stream.display_order,
        device_id=stream.device_id,
        capability_id=stream.capability_id,
        points=[
            PlantMetricHistoryPointResponse(
                bucket=rollup.bucket,
                bucket_start_at=rollup.bucket_start_at,
                bucket_end_at=rollup.bucket_end_at,
                min=display_optional_metric_value(stream.metric, rollup.min_value),
                avg=display_optional_metric_value(stream.metric, rollup.avg_value),
                max=display_optional_metric_value(stream.metric, rollup.max_value),
                source_min=rollup.min_value,
                source_avg=rollup.avg_value,
                source_max=rollup.max_value,
                sample_count=rollup.sample_count,
                source_unit=source_unit_for_metric(stream.metric, rollup.unit),
                display_unit=display_unit,
            )
            for rollup in rollups
        ],
    )


def metric_stream_key(stream: CloudPlantMetricStream) -> MetricStreamKey:
    return stream.device_id, stream.capability_id, stream.metric


def latest_metric_key(row: CloudLatestMetric) -> MetricStreamKey:
    return row.device_id, row.capability_id, row.metric


def rollup_key(row: CloudMetricRollup) -> MetricStreamKey:
    return row.device_id, row.capability_id, row.metric
