from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt.models.snapshot import Snapshot
from dirt.services.snapshots import get_latest_snapshot, get_snapshot_path


@pytest.fixture
async def db_engine(tmp_path):
    db_path = tmp_path / "test.db"
    eng = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest.fixture
async def full_app_client(db_engine):
    """Client against the full FastAPI app (for auth boundary tests)."""
    with (
        patch("dirt.services.capture.capture_loop"),
        patch("dirt.db.engine", db_engine),
    ):
        from dirt.app import app

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test", follow_redirects=False
        ) as ac:
            yield ac


# --- Auth boundary tests ---


async def test_mcp_requires_bearer_token(full_app_client: AsyncClient):
    response = await full_app_client.get("/mcp/")
    assert response.status_code == 401


async def test_mcp_rejects_invalid_token(full_app_client: AsyncClient):
    response = await full_app_client.get(
        "/mcp/", headers={"Authorization": "Bearer bad"}
    )
    assert response.status_code == 401


async def test_mcp_no_cookie_auth_redirect(full_app_client: AsyncClient):
    """MCP endpoint should not redirect to /login."""
    response = await full_app_client.get("/mcp/")
    assert response.headers.get("location") != "/login"


# --- Service layer tests ---


async def test_get_latest_snapshot_empty_db(db_engine):
    with patch("dirt.services.snapshots.engine", db_engine):
        result = await get_latest_snapshot()
    assert result is None


async def test_get_latest_snapshot_returns_most_recent(db_engine):
    async with AsyncSession(db_engine) as session:
        session.add(
            Snapshot(timestamp=datetime(2026, 1, 1, tzinfo=UTC), file_path="/old.jpg")
        )
        session.add(
            Snapshot(timestamp=datetime(2026, 3, 1, tzinfo=UTC), file_path="/new.jpg")
        )
        await session.commit()

    with patch("dirt.services.snapshots.engine", db_engine):
        result = await get_latest_snapshot()
    assert result is not None
    assert result.file_path == "/new.jpg"


async def test_get_snapshot_path_exists(tmp_path):
    img = tmp_path / "test.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0")
    snapshot = Snapshot(timestamp=datetime.now(UTC), file_path=str(img))
    assert get_snapshot_path(snapshot) == img


async def test_get_snapshot_path_missing():
    snapshot = Snapshot(timestamp=datetime.now(UTC), file_path="/nonexistent/photo.jpg")
    assert get_snapshot_path(snapshot) is None
