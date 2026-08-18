from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast

from sqlalchemy import and_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from dirt_control.api.browser_schemas.metrics import MetricAccent
from dirt_control.api.browser_schemas.plants import (
    PlantMetricHistoryCollectionResponse,
    PlantMetricHistoryPlantResponse,
    PlantMetricHistoryPointResponse,
    PlantMetricHistoryResponse,
    PlantMetricHistoryStreamResponse,
    PlantMetricReadingResponse,
    PlantMetricStreamResponse,
)
from dirt_control.models import (
    CloudLatestMetric,
    CloudMetricPresentation,
    CloudMetricRollup,
    CloudPlant,
    CloudPlantLocation,
    CloudPlantMetricStream,
)
from dirt_control.services.browser_tents import required_location_source_tent_id
from dirt_control.services.metric_rollups import require_consistent_metric_unit
from dirt_shared.metric_history import (
    MetricHistoryBucket,
    MetricHistoryRange,
    metric_history_range_spec,
)

MetricStreamKey = tuple[str, str, str]
ScopedMetricStreamKey = tuple[int, str, str, str]


SOURCE_UNITS_BY_METRIC = {
    "soil_moisture_pct": "%",
    "substrate_temp_c": "degC",
    "substrate_ec_us_cm": "us/cm",
    "substrate_ph": "pH",
}
DISPLAY_UNITS_BY_METRIC = {
    "soil_moisture_pct": "%",
    "substrate_temp_c": "degF",
    "substrate_ec_us_cm": "mS/cm",
    "substrate_ph": "pH",
}


@dataclass(frozen=True)
class PlantMetricStreamProjection:
    stream: CloudPlantMetricStream
    presentation: CloudMetricPresentation | None


@dataclass(frozen=True)
class MappedPlantHistoryTarget:
    source_plant_id: int
    key: str
    name: str
    grid_position: str | None
    source_tent_id: int


@dataclass(frozen=True)
class MappedPlantHistory:
    plant: MappedPlantHistoryTarget
    streams: tuple[PlantMetricHistoryStreamResponse, ...]


@dataclass(frozen=True)
class MappedPlantHistoryResult:
    range: MetricHistoryRange
    bucket: MetricHistoryBucket
    plants: tuple[MappedPlantHistory, ...]


def mapped_plant_history_target(
    plant: CloudPlant,
    location: CloudPlantLocation,
) -> MappedPlantHistoryTarget:
    return MappedPlantHistoryTarget(
        source_plant_id=plant.source_plant_id,
        key=plant.key,
        name=plant.name,
        grid_position=location.grid_position,
        source_tent_id=required_location_source_tent_id(location),
    )


async def active_current_plant_history_targets(
    session: AsyncSession,
    *,
    site_id: str,
    source_tent_id: int,
) -> list[MappedPlantHistoryTarget]:
    rows = (
        await session.execute(
            select(CloudPlant, CloudPlantLocation)
            .join(
                CloudPlantLocation,
                and_(
                    CloudPlantLocation.site_id == CloudPlant.site_id,
                    CloudPlantLocation.source_plant_id == CloudPlant.source_plant_id,
                ),
            )
            .where(
                CloudPlant.site_id == site_id,
                CloudPlant.is_active.is_(True),
                CloudPlantLocation.site_id == site_id,
                CloudPlantLocation.source_tent_id == source_tent_id,
                CloudPlantLocation.end_at.is_(None),
            )
            .order_by(CloudPlantLocation.grid_position, CloudPlant.key)
        )
    ).all()
    return [mapped_plant_history_target(plant, location) for plant, location in rows]


async def get_plant_metric_history_collection_response(
    session: AsyncSession,
    *,
    site_id: str,
    source_tent_id: int,
    range_key: MetricHistoryRange,
    now: datetime,
) -> PlantMetricHistoryCollectionResponse:
    result = await load_mapped_plant_histories(
        session,
        site_id=site_id,
        plants=await active_current_plant_history_targets(
            session,
            site_id=site_id,
            source_tent_id=source_tent_id,
        ),
        range_key=range_key,
        now=now,
    )
    return plant_metric_history_collection_response(result)


