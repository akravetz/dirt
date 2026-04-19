import asyncio
import contextlib
import json
import logging
import math

import serial
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.config import settings
from dirt.db import engine
from dirt.models.sensor_reading import SensorReading

logger = logging.getLogger(__name__)


def _c_to_f(celsius: float) -> float:
    return celsius * 9 / 5 + 32


def _saturation_vapor_pressure_kpa(temp_c: float) -> float:
    """Tetens formula for saturation vapor pressure (kPa) at the given temp (°C)."""
    return 0.6108 * math.exp(17.27 * temp_c / (temp_c + 237.3))


def _vpd_kpa(temp_c: float, rh_pct: float) -> float:
    """Vapor pressure deficit (kPa) from temperature and relative humidity."""
    svp = _saturation_vapor_pressure_kpa(temp_c)
    return svp * (1 - rh_pct / 100)


def _dew_point_c(temp_c: float, rh_pct: float) -> float:
    """Dew point (°C) via the Magnus formula."""
    a, b = 17.27, 237.7
    gamma = (a * temp_c) / (b + temp_c) + math.log(max(rh_pct, 0.01) / 100)
    return (b * gamma) / (a - gamma)


def _derive_metrics(data: dict) -> dict[str, float]:
    """Given a raw reading from the Arduino, return the full metric dict."""
    temp_c = float(data["temperature_c"])
    hum = float(data["humidity_pct"])
    pres = float(data["pressure_hpa"])
    return {
        "temperature_f": _c_to_f(temp_c),
        "humidity_pct": hum,
        "pressure_hpa": pres,
        "vpd_kpa": _vpd_kpa(temp_c, hum),
        "dew_point_f": _c_to_f(_dew_point_c(temp_c, hum)),
    }


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


async def _save_reading(metrics: dict[str, float]) -> None:
    """Save a full set of metrics as individual rows."""
    async with AsyncSession(engine) as session:
        for name, value in metrics.items():
            session.add(
                SensorReading(
                    location="tent", metric=name, value=value, source="arduino"
                )
            )
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
    ser: serial.Serial | None = None

    while not stop_event.is_set():
        try:
            if ser is None or not ser.is_open:
                ser = await loop.run_in_executor(
                    None, lambda: serial.Serial(port, baud, timeout=interval)
                )
                logger.info("Serial port opened: %s", port)

            data = await loop.run_in_executor(None, _read_line, ser)
            if data and all(
                k in data for k in ("temperature_c", "humidity_pct", "pressure_hpa")
            ):
                try:
                    metrics = _derive_metrics(data)
                except (KeyError, ValueError, TypeError) as e:
                    logger.warning("Could not derive metrics from %r: %s", data, e)
                else:
                    await _save_reading(metrics)
                    logger.debug(
                        "Saved reading: %.1f°F, %.1f%%, %.1fhPa, VPD=%.2fkPa",
                        metrics["temperature_f"],
                        metrics["humidity_pct"],
                        metrics["pressure_hpa"],
                        metrics["vpd_kpa"],
                    )
            elif data and "error" in data:
                logger.warning("Arduino reported error: %s", data["error"])

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
