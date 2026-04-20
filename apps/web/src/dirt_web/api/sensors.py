from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, JSONResponse

from dirt_shared.services.readings import ReadingsService
from dirt_web.deps import get_readings

router = APIRouter(tags=["sensors"])


@router.get("/api/sensors/readings")
async def sensor_readings(
    range: str = Query(default="24h", pattern="^(1h|24h|7d|30d)$"),
    readings: ReadingsService = Depends(get_readings),
) -> JSONResponse:
    """Return all sensor metrics for Chart.js.

    Response shape: {metric: {"labels": [...], "values": [...]}, ...}
    """
    data = await readings.get_sensor_history(range)
    return JSONResponse(data)


@router.get("/sensors/current", response_class=HTMLResponse)
async def current_readings(
    readings: ReadingsService = Depends(get_readings),
) -> HTMLResponse:
    """HTMX fragment showing the latest sensor values."""
    temp = await readings.get_latest_reading("temperature_f")
    hum = await readings.get_latest_reading("humidity_pct")
    pres = await readings.get_latest_reading("pressure_hpa")
    vpd = await readings.get_latest_reading("vpd_kpa")

    if temp is None or hum is None:
        return HTMLResponse('<div class="current-stats">No sensor data available</div>')

    stale = await readings.is_sensor_stale()
    warning = ""
    if stale:
        warning = (
            '<div style="background:#a33;color:#fff;padding:0.5rem 1rem;'
            'font-size:0.85rem;border-radius:4px;margin:0.5rem 1rem;">'
            "⚠ Sensor may be stuck — readings unchanged.</div>"
        )

    stats = [
        (f"{temp.value:.1f}°F", "Temperature"),
        (f"{hum.value:.1f}%", "Humidity"),
    ]
    if pres is not None:
        stats.append((f"{pres.value:.0f} hPa", "Pressure"))
    if vpd is not None:
        stats.append((f"{vpd.value:.2f} kPa", "VPD"))

    stat_html = "".join(
        f'<div class="stat">'
        f'<span class="stat-value">{value}</span>'
        f'<span class="stat-label">{label}</span>'
        f"</div>"
        for value, label in stats
    )
    return HTMLResponse(f'{warning}<div class="current-stats">{stat_html}</div>')
