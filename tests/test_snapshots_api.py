from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
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


@pytest.fixture
async def client(db_engine):
    with (
        patch("dirt.services.capture.capture_loop"),
        patch("dirt.db.engine", db_engine),
        patch("dirt.services.snapshots.engine", db_engine),
    ):
        from dirt.app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=False
        ) as ac:
            login = await ac.post(
                "/login", data={"username": "admin", "password": "changeme"}
            )
            ac.cookies = login.cookies
            yield ac


async def test_latest_snapshot_404_when_empty(client: AsyncClient):
    response = await client.get("/api/snapshots/latest")
    assert response.status_code == 404


async def test_latest_snapshot_returns_image(client: AsyncClient, db_engine, tmp_path):
    img_path = tmp_path / "test.jpg"
    img_path.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-data")

    async with AsyncSession(db_engine) as session:
        snapshot = Snapshot(timestamp=datetime.now(UTC), file_path=str(img_path))
        session.add(snapshot)
        await session.commit()

    response = await client.get("/api/snapshots/latest")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
