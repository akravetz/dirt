"""Wiki endpoints — filesystem-backed tree / file / search.

Thin FastAPI wrappers around ``dirt_shared.services.wiki``. The service
walks ``<repo>/wiki/`` on disk; all request paths are normalized and
rejected if they escape the wiki root.
"""

from __future__ import annotations

from dirt_contracts.webapp_v1.models import (
    MatchType,
    PlantStickerColor,
    WikiBacklink,
    WikiFile,
    WikiSearchResponse,
    WikiSearchResult,
    WikiTreeFile,
    WikiTreeFolder,
    WikiTreeNode,
    WikiTreeResponse,
)
from fastapi import APIRouter, HTTPException, Query

from dirt_shared.services import wiki as wiki_service

router = APIRouter(tags=["wiki"])


def _sticker(color: str | None) -> PlantStickerColor | None:
    if not color:
        return None
    try:
        return PlantStickerColor(color)
    except ValueError:
        return None


def _file_node(ref: wiki_service.WikiFileRef) -> WikiTreeNode:
    return WikiTreeNode(
        root=WikiTreeFile(
            type="file",
            name=ref.name,
            path=ref.path,
            title=ref.title,
            sticker_color=_sticker(ref.sticker_color),
        )
    )


def _folder_node(folder: wiki_service.WikiFolder) -> WikiTreeNode:
    return WikiTreeNode(
        root=WikiTreeFolder(
            type="folder",
            name=folder.name,
            children=[_file_node(f) for f in folder.files],
        )
    )


@router.get("/api/wiki/tree", response_model=WikiTreeResponse)
async def wiki_tree() -> WikiTreeResponse:
    """Sidebar file tree — folders + loose root files in ``wiki/``."""
    tree = wiki_service.get_tree()
    nodes: list[WikiTreeNode] = [_file_node(f) for f in tree.root_files]
    nodes.extend(_folder_node(folder) for folder in tree.folders)
    return WikiTreeResponse(tree=nodes)


@router.get("/api/wiki/file", response_model=WikiFile)
async def wiki_file(path: str = Query(..., min_length=1)) -> WikiFile:
    """Return frontmatter + raw markdown body + backlinks for one file.

    ``path`` accepts both ``foo/bar.md`` and ``wiki/foo/bar.md``. Any
    path that escapes ``wiki/`` (``..`` traversal) → 400; a well-formed
    path pointing at a nonexistent file → 404.
    """
    try:
        payload = wiki_service.get_file(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="invalid wiki path") from exc
    if payload is None:
        raise HTTPException(status_code=404, detail="wiki file not found")
    return WikiFile(
        path=payload.path,
        title=payload.title,
        subtitle=payload.subtitle,
        frontmatter=dict(payload.frontmatter),
        body_markdown=payload.body_markdown,
        backlinks=[WikiBacklink(path=b.path, title=b.title) for b in payload.backlinks],
    )


@router.get("/api/wiki/search", response_model=WikiSearchResponse)
async def wiki_search(q: str = Query(..., min_length=1)) -> WikiSearchResponse:
    """Substring scan over filenames + titles + markdown bodies.

    Empty/whitespace-only ``q`` → 400. FastAPI's ``min_length=1``
    validator handles the truly-empty case with 422; the explicit 400
    here is for whitespace-only queries, which would otherwise match
    everything. The SPA short-circuits the empty-state "recent files"
    list locally via ``shared/storage.ts`` (API.md §9).
    """
    if not q.strip():
        raise HTTPException(status_code=400, detail="q must not be empty")
    results = wiki_service.search(q)
    return WikiSearchResponse(
        q=q,
        results=[
            WikiSearchResult(
                path=r.path,
                title=r.title,
                match_type=MatchType(r.match_type),
                snippet=r.snippet,
            )
            for r in results
        ],
    )
