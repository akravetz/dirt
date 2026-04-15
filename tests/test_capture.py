from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.models.snapshot import Snapshot


@pytest.fixture
async def db_engine(tmp_path):
    db_path = tmp_path / "test.db"
    eng = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


async def test_capture_snapshot_saves_file_and_db_record(db_engine, tmp_path):
    # Minimal JPEG-shaped blob (SOI + EOI). capture_snapshot just persists
    # whatever bytes capture_frame returns; it doesn't decode them.
    fake_jpeg = b"\xff\xd8\xff\xd9"

    with (
        patch(
            "dirt.services.capture.capture_frame",
            new=AsyncMock(return_value=fake_jpeg),
        ),
        patch("dirt.services.capture.settings") as mock_settings,
        patch("dirt.services.capture.engine", db_engine),
    ):
        mock_settings.snapshot_dir = str(tmp_path / "snapshots")

        from dirt.services.capture import capture_snapshot

        snapshot = await capture_snapshot()

    assert snapshot is not None
    assert snapshot.file_path.endswith(".jpg")
    assert Path(snapshot.file_path).exists()
    assert Path(snapshot.file_path).read_bytes() == fake_jpeg

    async with AsyncSession(db_engine) as session:
        result = await session.exec(select(Snapshot))
        rows = result.all()
        assert len(rows) == 1
        assert rows[0].id == snapshot.id
