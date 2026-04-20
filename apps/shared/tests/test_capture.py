from pathlib import Path
from unittest.mock import AsyncMock, patch

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.snapshot import Snapshot


async def test_capture_snapshot_saves_file_and_db_record(pg_engine, tmp_path):
    # Minimal JPEG-shaped blob (SOI + EOI). capture_snapshot just persists
    # whatever bytes capture_frame returns; it doesn't decode them.
    fake_jpeg = b"\xff\xd8\xff\xd9"

    with (
        patch(
            "dirt_shared.services.capture.capture_frame",
            new=AsyncMock(return_value=fake_jpeg),
        ),
        patch("dirt_shared.services.capture.settings") as mock_settings,
    ):
        mock_settings.snapshot_dir = str(tmp_path / "snapshots")

        from dirt_shared.services.capture import capture_snapshot

        snapshot = await capture_snapshot()

    assert snapshot is not None
    assert snapshot.file_path.endswith(".jpg")
    assert Path(snapshot.file_path).exists()
    assert Path(snapshot.file_path).read_bytes() == fake_jpeg

    async with AsyncSession(pg_engine) as session:
        result = await session.exec(select(Snapshot))
        rows = result.all()
        assert len(rows) == 1
        assert rows[0].id == snapshot.id
