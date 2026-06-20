from __future__ import annotations

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from dirt_control.api.browser_schemas.metrics import (
    DISPLAY_UNITS_BY_METRIC,
    METRIC_HISTORY_RANGES,
    SOURCE_UNITS_BY_METRIC,
    CurrentMetricResponse,
    MetricHistoryPointResponse,
    MetricHistoryResponse,
    MetricPresentationHistoryGroupResponse,
    MetricPresentationMetricResponse,
    MetricPresentationRangeResponse,
    MetricPresentationResponse,
    MetricStreamKey,
)
from dirt_control.models import (
    CloudLatestMetric,
    CloudMetricPresentation,
    CloudMetricRollup,
)


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
    history_rows = sorted(
        (row for row in rows if row.history_enabled),
        key=lambda row: (
            row.dashboard_group_order if row.dashboard_group_order is not None else 0,
            row.display_order,
            row.metric,
        ),
    )
    history_groups: list[MetricPresentationHistoryGroupResponse] = []
    history_groups_by_key: dict[str, MetricPresentationHistoryGroupResponse] = {}
    for row in history_rows:
        group_key, group_label, group_order = history_group_parts(row)
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
        supported_ranges=supported_metric_ranges_response(),
    )


async def metric_history(  # noqa: PLR0913
    session: AsyncSession,
    *,
    site_id: str,
    source_tent_id: int,
    metric: str,
    range_key: str,
    device_id: str | None,
    capability_id: str | None,
    now: datetime,
) -> MetricHistoryResponse:
    range_spec = METRIC_HISTORY_RANGES.get(range_key)
    if range_spec is None:
        raise HTTPException(status_code=400, detail="invalid range")
    if (device_id is None) != (capability_id is None):
        raise HTTPException(
            status_code=400,
            detail="device_id and capability_id must be supplied together",
        )
    bucket, window = range_spec
    cutoff = now - window
    stream_filters = (
        (
            CloudMetricRollup.device_id == device_id,
            CloudMetricRollup.capability_id == capability_id,
        )
        if device_id is not None and capability_id is not None
        else ()
    )
    rows = (
        await session.execute(
            select(CloudMetricRollup)
            .where(
                CloudMetricRollup.site_id == site_id,
                CloudMetricRollup.source_tent_id == source_tent_id,
                CloudMetricRollup.metric == metric,
                CloudMetricRollup.bucket == bucket,
                CloudMetricRollup.bucket_start_at >= cutoff,
            )
            .where(*stream_filters)
            .order_by(CloudMetricRollup.bucket_start_at)
        )
    ).scalars()
    return MetricHistoryResponse(
        metric=metric,
        range=range_key,
        points=[
            MetricHistoryPointResponse(
                bucket=row.bucket,
                bucket_start_at=row.bucket_start_at,
                bucket_end_at=row.bucket_end_at,
                min=row.min_value,
                avg=row.avg_value,
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


def supported_metric_ranges_response() -> list[MetricPresentationRangeResponse]:
    return [
        MetricPresentationRangeResponse(range=range_key, bucket=bucket)
        for range_key, (bucket, _) in METRIC_HISTORY_RANGES.items()
    ]


def history_group_parts(row: CloudMetricPresentation) -> tuple[str, str, int]:
    if (
        row.dashboard_group is None
        or row.dashboard_group_label is None
        or row.dashboard_group_order is None
    ):
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "history metric presentation row missing dashboard group",
        )
    return row.dashboard_group, row.dashboard_group_label, row.dashboard_group_order


def metric_stream_filter_values(
    stream_keys: set[MetricStreamKey],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    return (
        tuple({device_id for device_id, _, _ in stream_keys}),
        tuple({capability_id for _, capability_id, _ in stream_keys}),
        tuple({metric for _, _, metric in stream_keys}),
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


def accent_for_metric(presentation: CloudMetricPresentation | None) -> str:
    return presentation.accent if presentation is not None else "neutral"
