"""Unit tests for GET /api/wiki/tree.

Thin wrapper over ``dirt_shared.services.wiki.get_tree``; tests drive
the full ASGI stack against a tmp_path-seeded fake wiki directory so we
don't depend on the live ``wiki/`` contents.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from dirt_contracts.webapp_v1.models import (
    PlantStickerColor,
    WikiTreeFile,
    WikiTreeFolder,
    WikiTreeResponse,
)
from httpx import ASGITransport, AsyncClient

from dirt_web.app import create_app


def _seed_wiki(root: Path) -> None:
    """Minimal realistic wiki layout: 2 root files + plants/ + concepts/."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "overview.md").write_text(
        "---\ntitle: Grow Overview\n---\n\n# Grow Overview\n\nbody\n",
        encoding="utf-8",
    )
    (root / "index.md").write_text(
        "# Wiki Index\n\nentry\n",
        encoding="utf-8",
    )
    # Agent-facing AGENTS.md must be excluded from the tree.
    (root / "AGENTS.md").write_text("# agent-only\n", encoding="utf-8")

    plants = root / "plants"
    plants.mkdir()
    (plants / "plant-a.md").write_text(
        "---\ntitle: Plant A — Purple Keeper Candidate\ntype: plant\n---\n\n"
        "# Plant A\n\nbody\n",
        encoding="utf-8",
    )
    (plants / "plant-b.md").write_text(
        "---\ntitle: Plant B\ntype: plant\n---\n\n# Plant B\n\nbody\n",
        encoding="utf-8",
    )

    concepts = root / "concepts"
    concepts.mkdir()
    (concepts / "topping.md").write_text(
        "---\ntitle: Topping\n---\n\n# Topping\n\nbody\n",
        encoding="utf-8",
    )


@pytest.fixture
def fake_wiki(tmp_path, monkeypatch):
    """Redirect the wiki service at a tmp_path-seeded fake wiki via env var.

    The ``_wiki_dir()`` helper in ``dirt_shared.services.wiki`` reads
    ``DIRT_WIKI_DIR`` on every call, so ``monkeypatch.setenv`` is enough
    — no ``setattr`` on dirt_* production modules (which the
    no-patching-production-code invariant would reject).
    """
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


async def test_wiki_tree_requires_auth(app_engine, fake_wiki):
    app = create_app(engine=app_engine, run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.get("/api/wiki/tree")
        assert response.status_code == 401
        assert response.headers["content-type"].startswith("application/json")


async def test_wiki_tree_returns_contract_shape(client: AsyncClient):
    response = await client.get("/api/wiki/tree")
    assert response.status_code == 200
    model = WikiTreeResponse.model_validate(response.json())

    # Root files first, then folders (alphabetical).
    root_names = [n.root.name for n in model.tree if isinstance(n.root, WikiTreeFile)]
    assert root_names == ["index.md", "overview.md"]
    # AGENTS.md excluded.
    assert "AGENTS.md" not in root_names

    folder_names = [
        n.root.name for n in model.tree if isinstance(n.root, WikiTreeFolder)
    ]
    assert folder_names == ["concepts", "plants"]


async def test_wiki_tree_plant_sticker_colors(client: AsyncClient):
    response = await client.get("/api/wiki/tree")
    model = WikiTreeResponse.model_validate(response.json())

    plants_node = next(
        n.root
        for n in model.tree
        if isinstance(n.root, WikiTreeFolder) and n.root.name == "plants"
    )
    by_name = {c.root.name: c.root for c in plants_node.children}
    assert isinstance(by_name["plant-a.md"], WikiTreeFile)
    assert by_name["plant-a.md"].sticker_color == PlantStickerColor.yellow
    assert by_name["plant-b.md"].sticker_color == PlantStickerColor.orange
    assert by_name["plant-a.md"].title == "Plant A — Purple Keeper Candidate"


async def test_wiki_tree_non_plant_folder_has_no_sticker(client: AsyncClient):
    response = await client.get("/api/wiki/tree")
    model = WikiTreeResponse.model_validate(response.json())

    concepts = next(
        n.root
        for n in model.tree
        if isinstance(n.root, WikiTreeFolder) and n.root.name == "concepts"
    )
    topping = concepts.children[0].root
    assert isinstance(topping, WikiTreeFile)
    assert topping.sticker_color is None
    assert topping.title == "Topping"
