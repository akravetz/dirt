from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, JSONResponse

from dirt.services.readings import (
    get_latest_reading,
    get_sensor_history,
    is_sensor_stale,
)

router = APIRouter(tags=["sensors"])


@router.get("/api/sensors/readings")
async def sensor_readings(
    range: str = Query(default="24h", pattern="^(1h|24h|7d|30d)$"),
) -> JSONResponse:
    """Return sensor data as JSON for Chart.js."""
    data = await get_sensor_history(range)
    return JSONResponse(data)


@router.get("/sensors/current", response_class=HTMLResponse)
async def current_readings() -> HTMLResponse:
    """HTMX fragment showing the latest sensor values."""
    reading = await get_latest_reading()
    if reading is None:
        return HTMLResponse('<div class="current-stats">No sensor data available</div>')
    stale = await is_sensor_stale()
    warning = ""
    if stale:
        warning = (
            '<div style="background:#a33;color:#fff;padding:0.5rem 1rem;'
            'font-size:0.85rem;border-radius:4px;margin:0.5rem 1rem;">'
            "⚠ Sensor may be stuck — readings unchanged. "
            "Check the DHT22 connection.</div>"
        )
    return HTMLResponse(
        f"{warning}"
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
