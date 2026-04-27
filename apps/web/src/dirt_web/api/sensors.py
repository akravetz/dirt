"""Sensor endpoints — current envelope + single-metric history.

``/api/sensors/current`` composes the latest ``sensorreading`` rows for
the five dashboard metrics (temperature, humidity, VPD, fan, reservoir)
with target bands and status colors from ``grow_state``. The SPA is a
pure renderer — all band/status computation happens server-side so the
front end can't drift.

``/api/sensors/history`` returns bucketed ``(ts, value)`` points for one
metric over the requested range — drives the five sparklines.
"""

import asyncio
from datetime import datetime
from typing import Protocol

from dirt_contracts.webapp_v1.models import (
    BandStatus as ContractBandStatus,
)
from dirt_contracts.webapp_v1.models import (
    HistoryPoint,
    MetricEnvelope,
    Metrics,
    Range,
    SensorMetric,
    SensorsCurrent,
    SensorsHistoryResponse,
    TargetBand,
)
from fastapi import APIRouter, Depends, Query

from dirt_shared.services.grow_state import (
    STAGE_TARGETS,
    GrowStateService,
    band_status,
)
from dirt_shared.services.readings import ReadingsService
from dirt_web.deps import get_grow, get_readings


class _ReadingLike(Protocol):
    """Structural shape of ``SensorReading`` used by the envelope helper.

    Declared here (not imported) because ``dirt_web.api`` is forbidden
    from importing ``dirt_shared.models.*`` directly — the import-
    boundary invariant requires api/* to go through services. The
    service returns ``SensorReading`` instances which duck-type into
    this Protocol; the helper doesn't need the model identity.
    """

    value: float
    ts: datetime


router = APIRouter(tags=["sensors"])


# Contract-name → DB-metric-name bridge. The API contract exposes
# ``fan_pct`` (kept stable to avoid contract churn) but the firmware
# writes ``fan_duty_pct``. Map here rather than rename either side.
_CONTRACT_TO_DB_METRIC: dict[SensorMetric, str] = {
    SensorMetric.fan_pct: "fan_duty_pct",
}

# Per-metric display unit shared between /api/sensors/current and
# /api/sensors/history. Kept local to the router to avoid threading yet
# another constants module through the services layer.
_METRIC_UNITS: dict[SensorMetric, str] = {
    SensorMetric.temperature_f: "°F",
    SensorMetric.humidity_pct: "%",
    SensorMetric.vpd_kpa: "kPa",
    SensorMetric.dew_point_f: "°F",
    SensorMetric.pressure_hpa: "hPa",
    SensorMetric.fan_pct: "%",
    SensorMetric.reservoir_in: "in",
}


def _envelope(
    reading: _ReadingLike | None,
    unit: str,
    band: tuple[float, float] | None,
    fallback_ts: datetime,
) -> MetricEnvelope:
    """Wrap one metric reading into the contract's MetricEnvelope shape.

    ``reading=None`` (cold-cluster case, no row yet) emits a well-typed
    envelope at value=0 so the contract shape stays valid; the client
    can check ``stale`` on the enclosing envelope to render the "no
    data" affordance. ``band=None`` for metrics without a stage-defined
    target (currently reservoir_in); ``band_status`` returns "ok" there.
    """
    value = reading.value if reading is not None else 0.0
    ts = reading.ts if reading is not None else fallback_ts
    target = TargetBand(root=[band[0], band[1]]) if band is not None else None
    status = ContractBandStatus(band_status(value, band))
    return MetricEnvelope(value=value, unit=unit, target=target, status=status, ts=ts)


@router.get("/api/sensors/current", response_model=SensorsCurrent)
async def sensors_current(
    readings: ReadingsService = Depends(get_readings),
    grow: GrowStateService = Depends(get_grow),
) -> SensorsCurrent:
    """Return the five-metric envelope with target bands, statuses, and stale flag."""
    # All independent latest-reading queries fan out concurrently —
    # otherwise we'd pay sequential round-trip latency on every render.
    stage, temp, hum, vpd, fan, reservoir, stale = await asyncio.gather(
        grow.current_stage(),
        readings.get_latest_reading("temperature_f"),
        readings.get_latest_reading("humidity_pct"),
        readings.get_latest_reading("vpd_kpa"),
        readings.get_latest_reading("fan_duty_pct"),
        readings.get_latest_reading("reservoir_in", "reservoir"),
        readings.is_sensor_stale(),
    )
    targets = STAGE_TARGETS[stage]

    # Top-level ``ts`` = newest reading seen across all real metrics
    # ("when did the tent last report?"). Fall back to the injected
    # clock when the DB is cold so the envelope is always well-formed.
    real_readings = [r for r in (temp, hum, vpd, fan, reservoir) if r is not None]
    top_ts = max((r.ts for r in real_readings), default=readings.now())

    metrics = Metrics(
        temperature_f=_envelope(temp, "°F", targets.get("temperature_f"), top_ts),
        humidity_pct=_envelope(hum, "%", targets.get("humidity_pct"), top_ts),
        vpd_kpa=_envelope(vpd, "kPa", targets.get("vpd_kpa"), top_ts),
        fan_pct=_envelope(fan, "%", targets.get("fan_pct"), top_ts),
        reservoir_in=_envelope(reservoir, "in", targets.get("reservoir_in"), top_ts),
    )

    return SensorsCurrent(ts=top_ts, stale=stale, metrics=metrics)


@router.get("/api/sensors/history", response_model=SensorsHistoryResponse)
async def sensors_history(
    range: Range = Query(...),
    metric: SensorMetric = Query(...),
    readings: ReadingsService = Depends(get_readings),
) -> SensorsHistoryResponse:
    """Return bucketed ``(ts, value)`` points for one metric over ``range``.

    ``fan_pct`` resolves to its DB-side name ``fan_duty_pct`` via
    ``_CONTRACT_TO_DB_METRIC``; every other metric's contract name
    matches the persisted name 1:1.

    FastAPI rejects out-of-enum ``range`` / ``metric`` values at the
    query layer with 422 before the handler runs — the contract's 400
    response covers the same intent, and the SPA treats any 4xx as
    "invalid input, don't retry."
    """
    unit = _METRIC_UNITS[metric]
    db_metric = _CONTRACT_TO_DB_METRIC.get(metric, metric.value)
    raw = await readings.get_metric_history(db_metric, range.value)
    points = [HistoryPoint(ts=ts, value=round(value, 2)) for ts, value in raw]
    return SensorsHistoryResponse(
        range=range,
        metric=metric,
        unit=unit,
        points=points,
    )
