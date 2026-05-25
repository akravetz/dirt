from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Protocol

import boto3

from dirt_control.security import UrlSigner, expires_from
from dirt_control.settings import CloudSettings


class AssetStore(Protocol):
    def presign_put(
        self,
        *,
        object_key: str,
        content_type: str,
        expires_in_s: int,
    ) -> str: ...

    def presign_get(self, *, object_key: str, expires_in_s: int) -> str: ...

    def delete_objects(self, object_keys: Sequence[str]) -> int: ...


class S3ObjectStore:
    def __init__(self, *, settings: CloudSettings) -> None:
        self._bucket_name = settings.bucket_name
        self._client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
        )

    def presign_put(
        self,
        *,
        object_key: str,
        content_type: str,
        expires_in_s: int,
    ) -> str:
        return self._client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self._bucket_name,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=expires_in_s,
            HttpMethod="PUT",
        )

    def presign_get(self, *, object_key: str, expires_in_s: int) -> str:
        return self._client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self._bucket_name, "Key": object_key},
            ExpiresIn=expires_in_s,
            HttpMethod="GET",
        )

    def delete_objects(self, object_keys: Sequence[str]) -> int:
        deleted = 0
        for start in range(0, len(object_keys), 1000):
            chunk = object_keys[start : start + 1000]
            if not chunk:
                continue
            response = self._client.delete_objects(
                Bucket=self._bucket_name,
                Delete={"Objects": [{"Key": key} for key in chunk], "Quiet": True},
            )
            deleted += len(response.get("Deleted", []))
        return deleted


class LocalAssetStore:
    def __init__(
        self,
        *,
        root: Path,
        base_url: str,
        signer: UrlSigner,
        clock: Callable[[], datetime],
    ) -> None:
        self._root = root
        self._base_url = base_url
        self._signer = signer
        self._clock = clock

    def presign_put(
        self,
        *,
        object_key: str,
        content_type: str,
        expires_in_s: int,
    ) -> str:
        return self._signer.build_signed_url(
            base_url=self._base_url,
            subject=object_key,
            signed_subject=_put_subject(
                object_key=object_key,
                content_type=content_type,
            ),
            expires_at=expires_from(self._clock(), expires_in_s),
            params={"method": "PUT", "content_type": content_type},
        )

    def presign_get(self, *, object_key: str, expires_in_s: int) -> str:
        return self._signer.build_signed_url(
            base_url=self._base_url,
            subject=object_key,
            expires_at=expires_from(self._clock(), expires_in_s),
        )

    def verify_url_signature(
        self,
        *,
        object_key: str,
        expires: int,
        signature: str,
        now: datetime,
    ) -> bool:
        return self._signer.verify(
            subject=object_key,
            expires=expires,
            signature=signature,
            now=now,
        )

    def verify_put_signature(
        self,
        *,
        object_key: str,
        content_type: str,
        expires: int,
        signature: str,
        now: datetime,
    ) -> bool:
        return self._signer.verify(
            subject=_put_subject(object_key=object_key, content_type=content_type),
            expires=expires,
            signature=signature,
            now=now,
        )

    def local_path(self, object_key: str) -> Path | None:
        return _resolve_object_path(root=self._root, object_key=object_key)

    def delete_objects(self, object_keys: Sequence[str]) -> int:
        deleted = 0
        for object_key in object_keys:
            path = self.local_path(object_key)
            if path is None or not path.is_file():
                continue
            path.unlink()
            deleted += 1
        return deleted


def create_asset_store(
    *,
    settings: CloudSettings,
    clock: Callable[[], datetime],
) -> AssetStore:
    signer = UrlSigner(settings.session_secret)
    if settings.asset_store == "local":
        return LocalAssetStore(
            root=settings.local_asset_root,
            base_url=settings.public_asset_base_url,
            signer=signer,
            clock=clock,
        )
    if settings.asset_store == "s3":
        if not _has_s3_settings(settings):
            raise ValueError("DIRT_CLOUD_ASSET_STORE=s3 requires S3 settings")
        return S3ObjectStore(settings=settings)
    raise ValueError(f"unsupported DIRT_CLOUD_ASSET_STORE: {settings.asset_store}")


def _has_s3_settings(settings: CloudSettings) -> bool:
    return bool(
        settings.s3_endpoint
        and settings.s3_region
        and settings.s3_access_key_id
        and settings.s3_secret_access_key
    )


def _put_subject(*, object_key: str, content_type: str) -> str:
    return f"PUT:{content_type}:{object_key}"


def _resolve_object_path(*, root: Path, object_key: str) -> Path | None:
    if not object_key or "\x00" in object_key:
        return None

    object_path = PurePosixPath(object_key)
    if object_path.is_absolute():
        return None
    if any(part in {"", ".", ".."} for part in object_path.parts):
        return None

    root_resolved = root.resolve(strict=False)
    candidate = root_resolved.joinpath(*object_path.parts).resolve(strict=False)
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        return None
    return candidate
