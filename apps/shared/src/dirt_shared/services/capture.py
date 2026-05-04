"""Capture service — thin client over the dirt-camera daemon socket.

The daemon owns ``/dev/video0`` (v4l2 streaming at 5fps MJPG) and exposes
a ``capture`` command that writes the latest frame to a tempfile. Python
reads that tempfile and returns the bytes.

All v4l2, white balance, exposure, and rotation concerns live in the daemon.
"""

import asyncio
import contextlib
import logging
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.config import CaptureConfig
from dirt_shared.models.device import Device
from dirt_shared.models.grow_run import GrowRun
from dirt_shared.models.snapshot import Snapshot
from dirt_shared.services.scope import DEFAULT_SITE_ID, DEFAULT_TENT_ID, resolve_scope

# Type alias for the camera-daemon boundary — exposed as a constructor
# parameter on ``CaptureService`` so tests can inject a fake without
# patching ``dirt_shared.services.capture.capture_frame``.
FrameCapturer = Callable[[], Awaitable[bytes | None]]

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
    """Parse `STATUS k=v k=v ...` into {'_status': STATUS, k: v, ...}."""
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

    Stateless — no engine, no config. Returns None if daemon unreachable.
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


class CaptureService:
    """Snapshot capture + persistence + periodic loop. Constructor-inject
    engine + ``CaptureConfig`` (snapshot_dir + capture_interval) plus the
    ``frame_capturer`` callable (defaults to the daemon-RPC implementation;
    tests inject a fake to skip the network round-trip).
    """

    def __init__(
        self,
        engine: AsyncEngine,
        config: CaptureConfig,
        *,
        frame_capturer: FrameCapturer = capture_frame,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._engine = engine
        self._config = config
        self._capture_frame = frame_capturer
        self._clock = clock

    async def capture_snapshot(self) -> Snapshot | None:
        """Capture a frame, save to disk, record in DB."""
        data = await self._capture_frame()
        if data is None:
            return None

        snapshot_dir = Path(self._config.snapshot_dir)
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        now = self._clock()
        filename = f"snapshot_{now.strftime('%Y%m%d_%H%M%S')}.jpg"
        file_path = snapshot_dir / filename
        await asyncio.to_thread(file_path.write_bytes, data)

        snapshot = Snapshot(ts=now, file_path=str(file_path))
        async with AsyncSession(self._engine) as session:
            scope = await resolve_scope(
                session, site_id=DEFAULT_SITE_ID, tent_id=DEFAULT_TENT_ID
            )
            if scope is not None:
                snapshot.site_id = scope.site_pk
                snapshot.tent_id = scope.tent_pk
                snapshot.device_id = (
                    await session.exec(
                        select(Device.id)
                        .where(Device.site_id == scope.site_pk)
                        .where(Device.device_id == "obsbot-main")
                        .limit(1)
                    )
                ).first()
                snapshot.growrun_id = (
                    await session.exec(
                        select(GrowRun.id)
                        .where(GrowRun.site_id == scope.site_pk)
                        .where(GrowRun.tent_id == scope.tent_pk)
                        .where(GrowRun.is_current.is_(True))
                        .limit(1)
                    )
                ).first()
            session.add(snapshot)
            await session.commit()
            await session.refresh(snapshot)

        logger.info("Captured snapshot: %s", file_path)
        return snapshot

    async def run(self, stop_event: asyncio.Event) -> None:
        """Periodically capture a snapshot at the configured interval.

        Exceptions propagate to the caller — the hwd supervisor restarts
        this loop with a sliding-window failure budget.
        """
        logger.info(
            "Starting capture loop (interval=%ds, via dirt-camera daemon)",
            self._config.capture_interval,
        )
        while not stop_event.is_set():
            await self.capture_snapshot()
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=self._config.capture_interval,
                )
