from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.camera import CapturedFrame, SnapshotArtifact, SnapshotWriter
from dirt_shared.config import CaptureConfig
from dirt_shared.models.snapshot import Snapshot
from dirt_shared.services.capture import CaptureService

JPEG_BYTES = b"\xff\xd8\xff\xd9"


@dataclass
class FakeCameraSource:
    frame: CapturedFrame
    captures: int = 0

    async def capture(self) -> CapturedFrame:
        self.captures += 1
        return self.frame


class RecordingSnapshotWriter:
    def __init__(self, delegate: SnapshotWriter) -> None:
        self._delegate = delegate
        self.frames: list[CapturedFrame] = []

    async def write(self, frame: CapturedFrame) -> SnapshotArtifact:
        self.frames.append(frame)
        return await self._delegate.write(frame)


async def test_capture_snapshot_saves_file_and_db_record(app_engine, tmp_path):
    # Minimal JPEG-shaped blob (SOI + EOI). capture_snapshot persists whatever
    # bytes the injected capturer returns; it doesn't decode them.
    async def fake_capturer() -> bytes:
        return JPEG_BYTES

    svc = CaptureService(
        app_engine,
        CaptureConfig(snapshot_dir=tmp_path / "snapshots", capture_interval=999),
        frame_capturer=fake_capturer,
    )
    snapshot = await svc.capture_snapshot()

    assert snapshot is not None
    assert snapshot.file_path.endswith(".jpg")
    assert Path(snapshot.file_path).exists()
    assert Path(snapshot.file_path).read_bytes() == JPEG_BYTES

    async with AsyncSession(app_engine) as session:
        result = await session.exec(select(Snapshot))
        rows = result.all()
        assert len(rows) == 1
        assert rows[0].id == snapshot.id
        assert rows[0].site_id is not None
        assert rows[0].tent_id is not None
        assert rows[0].device_id is not None
        assert rows[0].growrun_id is not None
        assert rows[0].view_id == "periodic"
        assert rows[0].kind == "periodic"


async def test_capture_snapshot_uses_camera_source_and_snapshot_writer(
    app_engine, tmp_path
):
    captured_at = datetime(2026, 5, 10, 12, 30, 45, tzinfo=UTC)
    frame = CapturedFrame(jpeg_bytes=JPEG_BYTES, captured_at=captured_at)
    source = FakeCameraSource(frame)
    writer = RecordingSnapshotWriter(SnapshotWriter(tmp_path / "snapshots"))

    svc = CaptureService(
        app_engine,
        CaptureConfig(snapshot_dir=tmp_path / "unused", capture_interval=999),
        camera_source=source,
        snapshot_writer=writer,
    )

    snapshot = await svc.capture_snapshot()

    assert snapshot is not None
    assert source.captures == 1
    assert writer.frames == [frame]
    assert snapshot.ts == captured_at
    assert Path(snapshot.file_path) == (
        tmp_path / "snapshots" / "snapshot_20260510_123045.jpg"
    )
    assert Path(snapshot.file_path).read_bytes() == JPEG_BYTES
