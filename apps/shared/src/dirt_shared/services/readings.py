"""Sensor reading ingest + query service.

Post-pg-cutover (ADR-006), all timestamp handling is native — no more
``char(58)`` workaround, no more lexical-compare coercion. The bucketed
history queries use ``date_trunc`` and compose cleanly with parametrized
``timestamptz`` bind values.

Location → sensornode_id indirection: callers still speak in location
(``'tent'`` / ``'plant-a'``) for ergonomics, but on-wire writes and FKs
reference the surrogate ``sensornode.id``. The initial Atlas migration
seeds one row per ``SensorLocation`` enum value, so
``_get_sensornode_id`` never has to create on miss — but it upserts
metadata when ingest reports fresh ip/firmware/uptime.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.db import engine
from dirt_shared.models.enums import SensorLocation, SensorSource
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading

# Metrics that get auto-calibrated at ingest (extrema-tracking).
AUTO_CALIBRATED_METRICS = {"soil_moisture_raw"}
# Plausible ADC range — values outside this are noise/spike and skipped.
CAL_CLAMP_MIN = 100.0
CAL_CLAMP_MAX = 3900.0


def compute_calibrated_pct(
    raw: float, raw_low: float, raw_high: float
) -> float | None:
    """Map a raw ADC reading to calibrated percentage via two-point linear.

    raw_low  = wettest ADC seen (100%)
    raw_high = driest ADC seen  (0%)
    Returns None if range is degenerate (raw_high <= raw_low).
    """
    if raw_high <= raw_low:
        return None
    pct = 100.0 * (raw_high - raw) / (raw_high - raw_low)
    return max(0.0, min(100.0, pct))


RANGE_DELTAS = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

# All metrics recorded by the serial reader (plus derived values).
METRICS = (
    "temperature_f",
    "humidity_pct",
    "pressure_hpa",
    "vpd_kpa",
    "dew_point_f",
)

# Native Postgres bucket expressions. 5-minute buckets for 24h, hourly for
# 7d / 30d. The 1h range returns raw readings (no bucketing).
#
# ``ts AT TIME ZONE 'UTC'`` converts timestamptz to a naive timestamp at
# UTC wall-clock — safe to apply date_trunc + arithmetic against. Result
# is formatted with 'Z' suffix for unambiguous wire labels.
_BUCKET_SQL = {
    "24h": (
        "SELECT to_char("
        "    date_trunc('hour', ts AT TIME ZONE 'UTC')"
        "    + make_interval(mins => (extract(minute from ts AT TIME ZONE 'UTC')::int / 5) * 5),"
        "    'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"'"
        ") AS bucket, "
        "AVG(value) AS avg_value "
        "FROM sensorreading "
        "WHERE ts >= :cutoff AND metric = :metric "
        "GROUP BY 1 ORDER BY 1"
    ),
    "7d": (
        "SELECT to_char(date_trunc('hour', ts AT TIME ZONE 'UTC'), "
        "'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') AS bucket, "
        "AVG(value) AS avg_value "
        "FROM sensorreading "
        "WHERE ts >= :cutoff AND metric = :metric "
        "GROUP BY 1 ORDER BY 1"
    ),
    "30d": (
        "SELECT to_char(date_trunc('hour', ts AT TIME ZONE 'UTC'), "
        "'YYYY-MM-DD\"T\"HH24:MI:SS\"Z\"') AS bucket, "
        "AVG(value) AS avg_value "
        "FROM sensorreading "
        "WHERE ts >= :cutoff AND metric = :metric "
        "GROUP BY 1 ORDER BY 1"
    ),
}


async def _get_metric_series(
    session: AsyncSession, metric: str, range_key: str, cutoff: datetime
) -> dict[str, list]:
    """Return {labels, values} for a single metric over the given range."""
    if range_key in _BUCKET_SQL:
        stmt = text(_BUCKET_SQL[range_key])
        result = await session.exec(
            stmt, params={"cutoff": cutoff, "metric": metric}
        )
        rows = result.all()
        return {
            "labels": [r[0] for r in rows],
            "values": [round(float(r[1]), 2) for r in rows],
        }
    # Raw readings (1h) — no bucketing.
    result = await session.exec(
        select(SensorReading)
        .where(SensorReading.ts >= cutoff)
        .where(SensorReading.metric == metric)
        .order_by(SensorReading.ts)
    )
    rows = result.all()
    return {
        "labels": [r.ts.isoformat() for r in rows],
        "values": [round(r.value, 2) for r in rows],
    }


async def _get_sensornode_id(
    session: AsyncSession, location: SensorLocation | str
) -> int | None:
    """Look up a sensornode surrogate id by its location enum value.

    Returns None if the location doesn't exist — though with the initial
    migration seeding one row per ``SensorLocation`` enum value, that only
    happens if you pass a string that isn't a valid enum member.
    """
    result = await session.exec(
        select(SensorNode.id).where(SensorNode.location == location)
    )
    return result.first()


async def get_latest_reading(
    metric: str, location: SensorLocation | str = SensorLocation.TENT
) -> SensorReading | None:
    """Return the most recent reading for ``metric`` at ``location``.

    Defaults to ``tent`` because every caller that predates the location
    parameter was implicitly reading tent-scoped metrics
    (temperature_f / humidity_pct / vpd_kpa).
    """
    async with AsyncSession(engine) as session:
        node_id = await _get_sensornode_id(session, location)
        if node_id is None:
            return None
        result = await session.exec(
            select(SensorReading)
            .where(SensorReading.sensornode_id == node_id)
            .where(SensorReading.metric == metric)
            .order_by(SensorReading.ts.desc())
            .limit(1)
        )
        return result.first()


async def is_sensor_stale(threshold: int = 10) -> bool:
    """Return True if the last ``threshold`` tent temperature readings are identical.

    A tent DHT22 that gets wedged tends to keep reporting the last valid value
    indefinitely. Detect that by checking the unique count over the most
    recent N readings.
    """
    async with AsyncSession(engine) as session:
        node_id = await _get_sensornode_id(session, SensorLocation.TENT)
        if node_id is None:
            return False
        result = await session.exec(
            select(SensorReading)
            .where(SensorReading.sensornode_id == node_id)
            .where(SensorReading.metric == "temperature_f")
            .order_by(SensorReading.ts.desc())
            .limit(threshold)
        )
        rows = result.all()
    if len(rows) < threshold:
        return False
    return len({r.value for r in rows}) == 1


async def _update_calibration(
    session: AsyncSession, sensornode_id: int, metric: str, value: float
) -> None:
    """Widen the (sensornode_id, metric) calibration range if value is a new extremum."""
    result = await session.exec(
        select(SensorCalibration)
        .where(SensorCalibration.sensornode_id == sensornode_id)
        .where(SensorCalibration.metric == metric)
    )
    cal = result.first()
    if cal is None:
        session.add(
            SensorCalibration(
                sensornode_id=sensornode_id,
                metric=metric,
                raw_low=value,
                raw_high=value,
            )
        )
    else:
        if value < cal.raw_low:
            cal.raw_low = value
        if value > cal.raw_high:
            cal.raw_high = value


async def ingest_reading(
    location: SensorLocation | str,
    metrics: dict[str, float],
    source: SensorSource | str = SensorSource.ESP32,
    ip: str | None = None,
    firmware_version: str | None = None,
    uptime_ms: int | None = None,
) -> None:
    """Record a batch of sensor readings and upsert node metadata.

    Order of operations inside the single transaction:
      1. Find or create the sensornode row for ``location`` (flushed so we
         have its ``id`` before we insert readings that FK to it).
      2. Insert one SensorReading per metric in ``metrics``.
      3. Update auto-calibration ranges for configured metrics.
      4. Commit.
    """
    now = datetime.now(UTC)
    async with AsyncSession(engine) as session:
        # Step 1 — find-or-upsert the sensornode and flush to get its id.
        node = (
            await session.exec(
                select(SensorNode).where(SensorNode.location == location)
            )
        ).first()
        if node is None:
            # Shouldn't happen post-seed — but if someone widens the enum and
            # forgets to seed, create rather than fail.
            node = SensorNode(location=location)
        # Only overwrite identity fields when the caller provided them. The
        # serial reader (Arduino) doesn't know firmware/ip/uptime and calls
        # with None; we don't want that to null out metadata the ESP32
        # ingest path populates for other nodes.
        if ip is not None:
            node.ip = ip
        if firmware_version is not None:
            node.firmware_version = firmware_version
        if uptime_ms is not None:
            node.uptime_ms = uptime_ms
        node.last_seen = now
        session.add(node)
        await session.flush()  # populate node.id for the FK on SensorReading
        assert node.id is not None

        # Step 2 + 3 — readings and (optional) calibration updates.
        for metric_name, value in metrics.items():
            session.add(
                SensorReading(
                    ts=now,
                    sensornode_id=node.id,
                    metric=metric_name,
                    value=value,
                    source=source,
                )
            )
            if (
                metric_name in AUTO_CALIBRATED_METRICS
                and CAL_CLAMP_MIN <= value <= CAL_CLAMP_MAX
            ):
                await _update_calibration(session, node.id, metric_name, value)

        await session.commit()


async def get_sensor_history(range_key: str) -> dict[str, dict[str, list]]:
    """Return all metrics over the given range, batched.

    Response shape: ``{metric_name: {"labels": [...], "values": [...]}, ...}``.
    """
    delta = RANGE_DELTAS[range_key]
    cutoff = datetime.now(UTC) - delta

    async with AsyncSession(engine) as session:
        return {
            metric: await _get_metric_series(session, metric, range_key, cutoff)
            for metric in METRICS
        }
