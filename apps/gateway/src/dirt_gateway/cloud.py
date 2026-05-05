"""HTTP client for the hosted control-plane gateway API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx


class CloudDeliveryError(RuntimeError):
    """Cloud API write failed and should be retried from the outbox."""


class HttpCloudGatewayClient:
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

    async def send_heartbeat(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST", "/api/gateway/v1/heartbeat", payload, idempotency_key
        )

    async def put_catalog(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        return await self._request(
            "PUT", "/api/gateway/v1/catalog", payload, idempotency_key
        )

    async def put_latest_metrics(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        return await self._request(
            "PUT", "/api/gateway/v1/metrics/latest", payload, idempotency_key
        )

    async def post_rollups(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST", "/api/gateway/v1/metrics/rollups", payload, idempotency_key
        )

    async def sign_upload(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST", "/api/gateway/v1/assets/sign-upload", payload, idempotency_key
        )

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
            with file_path.open("rb") as f:
                response = await self._client.put(
                    upload_url,
                    content=f,
                    headers=headers,
                )
            response.raise_for_status()
        except (OSError, httpx.HTTPError) as exc:
            raise CloudDeliveryError(str(exc)) from exc

    async def complete_asset(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        return await self._request(
            "POST", "/api/gateway/v1/assets/complete", payload, idempotency_key
        )

    async def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]:
        headers = {
            "authorization": f"Bearer {self._gateway_token}",
            "idempotency-key": idempotency_key,
        }
        try:
            response = await self._client.request(
                method,
                f"{self._base_url}{path}",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CloudDeliveryError(str(exc)) from exc
        if not isinstance(data, dict):
            raise CloudDeliveryError("cloud API returned a non-object response")
        return data
