"""Protocols and projection types for gateway dependency injection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from dirt_shared.config import CloudGatewayConfig


@dataclass(frozen=True)
class AssetProjection:
    sign_request: dict[str, Any]
    complete_request: dict[str, Any]
    file_path: Path


class CloudGatewayClient(Protocol):
    async def send_heartbeat(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]: ...

    async def put_catalog(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]: ...

    async def put_latest_metrics(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]: ...

    async def post_rollups(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]: ...

    async def sign_upload(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]: ...

    async def upload_asset(
        self,
        *,
        file_path: Path,
        upload_url: str,
        headers: dict[str, str],
        content_type: str,
    ) -> None: ...

    async def complete_asset(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]: ...

    async def report_asset_failure(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]: ...

    async def prune_expired_assets(
        self, payload: dict[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]: ...

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
    async def collect_catalog(self, site_id: str) -> dict[str, Any]: ...

    async def collect_latest_metrics(self, site_id: str) -> dict[str, Any]: ...

    async def collect_rollups(
        self, site_id: str, *, bucket_names: set[str] | None = None
    ) -> dict[str, Any]: ...

    async def latest_snapshot_asset(self, site_id: str) -> AssetProjection | None: ...


class Sleeper(Protocol):
    async def sleep(self, delay_s: float) -> None: ...


class BackoffPolicy(Protocol):
    def next_delay_s(self, attempt_count: int) -> float: ...


def build_heartbeat_payload(
    config: CloudGatewayConfig,
    *,
    backlog_depth: int,
) -> dict[str, Any]:
    return {
        "site_id": config.site_id,
        "gateway_id": config.gateway_id,
        "backlog_depth": backlog_depth,
    }