async def active_plant_metric_streams(
    session: AsyncSession,
    *,
    site_id: str,
    source_plant_ids: Collection[int],
) -> list[PlantMetricStreamProjection]:
    if not source_plant_ids:
        return []
    rows = (
        await session.execute(
            select(CloudPlantMetricStream, CloudMetricPresentation)
            .outerjoin(
                CloudMetricPresentation,
                CloudMetricPresentation.metric == CloudPlantMetricStream.metric,
            )
            .where(
                CloudPlantMetricStream.site_id == site_id,
                CloudPlantMetricStream.source_plant_id.in_(tuple(source_plant_ids)),
                CloudPlantMetricStream.is_active.is_(True),
            )
            .order_by(
                CloudPlantMetricStream.source_plant_id,
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
    streams: Sequence[CloudPlantMetricStream],
) -> dict[MetricStreamKey, CloudLatestMetric]:
    stream_keys = {metric_stream_key(stream) for stream in streams}
    if not stream_keys:
        return {}
    rows = (
        await session.execute(
            select(CloudLatestMetric).where(
                CloudLatestMetric.site_id == site_id,
                CloudLatestMetric.source_tent_id == source_tent_id,
                tuple_(
                    CloudLatestMetric.device_id,
                    CloudLatestMetric.capability_id,
                    CloudLatestMetric.metric,
                ).in_(tuple(stream_keys)),
            )
        )
    ).scalars()
    return {latest_metric_key(row): row for row in rows}


async def load_mapped_plant_histories(
    session: AsyncSession,
    *,
    site_id: str,
    plants: Sequence[MappedPlantHistoryTarget],
    range_key: MetricHistoryRange,
    now: datetime,
) -> MappedPlantHistoryResult:
    bucket, window = metric_history_range_spec(range_key)
    stream_rows = [
        row
        for row in await active_plant_metric_streams(
            session,
            site_id=site_id,
            source_plant_ids={plant.source_plant_id for plant in plants},
        )
        if row.presentation is not None and row.presentation.history_enabled
    ]
    streams_by_plant: dict[int, list[PlantMetricStreamProjection]] = {}
    for row in stream_rows:
        streams_by_plant.setdefault(row.stream.source_plant_id, []).append(row)

    plants_by_id = {plant.source_plant_id: plant for plant in plants}
    stream_keys = {
        scoped_metric_stream_key(
            plants_by_id[row.stream.source_plant_id].source_tent_id,
            row.stream,
        )
        for row in stream_rows
    }
    rollups_by_stream = await metric_rollups_by_stream(
        session,
        site_id=site_id,
        bucket=bucket,
        cutoff=now - window,
        stream_keys=stream_keys,
    )
    return MappedPlantHistoryResult(
        range=range_key,
        bucket=bucket,
        plants=tuple(
            MappedPlantHistory(
                plant=plant,
                streams=tuple(
                    plant_metric_history_stream_response(
                        row,
                        rollups_by_stream.get(
                            scoped_metric_stream_key(plant.source_tent_id, row.stream),
                            [],
                        ),
                    )
                    for row in streams_by_plant.get(plant.source_plant_id, [])
                ),
            )
            for plant in plants
        ),
    )


async def metric_rollups_by_stream(
    session: AsyncSession,
    *,
    site_id: str,
    bucket: MetricHistoryBucket,
    cutoff: datetime,
    stream_keys: Collection[ScopedMetricStreamKey],
) -> dict[ScopedMetricStreamKey, list[CloudMetricRollup]]:
    if not stream_keys:
        return {}
    rows = (
        (
            await session.execute(
                select(CloudMetricRollup)
                .where(
                    CloudMetricRollup.site_id == site_id,
                    CloudMetricRollup.bucket == bucket,
                    CloudMetricRollup.bucket_start_at >= cutoff,
                    tuple_(
                        CloudMetricRollup.source_tent_id,
                        CloudMetricRollup.device_id,
                        CloudMetricRollup.capability_id,
                        CloudMetricRollup.metric,
                    ).in_(tuple(stream_keys)),
                )
                .order_by(
                    CloudMetricRollup.bucket_start_at,
                    CloudMetricRollup.device_id,
                    CloudMetricRollup.capability_id,
                    CloudMetricRollup.metric,
                )
            )
        )
        .scalars()
        .all()
    )
    by_stream: dict[ScopedMetricStreamKey, list[CloudMetricRollup]] = {}
    for row in rows:
        by_stream.setdefault(rollup_key(row), []).append(row)
    return by_stream


def plant_metric_history_response(
    result: MappedPlantHistoryResult,
    *,
    source_plant_id: int,
) -> PlantMetricHistoryResponse:
    plant = next(
        plant
        for plant in result.plants
        if plant.plant.source_plant_id == source_plant_id
    )
    return PlantMetricHistoryResponse(
        range=result.range,
        bucket=result.bucket,
        streams=list(plant.streams),
    )


def plant_metric_history_collection_response(
    result: MappedPlantHistoryResult,
) -> PlantMetricHistoryCollectionResponse:
    return PlantMetricHistoryCollectionResponse(
        range=result.range,
        bucket=result.bucket,
        plants=[
            PlantMetricHistoryPlantResponse(
                id=plant.plant.source_plant_id,
                key=plant.plant.key,
                name=plant.plant.name,
                grid_position=plant.plant.grid_position,
                streams=list(plant.streams),
            )
            for plant in result.plants
            if plant.streams
        ],
    )


def plant_metric_history_stream_response(
    row: PlantMetricStreamProjection,
    rollups: Sequence[CloudMetricRollup],
) -> PlantMetricHistoryStreamResponse:
    stream = row.stream
    source_unit = source_unit_for_metric(
        stream.metric,
        require_consistent_metric_unit(
            (rollup.unit for rollup in rollups),
            metric=stream.metric,
        ),
    )
    return PlantMetricHistoryStreamResponse(
        metric=stream.metric,
        display_name=display_name_for_metric(stream.metric, row.presentation),
        display_unit=display_unit_for_metric(
            stream.metric, row.presentation, source_unit
        ),
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
                ts=rollup.bucket_start_at,
                value=display_optional_metric_value(stream.metric, rollup.avg_value),
            )
            for rollup in rollups
        ],
    )


