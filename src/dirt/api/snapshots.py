from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.db import get_session
from dirt.models.snapshot import Snapshot

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])

_get_session = Depends(get_session)


@router.get("/latest")
async def latest_snapshot(
    session: AsyncSession = _get_session,
) -> FileResponse:
    result = await session.exec(
        select(Snapshot).order_by(Snapshot.timestamp.desc()).limit(1)
    )
    snapshot = result.first()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshots available")

    file_path = Path(snapshot.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Snapshot file not found")

    return FileResponse(file_path, media_type="image/jpeg")
