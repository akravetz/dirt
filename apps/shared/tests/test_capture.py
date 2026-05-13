from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.camera import CapturedFrame, SnapshotArtifact, SnapshotWriter
from dirt_shared.models.snapshot import Snapshot
from dirt_shared.services.camera_publisher import (
    CameraCaptureMetadata,
    CameraCapturePublisher,
    CaptureDecision,
    LocalSnapshotSink,
)
from dirt_shared.services.scope import DEFAULT_SITE_ID, DEFAULT_TENT_ID

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


class DenyGate:
    async def evaluate(self, metadata: CameraCaptureMetadata) -> CaptureDecision:
        del metadata
        return CaptureDecision(allowed=False, reason="lights_off")


def _mainbox_metadata() -> CameraCaptureMetadata:
    return CameraCaptureMetadata(
        site_id=DEFAULT_SITE_ID,
        tent_id=DEFAULT_TENT_ID,
        camera_device_id="obsbot-main",
        camera_view_id="periodic",
        camera_kind="periodic",
    )


async def test_publisher_local_sink_saves_file_and_db_record(app_engine, tmp_path):
    captured_at = datetime(2026, 5, 10, 12, 30, 45, tzinfo=UTC)
    source = FakeCameraSource(
        CapturedFrame(jpeg_bytes=JPEG_BYTES, captured_at=captured_at)
    )
    publisher = CameraCapturePublisher(
        metadata=_mainbox_metadata(),
        source=source,
        writer=SnapshotWriter(tmp_path / "snapshots"),
        sinks=(LocalSnapshotSink(app_engine),),
        capture_interval_s=999,
    )
    result = await publisher.run_once()

    assert result is not None
    snapshot = result.sink_results[0]
    assert isinstance(snapshot, Snapshot)
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


async def test_publisher_local_sink_uses_camera_source_and_snapshot_writer(
    app_engine, tmp_path
):
    captured_at = datetime(2026, 5, 10, 12, 30, 45, tzinfo=UTC)
    frame = CapturedFrame(jpeg_bytes=JPEG_BYTES, captured_at=captured_at)
    source = FakeCameraSource(frame)
    writer = RecordingSnapshotWriter(SnapshotWriter(tmp_path / "snapshots"))

    publisher = CameraCapturePublisher(
        metadata=_mainbox_metadata(),
        source=source,
        writer=writer,
        sinks=(LocalSnapshotSink(app_engine),),
        capture_interval_s=999,
    )

    result = await publisher.run_once()

    assert result is not None
    snapshot = result.sink_results[0]
    assert isinstance(snapshot, Snapshot)
    assert source.captures == 1
    assert writer.frames == [frame]
    assert snapshot.ts == captured_at
    assert Path(snapshot.file_path) == (
        tmp_path / "snapshots" / "snapshot_20260510_123045.jpg"
    )
    assert Path(snapshot.file_path).read_bytes() == JPEG_BYTES


async def test_publisher_local_sink_skips_before_camera_when_gate_denies(
    app_engine, tmp_path
):
    captured_at = datetime(2026, 5, 10, 12, 30, 45, tzinfo=UTC)
    source = FakeCameraSource(
        CapturedFrame(jpeg_bytes=JPEG_BYTES, captured_at=captured_at)
    )
    writer = RecordingSnapshotWriter(SnapshotWriter(tmp_path / "snapshots"))

    publisher = CameraCapturePublisher(
        metadata=_mainbox_metadata(),
        source=source,
        writer=writer,
        sinks=(LocalSnapshotSink(app_engine),),
        capture_interval_s=999,
        gate=DenyGate(),
    )

    result = await publisher.run_once()

    assert result is None
    assert source.captures == 0
    assert writer.frames == []
    async with AsyncSession(app_engine) as session:
        rows = (await session.exec(select(Snapshot))).all()
    assert rows == []
