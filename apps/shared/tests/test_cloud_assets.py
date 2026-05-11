from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from dirt_shared.cloud_assets import AssetUploader, AssetUploadRequest
from dirt_shared.cloud_contract import (
    AssetCompleteRequest,
    AssetCompleteResponse,
    AssetFailureRequest,
    AssetFailureResponse,
    AssetSignUploadRequest,
    SignUploadResponse,
)

FIXED_NOW = datetime(2026, 5, 11, 12, 0, tzinfo=UTC)


class RecordingAssetClient:
    def __init__(self) -> None:
        self.upload_fail = False
        self.failure_report_fail = False
        self.calls: list[tuple[str, str]] = []
        self.uploads: list[dict[str, Any]] = []
        self.sign_requests: list[AssetSignUploadRequest] = []
        self.complete_requests: list[AssetCompleteRequest] = []
        self.failure_requests: list[AssetFailureRequest] = []
        self.call_counts: defaultdict[str, int] = defaultdict(int)

    async def sign_upload(
        self, payload: AssetSignUploadRequest, *, idempotency_key: str
    ) -> SignUploadResponse:
        self._record("sign", idempotency_key)
        self.sign_requests.append(payload)
        return SignUploadResponse(
            asset_id=payload.asset_id,
            object_key=payload.object_key,
            upload_url="https://assets.test/upload",
            method="PUT",
            headers={"Content-Type": payload.content_type},
            expires_at=FIXED_NOW + timedelta(minutes=10),
            byte_size=payload.byte_size,
        )

    async def upload_asset(
        self,
        *,
        file_path: Path,
        upload_url: str,
        headers: dict[str, str],
        content_type: str,
    ) -> None:
        self._record("upload", "")
        if self.upload_fail:
            raise RuntimeError("asset byte upload failed")
        self.uploads.append(
            {
                "file_path": file_path,
                "upload_url": upload_url,
                "headers": headers,
                "content_type": content_type,
            }
        )

    async def complete_asset(
        self, payload: AssetCompleteRequest, *, idempotency_key: str
    ) -> AssetCompleteResponse:
        self._record("complete", idempotency_key)
        self.complete_requests.append(payload)
        return AssetCompleteResponse(
            asset_id=payload.asset_id or payload.object_key,
            object_key=payload.object_key,
            uploaded_at=FIXED_NOW,
        )

    async def report_asset_failure(
        self, payload: AssetFailureRequest, *, idempotency_key: str
    ) -> AssetFailureResponse:
        self._record("failure", idempotency_key)
        if self.failure_report_fail:
            raise RuntimeError("failure report failed")
        self.failure_requests.append(payload)
        return AssetFailureResponse(ok=True, received_at=FIXED_NOW)

    def _record(self, call: str, idempotency_key: str) -> None:
        self.calls.append((call, idempotency_key))
        self.call_counts[call] += 1


def _payload(asset_file: Path) -> AssetUploadRequest:
    sign_request = AssetSignUploadRequest(
        site_id="homebox",
        tent_id="breeding",
        content_type="image/jpeg",
        byte_size=10,
        object_key="homebox/breeding/snapshots/snapshot.jpg",
        asset_id="asset-1",
        sha256="asset-1",
        kind="snapshot",
    )
    return AssetUploadRequest(
        sign_request=sign_request,
        complete_request=AssetCompleteRequest(
            **sign_request.model_dump(),
            captured_at=FIXED_NOW,
            device_id="obsbot-breeding",
        ),
        file_path=asset_file,
    )


async def test_asset_uploader_signs_uploads_and_completes_with_stable_keys(
    tmp_path: Path,
) -> None:
    asset_file = tmp_path / "snapshot.jpg"
    asset_file.write_bytes(b"jpeg-bytes")
    payload = _payload(asset_file)
    client = RecordingAssetClient()

    await AssetUploader(client).upload(payload, idempotency_key="asset-key")

    assert client.calls == [
        ("sign", "asset-key:sign"),
        ("upload", ""),
        ("complete", "asset-key:complete"),
    ]
    assert client.sign_requests == [payload.sign_request]
    assert client.complete_requests == [payload.complete_request]
    assert client.uploads == [
        {
            "file_path": asset_file,
            "upload_url": "https://assets.test/upload",
            "headers": {"Content-Type": "image/jpeg"},
            "content_type": "image/jpeg",
        }
    ]


async def test_asset_uploader_reports_upload_failure_then_reraises(
    tmp_path: Path,
) -> None:
    asset_file = tmp_path / "snapshot.jpg"
    asset_file.write_bytes(b"jpeg-bytes")
    payload = _payload(asset_file)
    client = RecordingAssetClient()
    client.upload_fail = True

    with pytest.raises(RuntimeError, match="asset byte upload failed"):
        await AssetUploader(client).upload(payload, idempotency_key="asset-key")

    assert client.call_counts["complete"] == 0
    assert client.calls == [
        ("sign", "asset-key:sign"),
        ("upload", ""),
        ("failure", "asset-key:failure"),
    ]
    assert client.failure_requests == [
        AssetFailureRequest(
            site_id="homebox",
            tent_id="breeding",
            asset_id="asset-1",
            object_key="homebox/breeding/snapshots/snapshot.jpg",
            stage="upload_or_complete",
            error="asset byte upload failed",
        )
    ]


async def test_asset_uploader_swallow_failure_report_error_with_hook(
    tmp_path: Path,
) -> None:
    asset_file = tmp_path / "snapshot.jpg"
    asset_file.write_bytes(b"jpeg-bytes")
    payload = _payload(asset_file)
    client = RecordingAssetClient()
    client.upload_fail = True
    client.failure_report_fail = True
    hook_calls: list[tuple[AssetUploadRequest, str, str]] = []

    def hook(
        failed_payload: AssetUploadRequest,
        idempotency_key: str,
        exc: Exception,
    ) -> None:
        hook_calls.append((failed_payload, idempotency_key, str(exc)))

    with pytest.raises(RuntimeError, match="asset byte upload failed"):
        await AssetUploader(client, on_failure_report_error=hook).upload(
            payload,
            idempotency_key="asset-key",
        )

    assert hook_calls == [(payload, "asset-key", "failure report failed")]
