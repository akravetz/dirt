import asyncio
import contextlib
import json
import logging

import serial
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.config import settings
from dirt.db import engine
from dirt.models.sensor_reading import SensorReading

logger = logging.getLogger(__name__)


def _read_line(ser: serial.Serial) -> dict | None:
    """Read a single JSON line from the serial port. Returns parsed dict or None."""
    try:
        line = ser.readline().decode().strip()
        if not line:
            return None
        return json.loads(line)
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        logger.warning("Bad serial line: %s", e)
        return None


async def _save_reading(data: dict) -> None:
    """Save a parsed sensor reading to the database."""
    reading = SensorReading(
        temperature_f=data["temperature_f"],
        humidity_pct=data["humidity_pct"],
        source="arduino",
    )
    async with AsyncSession(engine) as session:
        session.add(reading)
        await session.commit()


async def serial_reader_loop(stop_event: asyncio.Event) -> None:
    """Read sensor data from the Arduino over serial and save to DB."""
    port = settings.serial_port
    baud = settings.serial_baud
    interval = settings.sensor_poll_interval

    logger.info(
        "Starting serial reader (port=%s, baud=%d, interval=%ds)",
        port,
        baud,
        interval,
    )

    loop = asyncio.get_running_loop()
    ser = None

    while not stop_event.is_set():
        try:
            if ser is None or not ser.is_open:
                ser = await loop.run_in_executor(
                    None, lambda: serial.Serial(port, baud, timeout=interval)
                )
                logger.info("Serial port opened: %s", port)

            data = await loop.run_in_executor(None, _read_line, ser)
            if data and "temperature_f" in data and "humidity_pct" in data:
                await _save_reading(data)
                logger.debug(
                    "Saved reading: %.1f°F, %.1f%%",
                    data["temperature_f"],
                    data["humidity_pct"],
                )

            # Wait for the poll interval, but stop early if signaled
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=interval)

        except serial.SerialException as e:
            logger.error("Serial error: %s — retrying in %ds", e, interval)
            if ser is not None:
                ser.close()
                ser = None
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stop_event.wait(), timeout=interval)

    if ser is not None:
        ser.close()
        logger.info("Serial port closed")
