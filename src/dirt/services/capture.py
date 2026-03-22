import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from pathlib import Path

import cv2
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.config import settings
from dirt.db import engine
from dirt.models.snapshot import Snapshot

logger = logging.getLogger(__name__)


def _capture_frame(device: int) -> bytes | None:
    """Capture a single JPEG frame from the webcam. Runs in a thread."""
    cap = cv2.VideoCapture(device)
    try:
        if not cap.isOpened():
            logger.error("Failed to open camera device %d", device)
            return None
        ret, frame = cap.read()
        if not ret:
            logger.error("Failed to read frame from camera")
            return None
        _, buf = cv2.imencode(".jpg", frame)
        return buf.tobytes()
    finally:
        cap.release()


async def capture_snapshot() -> Snapshot | None:
    """Capture a snapshot, save to disk, and record in the database."""
    snapshot_dir = Path(settings.snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, _capture_frame, settings.camera_device)
    if data is None:
        return None

    now = datetime.now(UTC)
    filename = f"snapshot_{now.strftime('%Y%m%d_%H%M%S')}.jpg"
    file_path = snapshot_dir / filename
    file_path.write_bytes(data)

    snapshot = Snapshot(timestamp=now, file_path=str(file_path))
    async with AsyncSession(engine) as session:
        session.add(snapshot)
        await session.commit()
        await session.refresh(snapshot)

    logger.info("Captured snapshot: %s", file_path)
    return snapshot


async def capture_loop(stop_event: asyncio.Event) -> None:
    """Continuously capture snapshots at the configured interval."""
    logger.info(
        "Starting capture loop (interval=%ds, device=%d)",
        settings.capture_interval,
        settings.camera_device,
    )
    while not stop_event.is_set():
        try:
            await capture_snapshot()
        except Exception:
            logger.exception("Error capturing snapshot")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=settings.capture_interval)
