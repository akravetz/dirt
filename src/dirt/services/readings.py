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
        if range_key in ("7d", "30d"):
            stmt = text(
                "SELECT strftime('%Y-%m-%dT%H:00:00', timestamp) as bucket, "
                "AVG(temperature_f) as avg_temp, "
                "AVG(humidity_pct) as avg_hum "
                "FROM sensorreading "
                "WHERE timestamp >= :cutoff "
                "GROUP BY bucket "
                "ORDER BY bucket"
            )
            result = await session.exec(stmt, params={"cutoff": cutoff.isoformat()})
            rows = result.all()
            labels = [r[0] for r in rows]
            temperature = [round(r[1], 1) for r in rows]
            humidity = [round(r[2], 1) for r in rows]
        else:
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
