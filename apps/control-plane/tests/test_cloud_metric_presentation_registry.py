from __future__ import annotations

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_control.models import CloudMetricPresentation

PRODUCT_HISTORY_METRICS = {
    "temperature_f",
    "heater_intensity_pct",
    "fan_pct",
    "humidity_pct",
    "humidifier_intensity_pct",
    "dehumidifier_runtime_pct",
    "vpd_kpa",
    "reservoir_in",
    "reservoir_ph",
    "soil_moisture_pct",
}
RAW_OR_INTERNAL_METRICS = {
    "soil_moisture_raw",
    "reservoir_ph_probe_voltage",
    "temperature_c",
    "dew_point_f",
}


async def test_cloud_metric_presentation_seed_marks_product_history(cloud_engine):
    async with AsyncSession(cloud_engine) as session:
        rows = (
            await session.exec(
                select(CloudMetricPresentation).order_by(CloudMetricPresentation.metric)
            )
        ).all()

    by_metric = {row.metric: row for row in rows}
    history_metrics = {
        metric for metric, row in by_metric.items() if row.history_enabled
    }

    assert history_metrics >= PRODUCT_HISTORY_METRICS
    assert by_metric["soil_moisture_pct"].accent == "moisture"
    assert by_metric["soil_moisture_pct"].unit == "%"
    assert by_metric["soil_moisture_pct"].history_enabled is True
    assert by_metric["soil_moisture_pct"].current_enabled is False
    assert RAW_OR_INTERNAL_METRICS.isdisjoint(history_metrics)
    assert "soil_moisture_raw" not in by_metric


async def test_cloud_dehumidifier_presentation_uses_runtime_history_metric(
    cloud_engine,
):
    async with AsyncSession(cloud_engine) as session:
        rows = (
            await session.exec(
                select(CloudMetricPresentation).where(
                    CloudMetricPresentation.metric.in_(
                        ["dehumidifier_on", "dehumidifier_runtime_pct"]
                    )
                )
            )
        ).all()

    by_metric = {row.metric: row for row in rows}

    assert "dehumidifier_on" not in by_metric
    assert by_metric["dehumidifier_runtime_pct"].history_enabled is True
    assert by_metric["dehumidifier_runtime_pct"].current_enabled is False
    assert by_metric["dehumidifier_runtime_pct"].unit == "%"
