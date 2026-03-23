from datetime import UTC, datetime, timedelta

from sqlmodel import select, text
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.db import engine
from dirt.models.sensor_reading import SensorReading

RANGE_DELTAS = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

# char(58) = ':' — avoids SQLAlchemy parsing ':00' as a named bind parameter
_COLON = "char(58)"
_ZEROS = f"|| {_COLON} || '00'"

_BUCKET_SQL = {
    "24h": (
        "SELECT "
        f"strftime('%Y-%m-%dT%H', timestamp) || {_COLON} || "
        "substr('00' || ((cast(strftime('%M', timestamp) as int) / 5) * 5), -2) "
        f"{_ZEROS} as bucket, "
        "AVG(temperature_f) as avg_temp, "
        "AVG(humidity_pct) as avg_hum "
        "FROM sensorreading "
        "WHERE timestamp >= :cutoff "
        "GROUP BY bucket "
        "ORDER BY bucket"
    ),
    "7d": (
        f"SELECT strftime('%Y-%m-%dT%H', timestamp) {_ZEROS} {_ZEROS} as bucket, "
        "AVG(temperature_f) as avg_temp, "
        "AVG(humidity_pct) as avg_hum "
        "FROM sensorreading "
        "WHERE timestamp >= :cutoff "
        "GROUP BY bucket "
        "ORDER BY bucket"
    ),
    "30d": (
        f"SELECT strftime('%Y-%m-%dT%H', timestamp) {_ZEROS} {_ZEROS} as bucket, "
        "AVG(temperature_f) as avg_temp, "
        "AVG(humidity_pct) as avg_hum "
        "FROM sensorreading "
        "WHERE timestamp >= :cutoff "
        "GROUP BY bucket "
        "ORDER BY bucket"
    ),
}


async def get_latest_reading() -> SensorReading | None:
    async with AsyncSession(engine) as session:
        result = await session.exec(
            select(SensorReading).order_by(SensorReading.timestamp.desc()).limit(1)
        )
        return result.first()


async def get_sensor_history(range_key: str) -> dict[str, list]:
    """Return sensor history as {labels, temperature, humidity} for a time range."""
    delta = RANGE_DELTAS[range_key]
    cutoff = datetime.now(UTC) - delta

    async with AsyncSession(engine) as session:
        if range_key in _BUCKET_SQL:
            stmt = text(_BUCKET_SQL[range_key])
            result = await session.exec(stmt, params={"cutoff": cutoff.isoformat()})
            rows = result.all()
            labels = [r[0] for r in rows]
            temperature = [round(r[1], 1) for r in rows]
            humidity = [round(r[2], 1) for r in rows]
        else:
            # Raw readings (1h)
            result = await session.exec(
                select(SensorReading)
                .where(SensorReading.timestamp >= cutoff)
                .order_by(SensorReading.timestamp)
            )
            rows = result.all()
            labels = [r.timestamp.isoformat() for r in rows]
            temperature = [r.temperature_f for r in rows]
            humidity = [r.humidity_pct for r in rows]

    return {"labels": labels, "temperature": temperature, "humidity": humidity}
