"""Per-(location, metric) freshness alerter.

``DeviceWatchdog`` fires when a whole node stops heartbeating. This service
fires on the subtler case: a specific metric stops flowing while the node
keeps reporting other fields — the Arduino→ESP32-C3 case where
temperature + humidity kept arriving but pressure silently went dark.

Mirrors ``DeviceWatchdog``'s shape: poll the DB → diff against the last
known state → emit one ``state_change`` event per transition + fire
Telegram. State persists in ``<data_dir>/logs/metric_freshness/state.json``
so systemd restarts don't replay alerts.

Gated on ``sensornode.last_seen``: if the whole node is stale,
``DeviceWatchdog`` handles it; we skip emission so a dead node doesn't
produce one alert per expected metric.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from dirt_shared.observability import log_event
from dirt_shared.services.readings import ReadingsService
from dirt_shared.services.telegram import TelegramClient, TelegramError

logger = logging.getLogger(__name__)

STREAM = "metric_freshness"

# Mirrors the string literals used in state.json so a stale file with
# unknown values gets dropped on load.
_VALID_STATUSES: frozenset[str] = frozenset({"fresh", "stale"})


@dataclass(frozen=True)
class MetricFreshnessConfig:
    poll_interval: int
    stale_after_s: int
    state_path: Path
    telegram_bot_token: str
    telegram_chat_id: str


@dataclass(frozen=True)
class _Transition:
    location: str
    metric: str
    old: str
    new: str
    last_seen: datetime | None


class MetricFreshnessService:
    def __init__(
        self,
        config: MetricFreshnessConfig,
        *,
        readings: ReadingsService,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        http_client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self._config = config
        self._readings = readings
        self._clock = clock
        self._http_factory = http_client_factory or (
            lambda: httpx.AsyncClient(timeout=30.0)
        )

    async def run(self, stop_event: asyncio.Event) -> None:
        cfg = self._config
        if not cfg.telegram_bot_token or not cfg.telegram_chat_id:
            logger.warning(
                "telegram_bot_token/telegram_chat_id unset — "
                "metric freshness watchdog disabled",
            )
            return

        last_known = _load_state(cfg.state_path)
        logger.info(
            "metric freshness watchdog starting: interval=%ds stale_after=%ds "
            "seeded=%s",
            cfg.poll_interval,
            cfg.stale_after_s,
            bool(last_known),
        )

        async with self._http_factory() as http:
            telegram = TelegramClient(token=cfg.telegram_bot_token, http=http)
            while not stop_event.is_set():
                try:
                    current = await self._snapshot()
                    for t in _diff(last_known, current):
                        await self._announce(telegram, t)

                    new_state = {k: s for k, (s, _) in current.items()}
                    if new_state != last_known:
                        _save_state(cfg.state_path, new_state)
                        last_known = new_state

                except Exception as exc:
                    logger.exception("metric freshness error")
                    log_event(
                        STREAM,
                        "error",
                        error_type=type(exc).__name__,
                        error=repr(exc),
                    )

                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop_event.wait(), timeout=cfg.poll_interval)

        logger.info("metric freshness watchdog stopped")

    async def _snapshot(self) -> dict[str, tuple[str, datetime | None]]:
        """Classify every (location, metric) in PERSISTED_METRICS as fresh/stale."""
        stale_cutoff = self._clock() - timedelta(seconds=self._config.stale_after_s)
        raw = await self._readings.get_metric_freshness_snapshot(stale_cutoff)
        return {f"{loc.value}:{metric}": v for (loc, metric), v in raw.items()}

    async def _announce(self, telegram: TelegramClient, t: _Transition) -> None:
        if t.new == "stale":
            age = _format_age(self._clock(), t.last_seen)
            text = (
                f"⚠ <b>{t.location}</b> metric <b>{t.metric}</b> stopped flowing "
                f"(last seen {age})"
            )
        else:
            text = f"✓ <b>{t.location}</b> metric <b>{t.metric}</b> flowing again"

        log_event(
            STREAM,
            "state_change",
            location=t.location,
            metric=t.metric,
            old=t.old,
            new=t.new,
            last_seen=t.last_seen.isoformat() if t.last_seen else None,
        )
        logger.info("metric %s/%s: %s → %s", t.location, t.metric, t.old, t.new)

        try:
            await telegram.send_message(self._config.telegram_chat_id, text)
        except TelegramError:
            logger.exception("telegram send failed for %s/%s", t.location, t.metric)


# ============================================================
# Pure helpers
# ============================================================


def _as_utc(ts: datetime) -> datetime:
    return ts if ts.tzinfo is not None else ts.replace(tzinfo=UTC)


def _diff(
    last_known: dict[str, str],
    current: dict[str, tuple[str, datetime | None]],
) -> list[_Transition]:
    """Yield transitions. Skips first-seen keys (seeding an empty state file
    after a restart should not replay alerts for metrics that were already
    stale or already fresh)."""
    out: list[_Transition] = []
    for key_id, (new, last_seen) in current.items():
        old = last_known.get(key_id)
        if old is None:
            continue
        if old == new:
            continue
        location, _, metric = key_id.partition(":")
        out.append(
            _Transition(
                location=location,
                metric=metric,
                old=old,
                new=new,
                last_seen=last_seen,
            )
        )
    return out


def _load_state(path: Path) -> dict[str, str]:
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


def _save_state(path: Path, state: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True))
    tmp.replace(path)


def _format_age(now: datetime, last_seen: datetime | None) -> str:
    if last_seen is None:
        return "never"
    last_seen = _as_utc(last_seen)
    seconds = int((now - last_seen).total_seconds())
    if seconds < 60:
        return f"{seconds}s ago"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours, rem = divmod(minutes, 60)
    return f"{hours}h ago" if rem == 0 else f"{hours}h {rem}m ago"
