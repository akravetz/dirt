"""Reusable cloud asset upload workflow."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from dirt_shared.cloud_contract import (
    AssetCompleteRequest,
    AssetCompleteResponse,
    AssetFailureRequest,
    AssetFailureResponse,
    AssetSignUploadRequest,
    CloudContractModel,
    SignUploadResponse,
)


class CloudAssetDeliveryError(RuntimeError):
    """Cloud asset API write failed and should be retried by the caller."""


class AssetUploadRequest(CloudContractModel):
    sign_request: AssetSignUploadRequest
    complete_request: AssetCompleteRequest
    file_path: Path


@dataclass(frozen=True)
class AssetUploadProjection:
    sign_request: AssetSignUploadRequest
    complete_request: AssetCompleteRequest
    file_path: Path

    def to_outbox_payload(self) -> AssetUploadRequest:
        return AssetUploadRequest(
            sign_request=self.sign_request,
            complete_request=self.complete_request,
            file_path=self.file_path,
        )


class CloudAssetClient(Protocol):
    async def sign_upload(
        self, payload: AssetSignUploadRequest, *, idempotency_key: str
    ) -> SignUploadResponse: ...

    async def upload_asset(
        self,
        *,
        file_path: Path,
        upload_url: str,
        headers: dict[str, str],
        content_type: str,
    ) -> None: ...

    async def complete_asset(
        self, payload: AssetCompleteRequest, *, idempotency_key: str
    ) -> AssetCompleteResponse: ...

    async def report_asset_failure(
        self, payload: AssetFailureRequest, *, idempotency_key: str
    ) -> AssetFailureResponse: ...


class HttpCloudAssetClient:
    def __init__(
        self,
        *,
        base_url: str,
        gateway_token: str,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._gateway_token = gateway_token
        self._client = http_client or httpx.AsyncClient(timeout=20)
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def sign_upload(
        self, payload: AssetSignUploadRequest, *, idempotency_key: str
    ) -> SignUploadResponse:
        response = await self._request(
            "POST", "/api/gateway/v1/assets/sign-upload", payload, idempotency_key
        )
        return SignUploadResponse.model_validate(response)

    async def upload_asset(
        self,
        *,
        file_path: Path,
        upload_url: str,
        headers: dict[str, str],
        content_type: str,
    ) -> None:
        del content_type
        try:
            content = await asyncio.to_thread(file_path.read_bytes)
            response = await self._client.put(
                upload_url,
                content=content,
                headers=headers,
            )
            response.raise_for_status()
        except (OSError, httpx.HTTPError) as exc:
            raise CloudAssetDeliveryError(str(exc)) from exc

    async def complete_asset(
        self, payload: AssetCompleteRequest, *, idempotency_key: str
    ) -> AssetCompleteResponse:
        response = await self._request(
            "POST", "/api/gateway/v1/assets/complete", payload, idempotency_key
        )
        return AssetCompleteResponse.model_validate(response)

    async def report_asset_failure(
        self, payload: AssetFailureRequest, *, idempotency_key: str
    ) -> AssetFailureResponse:
        response = await self._request(
            "POST",
            "/api/gateway/v1/assets/upload-failure",
            payload,
            idempotency_key,
        )
        return AssetFailureResponse.model_validate(response)

    async def _request(
        self,
        method: str,
        path: str,
        payload: CloudContractModel,
        idempotency_key: str,
    ) -> dict[str, object]:
        headers = {
            "authorization": f"Bearer {self._gateway_token}",
            "idempotency-key": idempotency_key,
        }
        try:
            response = await self._client.request(
                method,
                f"{self._base_url}{path}",
                json=payload.model_dump(mode="json"),
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CloudAssetDeliveryError(str(exc)) from exc
        if not isinstance(data, dict):
            raise CloudAssetDeliveryError("cloud API returned a non-object response")
        return data


AssetFailureReportErrorHandler = Callable[[AssetUploadRequest, str, Exception], None]


class AssetUploader:
    def __init__(
        self,
        client: CloudAssetClient,
        *,
        on_failure_report_error: AssetFailureReportErrorHandler | None = None,
    ) -> None:
        self._client = client
        self._on_failure_report_error = on_failure_report_error

    async def upload(
        self,
        payload: AssetUploadRequest,
        *,
        idempotency_key: str,
    ) -> None:
        signed = await self._client.sign_upload(
            payload.sign_request,
            idempotency_key=f"{idempotency_key}:sign",
        )
        try:
            await self._client.upload_asset(
                file_path=payload.file_path,
                upload_url=signed.upload_url,
                headers=signed.headers,
                content_type=payload.sign_request.content_type,
            )
            await self._client.complete_asset(
                payload.complete_request,
                idempotency_key=f"{idempotency_key}:complete",
            )
        except Exception as exc:
            await self._report_failure(payload, exc, idempotency_key=idempotency_key)
            raise

    async def _report_failure(
        self,
        payload: AssetUploadRequest,
        exc: Exception,
        *,
        idempotency_key: str,
    ) -> None:
        try:
            await self._client.report_asset_failure(
                AssetFailureRequest(
                    site_id=payload.sign_request.site_id,
                    tent_id=payload.sign_request.tent_id,
                    asset_id=payload.sign_request.asset_id,
                    object_key=payload.sign_request.object_key,
                    stage="upload_or_complete",
                    error=str(exc)[:500],
                ),
                idempotency_key=f"{idempotency_key}:failure",
            )
        except Exception as report_exc:
            if self._on_failure_report_error is not None:
                self._on_failure_report_error(payload, idempotency_key, report_exc)
