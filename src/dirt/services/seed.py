import logging
import math
import random
from datetime import UTC, datetime, timedelta

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.models.sensor_reading import SensorReading

logger = logging.getLogger(__name__)

SEED_DAYS = 30
INTERVAL_MINUTES = 5
LIGHTS_ON_HOUR = 6
LIGHTS_OFF_HOUR = 0  # midnight


def _generate_readings(now: datetime) -> list[SensorReading]:
    """Generate realistic grow tent sensor data for SEED_DAYS days."""
    readings = []
    start = now - timedelta(days=SEED_DAYS)
    total_intervals = (SEED_DAYS * 24 * 60) // INTERVAL_MINUTES

    for i in range(total_intervals):
        ts = start + timedelta(minutes=i * INTERVAL_MINUTES)
        hour = ts.hour

        # Lights on 06:00-00:00 (18h), lights off 00:00-06:00 (6h)
        lights_on = LIGHTS_ON_HOUR <= hour < 24

        if lights_on:
            # Sinusoidal temp curve peaking mid-cycle (~15:00)
            cycle_progress = (hour - LIGHTS_ON_HOUR) / 18.0
            base_temp = 70 + 15 * math.sin(cycle_progress * math.pi)
            base_humidity = 40 + 15 * (1 - math.sin(cycle_progress * math.pi))
        else:
            # Lights off: cooler, more humid
            base_temp = 65 + 4 * math.sin((hour / 6.0) * math.pi)
            base_humidity = 50 + 8 * math.sin((hour / 6.0) * math.pi)

        temp = base_temp + random.uniform(-1.5, 1.5)
        humidity = max(0, min(100, base_humidity + random.uniform(-2.5, 2.5)))

        readings.append(
            SensorReading(
                timestamp=ts,
                temperature_f=round(temp, 1),
                humidity_pct=round(humidity, 1),
                source="mock",
            )
        )

    return readings


async def seed_sensor_data(session: AsyncSession) -> int:
    """Seed mock sensor data if none exists. Returns count of readings created."""
    result = await session.exec(select(SensorReading).limit(1))
    if result.first() is not None:
        logger.info("Sensor data already exists, skipping seed")
        return 0

    now = datetime.now(UTC)
    readings = _generate_readings(now)
    session.add_all(readings)
    await session.commit()
    logger.info("Seeded %d mock sensor readings", len(readings))
    return len(readings)
