from pathlib import Path

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.config import CaptureConfig
from dirt_shared.models.snapshot import Snapshot
from dirt_shared.services.capture import CaptureService


async def test_capture_snapshot_saves_file_and_db_record(app_engine, tmp_path):
    # Minimal JPEG-shaped blob (SOI + EOI). capture_snapshot persists whatever
    # bytes the injected capturer returns; it doesn't decode them.
    fake_jpeg = b"\xff\xd8\xff\xd9"

    async def fake_capturer() -> bytes:
        return fake_jpeg

    svc = CaptureService(
        app_engine,
        CaptureConfig(snapshot_dir=tmp_path / "snapshots", capture_interval=999),
        frame_capturer=fake_capturer,
    )
    snapshot = await svc.capture_snapshot()

    assert snapshot is not None
    assert snapshot.file_path.endswith(".jpg")
    assert Path(snapshot.file_path).exists()
    assert Path(snapshot.file_path).read_bytes() == fake_jpeg

    async with AsyncSession(app_engine) as session:
        result = await session.exec(select(Snapshot))
        rows = result.all()
        assert len(rows) == 1
        assert rows[0].id == snapshot.id
