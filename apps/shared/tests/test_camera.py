from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from dirt_shared.camera import (
    CameraCaptureError,
    CameraSource,
    CapturedFrame,
    ObsbotDaemonCameraSource,
    SnapshotSpool,
)

JPEG_BYTES = b"\xff\xd8fake-jpeg\xff\xd9"


@dataclass
class FakeCameraSource:
    frame: CapturedFrame

    async def capture(self) -> CapturedFrame:
        return self.frame


async def _capture_from_source(source: CameraSource) -> CapturedFrame:
    return await source.capture()


async def test_fake_camera_source_satisfies_capture_contract() -> None:
    captured_at = datetime(2026, 5, 10, 12, 30, 45, tzinfo=UTC)
    frame = CapturedFrame(
        jpeg_bytes=JPEG_BYTES,
        captured_at=captured_at,
        source_frame_age_ms=50,
        width=1920,
        height=1080,
        driver_diagnostics={"source": "fake"},
    )

    source = FakeCameraSource(frame)

    assert isinstance(source, CameraSource)
    assert await _capture_from_source(source) == frame


async def test_obsbot_daemon_camera_source_reads_daemon_tempfile(tmp_path) -> None:
    captured_at = datetime(2026, 5, 10, 12, 30, 45, tzinfo=UTC)
    tempfile = tmp_path / "daemon-frame.jpg"
    tempfile.write_bytes(JPEG_BYTES)
    calls: list[str] = []

    async def fake_rpc(line: str) -> dict[str, str]:
        calls.append(line)
        return {
            "_status": "ok",
            "path": str(tempfile),
            "bytes": str(len(JPEG_BYTES)),
            "width": "1920",
            "height": "1080",
            "age_ms": "37",
            "capture_ms": "11",
        }

    source = ObsbotDaemonCameraSource(rpc=fake_rpc, clock=lambda: captured_at)

    frame = await source.capture()

    assert calls == ["capture"]
    assert frame.jpeg_bytes == JPEG_BYTES
    assert frame.captured_at == captured_at
    assert frame.content_type == "image/jpeg"
    assert frame.source_frame_age_ms == 37
    assert frame.width == 1920
    assert frame.height == 1080
    assert frame.driver_diagnostics == {
        "bytes": str(len(JPEG_BYTES)),
        "capture_ms": "11",
    }


async def test_obsbot_daemon_camera_source_raises_on_failed_capture() -> None:
    async def fake_rpc(line: str) -> dict[str, str]:
        assert line == "capture"
        return {"_status": "error", "msg": "daemon_unreachable"}

    source = ObsbotDaemonCameraSource(rpc=fake_rpc)

    with pytest.raises(CameraCaptureError, match="daemon_unreachable"):
        await source.capture()


async def test_snapshot_spool_writes_stable_name_atomically_and_hashes(
    tmp_path,
) -> None:
    captured_at = datetime(2026, 5, 10, 12, 30, 45, tzinfo=UTC)
    frame = CapturedFrame(jpeg_bytes=JPEG_BYTES, captured_at=captured_at)
    spool = SnapshotSpool(tmp_path / "snapshots")

    artifact = await spool.write(frame)

    expected_path = tmp_path / "snapshots" / "snapshot_20260510_123045.jpg"
    assert artifact.path == expected_path
    assert artifact.filename == "snapshot_20260510_123045.jpg"
    assert artifact.sha256 == hashlib.sha256(JPEG_BYTES).hexdigest()
    assert artifact.size_bytes == len(JPEG_BYTES)
    assert artifact.content_type == "image/jpeg"
    assert artifact.captured_at == captured_at
    assert expected_path.read_bytes() == JPEG_BYTES
    assert [
        path
        for path in Path(tmp_path / "snapshots").iterdir()
        if path.name.endswith(".tmp")
    ] == []
