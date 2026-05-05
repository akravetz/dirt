"""Read-only cloud sync orchestration for the local gateway."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from dirt_gateway.cloud import CloudDeliveryError
from dirt_gateway.outbox import OutboxRepository, stable_json_hash
from dirt_gateway.protocols import (
    BackoffPolicy,
    CloudGatewayClient,
    LocalGatewayServices,
    Sleeper,
    build_heartbeat_payload,
)
from dirt_shared.config import CloudGatewayConfig
from dirt_shared.models import CloudOutbox
from dirt_shared.observability import log_event


@dataclass(frozen=True)
class SyncResult:
    enqueued: int
    delivered: int
    failed: int
    backlog_depth: int
    dry_run: bool


class ExponentialBackoff:
    def __init__(self, *, base_s: float = 5.0, max_s: float = 300.0) -> None:
        self._base_s = base_s
        self._max_s = max_s

    def next_delay_s(self, attempt_count: int) -> float:
        return min(self._max_s, self._base_s * (2 ** max(0, attempt_count - 1)))


class AsyncioSleeper:
    async def sleep(self, delay_s: float) -> None:
        await asyncio.sleep(delay_s)


class GatewaySyncService:
    def __init__(  # noqa: PLR0913
        self,
        *,
        config: CloudGatewayConfig,
        outbox: OutboxRepository,
        local_services: LocalGatewayServices,
        cloud_client: CloudGatewayClient,
        clock=lambda: datetime.now(UTC),
        sleeper: Sleeper | None = None,
        backoff: BackoffPolicy | None = None,
    ) -> None:
        self._config = config
        self._outbox = outbox
        self._local = local_services
        self._cloud = cloud_client
        self._clock = clock
        self._sleeper = sleeper or AsyncioSleeper()
        self._backoff = backoff or ExponentialBackoff()

    async def run_once(self) -> SyncResult:
        now = self._clock()
        backlog_before = await self._outbox.pending_count()
        log_event(
            "cloud_gateway",
            "cycle_started",
            site_id=self._config.site_id,
            gateway_id=self._config.gateway_id,
            backlog_depth=backlog_before,
        )

        projections = await self._collect_projections(backlog_depth=backlog_before)
        if self._config.dry_run:
            log_event(
                "cloud_gateway",
                "dry_run",
                site_id=self._config.site_id,
                gateway_id=self._config.gateway_id,
                projection_counts={
                    key: _count_projection(value) for key, value in projections.items()
                },
            )
            return await self._finish(enqueued=0, delivered=0, failed=0, dry_run=True)

        enqueued = await self._enqueue_projections(projections, now=now)
        delivered, failed = await self._deliver_due()
        return await self._finish(
            enqueued=enqueued,
            delivered=delivered,
            failed=failed,
            dry_run=False,
        )

    async def run_forever(self) -> None:
        while True:
            await self.run_once()
            await self._sleeper.sleep(self._config.sync_interval_s)

    async def _collect_projections(
        self, *, backlog_depth: int
    ) -> dict[str, dict[str, Any]]:
        projections: dict[str, dict[str, Any]] = {
            "heartbeat": build_heartbeat_payload(
                self._config,
                backlog_depth=backlog_depth,
            ),
            "catalog": await self._local.collect_catalog(self._config.site_id),
            "latest_metrics": await self._local.collect_latest_metrics(
                self._config.site_id
            ),
            "rollups": await self._local.collect_rollups(self._config.site_id),
        }
        if self._config.asset_sync_enabled:
            asset = await self._local.latest_snapshot_asset(self._config.site_id)
            if asset is not None:
                projections["asset_upload"] = {
                    "sign_request": asset.sign_request,
                    "complete_request": asset.complete_request,
                    "file_path": asset.file_path,
                }
        return projections

    async def _enqueue_projections(
        self,
        projections: dict[str, dict[str, Any]],
        *,
        now: datetime,
    ) -> int:
        created = 0
        for event_type, payload in projections.items():
            key = self._idempotency_key(event_type, payload, now=now)
            result = await self._outbox.enqueue(
                event_type=event_type,
                idempotency_key=key,
                payload=payload,
                now=now,
            )
            if result.created:
                created += 1
                log_event(
                    "cloud_gateway",
                    "enqueued",
                    site_id=self._config.site_id,
                    gateway_id=self._config.gateway_id,
                    event_type=event_type,
                    idempotency_key=key,
                )
        return created

    async def _deliver_due(self) -> tuple[int, int]:
        delivered = 0
        failed = 0
        rows = await self._outbox.due(now=self._clock())
        for row in rows:
            try:
                await self._dispatch(row)
            except Exception as exc:
                failed += 1
                await self._mark_delivery_failed(row, exc)
                continue
            delivered_at = self._clock()
            await self._outbox.mark_delivered(_row_id(row), now=delivered_at)
            await self._outbox.set_cursor(
                cursor_key=f"delivered:{row.event_type}",
                cursor_value={
                    "idempotency_key": row.idempotency_key,
                    "delivered_at": delivered_at,
                },
                now=delivered_at,
            )
            delivered += 1
            log_event(
                "cloud_gateway",
                "delivered",
                site_id=self._config.site_id,
                gateway_id=self._config.gateway_id,
                event_type=row.event_type,
                idempotency_key=row.idempotency_key,
                attempt_count=row.attempt_count,
            )
        return delivered, failed

    async def _dispatch(self, row: CloudOutbox) -> None:
        payload = row.payload
        if row.event_type == "heartbeat":
            await self._cloud.send_heartbeat(
                payload,
                idempotency_key=row.idempotency_key,
            )
            return
        if row.event_type == "catalog":
            await self._cloud.put_catalog(payload, idempotency_key=row.idempotency_key)
            return
        if row.event_type == "latest_metrics":
            await self._cloud.put_latest_metrics(
                payload, idempotency_key=row.idempotency_key
            )
            return
        if row.event_type == "rollups":
            await self._cloud.post_rollups(payload, idempotency_key=row.idempotency_key)
            return
        if row.event_type == "asset_upload":
            await self._deliver_asset(payload, idempotency_key=row.idempotency_key)
            return
        if row.event_type == "command_result":
            await self._cloud.report_command_result(
                command_id=str(payload["command_id"]),
                payload=dict(payload["result"]),
                idempotency_key=row.idempotency_key,
            )
            return
        raise CloudDeliveryError(f"unknown outbox event type: {row.event_type}")

    async def _deliver_asset(
        self,
        payload: dict[str, Any],
        *,
        idempotency_key: str,
    ) -> None:
        sign_request = payload["sign_request"]
        complete_request = payload["complete_request"]
        signed = await self._cloud.sign_upload(
            sign_request,
            idempotency_key=f"{idempotency_key}:sign",
        )
        await self._cloud.upload_asset(
            file_path=Path(payload["file_path"]),
            upload_url=signed["upload_url"],
            headers=dict(signed.get("headers") or {}),
            content_type=sign_request["content_type"],
        )
        await self._cloud.complete_asset(
            complete_request,
            idempotency_key=f"{idempotency_key}:complete",
        )

    async def _mark_delivery_failed(self, row: CloudOutbox, exc: Exception) -> None:
        delay = self._backoff.next_delay_s(row.attempt_count + 1)
        await self._outbox.mark_failed(
            _row_id(row),
            error=str(exc),
            now=self._clock(),
            retry_delay_s=delay,
        )
        log_event(
            "cloud_gateway",
            "delivery_failed",
            site_id=self._config.site_id,
            gateway_id=self._config.gateway_id,
            event_type=row.event_type,
            idempotency_key=row.idempotency_key,
            attempt_count=row.attempt_count + 1,
            retry_delay_s=delay,
            error=type(exc).__name__,
        )

    async def _finish(
        self,
        *,
        enqueued: int,
        delivered: int,
        failed: int,
        dry_run: bool,
    ) -> SyncResult:
        backlog_depth = await self._outbox.pending_count()
        log_event(
            "cloud_gateway",
            "cycle_finished",
            site_id=self._config.site_id,
            gateway_id=self._config.gateway_id,
            enqueued=enqueued,
            delivered=delivered,
            failed=failed,
            backlog_depth=backlog_depth,
            dry_run=dry_run,
        )
        return SyncResult(
            enqueued=enqueued,
            delivered=delivered,
            failed=failed,
            backlog_depth=backlog_depth,
            dry_run=dry_run,
        )

    def _idempotency_key(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        now: datetime,
    ) -> str:
        if event_type == "heartbeat":
            stamp = now.isoformat(timespec="seconds")
            return f"{self._config.site_id}:{self._config.gateway_id}:heartbeat:{stamp}"
        return f"{self._config.site_id}:{event_type}:{stable_json_hash(payload)}"


def _count_projection(value: dict[str, Any]) -> int:
    for key in ("metrics", "rollups", "tents", "devices", "capabilities"):
        item = value.get(key)
        if isinstance(item, list):
            return len(item)
    return 1


def _row_id(row: CloudOutbox) -> int:
    if row.id is None:
        raise CloudDeliveryError("outbox row is missing a primary key")
    return row.id
