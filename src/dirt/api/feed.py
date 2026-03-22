from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response

from dirt.services.capture import capture_frame
from dirt.services.snapshots import get_latest_snapshot

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
    ts_str = snapshot.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
    return HTMLResponse(f"Last capture: {ts_str}")
