from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.db import get_session
from dirt.models.snapshot import Snapshot

router = APIRouter(prefix="/feed", tags=["feed"])

_get_session = Depends(get_session)


@router.get("/image", response_class=HTMLResponse)
async def feed_image(session: AsyncSession = _get_session) -> HTMLResponse:
    result = await session.exec(
        select(Snapshot).order_by(Snapshot.timestamp.desc()).limit(1)
    )
    snapshot = result.first()
    if snapshot is None:
        return HTMLResponse('<div class="no-feed">Waiting for first snapshot...</div>')
    ts = int(snapshot.timestamp.timestamp())
    return HTMLResponse(f'<img src="/api/snapshots/latest?t={ts}" alt="Live feed">')


@router.get("/status", response_class=HTMLResponse)
async def feed_status(session: AsyncSession = _get_session) -> HTMLResponse:
    result = await session.exec(
        select(Snapshot).order_by(Snapshot.timestamp.desc()).limit(1)
    )
    snapshot = result.first()
    if snapshot is None:
        return HTMLResponse("No snapshots yet")
    ts_str = snapshot.timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")
    return HTMLResponse(f"Last capture: {ts_str}")
