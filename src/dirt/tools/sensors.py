"""Direct-read sensor tools. Sub-200ms; hit the local SQLite sensor DB."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from statistics import mean

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.db import engine
from dirt.models.sensor_calibration import SensorCalibration
from dirt.models.sensor_reading import SensorReading
from dirt.services.readings import METRICS, compute_calibrated_pct, get_latest_reading
from dirt.tools import ToolSpec

PLANT_LOCATIONS = ("plant-a", "plant-b", "plant-c", "plant-d")


# Flower-stage targets. V1 hardcode — source-of-truth belongs in wiki/environment/
# pages once we're ready to read them at tool boot. `pressure_hpa` and
# `dew_point_f` are informational (rarely actionable indoors); out-of-range is
# suppressed for them so we don't distract Claudia with non-signal.
_TARGETS = {
    "temperature_f": (70, 82),
    "humidity_pct": (40, 55),
    "vpd_kpa": (1.2, 1.5),
}

# Speech-friendly short labels for Claudia to say.
_LABELS = {
    "temperature_f": "temperature",
    "humidity_pct": "humidity",
    "pressure_hpa": "pressure",
    "vpd_kpa": "VPD",
    "dew_point_f": "dew point",
}


async def _latest_soil_moisture_pct() -> tuple[dict[str, float], list[float]]:
    """Latest calibrated soil moisture % per plant.

    Returns ({plant_letter: pct_rounded}, [reading_age_s, ...]) — letter is
    'a'/'b'/'c'/'d', pct is 0-100. Plants without a reading or without a
    usable calibration row are silently omitted; ages are reported only for
    plants that made it into the dict, so callers can fold them into the
    'oldest reading' calculation alongside tent-metric ages.
    """
    out: dict[str, float] = {}
    ages: list[float] = []
    now = datetime.now(UTC)
    async with AsyncSession(engine) as session:
        for loc in PLANT_LOCATIONS:
            reading_res = await session.exec(
                select(SensorReading)
                .where(SensorReading.location == loc)
                .where(SensorReading.metric == "soil_moisture_raw")
                .order_by(SensorReading.timestamp.desc())
                .limit(1)
            )
            row = reading_res.first()
            if row is None:
                continue
            cal_res = await session.exec(
                select(SensorCalibration)
                .where(SensorCalibration.location == loc)
                .where(SensorCalibration.metric == "soil_moisture_raw")
            )
            cal = cal_res.first()
            if cal is None:
                continue
            pct = compute_calibrated_pct(row.value, cal.raw_low, cal.raw_high)
            if pct is None:
                continue
            out[loc.removeprefix("plant-")] = round(pct, 1)
            ages.append((now - row.timestamp.replace(tzinfo=UTC)).total_seconds())
    return out, ages


async def _get_current_status() -> dict:
    readings = {}
    out_of_range = []
    oldest_age_s: float | None = None
    now = datetime.now(UTC)

    for metric in METRICS:
        r = await get_latest_reading(metric)
        if r is None:
            continue
        readings[metric] = round(r.value, 2)
        age_s = (now - r.timestamp.replace(tzinfo=UTC)).total_seconds()
        oldest_age_s = age_s if oldest_age_s is None else max(oldest_age_s, age_s)

        if metric in _TARGETS:
            lo, hi = _TARGETS[metric]
            if not (lo <= r.value <= hi):
                out_of_range.append({
                    "label": _LABELS[metric],
                    "value": round(r.value, 2),
                    "target": f"{lo}-{hi}",
                })

    soil, soil_ages = await _latest_soil_moisture_pct()
    for age_s in soil_ages:
        oldest_age_s = age_s if oldest_age_s is None else max(oldest_age_s, age_s)

    return {
        "readings": readings,
        "soil_moisture_pct": soil,
        "out_of_range": out_of_range,
        "last_reading_age_s": round(oldest_age_s) if oldest_age_s else None,
    }


async def _get_sensor_trend(sensor: str, hours_back: int = 24) -> dict:
    sensor = sensor.strip()
    if sensor not in METRICS:
        return {"error": f"unknown sensor {sensor!r}; valid: {', '.join(METRICS)}"}
    if not (1 <= hours_back <= 168):
        return {"error": "hours_back must be between 1 and 168"}

    cutoff = datetime.now(UTC) - timedelta(hours=hours_back)
    async with AsyncSession(engine) as session:
        result = await session.exec(
            select(SensorReading)
            .where(SensorReading.metric == sensor)
            .where(SensorReading.timestamp >= cutoff)
            .order_by(SensorReading.timestamp)
        )
        rows = result.all()

    if not rows:
        return {"error": f"no readings for {sensor} in the last {hours_back}h"}

    values = [r.value for r in rows]
    # Direction: compare first-half average to second-half average. Stable if
    # within ~3% of the observed range (noise threshold).
    mid = len(values) // 2
    first_avg = mean(values[:mid]) if mid else values[0]
    second_avg = mean(values[mid:]) if len(values) > mid else values[-1]
    span = max(values) - min(values) or 1.0
    delta = second_avg - first_avg
    if abs(delta) < 0.03 * span:
        direction = "stable"
    else:
        direction = "rising" if delta > 0 else "falling"

    return {
        "sensor": _LABELS.get(sensor, sensor),
        "window_hours": hours_back,
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "avg": round(mean(values), 2),
        "latest": round(values[-1], 2),
        "direction": direction,
        "sample_count": len(values),
    }


GET_CURRENT_STATUS = ToolSpec(
    name="get_current_status",
    description=(
        "Return the latest tent sensor readings (temperature, humidity, VPD, "
        "pressure, dew point) plus per-plant calibrated soil moisture percent "
        "for plants A through D, with in-range / out-of-range flags on the "
        "tent metrics. Use for 'how are things looking right now' questions."
    ),
    properties={},
    required=[],
    handler=_get_current_status,
    timeout_secs=2.0,
)


GET_SENSOR_TREND = ToolSpec(
    name="get_sensor_trend",
    description=(
        "Return min/max/avg and trend direction (rising/falling/stable) for a "
        "sensor over the last N hours. Use for 'how has humidity been today' "
        "style questions."
    ),
    properties={
        "sensor": {
            "type": "string",
            "description": "One of: temperature_f, humidity_pct, vpd_kpa, pressure_hpa, dew_point_f",
        },
        "hours_back": {
            "type": "integer",
            "description": "Lookback window in hours (1-168). Defaults to 24.",
            "default": 24,
        },
    },
    required=["sensor"],
    handler=_get_sensor_trend,
    timeout_secs=2.0,
)
