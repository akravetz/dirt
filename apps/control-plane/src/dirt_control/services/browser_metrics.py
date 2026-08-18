from __future__ import annotations

from datetime import datetime
from typing import cast

from fastapi import HTTPException, status
from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dirt_control.api.browser_schemas.metrics import (
    CurrentMetricResponse,
    MetricHistoryPointResponse,
    MetricHistoryResponse,
    MetricPresentationHistoryGroupResponse,
    MetricPresentationMetricResponse,
    MetricPresentationResponse,
)
from dirt_control.models import (
    CloudLatestMetric,
    CloudMetricPresentation,
    CloudMetricRollup,
)
from dirt_control.services.metric_rollups import require_consistent_metric_unit
from dirt_shared.metric_history import MetricHistoryRange, metric_history_range_spec


async def current_metrics(
    session: AsyncSession, *, site_id: str, source_tent_id: int
) -> list[CurrentMetricResponse]:
    rows = (
        await session.execute(
            select(CloudLatestMetric)
            .where(
                CloudLatestMetric.site_id == site_id,
                CloudLatestMetric.source_tent_id == source_tent_id,
            )
            .order_by(
                CloudLatestMetric.metric,
                CloudLatestMetric.device_id,
                CloudLatestMetric.capability_id,
            )
        )
    ).scalars()
    return [current_metric_response(row) for row in rows]


async def metric_presentation(session: AsyncSession) -> MetricPresentationResponse:
    rows = (
        (
            await session.execute(
                select(CloudMetricPresentation).order_by(
                    CloudMetricPresentation.display_order,
                    CloudMetricPresentation.metric,
                )
            )
        )
        .scalars()
        .all()
    )
    history_rows: list[tuple[CloudMetricPresentation, tuple[str, str, int]]] = []
    for row in rows:
        if not row.history_enabled:
            continue
        group_parts = history_group_parts(row)
        if group_parts is not None:
            history_rows.append((row, group_parts))
    history_rows.sort(
        key=lambda item: (
            item[1][2],
            item[0].display_order,
            item[0].metric,
        )
    )
    history_groups: list[MetricPresentationHistoryGroupResponse] = []
    history_groups_by_key: dict[str, MetricPresentationHistoryGroupResponse] = {}
    for row, group_parts in history_rows:
        group_key, group_label, group_order = group_parts
        existing_group = history_groups_by_key.get(group_key)
        if existing_group is None:
            existing_group = MetricPresentationHistoryGroupResponse(
                group=group_key,
                label=group_label,
                display_order=group_order,
                metrics=[],
            )
            history_groups_by_key[group_key] = existing_group
            history_groups.append(existing_group)
        existing_group.metrics.append(presentation_metric_response(row))

    return MetricPresentationResponse(
        current_metrics=[
            presentation_metric_response(row) for row in rows if row.current_enabled
        ],
        history_groups=history_groups,
    )


async def metric_history(  # noqa: PLR0913
    session: AsyncSession,
    *,
    site_id: str,
    source_tent_id: int,
    metric: str,
    range_key: MetricHistoryRange,
    now: datetime,
) -> MetricHistoryResponse:
    bucket, window = metric_history_range_spec(range_key)
    cutoff = now - window
    has_weighted_value = and_(
        CloudMetricRollup.avg_value.is_not(None),
        CloudMetricRollup.sample_count > 0,
    )
    rows = (
        await session.execute(
            select(
                CloudMetricRollup.bucket,
                CloudMetricRollup.bucket_start_at,
                func.max(CloudMetricRollup.bucket_end_at).label("bucket_end_at"),
                func.min(CloudMetricRollup.min_value).label("min_value"),
                func.sum(
                    case(
                        (
                            has_weighted_value,
                            CloudMetricRollup.avg_value
                            * CloudMetricRollup.sample_count,
                        ),
                        else_=0.0,
                    )
                ).label("weighted_sum"),
                func.sum(
                    case(
                        (has_weighted_value, CloudMetricRollup.sample_count),
                        else_=0,
                    )
                ).label("weighted_sample_count"),
                func.max(CloudMetricRollup.max_value).label("max_value"),
                func.sum(CloudMetricRollup.sample_count).label("sample_count"),
                CloudMetricRollup.unit,
            )
            .where(
                CloudMetricRollup.site_id == site_id,
                CloudMetricRollup.source_tent_id == source_tent_id,
                CloudMetricRollup.metric == metric,
                CloudMetricRollup.bucket == bucket,
                CloudMetricRollup.bucket_start_at >= cutoff,
            )
            .group_by(
                CloudMetricRollup.bucket,
                CloudMetricRollup.bucket_start_at,
                CloudMetricRollup.unit,
            )
            .order_by(CloudMetricRollup.bucket_start_at)
        )
    ).all()
    require_consistent_metric_unit((row.unit for row in rows), metric=metric)
    return MetricHistoryResponse(
        metric=metric,
        range=range_key,
        points=[
            MetricHistoryPointResponse(
                bucket=row.bucket,
                bucket_start_at=row.bucket_start_at,
                bucket_end_at=row.bucket_end_at,
                min=row.min_value,
                avg=(
                    row.weighted_sum / row.weighted_sample_count
                    if row.weighted_sample_count
                    else None
                ),
                max=row.max_value,
                sample_count=row.sample_count,
                unit=row.unit,
            )
            for row in rows
        ],
    )


def current_metric_response(row: CloudLatestMetric) -> CurrentMetricResponse:
    return CurrentMetricResponse(
        metric=row.metric,
        value=row.value,
        unit=row.unit,
        capability_id=row.capability_id,
        device_id=row.device_id,
        source_updated_at=row.source_updated_at,
        received_at=row.received_at,
        stale_after_s=row.stale_after_s,
    )


def presentation_metric_response(
    row: CloudMetricPresentation,
) -> MetricPresentationMetricResponse:
    return MetricPresentationMetricResponse(
        metric=row.metric,
        display_name=row.display_name,
        unit=row.unit,
        accent=row.accent,
        value_precision=row.value_precision,
        y_min=row.y_min,
        y_max=row.y_max,
        display_order=row.display_order,
    )


def history_group_parts(
    row: CloudMetricPresentation,
) -> tuple[str, str, int] | None:
    parts = (
        row.dashboard_group,
        row.dashboard_group_label,
        row.dashboard_group_order,
    )
    if all(part is None for part in parts):
        return None
    if any(part is None for part in parts):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "history metric presentation row has a partial dashboard group",
        )
    group, label, order = parts
    return cast(str, group), cast(str, label), cast(int, order)
