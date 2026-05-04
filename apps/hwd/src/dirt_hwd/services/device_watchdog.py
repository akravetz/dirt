"""Device offline/online Telegram alerter.

Polls ``SystemStatusService.get_device_statuses()`` and fires a Telegram
message when a device crosses the ``offline`` boundary in either direction.
Flapping between ``ok`` and ``warn`` is ignored.

State survives restarts via a small JSON file under
``<data_dir>/logs/device_watchdog/state.json``. A cold-start with no state
file treats every current device as first-seen, so a systemd restart
doesn't replay every existing offline state.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from dirt_shared.observability import log_event
from dirt_shared.services.system_status import (
    DeviceKind,
    DeviceStatus,
    DeviceStatus_t,
    SystemStatusService,
)
from dirt_shared.services.telegram import TelegramClient, TelegramError

logger = logging.getLogger(__name__)

STREAM = "device_status"

# Mirrors DeviceStatus_t in dirt_shared.services.system_status. Used to
# drop unknown status strings loaded from a stale state.json.
_VALID_STATUSES: frozenset[str] = frozenset({"ok", "warn", "offline", "listening"})


@dataclass(frozen=True)
class DeviceWatchdogConfig:
    poll_interval: int
    state_path: Path
    telegram_bot_token: str
    telegram_chat_id: str


class DeviceWatchdogService:
    def __init__(
        self,
        config: DeviceWatchdogConfig,
        *,
        system_status: SystemStatusService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        http_client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self._config = config
        self._status = system_status
        self._clock = clock
        self._http_factory = http_client_factory or (
            lambda: httpx.AsyncClient(timeout=30.0)
        )

    async def run(self, stop_event: asyncio.Event) -> None:
        cfg = self._config
        if not cfg.telegram_bot_token or not cfg.telegram_chat_id:
            logger.warning(
                "telegram_bot_token/telegram_chat_id unset — device watchdog disabled",
            )
            return

        last_known = _load_state(cfg.state_path)
        logger.info(
            "device watchdog starting: interval=%ds state=%s seeded=%s",
            cfg.poll_interval,
            cfg.state_path,
            bool(last_known),
        )

        async with self._http_factory() as http:
            telegram = TelegramClient(token=cfg.telegram_bot_token, http=http)
            while not stop_event.is_set():
                try:
                    devices = await self._status.get_device_statuses()
                    for t in _diff(last_known, devices):
                        await self._announce(telegram, t)

                    new_state = {
                        _device_key(d): d.status for d in devices if d.last_seen
                    }
                    if new_state != last_known:
                        _save_state(cfg.state_path, new_state)
                        last_known = new_state

                except Exception as exc:
                    logger.exception("device watchdog error")
                    log_event(
                        STREAM,
                        "error",
                        error_type=type(exc).__name__,
                        error=repr(exc),
                    )

                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=cfg.poll_interval)

        logger.info("device watchdog stopped")

    async def _announce(self, telegram: TelegramClient, t: _Transition) -> None:
        if t.new == "offline":
            age = _format_age(self._clock(), t.last_seen)
            text = f"⚠ <b>{t.name}</b> offline (last seen {age})"
        else:
            text = f"✓ <b>{t.name}</b> back online"

        log_event(
            STREAM,
            "state_change",
            name=t.name,
            kind=t.kind,
            device_id=t.device_id,
            site_id=t.site_id,
            tent_id=t.tent_id,
            zone_id=t.zone_id,
            old=t.old,
            new=t.new,
            last_seen=t.last_seen.isoformat() if t.last_seen else None,
        )
        logger.info("device %s: %s → %s", t.name, t.old, t.new)

        try:
            await telegram.send_message(self._config.telegram_chat_id, text)
        except TelegramError:
            logger.exception("telegram send failed for %s", t.name)


# ============================================================
# Pure helpers
# ============================================================


@dataclass(frozen=True)
class _Transition:
    name: str
    kind: DeviceKind
    device_id: str | None
    site_id: str
    tent_id: str | None
    zone_id: str | None
    old: DeviceStatus_t
    new: DeviceStatus_t
    last_seen: datetime | None


def _device_key(device: DeviceStatus) -> str:
    return device.device_id or device.name


def _diff(
    last_known: dict[str, DeviceStatus_t],
    devices: list[DeviceStatus],
) -> list[_Transition]:
    """Yield transitions that cross the offline boundary in either direction.

    A device missing ``last_seen`` (never reported — e.g. a never-installed
    sensor slot) is skipped: better silence than cry-wolf forever. A device
    absent from ``last_known`` is also skipped — first-seen is not a
    transition, so adding a new node to the fleet won't fire an alert.
    """
    out: list[_Transition] = []
    for d in devices:
        if d.last_seen is None:
            continue
        old = last_known.get(_device_key(d)) or last_known.get(d.name)
        if old is None:
            continue
        if (old == "offline") != (d.status == "offline"):
            out.append(
                _Transition(
                    name=d.name,
                    kind=d.kind,
                    device_id=d.device_id,
                    site_id=d.site_id,
                    tent_id=d.tent_id,
                    zone_id=d.zone_id,
                    old=old,
                    new=d.status,
                    last_seen=d.last_seen,
                )
            )
    return out


def _load_state(path: Path) -> dict[str, DeviceStatus_t]:
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {
        str(k): v  # type: ignore[misc]
        for k, v in raw.items()
        if isinstance(v, str) and v in _VALID_STATUSES
    }


def _save_state(path: Path, state: dict[str, DeviceStatus_t]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True))
    tmp.replace(path)


def _format_age(now: datetime, last_seen: datetime | None) -> str:
    if last_seen is None:
        return "never"
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=UTC)
    seconds = int((now - last_seen).total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours, rem = divmod(minutes, 60)
    return f"{hours}h ago" if rem == 0 else f"{hours}h {rem}m ago"
