"""Unit tests for GET /api/wiki/file.

Thin wrapper over ``dirt_shared.services.wiki.get_file``; tests drive
the full ASGI stack against a tmp_path-seeded fake wiki directory.
Path normalization accepts both ``foo/bar.md`` and ``wiki/foo/bar.md``;
``..`` traversal → 400, nonexistent-but-safe path → 404.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from dirt_contracts.webapp_v1.models import WikiFile
from httpx import ASGITransport, AsyncClient

from dirt_web.app import create_app


def _seed_wiki(root: Path) -> None:
    """Two interlinked pages so backlinks are exercised."""
    root.mkdir(parents=True, exist_ok=True)
    plants = root / "plants"
    plants.mkdir()
    (plants / "plant-a.md").write_text(
        "---\n"
        "title: Plant A — Purple Keeper Candidate\n"
        "type: plant\n"
        "related: [wiki/concepts/topping.md]\n"
        "---\n\n"
        "# Plant A\n\n"
        "*Formerly labeled Plant 1.*\n\n"
        "## Current State\n\n"
        "Body goes here.\n",
        encoding="utf-8",
    )

    concepts = root / "concepts"
    concepts.mkdir()
    (concepts / "topping.md").write_text(
        "---\ntitle: Topping\n---\n\n"
        "# Topping\n\n"
        "See also [Plant A](../plants/plant-a.md) for a worked example.\n",
        encoding="utf-8",
    )


@pytest.fixture
def fake_wiki(tmp_path, monkeypatch):
    wiki_dir = tmp_path / "wiki"
    _seed_wiki(wiki_dir)
    monkeypatch.setenv("DIRT_WIKI_DIR", str(wiki_dir))
    return wiki_dir


@pytest.fixture
async def client(app_engine, fake_wiki):
    app = create_app(engine=app_engine, run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        login = await ac.post(
            "/api/auth/login",
            json={"username": "admin", "password": "changeme"},
        )
        ac.cookies = login.cookies
        yield ac


async def test_wiki_file_requires_auth(app_engine, fake_wiki):
    app = create_app(engine=app_engine, run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.get("/api/wiki/file", params={"path": "plants/plant-a.md"})
        assert response.status_code == 401


async def test_wiki_file_returns_frontmatter_body_and_subtitle(client: AsyncClient):
    response = await client.get("/api/wiki/file", params={"path": "plants/plant-a.md"})
    assert response.status_code == 200
    model = WikiFile.model_validate(response.json())

    assert model.path == "wiki/plants/plant-a.md"
    assert model.title == "Plant A — Purple Keeper Candidate"
    assert model.subtitle == "Formerly labeled Plant 1."
    assert model.frontmatter["type"] == "plant"
    # Raw markdown body with frontmatter stripped.
    assert model.body_markdown.startswith("\n# Plant A")
    assert "## Current State" in model.body_markdown
    # Frontmatter-dashes are gone.
    assert "---" not in model.body_markdown.split("##")[0]


async def test_wiki_file_accepts_prefixed_path(client: AsyncClient):
    """``wiki/foo/bar.md`` is equivalent to ``foo/bar.md``."""
    response = await client.get(
        "/api/wiki/file", params={"path": "wiki/plants/plant-a.md"}
    )
    assert response.status_code == 200
    assert response.json()["path"] == "wiki/plants/plant-a.md"


async def test_wiki_file_backlinks(client: AsyncClient):
    """Files that link or ``related:``-reference the target appear as backlinks."""
    response = await client.get("/api/wiki/file", params={"path": "plants/plant-a.md"})
    model = WikiFile.model_validate(response.json())
    backlink_paths = {b.path for b in model.backlinks}
    # topping.md has a relative markdown link to plant-a.md.
    assert "wiki/concepts/topping.md" in backlink_paths


async def test_wiki_file_traversal_returns_400(client: AsyncClient):
    """``..`` escape must be rejected before the filesystem is touched."""
    response = await client.get("/api/wiki/file", params={"path": "../etc/passwd"})
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")


async def test_wiki_file_missing_returns_404(client: AsyncClient):
    """Well-formed path pointing at a nonexistent file → 404."""
    response = await client.get("/api/wiki/file", params={"path": "plants/plant-z.md"})
    assert response.status_code == 404


async def test_wiki_file_empty_path_rejected(client: AsyncClient):
    """Empty ``path`` trips FastAPI's ``min_length=1`` validator (422)."""
    response = await client.get("/api/wiki/file", params={"path": ""})
    assert response.status_code == 422
