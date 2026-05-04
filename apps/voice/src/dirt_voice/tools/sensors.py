"""Direct-read sensor tools. Sub-200ms; hit the local sensor DB.

Built via ``build_sensor_tools(engine, readings, grow)`` from the voice
channel's composition root (``voice.py:main``). No module-level service
access — everything closures over the parameters at construction time.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from statistics import mean

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.plant import Plant
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.sensor_contract import persisted_metrics_for_device_id
from dirt_shared.services.grow_state import GrowStateService, in_band
from dirt_shared.services.readings import (
    ReadingsService,
    compute_calibrated_pct,
    resolve_metric_capability_id,
)
from dirt_shared.services.scope import current_grow_run
from dirt_voice.tools import ToolSpec

DEFAULT_TENT_SENSOR_DEVICE_ID = "fan-controller"

# `dew_point_f` is informational (rarely actionable indoors); out-of-range
# is suppressed for it so we don't distract Claudia with non-signal. Temp /
# RH / VPD bands live in services.grow_state and shift with stage.

# Speech-friendly short labels for Claudia to say.
_LABELS = {
    "temperature_f": "temperature",
    "humidity_pct": "humidity",
    "vpd_kpa": "VPD",
    "dew_point_f": "dew point",
}


async def _latest_soil_moisture_pct(
    engine: AsyncEngine,
    now: datetime,
) -> tuple[dict[str, float], list[float]]:
    """Latest calibrated soil moisture % per plant.

    Returns ``({plant_letter: pct_rounded}, [reading_age_s, ...])`` —
    letter is 'a'/'b'/'c'/'d', pct is 0-100. Plants without a reading
    or without a usable calibration row are silently omitted.
    """
    out: dict[str, float] = {}
    ages: list[float] = []
    async with AsyncSession(engine) as session:
        grow = await current_grow_run(session)
        if grow is None:
            return out, ages
        plant_rows = (
            await session.exec(
                select(Plant.code, Plant.moisture_capability_id)
                .where(Plant.growrun_id == grow.id)
                .where(Plant.moisture_capability_id.is_not(None))
                .order_by(Plant.code)
            )
        ).all()
        for plant_code, moisture_capability_id in plant_rows:
            reading_res = await session.exec(
                select(SensorReading)
                .where(SensorReading.capability_id == moisture_capability_id)
                .where(SensorReading.metric == "soil_moisture_raw")
                .order_by(SensorReading.ts.desc())
                .limit(1)
            )
            row = reading_res.first()
            if row is None:
                continue
            cal_res = await session.exec(
                select(SensorCalibration)
                .where(SensorCalibration.capability_id == moisture_capability_id)
                .where(SensorCalibration.metric == "soil_moisture_raw")
            )
            cal = cal_res.first()
            if cal is None:
                continue
            pct = compute_calibrated_pct(row.value, cal.raw_low, cal.raw_high)
            if pct is None:
                continue
            out[plant_code] = round(pct, 1)
            ages.append((now - row.ts).total_seconds())
    return out, ages


def build_sensor_tools(
    *,
    engine: AsyncEngine,
    readings: ReadingsService,
    grow: GrowStateService,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> list[ToolSpec]:
    """Build the sensor tool list with services injected via closure.

    ``clock`` is the same one wired through ``build_core_services`` —
    keeping age computations and trend cutoffs aligned with the services
    the tools consume."""
    tent_metrics: frozenset[str] = persisted_metrics_for_device_id(
        DEFAULT_TENT_SENSOR_DEVICE_ID
    )

    async def _get_current_status() -> dict:
        readings_out: dict[str, float] = {}
        out_of_range: list[dict] = []
        oldest_age_s: float | None = None
        now = clock()
        targets = await grow.current_targets()

        for metric in sorted(tent_metrics):
            r = await readings.get_latest_reading(
                metric, device_id=DEFAULT_TENT_SENSOR_DEVICE_ID
            )
            if r is None:
                continue
            readings_out[metric] = round(r.value, 2)
            age_s = (now - r.ts).total_seconds()
            oldest_age_s = age_s if oldest_age_s is None else max(oldest_age_s, age_s)

            if metric in targets:
                lo, hi = targets[metric]
                if not in_band(r.value, (lo, hi)):
                    out_of_range.append(
                        {
                            "label": _LABELS[metric],
                            "value": round(r.value, 2),
                            "target": f"{lo}-{hi}",
                        }
                    )

        soil, soil_ages = await _latest_soil_moisture_pct(engine, now)
        for age_s in soil_ages:
            oldest_age_s = age_s if oldest_age_s is None else max(oldest_age_s, age_s)

        return {
            "readings": readings_out,
            "soil_moisture_pct": soil,
            "out_of_range": out_of_range,
            "last_reading_age_s": (round(oldest_age_s) if oldest_age_s else None),
        }

    async def _get_sensor_trend(sensor: str, hours_back: int = 24) -> dict:
        sensor = sensor.strip()
        if sensor not in tent_metrics:
            valid = ", ".join(sorted(tent_metrics))
            return {"error": f"unknown sensor {sensor!r}; valid: {valid}"}
        if not (1 <= hours_back <= 168):
            return {"error": "hours_back must be between 1 and 168"}

        cutoff = clock() - timedelta(hours=hours_back)
        async with AsyncSession(engine) as session:
            capability_id = await resolve_metric_capability_id(
                session,
                metric=sensor,
                device_id=DEFAULT_TENT_SENSOR_DEVICE_ID,
            )
            if capability_id is None:
                return {"error": f"no capability for {sensor}"}
            result = await session.exec(
                select(SensorReading)
                .join(Capability, Capability.id == SensorReading.capability_id)
                .join(Device, Device.id == Capability.device_id)
                .where(SensorReading.capability_id == capability_id)
                .where(Device.device_id == DEFAULT_TENT_SENSOR_DEVICE_ID)
                .where(SensorReading.metric == sensor)
                .where(SensorReading.ts >= cutoff)
                .order_by(SensorReading.ts)
            )
            rows = result.all()

        if not rows:
            return {"error": f"no readings for {sensor} in the last {hours_back}h"}

        values = [r.value for r in rows]
        # Direction: compare first-half average to second-half average.
        # Stable if within ~3% of the observed range (noise threshold).
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

    return [
        ToolSpec(
            name="get_current_status",
            description=(
                "Return the latest tent sensor readings (temperature, humidity, "
                "VPD, dew point) plus per-plant calibrated soil moisture "
                "percent for plants A through D, with in-range / out-of-range "
                "flags on the tent metrics. Use for 'how are things looking "
                "right now' questions."
            ),
            properties={},
            required=[],
            handler=_get_current_status,
            timeout_secs=2.0,
        ),
        ToolSpec(
            name="get_sensor_trend",
            description=(
                "Return min/max/avg and trend direction (rising/falling/stable) "
                "for a sensor over the last N hours. Use for 'how has humidity "
                "been today' style questions."
            ),
            properties={
                "sensor": {
                    "type": "string",
                    "description": (
                        "One of: temperature_f, humidity_pct, vpd_kpa, dew_point_f"
                    ),
                },
                "hours_back": {
                    "type": "integer",
                    "description": (
                        "Lookback window in hours (1-168). Defaults to 24."
                    ),
                    "default": 24,
                },
            },
            required=["sensor"],
            handler=_get_sensor_trend,
            timeout_secs=2.0,
        ),
    ]
