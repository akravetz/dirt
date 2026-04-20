"""Capture service — thin client over the dirt-camera daemon socket.

The daemon owns `/dev/video0` (v4l2 streaming at 5fps MJPG) and exposes a
`capture` command that writes the latest frame to a tempfile. Python reads
that tempfile and returns the bytes.

All v4l2, white balance, exposure, and rotation concerns live in the daemon.
"""

import asyncio
import contextlib
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.config import settings
from dirt_shared.db import engine
from dirt_shared.models.snapshot import Snapshot

logger = logging.getLogger(__name__)


def _daemon_socket_path() -> str:
    """Match the daemon's default: $XDG_RUNTIME_DIR/dirt-camera.sock."""
    explicit = os.environ.get("DIRT_CAMERA_SOCKET")
    if explicit:
        return explicit
    xdg = os.environ.get("XDG_RUNTIME_DIR")
    if xdg:
        return f"{xdg}/dirt-camera.sock"
    return "/tmp/dirt-camera.sock"


def _parse_response(line: str) -> dict[str, str]:
    """Parse `STATUS k=v k=v ...` into {'_status': STATUS, k: v, ...}.

    Values stay as strings.
    """
    toks = line.split()
    if not toks:
        return {"_status": "empty"}
    out: dict[str, str] = {"_status": toks[0]}
    for kv in toks[1:]:
        if "=" in kv:
            k, v = kv.split("=", 1)
            out[k] = v
    return out


async def _daemon_rpc(line: str, timeout: float = 5.0) -> dict[str, str]:
    """Send one line to the daemon, return the parsed response."""
    path = _daemon_socket_path()
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_unix_connection(path), timeout=timeout
        )
    except (FileNotFoundError, ConnectionRefusedError) as e:
        logger.error("camera daemon not reachable at %s: %s", path, e)
        return {"_status": "error", "msg": "daemon_unreachable"}
    except TimeoutError:
        logger.error("camera daemon connect timeout at %s", path)
        return {"_status": "error", "msg": "connect_timeout"}

    try:
        writer.write((line + "\n").encode())
        await writer.drain()
        raw = await asyncio.wait_for(reader.readline(), timeout=timeout)
    except TimeoutError:
        logger.error("camera daemon response timeout for: %s", line)
        writer.close()
        return {"_status": "error", "msg": "response_timeout"}
    finally:
        writer.close()
        with contextlib.suppress(Exception):
            await writer.wait_closed()

    return _parse_response(raw.decode().strip())


async def capture_frame() -> bytes | None:
    """Ask the daemon to capture a frame; read the tempfile; return bytes.

    Returns None if the daemon is unreachable or the capture failed.
    The tempfile is not deleted here — daemon TTL-sweeps its own dir.
    """
    resp = await _daemon_rpc("capture")
    if resp.get("_status") != "ok":
        logger.error("camera capture failed: %s", resp)
        return None
    path = resp.get("path")
    if not path:
        logger.error("camera capture response missing path: %s", resp)
        return None
    try:
        return await asyncio.to_thread(Path(path).read_bytes)
    except OSError as e:
        logger.error("failed to read capture tempfile %s: %s", path, e)
        return None


async def capture_snapshot() -> Snapshot | None:
    """Capture a frame, save to disk, and record in the database."""
    data = await capture_frame()
    if data is None:
        return None

    snapshot_dir = Path(settings.snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(UTC)
    filename = f"snapshot_{now.strftime('%Y%m%d_%H%M%S')}.jpg"
    file_path = snapshot_dir / filename
    await asyncio.to_thread(file_path.write_bytes, data)

    snapshot = Snapshot(ts=now, file_path=str(file_path))
    async with AsyncSession(engine) as session:
        session.add(snapshot)
        await session.commit()
        await session.refresh(snapshot)

    logger.info("Captured snapshot: %s", file_path)
    return snapshot


async def capture_loop(stop_event: asyncio.Event) -> None:
    """Periodically archive a snapshot at the configured interval."""
    logger.info(
        "Starting capture loop (interval=%ds, via dirt-camera daemon)",
        settings.capture_interval,
    )
    while not stop_event.is_set():
        try:
            await capture_snapshot()
        except Exception:
            logger.exception("Error capturing snapshot")
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop_event.wait(), timeout=settings.capture_interval)
