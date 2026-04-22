"""Unit tests for GET /api/wiki/search.

Thin wrapper over ``dirt_shared.services.wiki.search``. Empty/whitespace
``q`` → 400 (the SPA short-circuits the recent-files list locally). All
three match types (title > path > content) are exercised.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from dirt_contracts.webapp_v1.models import MatchType, WikiSearchResponse
from httpx import ASGITransport, AsyncClient

from dirt_web.app import create_app


def _seed_wiki(root: Path) -> None:
    """Three pages chosen so each match_type has a natural hit."""
    root.mkdir(parents=True, exist_ok=True)
    concepts = root / "concepts"
    concepts.mkdir()
    # Exact title match for "topping".
    (concepts / "topping.md").write_text(
        "---\ntitle: Topping\n---\n\n# Topping\n\nPrune apical meristem.\n",
        encoding="utf-8",
    )

    plants = root / "plants"
    plants.mkdir()
    # Body mentions "topping" — content match.
    (plants / "plant-a.md").write_text(
        "---\ntitle: Plant A\n---\n\n"
        "# Plant A\n\n"
        "Applied topping above node 4; 5th node was emerging when we cut.\n",
        encoding="utf-8",
    )
    # Filename contains "anthocyanin"; title doesn't — path match.
    (concepts / "anthocyanin.md").write_text(
        "---\ntitle: Purple Pigment Biology\n---\n\n"
        "# Purple Pigment Biology\n\nUnrelated body text.\n",
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


async def test_wiki_search_requires_auth(app_engine, fake_wiki):
    app = create_app(engine=app_engine, run_mcp=False)
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport, base_url="http://test", follow_redirects=False
    ) as ac:
        response = await ac.get("/api/wiki/search", params={"q": "topping"})
        assert response.status_code == 401


async def test_wiki_search_title_match_ranks_first(client: AsyncClient):
    """Title hits bubble above content hits (``topping`` appears in both)."""
    response = await client.get("/api/wiki/search", params={"q": "topping"})
    assert response.status_code == 200
    model = WikiSearchResponse.model_validate(response.json())

    assert model.q == "topping"
    assert len(model.results) >= 2
    # Title hit first, content hit after.
    assert model.results[0].path == "wiki/concepts/topping.md"
    assert model.results[0].match_type == MatchType.title
    assert model.results[0].snippet is None

    content_hit = next(r for r in model.results if r.path == "wiki/plants/plant-a.md")
    assert content_hit.match_type == MatchType.content
    assert content_hit.snippet is not None
    assert "topping" in content_hit.snippet.lower()


async def test_wiki_search_path_match(client: AsyncClient):
    """Filename hit when neither title nor body contains the needle."""
    response = await client.get("/api/wiki/search", params={"q": "anthocyanin"})
    model = WikiSearchResponse.model_validate(response.json())

    assert len(model.results) == 1
    hit = model.results[0]
    assert hit.path == "wiki/concepts/anthocyanin.md"
    assert hit.match_type == MatchType.path
    assert hit.snippet is None


async def test_wiki_search_empty_q_returns_400(client: AsyncClient):
    """Whitespace-only ``q`` → 400 (min_length=1 catches the truly-empty form)."""
    response = await client.get("/api/wiki/search", params={"q": "   "})
    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    assert response.json()["detail"]


async def test_wiki_search_missing_q_returns_422(client: AsyncClient):
    """FastAPI's own ``Query(..., min_length=1)`` validator rejects empty string."""
    response = await client.get("/api/wiki/search", params={"q": ""})
    assert response.status_code == 422


async def test_wiki_search_no_matches_returns_empty_list(client: AsyncClient):
    response = await client.get("/api/wiki/search", params={"q": "xyzzynoresult"})
    assert response.status_code == 200
    model = WikiSearchResponse.model_validate(response.json())
    assert model.q == "xyzzynoresult"
    assert model.results == []
