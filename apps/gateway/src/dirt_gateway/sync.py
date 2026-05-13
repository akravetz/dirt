"""Read-only cloud sync orchestration for the local gateway."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel

from dirt_gateway.cloud import CloudDeliveryError
from dirt_gateway.outbox import OutboxRepository, stable_json_hash
from dirt_gateway.protocols import (
    AssetUploadProjection,
    BackoffPolicy,
    CloudGatewayClient,
    LocalGatewayServices,
    Sleeper,
    build_heartbeat_payload,
)
from dirt_shared.cloud_assets import AssetUploader, AssetUploadRequest
from dirt_shared.cloud_contract import (
    AssetRetentionRequest,
    CatalogRequest,
    CommandResultOutboxPayload,
    HeartbeatRequest,
    LatestMetricsRequest,
    RollupsRequest,
)
from dirt_shared.config import CloudGatewayConfig
from dirt_shared.models import CloudOutbox
from dirt_shared.observability import log_event

ReadOnlyProjectionPayload = (
    HeartbeatRequest | CatalogRequest | LatestMetricsRequest | RollupsRequest
)
TypedProjectionPayload = (
    ReadOnlyProjectionPayload | AssetRetentionRequest | AssetUploadProjection
)
ProjectionPayload = TypedProjectionPayload | dict[str, Any]


@dataclass(frozen=True)
class SyncResult:
    enqueued: int
    delivered: int
    failed: int
    backlog_depth: int
    dry_run: bool


@dataclass(frozen=True)
class _Projection:
    payload: ProjectionPayload
    rollup_bucket_names: frozenset[str] = frozenset()


ROLLUP_SYNC_INTERVALS: dict[str, timedelta] = {
    "5m": timedelta(minutes=5),
    "1h": timedelta(hours=1),
    "4h": timedelta(hours=4),
}


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
    HIGH_PRIORITY_EVENT_TYPES = frozenset(
        {
            "heartbeat",
            "latest_metrics",
            "catalog",
            "asset_upload",
            "asset_retention",
            "command_result",
        }
    )

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
        self._asset_uploader = AssetUploader(
            cloud_client,
            on_failure_report_error=self._log_asset_failure_report_failed,
        )
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

        projections = await self._collect_projections(
            backlog_depth=backlog_before,
            now=now,
        )
        if self._config.dry_run:
            log_event(
                "cloud_gateway",
                "dry_run",
                site_id=self._config.site_id,
                gateway_id=self._config.gateway_id,
                projection_counts={
                    key: _count_projection(_projection_payload_json(projection.payload))
                    for key, projection in projections.items()
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
        self, *, backlog_depth: int, now: datetime
    ) -> dict[str, _Projection]:
        projections: dict[str, _Projection] = {
            "heartbeat": _Projection(
                build_heartbeat_payload(
                    self._config,
                    backlog_depth=backlog_depth,
                )
            ),
            "catalog": _Projection(
                await self._local.collect_catalog(self._config.site_id)
            ),
            "latest_metrics": _Projection(
                await self._local.collect_latest_metrics(self._config.site_id)
            ),
        }
        rollup_buckets = await self._due_rollup_buckets(now)
        if rollup_buckets:
            projections["rollups"] = _Projection(
                await self._local.collect_rollups(
                    self._config.site_id,
                    bucket_names=set(rollup_buckets),
                ),
                rollup_bucket_names=rollup_buckets,
            )
        if self._config.asset_sync_enabled:
            projections["asset_retention"] = _Projection(
                AssetRetentionRequest(
                    site_id=self._config.site_id,
                    as_of_date=self._clock().date(),
                )
            )
            asset = await self._local.latest_snapshot_asset(self._config.site_id)
            if asset is not None:
                projections["asset_upload"] = _Projection(asset)
        return projections

    async def _due_rollup_buckets(self, now: datetime) -> frozenset[str]:
        due: set[str] = set()
        for bucket, interval in ROLLUP_SYNC_INTERVALS.items():
            cursor = await self._outbox.get_cursor(_rollup_cursor_key(bucket))
            last_enqueued_at = _cursor_datetime(cursor, "last_enqueued_at")
            if last_enqueued_at is None or now - last_enqueued_at >= interval:
                due.add(bucket)
        return frozenset(due)

    async def _enqueue_projections(
        self,
        projections: dict[str, _Projection],
        *,
        now: datetime,
    ) -> int:
        created = 0
        for event_type, projection in projections.items():
            payload = _projection_payload_json(projection.payload)
            key = self._idempotency_key(event_type, payload, now=now)
            result = await self._outbox.enqueue(
                event_type=event_type,
                idempotency_key=key,
                payload=payload,
                now=now,
            )
            if event_type == "rollups":
                superseded = await self._outbox.supersede_pending(
                    event_type=event_type,
                    keep_idempotency_key=key,
                    now=now,
                )
                if superseded:
                    log_event(
                        "cloud_gateway",
                        "superseded",
                        site_id=self._config.site_id,
                        gateway_id=self._config.gateway_id,
                        event_type=event_type,
                        count=superseded,
                    )
                for bucket in projection.rollup_bucket_names:
                    await self._outbox.set_cursor(
                        cursor_key=_rollup_cursor_key(bucket),
                        cursor_value={
                            "bucket": bucket,
                            "last_enqueued_at": now,
                            "idempotency_key": key,
                        },
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
        rows = [
            *(
                await self._outbox.due_for_event_types(
                    event_types=set(self.HIGH_PRIORITY_EVENT_TYPES),
                    now=self._clock(),
                    limit=20,
                )
            ),
            *(
                await self._outbox.due_for_event_types(
                    event_types={"rollups"},
                    now=self._clock(),
                    limit=1,
                )
            ),
        ]
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
                _validate_read_only_payload(row.event_type, payload),
                idempotency_key=row.idempotency_key,
            )
            return
        if row.event_type == "catalog":
            await self._cloud.put_catalog(
                _validate_read_only_payload(row.event_type, payload),
                idempotency_key=row.idempotency_key,
            )
            return
        if row.event_type == "latest_metrics":
            await self._cloud.put_latest_metrics(
                _validate_read_only_payload(row.event_type, payload),
                idempotency_key=row.idempotency_key,
            )
            return
        if row.event_type == "rollups":
            await self._cloud.post_rollups(
                _validate_read_only_payload(row.event_type, payload),
                idempotency_key=row.idempotency_key,
            )
            return
        if row.event_type == "asset_upload":
            await self._deliver_asset(
                AssetUploadRequest.model_validate(payload),
                idempotency_key=row.idempotency_key,
            )
            return
        if row.event_type == "asset_retention":
            await self._cloud.prune_expired_assets(
                AssetRetentionRequest.model_validate(payload),
                idempotency_key=row.idempotency_key,
            )
            return
        if row.event_type == "command_result":
            command_result = CommandResultOutboxPayload.model_validate(payload)
            await self._cloud.report_command_result(
                command_id=command_result.command_id,
                payload=command_result.result,
                idempotency_key=row.idempotency_key,
            )
            return
        raise CloudDeliveryError(f"unknown outbox event type: {row.event_type}")

    async def _deliver_asset(
        self,
        payload: AssetUploadRequest,
        *,
        idempotency_key: str,
    ) -> None:
        await self._asset_uploader.upload(payload, idempotency_key=idempotency_key)

    def _log_asset_failure_report_failed(
        self,
        payload: AssetUploadRequest,
        idempotency_key: str,
        exc: Exception,
    ) -> None:
        del exc
        log_event(
            "cloud_gateway",
            "asset_failure_report_failed",
            site_id=self._config.site_id,
            gateway_id=self._config.gateway_id,
            asset_id=payload.complete_request.asset_id,
            idempotency_key=idempotency_key,
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


def _projection_payload_json(payload: ProjectionPayload) -> dict[str, Any]:
    if isinstance(payload, AssetUploadProjection):
        return payload.to_outbox_payload().model_dump(mode="json")
    if isinstance(payload, BaseModel):
        return payload.model_dump(mode="json")
    return dict(payload)


def _validate_read_only_payload(
    event_type: str,
    payload: dict[str, Any],
) -> ReadOnlyProjectionPayload:
    model = _READ_ONLY_EVENT_MODELS[event_type]
    return model.model_validate(payload)


def _row_id(row: CloudOutbox) -> int:
    if row.id is None:
        raise CloudDeliveryError("outbox row is missing a primary key")
    return row.id


def _rollup_cursor_key(bucket: str) -> str:
    return f"rollups:last_enqueued:{bucket}"


def _cursor_datetime(cursor: dict[str, Any] | None, key: str) -> datetime | None:
    if cursor is None:
        return None
    value = cursor.get(key)
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value)
    return None


_READ_ONLY_EVENT_MODELS: dict[str, type[ReadOnlyProjectionPayload]] = {
    "heartbeat": HeartbeatRequest,
    "catalog": CatalogRequest,
    "latest_metrics": LatestMetricsRequest,
    "rollups": RollupsRequest,
}