def plant_metric_stream_responses(
    rows: Sequence[PlantMetricStreamProjection],
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


def display_metric_value(metric: str, value: float) -> float:
    if metric == "substrate_temp_c":
        return value * 9 / 5 + 32
    if metric == "substrate_ec_us_cm":
        return value / 1000
    return value


def display_optional_metric_value(metric: str, value: float | None) -> float | None:
    if value is None:
        return None
    return display_metric_value(metric, value)


def source_unit_for_metric(metric: str, source_unit: str | None) -> str | None:
    return source_unit or SOURCE_UNITS_BY_METRIC.get(metric)


def display_unit_for_metric(
    metric: str,
    presentation: CloudMetricPresentation | None,
    source_unit: str | None,
) -> str:
    if presentation is not None:
        return presentation.unit
    return DISPLAY_UNITS_BY_METRIC.get(metric) or source_unit or ""


def display_name_for_metric(
    metric: str, presentation: CloudMetricPresentation | None
) -> str:
    if presentation is not None:
        return presentation.display_name
    return metric.replace("_", " ").title()


def value_precision_for_metric(presentation: CloudMetricPresentation | None) -> int:
    return presentation.value_precision if presentation is not None else 1


def accent_for_metric(presentation: CloudMetricPresentation | None) -> MetricAccent:
    if presentation is None:
        return "neutral"
    return cast(MetricAccent, presentation.accent)


def metric_stream_key(stream: CloudPlantMetricStream) -> MetricStreamKey:
    return stream.device_id, stream.capability_id, stream.metric


def latest_metric_key(row: CloudLatestMetric) -> MetricStreamKey:
    return row.device_id, row.capability_id, row.metric


def scoped_metric_stream_key(
    source_tent_id: int,
    stream: CloudPlantMetricStream,
) -> ScopedMetricStreamKey:
    return source_tent_id, *metric_stream_key(stream)


def rollup_key(row: CloudMetricRollup) -> ScopedMetricStreamKey:
    if row.source_tent_id is None:
        raise ValueError("mapped metric rollup is missing source_tent_id")
    return row.source_tent_id, row.device_id, row.capability_id, row.metric
