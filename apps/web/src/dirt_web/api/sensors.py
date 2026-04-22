"""Sensor endpoints — history (Chart.js fragment, legacy) + current envelope.

``/api/sensors/current`` composes the latest ``sensorreading`` rows for the
five dashboard metrics (temperature, humidity, VPD, fan, reservoir) with
target bands and status colors from ``grow_state``, and the pure mock
helpers in ``mock_sensors`` for the two metrics we don't have hardware
for yet. The SPA is a pure renderer — all band/status computation
happens server-side so the front end can't drift.
"""

import asyncio
from datetime import datetime
from typing import Protocol

from dirt_contracts.webapp_v1.models import (
    BandStatus as ContractBandStatus,
)
from dirt_contracts.webapp_v1.models import (
    MetricEnvelope,
    Metrics,
    SensorsCurrent,
    TargetBand,
)
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from dirt_shared.services.grow_state import (
    STAGE_TARGETS,
    GrowStateService,
    band_status,
)
from dirt_shared.services.mock_sensors import get_fan_pct, get_reservoir_in
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


@router.get("/api/sensors/readings")
async def sensor_readings(
    range: str = Query(default="24h", pattern="^(1h|24h|7d|30d)$"),
    readings: ReadingsService = Depends(get_readings),
) -> JSONResponse:
    """Return all sensor metrics for Chart.js.

    Response shape: {metric: {"labels": [...], "values": [...]}, ...}
    """
    data = await readings.get_sensor_history(range)
    return JSONResponse(data)


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
    # Fan out the independent DB queries (stage, three latest readings,
    # staleness) concurrently — five round-trips sequential is ~5x
    # latency on every dashboard render.
    stage, temp, hum, vpd, stale = await asyncio.gather(
        grow.current_stage(),
        readings.get_latest_reading("temperature_f"),
        readings.get_latest_reading("humidity_pct"),
        readings.get_latest_reading("vpd_kpa"),
        readings.is_sensor_stale(),
    )
    targets = STAGE_TARGETS[stage]

    # Top-level ``ts`` = newest reading seen across the real metrics
    # ("when did the tent last report?"). Fall back to the injected
    # clock when the DB is cold so the envelope is always well-formed.
    real_readings = [r for r in (temp, hum, vpd) if r is not None]
    top_ts = max((r.ts for r in real_readings), default=readings.now())

    metrics = Metrics(
        temperature_f=_envelope(temp, "\u00b0F", targets.get("temperature_f"), top_ts),
        humidity_pct=_envelope(hum, "%", targets.get("humidity_pct"), top_ts),
        vpd_kpa=_envelope(vpd, "kPa", targets.get("vpd_kpa"), top_ts),
        # Mock metrics share top_ts so the dashboard's "as of …" label
        # stays coherent across the tile set.
        fan_pct=_mock_envelope(get_fan_pct(top_ts), "%", top_ts),
        reservoir_in=_mock_envelope(get_reservoir_in(top_ts), "in", top_ts),
    )

    return SensorsCurrent(ts=top_ts, stale=stale, metrics=metrics)
