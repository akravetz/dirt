"""Single source of truth for sensor-metric metadata.

Used by:
  - ``apps/web/src/dirt_web/api/sensors.py`` for unit / DB-name / value
    transform / band lookup at request time
  - ``GET /api/sensors/metadata`` for the public-facing metadata the SPA
    consumes to render its dashboard tiles
  - The frontend, indirectly, via the metadata endpoint above

A metric's contract name (``humidifier_intensity_pct``) can differ from
its DB name (``humidifier_mist_level``). When they differ, ``transform``
is the function that takes the raw DB value to the display value (here,
mist level 0..9 → intensity 0..100%).

Stage-dependent target bands stay in ``grow_state.STAGE_TARGETS`` —
those are stage-keyed tables, not per-metric singletons. This registry
declares ``has_target_band`` so the API knows whether to look up a band
for a given metric.

The registry dict is built lazily on first access so the no-module-
level-singletons invariant doesn't fire on the (otherwise harmless)
declarative ``MetricSpec(...)`` calls.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass

from dirt_contracts.webapp_v1.models import SensorMetric


@dataclass(frozen=True)
class MetricSpec:
    """Per-metric metadata. One entry per ``SensorMetric`` enum value."""

    metric: SensorMetric
    display_name: str
    unit: str
    accent: str  # FE palette key: "temp" | "humidity" | "vpd" | "fan" | etc.
    y_min: float | None
    y_max: float | None
    has_target_band: bool
    db_metric: str
    db_location: str = "tent"
    transform: Callable[[float], float] | None = None
    dashboard_position: int | None = None


def _mist_level_to_pct(v: float) -> float:
    """H7142 Manual-mode level (0..9) → intensity percent (0..100)."""
    return v * 100.0 / 9.0


@functools.cache
def _registry() -> dict[SensorMetric, MetricSpec]:
    return {
        SensorMetric.temperature_f: MetricSpec(
            metric=SensorMetric.temperature_f,
            display_name="Temperature",
            unit="°F",
            accent="temp",
            y_min=60.0,
            y_max=95.0,
            has_target_band=True,
            db_metric="temperature_f",
            dashboard_position=0,
        ),
        SensorMetric.humidity_pct: MetricSpec(
            metric=SensorMetric.humidity_pct,
            display_name="Humidity",
            unit="%",
            accent="humidity",
            y_min=30.0,
            y_max=80.0,
            has_target_band=True,
            db_metric="humidity_pct",
            dashboard_position=1,
        ),
        SensorMetric.vpd_kpa: MetricSpec(
            metric=SensorMetric.vpd_kpa,
            display_name="VPD",
            unit="kPa",
            accent="vpd",
            y_min=0.3,
            y_max=2.0,
            has_target_band=True,
            db_metric="vpd_kpa",
            dashboard_position=2,
        ),
        SensorMetric.dew_point_f: MetricSpec(
            metric=SensorMetric.dew_point_f,
            display_name="Dew Point",
            unit="°F",
            accent="temp",
            y_min=40.0,
            y_max=70.0,
            has_target_band=False,
            db_metric="dew_point_f",
            # Not on the dashboard tile grid; keep registered for /api/sensors/history.
            dashboard_position=None,
        ),
        SensorMetric.pressure_hpa: MetricSpec(
            metric=SensorMetric.pressure_hpa,
            display_name="Pressure",
            unit="hPa",
            accent="neutral",
            y_min=970.0,
            y_max=1040.0,
            has_target_band=False,
            db_metric="pressure_hpa",
            dashboard_position=None,
        ),
        SensorMetric.fan_pct: MetricSpec(
            metric=SensorMetric.fan_pct,
            display_name="Fan",
            unit="%",
            accent="neutral",
            y_min=0.0,
            y_max=100.0,
            has_target_band=True,
            # Firmware writes ``fan_duty_pct``; contract name is ``fan_pct``.
            db_metric="fan_duty_pct",
            dashboard_position=3,
        ),
        SensorMetric.humidifier_intensity_pct: MetricSpec(
            metric=SensorMetric.humidifier_intensity_pct,
            display_name="Humidifier",
            unit="%",
            accent="humidity",
            y_min=0.0,
            y_max=100.0,
            has_target_band=False,
            # Loop writes the raw H7142 Manual-mode level; we serve a
            # normalized percent. See `humidifier.py:_record_actuator`.
            db_metric="humidifier_mist_level",
            transform=_mist_level_to_pct,
            dashboard_position=4,
        ),
        SensorMetric.reservoir_in: MetricSpec(
            metric=SensorMetric.reservoir_in,
            display_name="Reservoir",
            unit="in",
            accent="moisture",
            y_min=10.0,
            y_max=40.0,
            has_target_band=False,
            db_metric="reservoir_in",
            db_location="reservoir",
            dashboard_position=5,
        ),
    }


def metric_spec(metric: SensorMetric) -> MetricSpec:
    return _registry()[metric]


def transform_value(metric: SensorMetric, value: float) -> float:
    """Apply the metric's display transform (if any), else return as-is."""
    spec = metric_spec(metric)
    return spec.transform(value) if spec.transform is not None else value


def dashboard_metrics() -> list[MetricSpec]:
    """Metric specs in dashboard render order."""
    ordered = sorted(
        (s for s in _registry().values() if s.dashboard_position is not None),
        key=lambda s: s.dashboard_position or 0,
    )
    return ordered
