from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from dirt.services.snapshots import get_latest_snapshot

router = APIRouter(prefix="/feed", tags=["feed"])


@router.get("/image", response_class=HTMLResponse)
async def feed_image() -> HTMLResponse:
    snapshot = await get_latest_snapshot()
    if snapshot is None:
        return HTMLResponse('<div class="no-feed">Waiting for first snapshot...</div>')
    ts = int(snapshot.timestamp.timestamp())
    return HTMLResponse(f'<img src="/api/snapshots/latest?t={ts}" alt="Live feed">')


@router.get("/status", response_class=HTMLResponse)
async def feed_status() -> HTMLResponse:
    snapshot = await get_latest_snapshot()
    if snapshot is None:
        return HTMLResponse("No snapshots yet")
    ts_str = snapshot.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
    return HTMLResponse(f"Last capture: {ts_str}")
