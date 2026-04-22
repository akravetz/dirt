"""Live feed endpoint — one JPEG per request.

The SPA refreshes by bumping a cache-busting query param on its
``<img src=".../live.jpg?t=...">``, so we always return fresh bytes
from the camera daemon (``capture_frame()`` is a one-shot RPC, not
an MJPEG stream).

Legacy ``/feed/live``, ``/feed/image`` (HTMX fragment) and
``/feed/status`` (HTMX fragment) are deleted with this rename; the SPA
renders the timestamp client-side.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import Response

from dirt_shared.services.capture import FrameCapturer
from dirt_web.deps import get_frame_capturer

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
