"""Capture service for snapshot persistence and periodic main-tent capture."""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.camera import (
    CameraCaptureError,
    CameraSource,
    CapturedFrame,
    ObsbotDaemonCameraSource,
    SnapshotArtifact,
    SnapshotWriter,
)
from dirt_shared.config import CaptureConfig
from dirt_shared.models.device import Device
from dirt_shared.models.grow_run import GrowRun
from dirt_shared.models.snapshot import Snapshot
from dirt_shared.services.scope import DEFAULT_SITE_ID, DEFAULT_TENT_ID, resolve_scope

# Type alias for the camera-daemon boundary — exposed as a constructor
# parameter on ``CaptureService`` so tests can inject a fake without
# patching the daemon socket.
FrameCapturer = Callable[[], Awaitable[bytes | None]]

logger = logging.getLogger(__name__)


class SnapshotWritable(Protocol):
    async def write(self, frame: CapturedFrame) -> SnapshotArtifact:
        """Write one captured frame and return the resulting artifact."""


class _FrameCapturerCameraSource:
    def __init__(
        self,
        frame_capturer: FrameCapturer,
        clock: Callable[[], datetime],
    ) -> None:
        self._frame_capturer = frame_capturer
        self._clock = clock

    async def capture(self) -> CapturedFrame:
        data = await self._frame_capturer()
        if data is None:
            raise CameraCaptureError("camera capture returned no frame")
        return CapturedFrame(jpeg_bytes=data, captured_at=self._clock())


class CaptureService:
    """Snapshot capture + persistence + periodic loop."""

    def __init__(  # noqa: PLR0913 - preserves existing capture test seams.
        self,
        engine: AsyncEngine,
        config: CaptureConfig,
        *,
        camera_source: CameraSource | None = None,
        snapshot_writer: SnapshotWritable | None = None,
        frame_capturer: FrameCapturer | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._engine = engine
        self._config = config
        self._camera_source = camera_source or (
            _FrameCapturerCameraSource(frame_capturer, clock)
            if frame_capturer is not None
            else ObsbotDaemonCameraSource(
                socket_path=self._config.camera_socket_path,
                clock=clock,
            )
        )
        self._snapshot_writer = snapshot_writer or SnapshotWriter(
            Path(self._config.snapshot_dir)
        )

    async def capture_snapshot(self) -> Snapshot | None:
        """Capture a frame, save to disk, record in DB."""
        try:
            frame = await self._camera_source.capture()
            artifact = await self._snapshot_writer.write(frame)
        except CameraCaptureError as exc:
            logger.error("camera capture failed: %s", exc)
            return None

        snapshot = Snapshot(ts=artifact.captured_at, file_path=str(artifact.path))
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

        logger.info("Captured snapshot: %s", artifact.path)
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
