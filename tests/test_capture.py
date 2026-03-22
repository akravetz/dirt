from unittest.mock import patch

import cv2
import numpy as np
import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.models.snapshot import Snapshot


def _make_fake_jpeg() -> bytes:
    """Create minimal valid JPEG bytes."""
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    _, buf = cv2.imencode(".jpg", frame)
    return buf.tobytes()


@pytest.fixture
async def db_engine(tmp_path):
    db_path = tmp_path / "test.db"
    eng = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


async def test_capture_snapshot_saves_file_and_db_record(db_engine, tmp_path):
    fake_jpeg = _make_fake_jpeg()

    with (
        patch(
            "dirt.services.capture._auto_expose_and_capture",
            return_value=fake_jpeg,
        ),
        patch("dirt.services.capture.settings") as mock_settings,
        patch("dirt.services.capture.engine", db_engine),
    ):
        mock_settings.snapshot_dir = str(tmp_path / "snapshots")

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
