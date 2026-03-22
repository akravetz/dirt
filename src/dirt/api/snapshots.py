from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from dirt.services.snapshots import get_latest_snapshot, get_snapshot_path

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


@router.get("/latest")
async def latest_snapshot() -> FileResponse:
    snapshot = await get_latest_snapshot()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshots available")

    file_path = get_snapshot_path(snapshot)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Snapshot file not found")

    return FileResponse(file_path, media_type="image/jpeg")
