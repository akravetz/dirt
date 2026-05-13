"""HTTP client for the hosted control-plane gateway API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from dirt_shared.cloud_assets import (
    CloudAssetDeliveryError as CloudDeliveryError,
)
from dirt_shared.cloud_assets import (
    HttpCloudAssetClient,
)
from dirt_shared.cloud_contract import (
    AssetCompleteRequest,
    AssetCompleteResponse,
    AssetFailureRequest,
    AssetFailureResponse,
    AssetRetentionRequest,
    AssetSignUploadRequest,
    CatalogRequest,
    CatalogResponse,
    CommandClaimRequest,
    CommandClaimResponse,
    CommandResultRequest,
    CommandResultResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    LatestMetricsRequest,
    PruneAssetsResponse,
    RollupsRequest,
    SignUploadResponse,
    UpsertCountResponse,
)


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
        self._assets = HttpCloudAssetClient(
            base_url=base_url,
            gateway_token=gateway_token,
            http_client=self._client,
        )
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def send_heartbeat(
        self, payload: HeartbeatRequest, *, idempotency_key: str
    ) -> HeartbeatResponse:
        response = await self._request(
            "POST", "/api/gateway/v1/heartbeat", payload, idempotency_key
        )
        return HeartbeatResponse.model_validate(response)

    async def put_catalog(
        self, payload: CatalogRequest, *, idempotency_key: str
    ) -> CatalogResponse:
        response = await self._request(
            "PUT", "/api/gateway/v1/catalog", payload, idempotency_key
        )
        return CatalogResponse.model_validate(response)

    async def put_latest_metrics(
        self, payload: LatestMetricsRequest, *, idempotency_key: str
    ) -> UpsertCountResponse:
        response = await self._request(
            "PUT", "/api/gateway/v1/metrics/latest", payload, idempotency_key
        )
        return UpsertCountResponse.model_validate(response)

    async def post_rollups(
        self, payload: RollupsRequest, *, idempotency_key: str
    ) -> UpsertCountResponse:
        response = await self._request(
            "POST", "/api/gateway/v1/metrics/rollups", payload, idempotency_key
        )
        return UpsertCountResponse.model_validate(response)

    async def sign_upload(
        self, payload: AssetSignUploadRequest, *, idempotency_key: str
    ) -> SignUploadResponse:
        return await self._assets.sign_upload(payload, idempotency_key=idempotency_key)

    async def upload_asset(
        self,
        *,
        file_path: Path,
        upload_url: str,
        headers: dict[str, str],
        content_type: str,
    ) -> None:
        await self._assets.upload_asset(
            file_path=file_path,
            upload_url=upload_url,
            headers=headers,
            content_type=content_type,
        )

    async def complete_asset(
        self, payload: AssetCompleteRequest, *, idempotency_key: str
    ) -> AssetCompleteResponse:
        return await self._assets.complete_asset(
            payload,
            idempotency_key=idempotency_key,
        )

    async def report_asset_failure(
        self, payload: AssetFailureRequest, *, idempotency_key: str
    ) -> AssetFailureResponse:
        return await self._assets.report_asset_failure(
            payload,
            idempotency_key=idempotency_key,
        )

    async def prune_expired_assets(
        self, payload: AssetRetentionRequest, *, idempotency_key: str
    ) -> PruneAssetsResponse:
        response = await self._request(
            "POST",
            "/api/gateway/v1/assets/prune-expired",
            payload,
            idempotency_key,
        )
        return PruneAssetsResponse.model_validate(response)

    async def claim_commands(
        self, *, site_id: str, limit: int, idempotency_key: str
    ) -> CommandClaimResponse:
        response = await self._request(
            "POST",
            "/api/gateway/v1/commands/claim",
            CommandClaimRequest(site_id=site_id, limit=limit),
            idempotency_key,
        )
        return CommandClaimResponse.model_validate(response)

    async def report_command_result(
        self,
        *,
        command_id: str,
        payload: CommandResultRequest,
        idempotency_key: str,
    ) -> CommandResultResponse:
        response = await self._request(
            "POST",
            f"/api/gateway/v1/commands/{command_id}/result",
            payload,
            idempotency_key,
        )
        return CommandResultResponse.model_validate(response)

    async def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | BaseModel,
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
                json=_json_payload(payload),
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise CloudDeliveryError(str(exc)) from exc
        if not isinstance(data, dict):
            raise CloudDeliveryError("cloud API returned a non-object response")
        return data


def _json_payload(payload: dict[str, Any] | BaseModel) -> dict[str, Any]:
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json")
    return payload
