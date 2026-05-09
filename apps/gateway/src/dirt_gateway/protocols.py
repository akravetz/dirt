"""Protocols and projection types for gateway dependency injection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from dirt_shared.cloud_contract import (
    AssetCompleteRequest,
    AssetCompleteResponse,
    AssetFailureRequest,
    AssetFailureResponse,
    AssetRetentionRequest,
    AssetSignUploadRequest,
    CatalogRequest,
    CloudContractModel,
    HeartbeatRequest,
    LatestMetricsRequest,
    PruneAssetsResponse,
    RollupsRequest,
    SignUploadResponse,
)
from dirt_shared.config import CloudGatewayConfig


@dataclass(frozen=True)
class AssetUploadProjection:
    sign_request: AssetSignUploadRequest
    complete_request: AssetCompleteRequest
    file_path: Path

    def to_outbox_payload(self) -> AssetUploadOutboxPayload:
        return AssetUploadOutboxPayload(
            sign_request=self.sign_request,
            complete_request=self.complete_request,
            file_path=self.file_path,
        )


class AssetUploadOutboxPayload(CloudContractModel):
    sign_request: AssetSignUploadRequest
    complete_request: AssetCompleteRequest
    file_path: Path


class CloudGatewayClient(Protocol):
    async def send_heartbeat(
        self, payload: HeartbeatRequest, *, idempotency_key: str
    ) -> dict[str, Any]: ...

    async def put_catalog(
        self, payload: CatalogRequest, *, idempotency_key: str
    ) -> dict[str, Any]: ...

    async def put_latest_metrics(
        self, payload: LatestMetricsRequest, *, idempotency_key: str
    ) -> dict[str, Any]: ...

    async def post_rollups(
        self, payload: RollupsRequest, *, idempotency_key: str
    ) -> dict[str, Any]: ...

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

    async def prune_expired_assets(
        self, payload: AssetRetentionRequest, *, idempotency_key: str
    ) -> PruneAssetsResponse: ...

    async def claim_commands(
        self, *, site_id: str, limit: int, idempotency_key: str
    ) -> dict[str, Any]: ...

    async def report_command_result(
        self,
        *,
        command_id: str,
        payload: dict[str, Any],
        idempotency_key: str,
    ) -> dict[str, Any]: ...


class LocalGatewayServices(Protocol):
    async def collect_catalog(self, site_id: str) -> CatalogRequest: ...

    async def collect_latest_metrics(self, site_id: str) -> LatestMetricsRequest: ...

    async def collect_rollups(
        self, site_id: str, *, bucket_names: set[str] | None = None
    ) -> RollupsRequest: ...

    async def latest_snapshot_asset(
        self, site_id: str
    ) -> AssetUploadProjection | None: ...


class Sleeper(Protocol):
    async def sleep(self, delay_s: float) -> None: ...


class BackoffPolicy(Protocol):
    def next_delay_s(self, attempt_count: int) -> float: ...


def build_heartbeat_payload(
    config: CloudGatewayConfig,
    *,
    backlog_depth: int,
) -> HeartbeatRequest:
    return HeartbeatRequest(
        site_id=config.site_id,
        gateway_id=config.gateway_id,
        backlog_depth=backlog_depth,
    )
