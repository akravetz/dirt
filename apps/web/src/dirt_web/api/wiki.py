"""Wiki endpoints — filesystem-backed tree / file / search.

Thin FastAPI wrappers around ``dirt_shared.services.wiki``. The service
walks ``<repo>/wiki/`` on disk; all request paths are normalized and
rejected if they escape the wiki root.
"""

from __future__ import annotations

from dirt_contracts.webapp_v1.models import (
    PlantStickerColor,
    WikiTreeFile,
    WikiTreeFolder,
    WikiTreeNode,
    WikiTreeResponse,
)
from fastapi import APIRouter

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
