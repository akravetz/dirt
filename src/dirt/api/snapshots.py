from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.db import get_session
from dirt.services.snapshots import get_latest_snapshot, get_snapshot_path

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])

_get_session = Depends(get_session)


@router.get("/latest")
async def latest_snapshot(
    session: AsyncSession = _get_session,
) -> FileResponse:
    snapshot = await get_latest_snapshot(session)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshots available")

    file_path = get_snapshot_path(snapshot)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Snapshot file not found")

    return FileResponse(file_path, media_type="image/jpeg")
