from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from dirt_shared.services.snapshots import SnapshotsService, get_snapshot_path
from dirt_web.deps import get_snapshots

router = APIRouter(prefix="/api/snapshots", tags=["snapshots"])


@router.get("/latest")
async def latest_snapshot(
    snaps: SnapshotsService = Depends(get_snapshots),
) -> FileResponse:
    snapshot = await snaps.latest()
    if snapshot is None:
        raise HTTPException(status_code=404, detail="No snapshots available")

    file_path = get_snapshot_path(snapshot)
    if file_path is None:
        raise HTTPException(status_code=404, detail="Snapshot file not found")

    return FileResponse(file_path, media_type="image/jpeg")
