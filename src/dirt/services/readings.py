from datetime import UTC, datetime, timedelta

from sqlmodel import select, text
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.db import engine
from dirt.models.sensor_calibration import SensorCalibration
from dirt.models.sensor_node import SensorNode
from dirt.models.sensor_reading import SensorReading

# Metrics that get auto-calibrated at ingest (extrema-tracking).
AUTO_CALIBRATED_METRICS = {"soil_moisture_raw"}
# Plausible ADC range — values outside this are noise/spike and skipped.
CAL_CLAMP_MIN = 100.0
CAL_CLAMP_MAX = 3900.0


def compute_calibrated_pct(raw: float, raw_low: float, raw_high: float) -> float | None:
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

# char(58) = ':' — avoids SQLAlchemy parsing ':00' as a named bind parameter
_COLON = "char(58)"
_ZEROS = f"|| {_COLON} || '00'"
_UTC_Z = "|| 'Z'"

# Bucketed SQL per range. Each query returns (bucket, avg_value) for a single metric.
_BUCKET_SQL = {
    "24h": (
        "SELECT "
        f"strftime('%Y-%m-%dT%H', timestamp) || {_COLON} || "
        "substr('00' || ((cast(strftime('%M', timestamp) as int) / 5) * 5), -2) "
        f"{_ZEROS} {_UTC_Z} as bucket, "
        "AVG(value) as avg_value "
        "FROM sensorreading "
        "WHERE timestamp >= :cutoff AND metric = :metric "
        "GROUP BY bucket "
        "ORDER BY bucket"
    ),
    "7d": (
        "SELECT strftime('%Y-%m-%dT%H', timestamp) "
        f"{_ZEROS} {_ZEROS} {_UTC_Z} as bucket, "
        "AVG(value) as avg_value "
        "FROM sensorreading "
        "WHERE timestamp >= :cutoff AND metric = :metric "
        "GROUP BY bucket "
        "ORDER BY bucket"
    ),
    "30d": (
        "SELECT strftime('%Y-%m-%dT%H', timestamp) "
        f"{_ZEROS} {_ZEROS} {_UTC_Z} as bucket, "
        "AVG(value) as avg_value "
        "FROM sensorreading "
        "WHERE timestamp >= :cutoff AND metric = :metric "
        "GROUP BY bucket "
        "ORDER BY bucket"
    ),
}


async def _get_metric_series(
    session: AsyncSession, metric: str, range_key: str, cutoff: datetime
) -> dict[str, list]:
    """Return {labels, values} for a single metric over the given range."""
    if range_key in _BUCKET_SQL:
        # SQLite stores datetimes as TEXT and the bucketed text() queries
        # compare them lexically. Stored format is "YYYY-MM-DD HH:MM:SS.ffffff"
        # (space separator, no tz). cutoff.isoformat() produces a "T" separator
        # plus "+00:00" suffix — lexically " " < "T", so naive .isoformat()
        # filters out anything before the next UTC midnight. Match the stored
        # format explicitly.
        cutoff_str = cutoff.replace(tzinfo=None).isoformat(sep=" ")
        stmt = text(_BUCKET_SQL[range_key])
        result = await session.exec(
            stmt, params={"cutoff": cutoff_str, "metric": metric}
        )
        rows = result.all()
        return {
            "labels": [r[0] for r in rows],
            "values": [round(r[1], 2) for r in rows],
        }
    else:
        # Raw readings (1h) — no bucketing
        result = await session.exec(
            select(SensorReading)
            .where(SensorReading.timestamp >= cutoff)
            .where(SensorReading.metric == metric)
            .order_by(SensorReading.timestamp)
        )
        rows = result.all()
        return {
            "labels": [r.timestamp.isoformat() for r in rows],
            "values": [round(r.value, 2) for r in rows],
        }


async def get_latest_reading(metric: str) -> SensorReading | None:
    """Return the most recent reading for a given metric."""
    async with AsyncSession(engine) as session:
        result = await session.exec(
            select(SensorReading)
            .where(SensorReading.metric == metric)
            .order_by(SensorReading.timestamp.desc())
            .limit(1)
        )
        return result.first()


async def is_sensor_stale(threshold: int = 10) -> bool:
    """Check if the last N temperature readings are all identical."""
    async with AsyncSession(engine) as session:
        result = await session.exec(
            select(SensorReading)
            .where(SensorReading.metric == "temperature_f")
            .order_by(SensorReading.timestamp.desc())
            .limit(threshold)
        )
        rows = result.all()
    if len(rows) < threshold:
        return False
    return len({r.value for r in rows}) == 1


async def _update_calibration(
    session: AsyncSession, location: str, metric: str, value: float
) -> None:
    """Widen the (location, metric) calibration range if value is a new extremum."""
    result = await session.exec(
        select(SensorCalibration)
        .where(SensorCalibration.location == location)
        .where(SensorCalibration.metric == metric)
    )
    cal = result.first()
    if cal is None:
        session.add(
            SensorCalibration(
                location=location, metric=metric, raw_low=value, raw_high=value
            )
        )
    else:
        if value < cal.raw_low:
            cal.raw_low = value
        if value > cal.raw_high:
            cal.raw_high = value


async def ingest_reading(
    location: str,
    metrics: dict[str, float],
    source: str = "esp32",
    ip: str | None = None,
    firmware_version: str | None = None,
    uptime_ms: int | None = None,
) -> None:
    """Record a batch of sensor readings and upsert node metadata.

    Called by the ESP32 ingest endpoint. Inserts one row per metric,
    all sharing the same timestamp and location, then upserts the
    sensornode row for `location`.
    """
    now = datetime.now(UTC)
    async with AsyncSession(engine) as session:
        for metric_name, value in metrics.items():
            session.add(
                SensorReading(
                    timestamp=now,
                    location=location,
                    metric=metric_name,
                    value=value,
                    source=source,
                )
            )
            if (
                metric_name in AUTO_CALIBRATED_METRICS
                and CAL_CLAMP_MIN <= value <= CAL_CLAMP_MAX
            ):
                await _update_calibration(session, location, metric_name, value)
        node = await session.get(SensorNode, location)
        if node is None:
            node = SensorNode(location=location)
        node.ip = ip
        node.firmware_version = firmware_version
        node.uptime_ms = uptime_ms
        node.last_seen = now
        session.add(node)
        await session.commit()


async def get_sensor_history(range_key: str) -> dict[str, dict[str, list]]:
    """Return all metrics over the given range, batched.

    Response shape: {metric_name: {"labels": [...], "values": [...]}, ...}
    """
    delta = RANGE_DELTAS[range_key]
    cutoff = datetime.now(UTC) - delta

    async with AsyncSession(engine) as session:
        return {
            metric: await _get_metric_series(session, metric, range_key, cutoff)
            for metric in METRICS
        }
