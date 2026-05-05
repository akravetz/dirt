"""PTZ-only cloud command execution for the local gateway."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from dirt_gateway.cloud import CloudDeliveryError
from dirt_gateway.outbox import OutboxRepository
from dirt_gateway.protocols import BackoffPolicy, CloudGatewayClient, Sleeper
from dirt_gateway.sync import ExponentialBackoff
from dirt_shared.config import CloudGatewayConfig
from dirt_shared.models import CloudOutbox
from dirt_shared.models.command import Command
from dirt_shared.observability import log_event
from dirt_shared.services.commands import CommandService
from dirt_shared.services.ptz import PTZService

TERMINAL_CLOUD_STATUSES = frozenset({"succeeded", "failed", "rejected", "expired"})
LOCAL_PTZ_DEVICE_ID = "obsbot-main"
LOCAL_PTZ_CAPABILITY_ID = "ptz_move"


@dataclass(frozen=True)
class CommandLoopResult:
    claimed: int
    executed: int
    reported: int
    failed: int
    dry_run: bool


class PTZExecutor(Protocol):
    def get_preset(self, preset_id: str): ...

    async def apply_preset(self, preset_id: str) -> dict[str, Any]: ...

    async def look_at_normalized(self, x: float, y: float) -> dict[str, Any]: ...

    async def zoom_to(self, value: float) -> dict[str, Any]: ...

    async def zoom_by(self, delta: float) -> dict[str, Any]: ...


class GatewayCommandService:
    def __init__(  # noqa: PLR0913
        self,
        *,
        config: CloudGatewayConfig,
        cloud_client: CloudGatewayClient,
        command_ledger: CommandService,
        outbox: OutboxRepository,
        ptz: PTZExecutor | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        backoff: BackoffPolicy | None = None,
        claim_limit: int = 5,
    ) -> None:
        self._config = config
        self._cloud = cloud_client
        self._ledger = command_ledger
        self._outbox = outbox
        self._ptz = ptz or PTZService()
        self._clock = clock
        self._backoff = backoff or ExponentialBackoff()
        self._claim_limit = claim_limit

    async def run_once(self) -> CommandLoopResult:
        if self._config.dry_run:
            log_event(
                "cloud_gateway",
                "command_dry_run",
                site_id=self._config.site_id,
                gateway_id=self._config.gateway_id,
            )
            return CommandLoopResult(
                claimed=0,
                executed=0,
                reported=0,
                failed=0,
                dry_run=True,
            )

        try:
            response = await self._cloud.claim_commands(
                site_id=self._config.site_id,
                limit=self._claim_limit,
                idempotency_key=self._claim_idempotency_key(),
            )
        except Exception as exc:
            log_event(
                "cloud_gateway",
                "command_claim_failed",
                site_id=self._config.site_id,
                gateway_id=self._config.gateway_id,
                error=type(exc).__name__,
            )
            return CommandLoopResult(
                claimed=0,
                executed=0,
                reported=0,
                failed=1,
                dry_run=False,
            )

        commands = response.get("commands") if isinstance(response, dict) else None
        if not isinstance(commands, list):
            raise CloudDeliveryError("command claim response missing commands list")

        executed = 0
        reported = 0
        failed = 0
        for item in commands:
            if not isinstance(item, dict):
                failed += 1
                continue
            try:
                outcome = await self._handle_command(item)
            except Exception as exc:
                failed += 1
                log_event(
                    "cloud_gateway",
                    "command_failed",
                    site_id=self._config.site_id,
                    gateway_id=self._config.gateway_id,
                    command_id=str(item.get("command_id", "")),
                    error=type(exc).__name__,
                )
                continue
            executed += int(outcome.executed)
            reported += int(outcome.reported)

        return CommandLoopResult(
            claimed=len(commands),
            executed=executed,
            reported=reported,
            failed=failed,
            dry_run=False,
        )

    async def run_forever(self, sleeper: Sleeper) -> None:
        while True:
            await self.run_once()
            await sleeper.sleep(self._config.command_poll_interval_s)

    async def _handle_command(self, item: dict[str, Any]) -> _CommandOutcome:
        command_id = _required_str(item, "command_id")
        now = self._clock()
        expires_at = _parse_datetime(item.get("expires_at"))
        if expires_at <= now:
            reported = await self._enqueue_and_try_report(
                command_id=command_id,
                status="expired",
                error="command expired before local execution",
            )
            return _CommandOutcome(executed=False, reported=reported)

        validation_error = self._validate_claimed_command(item)
        if validation_error is not None:
            reported = await self._enqueue_and_try_report(
                command_id=command_id,
                status="rejected",
                error=validation_error,
            )
            return _CommandOutcome(executed=False, reported=reported)

        local_command = await self._ledger.enqueue(
            command_type=_local_command_type(str(item["command_type"])),
            payload=_local_payload(item),
            idempotency_key=f"cloud-command:{command_id}",
            requested_by=f"cloud:{item.get('requested_by', 'browser')}",
            source="cloud_gateway",
            site_id=self._config.site_id,
            tent_id=str(item["tent_id"]),
            device_id=LOCAL_PTZ_DEVICE_ID,
            capability_id=LOCAL_PTZ_CAPABILITY_ID,
            zone_id=_zone_for_command(item),
        )
        if local_command.status == "queued":
            return await self._execute_new_command(item, local_command)
        return await self._report_existing_local_terminal(command_id, local_command)

    async def _execute_new_command(
        self, item: dict[str, Any], local_command: Command
    ) -> _CommandOutcome:
        command_id = str(item["command_id"])
        await self._ledger.start(local_command.command_id)
        await self._try_report_running(command_id)
        try:
            result = await self._execute_ptz(item)
        except Exception as exc:
            error = {"error_type": type(exc).__name__, "error": str(exc)}
            await self._ledger.fail(local_command.command_id, error)
            reported = await self._enqueue_and_try_report(
                command_id=command_id,
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
            )
            return _CommandOutcome(executed=True, reported=reported)

        if result.get("ok") is False:
            await self._ledger.fail(local_command.command_id, {"result": result})
            reported = await self._enqueue_and_try_report(
                command_id=command_id,
                status="failed",
                result=result,
                error="PTZ service returned ok=false",
            )
            return _CommandOutcome(executed=True, reported=reported)

        await self._ledger.succeed(local_command.command_id, result)
        reported = await self._enqueue_and_try_report(
            command_id=command_id,
            status="succeeded",
            result=result,
        )
        log_event(
            "cloud_gateway",
            "command_executed",
            site_id=self._config.site_id,
            gateway_id=self._config.gateway_id,
            command_id=command_id,
            command_type=str(item["command_type"]),
        )
        return _CommandOutcome(executed=True, reported=reported)

    async def _report_existing_local_terminal(
        self, cloud_command_id: str, local_command: Command
    ) -> _CommandOutcome:
        if local_command.status == "succeeded":
            reported = await self._enqueue_and_try_report(
                command_id=cloud_command_id,
                status="succeeded",
                result=local_command.result or {},
            )
            return _CommandOutcome(executed=False, reported=reported)
        if local_command.status == "failed":
            reported = await self._enqueue_and_try_report(
                command_id=cloud_command_id,
                status="failed",
                error=_error_text(local_command.error),
            )
            return _CommandOutcome(executed=False, reported=reported)

        failed = await self._ledger.fail(
            local_command.command_id,
            {"error": "gateway restarted with non-terminal cloud command ledger row"},
        )
        reported = await self._enqueue_and_try_report(
            command_id=cloud_command_id,
            status="failed",
            error=_error_text(failed.error),
        )
        return _CommandOutcome(executed=False, reported=reported)

    async def _execute_ptz(self, item: dict[str, Any]) -> dict[str, Any]:
        command_type = str(item["command_type"])
        payload = item["payload"]
        if command_type == "ptz_preset":
            return await self._ptz.apply_preset(str(payload["preset_id"]))
        if command_type == "ptz_look":
            return await self._ptz.look_at_normalized(
                float(payload["x"]),
                float(payload["y"]),
            )
        if command_type == "ptz_zoom":
            if "zoom" in payload:
                return await self._ptz.zoom_to(float(payload["zoom"]))
            return await self._ptz.zoom_by(float(payload["delta"]))
        raise ValueError(f"unsupported command_type: {command_type}")

    async def _try_report_running(self, command_id: str) -> None:
        try:
            await self._cloud.report_command_result(
                command_id=command_id,
                payload={"site_id": self._config.site_id, "status": "running"},
                idempotency_key=f"{self._config.site_id}:command:{command_id}:running",
            )
        except Exception:
            log_event(
                "cloud_gateway",
                "command_running_report_failed",
                site_id=self._config.site_id,
                gateway_id=self._config.gateway_id,
                command_id=command_id,
            )

    async def _enqueue_and_try_report(
        self,
        *,
        command_id: str,
        status: str,
        result: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> bool:
        now = self._clock()
        payload = {
            "site_id": self._config.site_id,
            "status": status,
            "result": result,
            "error": error,
        }
        key = f"{self._config.site_id}:command:{command_id}:{status}"
        enqueued = await self._outbox.enqueue(
            event_type="command_result",
            idempotency_key=key,
            payload={"command_id": command_id, "result": payload},
            now=now,
        )
        try:
            await self._cloud.report_command_result(
                command_id=command_id,
                payload=payload,
                idempotency_key=key,
            )
        except Exception as exc:
            if not enqueued.created and enqueued.row.status == "delivered":
                return False
            delay = self._backoff.next_delay_s(enqueued.row.attempt_count + 1)
            await self._outbox.mark_failed(
                _outbox_row_id(enqueued.row),
                error=str(exc),
                now=now,
                retry_delay_s=delay,
            )
            log_event(
                "cloud_gateway",
                "command_result_report_failed",
                site_id=self._config.site_id,
                gateway_id=self._config.gateway_id,
                command_id=command_id,
                status=status,
                error=type(exc).__name__,
            )
            return False

        await self._outbox.mark_delivered(_outbox_row_id(enqueued.row), now=now)
        log_event(
            "cloud_gateway",
            "command_result_reported",
            site_id=self._config.site_id,
            gateway_id=self._config.gateway_id,
            command_id=command_id,
            status=status,
        )
        return True

    def _validate_claimed_command(self, item: dict[str, Any]) -> str | None:
        if item.get("site_id") != self._config.site_id:
            return "command site scope does not match this gateway"
        if item.get("device_id") != LOCAL_PTZ_DEVICE_ID:
            return "unsupported PTZ device target"
        if item.get("capability_id") != LOCAL_PTZ_CAPABILITY_ID:
            return "unsupported PTZ capability target"
        command_type = item.get("command_type")
        payload = item.get("payload")
        if not isinstance(payload, dict):
            return "command payload must be an object"
        if command_type == "ptz_preset":
            preset_id = payload.get("preset_id")
            if not isinstance(preset_id, str) or not preset_id:
                return "ptz_preset requires preset_id"
            if self._ptz.get_preset(preset_id) is None:
                return "unknown PTZ preset"
            return None
        if command_type == "ptz_look":
            return _validate_number(payload, "x", -0.5, 0.5) or _validate_number(
                payload, "y", -0.5, 0.5
            )
        if command_type == "ptz_zoom":
            has_zoom = "zoom" in payload
            has_delta = "delta" in payload
            if has_zoom == has_delta:
                return "ptz_zoom requires exactly one of zoom or delta"
            if has_zoom:
                return _validate_number(payload, "zoom", 1.0, 2.0)
            return _validate_number(payload, "delta", -1.0, 1.0)
        return "unsupported cloud command type"

    def _claim_idempotency_key(self) -> str:
        stamp = self._clock().isoformat(timespec="seconds")
        return f"{self._config.site_id}:{self._config.gateway_id}:command-claim:{stamp}"


@dataclass(frozen=True)
class _CommandOutcome:
    executed: bool
    reported: bool


def _required_str(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    if not isinstance(value, str) or not value:
        raise CloudDeliveryError(f"claimed command missing {key}")
    return value


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    raise CloudDeliveryError("claimed command missing expires_at")


def _validate_number(
    payload: dict[str, Any],
    key: str,
    minimum: float,
    maximum: float,
) -> str | None:
    value = payload.get(key)
    if not isinstance(value, int | float):
        return f"{key} must be numeric"
    if not minimum <= float(value) <= maximum:
        return f"{key} must be between {minimum:g} and {maximum:g}"
    return None


def _local_command_type(cloud_type: str) -> str:
    return {
        "ptz_preset": "ptz.preset",
        "ptz_look": "ptz.look",
        "ptz_zoom": "ptz.zoom",
    }[cloud_type]


def _local_payload(item: dict[str, Any]) -> dict[str, Any]:
    payload = item["payload"]
    command_type = item["command_type"]
    if command_type == "ptz_preset":
        return {"preset_id": str(payload["preset_id"])}
    if command_type == "ptz_look":
        return {"x": float(payload["x"]), "y": float(payload["y"])}
    if "zoom" in payload:
        return {"zoom": float(payload["zoom"])}
    return {"delta": float(payload["delta"])}


def _zone_for_command(item: dict[str, Any]) -> str | None:
    if item["command_type"] != "ptz_preset":
        return "canopy"
    preset_id = str(item["payload"]["preset_id"])
    if preset_id.startswith("plant_") and len(preset_id) == len("plant_a"):
        return preset_id.replace("_", "-")
    return "canopy"


def _error_text(error: dict[str, Any] | None) -> str:
    if not error:
        return "local command failed"
    return str(error)[:500]


def _outbox_row_id(row: CloudOutbox) -> int:
    if row.id is None:
        raise CloudDeliveryError("outbox row is missing a primary key")
    return row.id
