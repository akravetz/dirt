from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlmodel import select, text
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.db import get_session
from dirt.models.sensor_reading import SensorReading

router = APIRouter(tags=["sensors"])

_get_session = Depends(get_session)

RANGE_DELTAS = {
    "1h": timedelta(hours=1),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}


@router.get("/api/sensors/readings")
async def sensor_readings(
    session: AsyncSession = _get_session,
    range: str = Query(default="24h", pattern="^(1h|24h|7d|30d)$"),
) -> JSONResponse:
    """Return sensor data as JSON for Chart.js."""
    delta = RANGE_DELTAS[range]
    cutoff = datetime.now(UTC) - delta

    if range in ("7d", "30d"):
        # Hourly averages for longer ranges
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
        # Raw readings for shorter ranges
        result = await session.exec(
            select(SensorReading)
            .where(SensorReading.timestamp >= cutoff)
            .order_by(SensorReading.timestamp)
        )
        rows = result.all()
        labels = [r.timestamp.isoformat() for r in rows]
        temperature = [r.temperature_f for r in rows]
        humidity = [r.humidity_pct for r in rows]

    return JSONResponse(
        {"labels": labels, "temperature": temperature, "humidity": humidity}
    )


@router.get("/sensors/current", response_class=HTMLResponse)
async def current_readings(
    session: AsyncSession = _get_session,
) -> HTMLResponse:
    """HTMX fragment showing the latest sensor values."""
    result = await session.exec(
        select(SensorReading).order_by(SensorReading.timestamp.desc()).limit(1)
    )
    reading = result.first()
    if reading is None:
        return HTMLResponse('<div class="current-stats">No sensor data available</div>')
    return HTMLResponse(
        f'<div class="current-stats">'
        f'<div class="stat">'
        f'<span class="stat-value">{reading.temperature_f:.1f}°F</span>'
        f'<span class="stat-label">Temperature</span>'
        f"</div>"
        f'<div class="stat">'
        f'<span class="stat-value">{reading.humidity_pct:.1f}%</span>'
        f'<span class="stat-label">Humidity</span>'
        f"</div>"
        f"</div>"
    )
