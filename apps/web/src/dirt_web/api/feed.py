from zoneinfo import ZoneInfo

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from dirt_shared.services.capture import capture_frame
from dirt_shared.services.snapshots import get_latest_snapshot

_MT = ZoneInfo("America/Denver")

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("/live")
async def live_frame() -> Response:
    """Return a live JPEG frame from the camera (not saved to disk or DB)."""
    data = await capture_frame()
    if data is None:
        return Response(status_code=503)
    return Response(content=data, media_type="image/jpeg")


@router.get("/image", response_class=HTMLResponse)
async def feed_image() -> HTMLResponse:
    """HTMX fragment that renders a live feed image, refreshing via cache-bust."""
    return HTMLResponse(
        '<img src="/feed/live" alt="Live feed" '
        'hx-get="/feed/image" hx-trigger="load delay:15s" hx-swap="outerHTML">'
    )


@router.get("/status", response_class=HTMLResponse)
async def feed_status() -> HTMLResponse:
    snapshot = await get_latest_snapshot()
    if snapshot is None:
        return HTMLResponse("No snapshots yet")
    ts_mt = snapshot.timestamp.astimezone(_MT)
    ts_str = ts_mt.strftime("%Y-%m-%d %I:%M:%S %p MT")
    return HTMLResponse(f"Last capture: {ts_str}")
