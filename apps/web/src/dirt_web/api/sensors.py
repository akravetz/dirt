"""Sensor endpoints — history (Chart.js fragment, legacy) + current envelope.

``/api/sensors/current`` composes the latest ``sensorreading`` rows for the
five dashboard metrics (temperature, humidity, VPD, fan, reservoir) with
target bands and status colors from ``grow_state``, and the pure mock
helpers in ``mock_sensors`` for the two metrics we don't have hardware
for yet. The SPA is a pure renderer — all band/status computation
happens server-side so the front end can't drift.
"""

from datetime import datetime

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
    value: float,
    unit: str,
    band: tuple[float, float] | None,
    ts: datetime,
) -> MetricEnvelope:
    """Wrap one metric reading into the contract's MetricEnvelope shape.

    ``band`` is ``None`` for metrics without a stage-defined target
    (fan_pct, reservoir_in today). ``band_status`` returns "ok" in that
    case — the client renders the tile without a target pill.
    """
    target = TargetBand(root=[band[0], band[1]]) if band is not None else None
    status = ContractBandStatus(band_status(value, band))
    return MetricEnvelope(value=value, unit=unit, target=target, status=status, ts=ts)


@router.get("/api/sensors/current", response_model=SensorsCurrent)
async def sensors_current(
    readings: ReadingsService = Depends(get_readings),
    grow: GrowStateService = Depends(get_grow),
) -> SensorsCurrent:
    """Return the five-metric envelope with target bands, statuses, and stale flag."""
    stage = await grow.current_stage()
    targets = STAGE_TARGETS[stage]

    temp = await readings.get_latest_reading("temperature_f")
    hum = await readings.get_latest_reading("humidity_pct")
    vpd = await readings.get_latest_reading("vpd_kpa")

    # The top-level ``ts`` is the newest reading seen across the real
    # sensor metrics — i.e. "when did the tent last report?". We fall
    # back to now() if the DB has nothing at all, so the envelope is
    # always well-formed (stale=True in that case is handled below).
    real_readings = [r for r in (temp, hum, vpd) if r is not None]
    top_ts = max((r.ts for r in real_readings), default=readings.now())

    # Missing-reading fallbacks: emit a well-typed envelope with value=0
    # + status=crit so the client tile renders the "no data" affordance
    # without the request 500ing. In practice the DB is seeded before
    # dirt-web starts serving; this path only fires on a cold cluster.
    def _maybe(
        metric_value: float | None, reading_ts: datetime | None, unit: str, band
    ):
        if metric_value is None:
            return _envelope(0.0, unit, band, top_ts)
        return _envelope(metric_value, unit, band, reading_ts or top_ts)

    metrics = Metrics(
        temperature_f=_maybe(
            temp.value if temp else None,
            temp.ts if temp else None,
            "\u00b0F",
            targets.get("temperature_f"),
        ),
        humidity_pct=_maybe(
            hum.value if hum else None,
            hum.ts if hum else None,
            "%",
            targets.get("humidity_pct"),
        ),
        vpd_kpa=_maybe(
            vpd.value if vpd else None,
            vpd.ts if vpd else None,
            "kPa",
            targets.get("vpd_kpa"),
        ),
        # Mock metrics keyed on the same top_ts as the real reading bundle,
        # so a single "as of …" label in the UI stays coherent.
        fan_pct=_envelope(get_fan_pct(top_ts), "%", None, top_ts),
        reservoir_in=_envelope(get_reservoir_in(top_ts), "in", None, top_ts),
    )

    return SensorsCurrent(
        ts=top_ts,
        stale=await readings.is_sensor_stale(),
        metrics=metrics,
    )
