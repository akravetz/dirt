import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.config import settings
from dirt.db import engine
from dirt.models.snapshot import Snapshot

logger = logging.getLogger(__name__)

_camera: cv2.VideoCapture | None = None
_current_exposure: int = settings.camera_exposure

EXPOSURE_MIN = 3
EXPOSURE_MAX = 2047
BRIGHTNESS_TOLERANCE = 15
MAX_ADJUST_ITERATIONS = 8


def _open_camera(device: int) -> cv2.VideoCapture | None:
    """Open the camera and configure settings."""
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        logger.error("Failed to open camera device %d", device)
        return None

    cap.set(cv2.CAP_PROP_AUTO_WB, 0)
    cap.set(cv2.CAP_PROP_WB_TEMPERATURE, settings.camera_white_balance)
    cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)  # Manual
    cap.set(cv2.CAP_PROP_GAIN, settings.camera_gain)
    cap.set(cv2.CAP_PROP_EXPOSURE, _current_exposure)

    logger.info(
        "Camera opened: device=%d, wb=%dK, exposure=%d, gain=%d",
        device,
        settings.camera_white_balance,
        _current_exposure,
        settings.camera_gain,
    )
    return cap


def _auto_expose_and_capture() -> bytes | None:
    """Capture a frame, auto-tuning exposure to hit target brightness.

    Adjusts exposure iteratively, then saves only the final frame.
    """
    global _camera, _current_exposure

    if _camera is None or not _camera.isOpened():
        _camera = _open_camera(settings.camera_device)
        if _camera is None:
            return None

    target = settings.camera_target_brightness

    for i in range(MAX_ADJUST_ITERATIONS):
        _camera.set(cv2.CAP_PROP_EXPOSURE, _current_exposure)
        # Read a few frames to let the new exposure settle
        for _ in range(3):
            _camera.read()

        ret, frame = _camera.read()
        if not ret:
            logger.error("Failed to read frame, reopening camera")
            _camera.release()
            _camera = None
            return None

        brightness = float(np.mean(frame))
        diff = brightness - target

        if abs(diff) <= BRIGHTNESS_TOLERANCE:
            logger.debug(
                "Exposure converged: exp=%d, brightness=%.0f (iter %d)",
                _current_exposure,
                brightness,
                i,
            )
            _, buf = cv2.imencode(".jpg", frame)
            return buf.tobytes()

        # Adjust: proportional step based on how far off we are
        ratio = target / max(brightness, 1)
        new_exposure = int(_current_exposure * ratio)
        new_exposure = max(EXPOSURE_MIN, min(EXPOSURE_MAX, new_exposure))

        if new_exposure == _current_exposure:
            # Can't adjust further, use what we have
            break

        logger.debug(
            "Adjusting exposure: %d → %d (brightness=%.0f, target=%d)",
            _current_exposure,
            new_exposure,
            brightness,
            target,
        )
        _current_exposure = new_exposure

    # Exhausted iterations or can't adjust further — use last frame
    logger.debug(
        "Exposure settled: exp=%d, brightness=%.0f",
        _current_exposure,
        brightness,
    )
    _, buf = cv2.imencode(".jpg", frame)
    return buf.tobytes()


def _release_camera() -> None:
    """Release the camera."""
    global _camera
    if _camera is not None:
        _camera.release()
        _camera = None
        logger.info("Camera released")


async def capture_frame() -> bytes | None:
    """Capture a single JPEG frame from the camera. Does not save to disk or DB."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _auto_expose_and_capture)


async def capture_snapshot() -> Snapshot | None:
    """Capture a snapshot, save to disk, and record in the database."""
    snapshot_dir = Path(settings.snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, _auto_expose_and_capture)
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

    logger.info("Captured snapshot: %s (exposure=%d)", file_path, _current_exposure)
    return snapshot


async def capture_loop(stop_event: asyncio.Event) -> None:
    """Continuously capture snapshots at the configured interval."""
    logger.info(
        "Starting capture loop (interval=%ds, device=%d, wb=%dK, target_brightness=%d)",
        settings.capture_interval,
        settings.camera_device,
        settings.camera_white_balance,
        settings.camera_target_brightness,
    )
    while not stop_event.is_set():
        try:
            await capture_snapshot()
        except Exception:
            logger.exception("Error capturing snapshot")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=settings.capture_interval)

    await asyncio.get_running_loop().run_in_executor(None, _release_camera)
