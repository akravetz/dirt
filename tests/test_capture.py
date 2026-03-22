from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.models.snapshot import Snapshot


def _make_fake_capture(*args, **kwargs):
    """Create a mock VideoCapture that returns a valid frame."""
    cap = MagicMock()
    cap.isOpened.return_value = True
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    cap.read.return_value = (True, fake_frame)
    return cap


@pytest.fixture
async def db_engine(tmp_path):
    db_path = tmp_path / "test.db"
    eng = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


async def test_capture_snapshot_saves_file_and_db_record(db_engine, tmp_path):
    with (
        patch("dirt.services.capture.cv2.VideoCapture", side_effect=_make_fake_capture),
        patch("dirt.services.capture.settings") as mock_settings,
        patch("dirt.services.capture.engine", db_engine),
    ):
        mock_settings.snapshot_dir = str(tmp_path / "snapshots")
        mock_settings.camera_device = 0

        from dirt.services.capture import capture_snapshot

        snapshot = await capture_snapshot()

    assert snapshot is not None
    assert snapshot.file_path.endswith(".jpg")

    from pathlib import Path

    assert Path(snapshot.file_path).exists()

    async with AsyncSession(db_engine) as session:
        result = await session.exec(select(Snapshot))
        rows = result.all()
        assert len(rows) == 1
        assert rows[0].id == snapshot.id
