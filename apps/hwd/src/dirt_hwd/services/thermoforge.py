"""Schedule-driven AC Infinity ThermoForge heater control."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, time
from pathlib import Path
from typing import Protocol
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_hwd.services.thermoforge_ble import (
    ThermoForgeBleClient,
    ThermoForgeBleConfig,
    ThermoForgeError,
)
from dirt_hwd.services.thermoforge_protocol import ThermoForgeStatus
from dirt_shared.config import ThermoForgeConfig
from dirt_shared.models import Capability, Schedule, Site, Tent, Zone
from dirt_shared.models import Device as DbDevice
from dirt_shared.models.enums import SensorSource
from dirt_shared.observability import log_event
from dirt_shared.services.grow_state import derive_lights_from_times
from dirt_shared.services.readings import ReadingsService
from dirt_shared.services.telegram import TelegramClient, TelegramError

logger = logging.getLogger(__name__)

_VALID_ALERT_STATES: frozenset[str] = frozenset({"online", "offline"})
HEATER_STREAM = "heater"


@dataclass(frozen=True, slots=True)
class ScheduledThermoForgeTarget:
    site_id: str
    tent_id: str
    zone_id: str | None
    device_id: str
    capability_id: str
    schedule_id: str
    provider_uid: str
    starts_local: time
    ends_local: time
    timezone: str


@dataclass(frozen=True, slots=True)
class ThermoForgeScheduleTarget:
    running: bool
    level: int | None = None


class ThermoForgeClient(Protocol):
    async def connect(self) -> ThermoForgeStatus: ...

    async def disconnect(self) -> None: ...

    async def read_status(self) -> ThermoForgeStatus: ...

    async def set_power(self, on: bool) -> ThermoForgeStatus: ...

    async def set_level(self, level: int) -> ThermoForgeStatus: ...


ThermoForgeClientFactory = Callable[[str], ThermoForgeClient]
ThermoForgeTargetLoader = Callable[[], Awaitable[list[ScheduledThermoForgeTarget]]]
ThermoForgeAnnouncer = Callable[[str], Awaitable[None]]
EventLogger = Callable[..., None]


class ThermoForgeReadingsRecorder(Protocol):
    async def ingest_reading(
        self,
        metrics: dict[str, float],
        **kwargs: object,
    ) -> int: ...


class ScheduledThermoForgeService:
    """Reconcile enabled DB-known ThermoForge heater schedules over BLE."""

    def __init__(  # noqa: PLR0913 - test seams plus optional DB loader/client factory.
        self,
        config: ThermoForgeConfig,
        *,
        engine: AsyncEngine | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        target_loader: ThermoForgeTargetLoader | None = None,
        client_factory: ThermoForgeClientFactory | None = None,
        announcer: ThermoForgeAnnouncer | None = None,
        readings: ThermoForgeReadingsRecorder | None = None,
        event_logger: EventLogger = log_event,
    ) -> None:
        if engine is None and target_loader is None:
            raise ValueError("engine is required when target_loader is not provided")
        self._config = config
        self._engine = engine
        self._clock = clock
        self._target_loader = target_loader
        self._client_factory = client_factory or self._make_client
        self._announcer = announcer
        self._readings = (
            readings
            if readings is not None or engine is None
            else ReadingsService(engine, clock=clock)
        )
        self._log_event = event_logger
        self._failure_counts: dict[str, int] = {}

    async def run(self, stop_event: asyncio.Event) -> None:
        logger.info(
            "scheduled ThermoForge service starting: interval=%ds night_level=%d",
            self._config.poll_interval,
            self._config.night_level,
        )
        clients: dict[str, ThermoForgeClient] = {}

        while not stop_event.is_set():
            await self._tick(clients)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=self._config.poll_interval,
                )

        for client in clients.values():
            await self._safe_disconnect(client)
        logger.info("scheduled ThermoForge service stopped")

    async def _tick(self, clients: dict[str, ThermoForgeClient] | None = None) -> None:
        cached_clients = clients if clients is not None else {}
        targets = await self._load_targets()
        active_macs = {target.provider_uid for target in targets}
        for mac in set(cached_clients) - active_macs:
            await self._safe_disconnect(cached_clients.pop(mac))

        for target in targets:
            try:
                client = cached_clients.get(target.provider_uid)
                if client is None:
                    client = self._client_factory(target.provider_uid)
                    cached_clients[target.provider_uid] = client
                    live = await client.connect()
                else:
                    live = await client.read_status()
                desired = self._derive_target(target)
                self._log_status_read(target, live, desired)
                await self._record_readings(target, live)
                final_status = await self._reconcile_target(
                    target, client, live, desired
                )
            except ThermoForgeError as exc:
                logger.warning(
                    "ThermoForge target failed: device_id=%s error=%r",
                    target.device_id,
                    exc,
                )
                await self._safe_disconnect(
                    cached_clients.pop(target.provider_uid, None)
                )
                consecutive_failures = self._record_failure(target)
                will_mark_offline = self._should_mark_offline(
                    target,
                    consecutive_failures,
                )
                self._log_poll_failed(
                    target,
                    exc,
                    consecutive_failures=consecutive_failures,
                    will_mark_offline=will_mark_offline,
                )
                if will_mark_offline:
                    await self._mark_offline(target, exc)
            else:
                self._clear_failure(target)
                await self._mark_online(target, final_status)

    async def _load_targets(self) -> list[ScheduledThermoForgeTarget]:
        if self._target_loader is not None:
            return await self._target_loader()
        if self._engine is None:
            raise RuntimeError("engine missing for DB target load")

        async with AsyncSession(self._engine) as session:
            rows = (
                await session.exec(
                    select(
                        Schedule,
                        Site.site_id,
                        Tent.tent_id,
                        Zone.zone_id,
                        DbDevice.device_id,
                        DbDevice.provider_uid,
                        Capability.capability_id,
                    )
                    .join(Site, Site.id == Schedule.site_id)
                    .join(Tent, Tent.id == Schedule.tent_id)
                    .join(DbDevice, DbDevice.id == Schedule.device_id)
                    .outerjoin(Zone, Zone.id == DbDevice.zone_id)
                    .join(Capability, Capability.id == Schedule.capability_id)
                    .where(Schedule.kind == "heater")
                    .where(Schedule.enabled.is_(True))
                    .where(col(Schedule.starts_local).is_not(None))
                    .where(col(Schedule.ends_local).is_not(None))
                    .where(DbDevice.enabled.is_(True))
                    .where(DbDevice.controller == "ac_infinity_ble")
                    .where(DbDevice.provider_uid_kind == "mac")
                    .where(col(DbDevice.provider_uid).is_not(None))
                    .where(Capability.enabled.is_(True))
                    .order_by(Tent.tent_id, Schedule.schedule_id)
                )
            ).all()

        targets: list[ScheduledThermoForgeTarget] = []
        for (
            schedule,
            site_id,
            tent_id,
            zone_id,
            device_id,
            provider_uid,
            capability_id,
        ) in rows:
            if (
                schedule.starts_local is None
                or schedule.ends_local is None
                or provider_uid is None
            ):
                continue
            targets.append(
                ScheduledThermoForgeTarget(
                    site_id=site_id,
                    tent_id=tent_id,
                    zone_id=zone_id,
                    device_id=device_id,
                    capability_id=capability_id,
                    schedule_id=schedule.schedule_id,
                    provider_uid=provider_uid,
                    starts_local=schedule.starts_local,
                    ends_local=schedule.ends_local,
                    timezone=schedule.timezone,
                )
            )
        return targets

    def _derive_target(
        self,
        target: ScheduledThermoForgeTarget,
    ) -> ThermoForgeScheduleTarget:
        active = derive_lights_from_times(
            target.starts_local,
            target.ends_local,
            self._clock().astimezone(ZoneInfo(target.timezone)),
        ).on
        if active:
            return ThermoForgeScheduleTarget(
                running=True,
                level=self._config.night_level,
            )
        return ThermoForgeScheduleTarget(running=False)

    async def _reconcile_target(
        self,
        target: ScheduledThermoForgeTarget,
        client: ThermoForgeClient,
        live: ThermoForgeStatus,
        desired: ThermoForgeScheduleTarget,
    ) -> ThermoForgeStatus:
        if self._status_matches(live, desired):
            return live

        reason = "scheduled_on" if desired.running else "scheduled_off"
        if not desired.running:
            self._log_command_sent(target, command="off")
            status = await client.set_power(False)
            status = await self._wait_for_target_status(target, client, status, desired)
            self._log_state_change(target, live, status, reason)
            await self._record_readings(target, status)
            return status

        status = live
        if not status.running:
            self._log_command_sent(target, command="on")
            status = await client.set_power(True)
        if desired.level is not None and status.level != desired.level:
            self._log_command_sent(target, command="heat_level", level=desired.level)
            status = await client.set_level(desired.level)
        status = await self._wait_for_target_status(target, client, status, desired)
        self._log_state_change(target, live, status, reason)
        await self._record_readings(target, status)
        return status

    async def _wait_for_target_status(
        self,
        target: ScheduledThermoForgeTarget,
        client: ThermoForgeClient,
        status: ThermoForgeStatus,
        desired: ThermoForgeScheduleTarget,
    ) -> ThermoForgeStatus:
        deadline = asyncio.get_running_loop().time() + self._config.connect_timeout_s
        while not self._status_matches(status, desired):
            if asyncio.get_running_loop().time() >= deadline:
                self._raise_status_mismatch(target, status, desired)
            status = await client.read_status()
        return status

    def _raise_status_mismatch(
        self,
        target: ScheduledThermoForgeTarget,
        status: ThermoForgeStatus,
        desired: ThermoForgeScheduleTarget,
    ) -> None:
        raise ThermoForgeError(
            "ThermoForge status did not reach target "
            f"device_id={target.device_id} "
            f"target_running={desired.running} target_level={desired.level} "
            f"status_running={status.running} status_level={status.level}"
        )

    def _status_matches(
        self,
        status: ThermoForgeStatus,
        desired: ThermoForgeScheduleTarget,
    ) -> bool:
        if status.running != desired.running:
            return False
        return not desired.running or status.level == desired.level

    def _make_client(self, mac: str) -> ThermoForgeClient:
        return ThermoForgeBleClient(
            ThermoForgeBleConfig(
                mac=mac,
                status_timeout_s=self._config.connect_timeout_s,
            )
        )

    async def _safe_disconnect(self, client: ThermoForgeClient | None) -> None:
        if client is None:
            return
        with contextlib.suppress(Exception):
            await client.disconnect()

    def _record_failure(self, target: ScheduledThermoForgeTarget) -> int:
        key = _state_key(target)
        count = self._failure_counts.get(key, 0) + 1
        self._failure_counts[key] = count
        return count

    def _clear_failure(self, target: ScheduledThermoForgeTarget) -> None:
        self._failure_counts.pop(_state_key(target), None)

    def _should_mark_offline(
        self,
        target: ScheduledThermoForgeTarget,
        consecutive_failures: int,
    ) -> bool:
        state = _load_state(self._config.state_path)
        if state.get(_state_key(target)) == "offline":
            return False
        return consecutive_failures >= self._config.offline_alert_failures

    def _log_poll_failed(
        self,
        target: ScheduledThermoForgeTarget,
        exc: ThermoForgeError,
        *,
        consecutive_failures: int,
        will_mark_offline: bool,
    ) -> None:
        self._log_event(
            HEATER_STREAM,
            "poll_failed",
            **_scope_fields(target),
            error_type=type(exc).__name__,
            error=str(exc),
            consecutive_failures=consecutive_failures,
            offline_alert_failures=self._config.offline_alert_failures,
            will_mark_offline=will_mark_offline,
            next_poll_interval_s=self._config.poll_interval,
        )

    async def _mark_offline(
        self,
        target: ScheduledThermoForgeTarget,
        exc: ThermoForgeError,
    ) -> None:
        key = _state_key(target)
        state = _load_state(self._config.state_path)
        if state.get(key) == "offline":
            return
        state[key] = "offline"
        _save_state(self._config.state_path, state)
        self._log_event(
            HEATER_STREAM,
            "offline",
            **_scope_fields(target),
            error_type=type(exc).__name__,
            error=str(exc),
            next_poll_interval_s=self._config.poll_interval,
        )
        text = (
            f"WARNING: <b>{target.device_id}</b> ThermoForge controller offline "
            f"({type(exc).__name__}: {exc})"
        )
        await self._announce(text, target.device_id)

    async def _mark_online(
        self,
        target: ScheduledThermoForgeTarget,
        status: ThermoForgeStatus,
    ) -> None:
        key = _state_key(target)
        state = _load_state(self._config.state_path)
        old = state.get(key)
        if old is None or old == "online":
            return
        state[key] = "online"
        _save_state(self._config.state_path, state)
        if old == "offline":
            self._log_event(
                HEATER_STREAM,
                "recovered",
                **_scope_fields(target),
                running=status.running,
                level=_effective_level(status),
            )
            await self._announce(
                f"OK: <b>{target.device_id}</b> ThermoForge controller back online",
                target.device_id,
            )

    def _log_status_read(
        self,
        target: ScheduledThermoForgeTarget,
        status: ThermoForgeStatus,
        desired: ThermoForgeScheduleTarget,
    ) -> None:
        self._log_event(
            HEATER_STREAM,
            "status_read",
            **_scope_fields(target),
            schedule_id=target.schedule_id,
            running=status.running,
            level=_effective_level(status),
            target_running=desired.running,
            target_level=_target_level(desired),
        )

    def _log_state_change(
        self,
        target: ScheduledThermoForgeTarget,
        previous: ThermoForgeStatus,
        new: ThermoForgeStatus,
        reason: str,
    ) -> None:
        self._log_event(
            HEATER_STREAM,
            "state_change",
            **_scope_fields(target),
            schedule_id=target.schedule_id,
            previous_running=previous.running,
            previous_level=_effective_level(previous),
            new_running=new.running,
            new_level=_effective_level(new),
            reason=reason,
        )

    def _log_command_sent(
        self,
        target: ScheduledThermoForgeTarget,
        *,
        command: str,
        level: int | None = None,
    ) -> None:
        fields: dict[str, str | int | None] = {
            **_scope_fields(target),
            "schedule_id": target.schedule_id,
            "command": command,
        }
        if level is not None:
            fields["level"] = level
        self._log_event(HEATER_STREAM, "command_sent", **fields)

    async def _record_readings(
        self,
        target: ScheduledThermoForgeTarget,
        status: ThermoForgeStatus,
    ) -> None:
        if self._readings is None:
            return
        await self._readings.ingest_reading(
            {
                "heater_on": 1.0 if status.running else 0.0,
                "heater_intensity_pct": float(_effective_level(status) * 10),
            },
            device_id=target.device_id,
            source=SensorSource.AC_INFINITY,
            site_id=target.site_id,
            tent_id=target.tent_id,
            zone_id=target.zone_id,
        )

    async def _announce(self, text: str, device_id: str) -> None:
        if self._announcer is not None:
            await self._announcer(text)
            return
        if not self._config.telegram_bot_token or not self._config.telegram_chat_id:
            return
        try:
            async with httpx.AsyncClient(timeout=30.0) as http:
                telegram = TelegramClient(
                    token=self._config.telegram_bot_token,
                    http=http,
                )
                await telegram.send_message(self._config.telegram_chat_id, text)
        except TelegramError:
            logger.exception("telegram send failed for ThermoForge %s", device_id)


def _state_key(target: ScheduledThermoForgeTarget) -> str:
    return target.device_id or target.provider_uid


def _scope_fields(target: ScheduledThermoForgeTarget) -> dict[str, str | None]:
    return {
        "site_id": target.site_id,
        "tent_id": target.tent_id,
        "zone_id": target.zone_id,
        "device_id": target.device_id,
        "capability_id": target.capability_id,
    }


def _effective_level(status: ThermoForgeStatus) -> int:
    return status.level if status.running else 0


def _target_level(target: ThermoForgeScheduleTarget) -> int:
    return target.level if target.running and target.level is not None else 0


def _load_state(path: Path) -> dict[str, str]:
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {
        str(k): v
        for k, v in raw.items()
        if isinstance(v, str) and v in _VALID_ALERT_STATES
    }


def _save_state(path: Path, state: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True))
    tmp.replace(path)
