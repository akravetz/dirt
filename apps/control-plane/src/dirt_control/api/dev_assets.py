from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from starlette.responses import FileResponse

from dirt_control.deps import get_asset_store, get_clock
from dirt_control.storage import LocalAssetStore

router = APIRouter(prefix="/api/dev-assets")


@router.get("/{object_key:path}")
async def read_dev_asset(
    object_key: str,
    expires: int | None = None,
    signature: str | None = None,
    asset_store=Depends(get_asset_store),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> FileResponse:
    store = _require_local_asset_store(asset_store)
    if expires is None or signature is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid asset signature")
    if not store.verify_url_signature(
        object_key=object_key,
        expires=expires,
        signature=signature,
        now=clock(),
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid asset signature")

    path = store.local_path(object_key)
    if path is None or not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "asset not found")
    return FileResponse(path)


@router.put("/{object_key:path}", status_code=status.HTTP_204_NO_CONTENT)
async def write_dev_asset(  # noqa: PLR0913
    object_key: str,
    request: Request,
    expires: int | None = None,
    signature: str | None = None,
    method: str | None = None,
    content_type: str | None = None,
    asset_store=Depends(get_asset_store),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> Response:
    store = _require_local_asset_store(asset_store)
    if expires is None or signature is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid asset signature")
    if method != "PUT" or content_type is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid asset signature")
    if request.headers.get("content-type") != content_type:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid asset signature")
    if not store.verify_put_signature(
        object_key=object_key,
        content_type=content_type,
        expires=expires,
        signature=signature,
        now=clock(),
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid asset signature")

    path = store.local_path(object_key)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "asset not found")
    body = await request.body()
    await anyio.to_thread.run_sync(_write_bytes, path, body)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _require_local_asset_store(asset_store) -> LocalAssetStore:
    if not isinstance(asset_store, LocalAssetStore):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "asset not found")
    return asset_store


def _write_bytes(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
