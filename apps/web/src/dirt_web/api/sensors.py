"""Sensor endpoints — current envelope + single-metric history + metadata.

``/api/sensors/current`` composes the latest ``sensorreading`` rows for
the dashboard metrics with target bands and status colors from
``grow_state``. The SPA is a pure renderer — all band/status computation
happens server-side so the front end can't drift.

``/api/sensors/history`` returns bucketed ``(ts, value)`` points for one
metric over the requested range — drives the sparklines.

``/api/sensors/metadata`` returns the registry-driven dashboard config
(per-metric display name / unit / accent / y-axis bounds / band-presence
flag). The SPA fetches this once at boot to render its tile grid.

Per-metric metadata (db name, unit, transform, accent, y-axis bounds)
lives in ``metric_registry.METRICS``. Add a metric there, not here.
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
    SensorMetricMetadata,
    SensorsCurrent,
    SensorsHistoryResponse,
    SensorsMetadataResponse,
    TargetBand,
)
from fastapi import APIRouter, Depends, Query

from dirt_shared.services.grow_state import (
    STAGE_TARGETS,
    GrowStateService,
    band_status,
)
from dirt_shared.services.readings import ReadingsService
from dirt_shared.services.scope import DEFAULT_SITE_ID, DEFAULT_TENT_ID
from dirt_web.api.metric_registry import (
    MetricSpec,
    dashboard_metrics,
    metric_spec,
    transform_value,
)
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


def _envelope(
    reading: _ReadingLike | None,
    metric: SensorMetric,
    band: tuple[float, float] | None,
    fallback_ts: datetime,
) -> MetricEnvelope:
    """Wrap one metric reading into the contract's MetricEnvelope shape.

    ``reading=None`` (cold-cluster case, no row yet) emits a well-typed
    envelope at value=0 so the contract shape stays valid; the client
    can check ``stale`` on the enclosing envelope to render the "no
    data" affordance. ``band=None`` for metrics without a stage-defined
    target; ``band_status`` returns "ok" there.

    Applies the registry's value transform (e.g. mist level → percent)
    so the envelope's ``value`` is always in display units.
    """
    spec = metric_spec(metric)
    raw = reading.value if reading is not None else 0.0
    value = transform_value(metric, raw)
    ts = reading.ts if reading is not None else fallback_ts
    target = TargetBand(root=[band[0], band[1]]) if band is not None else None
    status = ContractBandStatus(band_status(value, band))
    return MetricEnvelope(
        value=value, unit=spec.unit, target=target, status=status, ts=ts
    )


@router.get("/api/sensors/current", response_model=SensorsCurrent)
async def sensors_current(
    site_id: str = Query(DEFAULT_SITE_ID),
    tent_id: str = Query(DEFAULT_TENT_ID),
    readings: ReadingsService = Depends(get_readings),
    grow: GrowStateService = Depends(get_grow),
) -> SensorsCurrent:
    """Dashboard-metric envelope with target bands, statuses, stale flag."""
    # Resolve DB read tuples (metric, location) from the registry, then
    # fan out concurrently — sequential awaits would pay round-trip
    # latency on every render. Stage + stale are independent reads.
    temp_spec = metric_spec(SensorMetric.temperature_f)
    hum_spec = metric_spec(SensorMetric.humidity_pct)
    vpd_spec = metric_spec(SensorMetric.vpd_kpa)
    fan_spec = metric_spec(SensorMetric.fan_pct)
    humidifier_spec = metric_spec(SensorMetric.humidifier_intensity_pct)
    reservoir_spec = metric_spec(SensorMetric.reservoir_in)

    def latest(spec: MetricSpec):
        return readings.get_latest_reading(
            spec.db_metric,
            site_id=site_id,
            tent_id=tent_id,
            device_id=spec.db_device_id if tent_id == DEFAULT_TENT_ID else None,
        )

    stage, temp, hum, vpd, fan, humidifier, reservoir, stale = await asyncio.gather(
        grow.current_stage(site_id=site_id, tent_id=tent_id),
        latest(temp_spec),
        latest(hum_spec),
        latest(vpd_spec),
        latest(fan_spec),
        latest(humidifier_spec),
        latest(reservoir_spec),
        readings.is_sensor_stale(site_id=site_id, tent_id=tent_id),
    )
    targets = STAGE_TARGETS[stage]

    # Top-level ``ts`` = newest reading seen across all real metrics
    # ("when did the tent last report?"). Fall back to the injected
    # clock when the DB is cold so the envelope is always well-formed.
    real_readings = [
        r for r in (temp, hum, vpd, fan, humidifier, reservoir) if r is not None
    ]
    top_ts = max((r.ts for r in real_readings), default=readings.now())

    metrics = Metrics(
        temperature_f=_envelope(
            temp, SensorMetric.temperature_f, targets.get("temperature_f"), top_ts
        ),
        humidity_pct=_envelope(
            hum, SensorMetric.humidity_pct, targets.get("humidity_pct"), top_ts
        ),
        vpd_kpa=_envelope(vpd, SensorMetric.vpd_kpa, targets.get("vpd_kpa"), top_ts),
        fan_pct=_envelope(fan, SensorMetric.fan_pct, targets.get("fan_pct"), top_ts),
        humidifier_intensity_pct=_envelope(
            humidifier, SensorMetric.humidifier_intensity_pct, None, top_ts
        ),
        reservoir_in=_envelope(
            reservoir, SensorMetric.reservoir_in, targets.get("reservoir_in"), top_ts
        ),
    )

    return SensorsCurrent(ts=top_ts, stale=stale, metrics=metrics)


@router.get("/api/sensors/history", response_model=SensorsHistoryResponse)
async def sensors_history(
    range: Range = Query(...),
    metric: SensorMetric = Query(...),
    site_id: str = Query(DEFAULT_SITE_ID),
    tent_id: str = Query(DEFAULT_TENT_ID),
    readings: ReadingsService = Depends(get_readings),
) -> SensorsHistoryResponse:
    """Return bucketed ``(ts, value)`` points for one metric over ``range``.

    DB metric name + value transform come from the registry. ``fan_pct``
    resolves to its DB-side name ``fan_duty_pct``;
    ``humidifier_intensity_pct`` resolves to ``humidifier_mist_level``
    with a ``× 100/9`` transform.

    FastAPI rejects out-of-enum ``range`` / ``metric`` values at the
    query layer with 422 before the handler runs — the contract's 400
    response covers the same intent.
    """
    spec = metric_spec(metric)
    raw = await readings.get_metric_history(
        spec.db_metric,
        range.value,
        site_id=site_id,
        tent_id=tent_id,
        device_id=spec.db_device_id if tent_id == DEFAULT_TENT_ID else None,
    )
    points = [
        HistoryPoint(ts=ts, value=round(transform_value(metric, value), 2))
        for ts, value in raw
    ]
    return SensorsHistoryResponse(
        range=range,
        metric=metric,
        unit=spec.unit,
        points=points,
    )


@router.get("/api/sensors/metadata", response_model=SensorsMetadataResponse)
async def sensors_metadata() -> SensorsMetadataResponse:
    """Return per-metric display metadata for the dashboard.

    Read once at SPA boot; drives the gauge + sparkline grid. Stable
    across stage flips — target *values* come from ``/api/sensors/current``,
    only the *presence* of a band is declared here.
    """
    return SensorsMetadataResponse(
        metrics=[
            SensorMetricMetadata(
                metric=spec.metric,
                display_name=spec.display_name,
                unit=spec.unit,
                accent=spec.accent,
                y_min=spec.y_min,
                y_max=spec.y_max,
                has_target_band=spec.has_target_band,
            )
            for spec in dashboard_metrics()
        ]
    )
