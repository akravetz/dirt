from __future__ import annotations

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models import MetricPresentation

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
    "substrate_temp_c",
    "substrate_ec_us_cm",
    "substrate_ph",
}
SUBSTRATE_PRESENTATION_ROWS = {
    "substrate_temp_c": ("Substrate Temp", "°F", 1),
    "substrate_ec_us_cm": ("Substrate EC", "mS/cm", 2),
    "substrate_ph": ("Substrate pH", "pH", 1),
}
RAW_OR_INTERNAL_METRICS = {
    "soil_moisture_raw",
    "reservoir_ph_probe_voltage",
    "temperature_c",
    "dew_point_f",
}


async def test_local_metric_presentation_seed_marks_product_history(app_engine):
    async with AsyncSession(app_engine) as session:
        rows = (
            await session.exec(
                select(MetricPresentation).order_by(MetricPresentation.metric)
            )
        ).all()

    by_metric = {row.metric: row for row in rows}
    history_metrics = {
        metric for metric, row in by_metric.items() if row.history_enabled
    }

    assert history_metrics >= PRODUCT_HISTORY_METRICS
    assert by_metric["soil_moisture_pct"].accent == "moisture"
    assert by_metric["soil_moisture_pct"].id is not None
    assert by_metric["soil_moisture_pct"].unit == "%"
    assert by_metric["soil_moisture_pct"].history_enabled is True
    assert by_metric["soil_moisture_pct"].current_enabled is False
    for metric, (display_name, unit, precision) in SUBSTRATE_PRESENTATION_ROWS.items():
        row = by_metric[metric]
        assert row.display_name == display_name
        assert row.unit == unit
        assert row.value_precision == precision
        assert row.history_enabled is True
        assert row.current_enabled is False
    assert RAW_OR_INTERNAL_METRICS.isdisjoint(history_metrics)
    assert "soil_moisture_raw" not in by_metric


async def test_dehumidifier_presentation_uses_runtime_history_metric(app_engine):
    async with AsyncSession(app_engine) as session:
        rows = (
            await session.exec(
                select(MetricPresentation).where(
                    MetricPresentation.metric.in_(
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
