"""Sensor endpoints — current envelope + single-metric history.

``/api/sensors/current`` composes the latest ``sensorreading`` rows for the
five dashboard metrics (temperature, humidity, VPD, fan, reservoir) with
target bands and status colors from ``grow_state``, and the pure mock
helpers in ``mock_sensors`` for the two metrics we don't have hardware
for yet. The SPA is a pure renderer — all band/status computation
happens server-side so the front end can't drift.

``/api/sensors/history`` returns bucketed ``(ts, value)`` points for one
metric over the requested range — drives the five sparklines. Mock
metrics (``fan_pct``, ``reservoir_in``) are synthesized on the fly from
the deterministic helpers in ``mock_sensors``; DB-backed metrics go
through ``ReadingsService.get_metric_history``.
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
from dirt_shared.services.mock_sensors import (
    get_reservoir_history,
    get_reservoir_in,
)
from dirt_shared.services.readings import RANGE_DELTAS, ReadingsService
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


# Contract-allowed metric values that are NOT backed by DB readings — the
# endpoint synthesizes their history from the deterministic helpers in
# ``mock_sensors`` so the sparkline shape matches the live-hardware case.
_MOCK_METRICS = {SensorMetric.reservoir_in}

# Contract-name → DB-metric-name bridge. The API contract exposes
# ``fan_pct`` (historical — was once a mock sine wave), but the fan-
# controller firmware writes the reading as ``fan_duty_pct``. Map here
# rather than churn the contract or rename the firmware payload.
_CONTRACT_TO_DB_METRIC: dict[SensorMetric, str] = {
    SensorMetric.fan_pct: "fan_duty_pct",
}

# Per-metric display unit shared between /api/sensors/current and
# /api/sensors/history. Kept local to the router to avoid threading yet
# another constants module through the services layer.
_METRIC_UNITS: dict[SensorMetric, str] = {
    SensorMetric.temperature_f: "\u00b0F",
    SensorMetric.humidity_pct: "%",
    SensorMetric.vpd_kpa: "kPa",
    SensorMetric.dew_point_f: "\u00b0F",
    SensorMetric.pressure_hpa: "hPa",
    SensorMetric.fan_pct: "%",
    SensorMetric.reservoir_in: "in",
}

# Approximate point counts per range for the mock-metric sparklines.
# Matches the DB-backed bucket density: 1h raw (assumed ~1 / min), 5-min
# buckets for 24h, hourly for 7d. Keeping parity so the sparklines for
# mocked + real metrics look coherent in the UI.
_MOCK_POINT_COUNT: dict[Range, int] = {
    Range.field_1h: 60,
    Range.field_24h: 288,
    Range.field_7d: 168,
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
    target (fan_pct, reservoir_in); ``band_status`` returns "ok" there.
    """
    value = reading.value if reading is not None else 0.0
    ts = reading.ts if reading is not None else fallback_ts
    target = TargetBand(root=[band[0], band[1]]) if band is not None else None
    status = ContractBandStatus(band_status(value, band))
    return MetricEnvelope(value=value, unit=unit, target=target, status=status, ts=ts)


def _mock_envelope(value: float, unit: str, ts: datetime) -> MetricEnvelope:
    """Envelope for an untargeted mock metric (fan_pct, reservoir_in)."""
    return MetricEnvelope(
        value=value,
        unit=unit,
        target=None,
        status=ContractBandStatus(band_status(value, None)),
        ts=ts,
    )


@router.get("/api/sensors/current", response_model=SensorsCurrent)
async def sensors_current(
    readings: ReadingsService = Depends(get_readings),
    grow: GrowStateService = Depends(get_grow),
) -> SensorsCurrent:
    """Return the five-metric envelope with target bands, statuses, and stale flag."""
    # Fan out the independent DB queries (stage, four latest readings,
    # staleness) concurrently — six round-trips sequential is ~6x
    # latency on every dashboard render.
    stage, temp, hum, vpd, fan, stale = await asyncio.gather(
        grow.current_stage(),
        readings.get_latest_reading("temperature_f"),
        readings.get_latest_reading("humidity_pct"),
        readings.get_latest_reading("vpd_kpa"),
        readings.get_latest_reading("fan_duty_pct"),
        readings.is_sensor_stale(),
    )
    targets = STAGE_TARGETS[stage]

    # Top-level ``ts`` = newest reading seen across the real metrics
    # ("when did the tent last report?"). Fall back to the injected
    # clock when the DB is cold so the envelope is always well-formed.
    real_readings = [r for r in (temp, hum, vpd, fan) if r is not None]
    top_ts = max((r.ts for r in real_readings), default=readings.now())

    metrics = Metrics(
        temperature_f=_envelope(temp, "\u00b0F", targets.get("temperature_f"), top_ts),
        humidity_pct=_envelope(hum, "%", targets.get("humidity_pct"), top_ts),
        vpd_kpa=_envelope(vpd, "kPa", targets.get("vpd_kpa"), top_ts),
        fan_pct=_envelope(fan, "%", targets.get("fan_pct"), top_ts),
        # Reservoir remains mocked until an XKC-Y25-T12V sensor is wired.
        reservoir_in=_mock_envelope(get_reservoir_in(top_ts), "in", top_ts),
    )

    return SensorsCurrent(ts=top_ts, stale=stale, metrics=metrics)


@router.get("/api/sensors/history", response_model=SensorsHistoryResponse)
async def sensors_history(
    range: Range = Query(...),
    metric: SensorMetric = Query(...),
    readings: ReadingsService = Depends(get_readings),
) -> SensorsHistoryResponse:
    """Return bucketed ``(ts, value)`` points for one metric over ``range``.

    DB-backed metrics go through ``ReadingsService.get_metric_history``;
    mock metrics (``fan_pct``, ``reservoir_in``) are sampled from the
    deterministic helpers in ``mock_sensors`` so the sparkline shape is
    shape-identical to a live-hardware series.

    FastAPI rejects out-of-enum ``range`` / ``metric`` values at the
    query layer with 422 before the handler runs — the contract's 400
    response covers the same intent, and the SPA treats any 4xx as
    "invalid input, don't retry."
    """
    unit = _METRIC_UNITS[metric]
    if metric in _MOCK_METRICS:
        end = readings.now()
        start = end - RANGE_DELTAS[range.value]
        n = _MOCK_POINT_COUNT[range]
        points = [
            HistoryPoint(ts=p.ts, value=round(p.value, 2))
            for p in get_reservoir_history(start, end, n)
        ]
    else:
        db_metric = _CONTRACT_TO_DB_METRIC.get(metric, metric.value)
        raw = await readings.get_metric_history(db_metric, range.value)
        points = [HistoryPoint(ts=ts, value=round(value, 2)) for ts, value in raw]
    return SensorsHistoryResponse(
        range=range,
        metric=metric,
        unit=unit,
        points=points,
    )
