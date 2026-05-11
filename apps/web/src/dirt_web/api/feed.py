"""Live feed endpoint — one JPEG per request.

The SPA refreshes by bumping a cache-busting query param on its
``<img src=".../live.jpg?t=...">``, so we always return fresh bytes
from the camera daemon through the shared camera source.

Legacy ``/feed/live``, ``/feed/image`` (HTMX fragment) and
``/feed/status`` (HTMX fragment) are deleted with this rename; the SPA
renders the timestamp client-side.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response

from dirt_shared.services.capture import FrameCapturer
from dirt_shared.services.scope import DEFAULT_SITE_ID, DEFAULT_TENT_ID
from dirt_shared.services.snapshots import SnapshotsService, get_snapshot_path
from dirt_web.deps import get_frame_capturer, get_snapshots

router = APIRouter(prefix="/api/feed", tags=["feed"])


@router.get("/live.jpg")
async def live_frame(
    capture: FrameCapturer = Depends(get_frame_capturer),
) -> Response:
    """Return one live JPEG frame from the camera daemon.

    503 when the daemon is unreachable or returns no bytes. The
    ``Cache-Control: no-store`` header is deliberate — the caller
    cache-busts on its side, but any cache between client and server
    must not serve stale frames either.
    """
    data = await capture()
    if data is None:
        return Response(status_code=503)
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/snapshot/latest")
async def latest_snapshot(
    site_id: str = Query(DEFAULT_SITE_ID),
    tent_id: str = Query(DEFAULT_TENT_ID),
    snaps: SnapshotsService = Depends(get_snapshots),
) -> FileResponse:
    """Return the most recent archived snapshot from disk.

    This is the renamed ``/api/snapshots/latest``. 404 when no
    snapshot rows exist yet, or the row's ``file_path`` is missing
    from disk (archive drift).
    """
    snapshot = await snaps.latest(site_id=site_id, tent_id=tent_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshots available")

    file_path = get_snapshot_path(snapshot)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Snapshot file not found")

    return FileResponse(file_path, media_type="image/jpeg")
