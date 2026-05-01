"""Ingest-time sensor quality guardrails.

Rejects values that are physically impossible before they become dashboard
readings, while alerting only on bad<->ok transitions. State is persisted so a
service restart during an active fault does not replay Telegram alerts every
30 seconds.
"""

from __future__ import annotations

import html
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx

from dirt_shared.observability import log_event
from dirt_shared.services.telegram import TelegramClient, TelegramError

logger = logging.getLogger(__name__)

STREAM = "sensor_quality"

RESERVOIR_LOCATION = "reservoir"
RESERVOIR_METRICS = frozenset({"reservoir_pressure_raw", "reservoir_in"})

# Firmware calibration says dry-air zero is raw ~= 18540 and the probe's
# published depth bottoms out around 0.79 in. Anything materially below this
# is not "empty reservoir"; it is an analog-chain/loop fault.
RESERVOIR_RAW_MIN = 17_000.0
RESERVOIR_RAW_MAX = 30_000.0
RESERVOIR_IN_MIN = 0.0
RESERVOIR_IN_MAX = 40.0

_VALID_STATES = frozenset({"ok", "bad"})


@dataclass(frozen=True)
class SensorQualityConfig:
    state_path: Path
    telegram_bot_token: str
    telegram_chat_id: str


@dataclass(frozen=True)
class QualityDecision:
    metrics: dict[str, float]
    rejected: frozenset[str]
    reasons: tuple[str, ...]


class SensorQualityService:
    def __init__(
        self,
        config: SensorQualityConfig,
        *,
        http_client_factory: Callable[[], httpx.AsyncClient] | None = None,
    ) -> None:
        self._config = config
        self._http_factory = http_client_factory or (
            lambda: httpx.AsyncClient(timeout=30.0)
        )

    async def filter_metrics(
        self, location: str, metrics: dict[str, float]
    ) -> QualityDecision:
        """Return metrics safe to persist, alerting on quality transitions."""
        decision = evaluate_metrics(location, metrics)
        await self._record_transition(location, metrics, decision)
        if decision.rejected:
            log_event(
                STREAM,
                "rejected",
                location=location,
                rejected=sorted(decision.rejected),
                reasons=list(decision.reasons),
                metrics=metrics,
            )
        return decision

    async def _record_transition(
        self,
        location: str,
        metrics: dict[str, float],
        decision: QualityDecision,
    ) -> None:
        if location != RESERVOIR_LOCATION:
            return

        key = RESERVOIR_LOCATION
        state = _load_state(self._config.state_path)
        old = state.get(key)
        new = "bad" if decision.rejected else "ok"
        if old == new:
            return

        state[key] = new
        _save_state(self._config.state_path, state)

        log_event(
            STREAM,
            "state_change",
            location=location,
            old=old,
            new=new,
            rejected=sorted(decision.rejected),
            reasons=list(decision.reasons),
            metrics=metrics,
        )

        if old is None and new == "ok":
            return
        await self._send_transition(location, metrics, decision, old=old, new=new)

    async def _send_transition(
        self,
        location: str,
        metrics: dict[str, float],
        decision: QualityDecision,
        *,
        old: str | None,
        new: str,
    ) -> None:
        if not self._config.telegram_bot_token or not self._config.telegram_chat_id:
            logger.info("telegram creds unset — sensor-quality alert log-only")
            return

        if new == "bad":
            text = _bad_message(location, metrics, decision.reasons)
        else:
            text = _recovered_message(location, metrics, old)

        try:
            async with self._http_factory() as http:
                telegram = TelegramClient(
                    token=self._config.telegram_bot_token,
                    http=http,
                )
                await telegram.send_message(self._config.telegram_chat_id, text)
        except TelegramError:
            logger.exception("telegram send failed for sensor-quality alert")


def evaluate_metrics(location: str, metrics: dict[str, float]) -> QualityDecision:
    if location != RESERVOIR_LOCATION:
        return QualityDecision(metrics=dict(metrics), rejected=frozenset(), reasons=())

    reasons = _reservoir_reasons(metrics)
    if not reasons:
        return QualityDecision(metrics=dict(metrics), rejected=frozenset(), reasons=())

    # The depth value is derived from the raw pressure reading in firmware; if
    # either side is physically impossible, keep both out of the fact table.
    rejected = RESERVOIR_METRICS & metrics.keys()
    accepted = {k: v for k, v in metrics.items() if k not in rejected}
    return QualityDecision(
        metrics=accepted,
        rejected=frozenset(rejected),
        reasons=tuple(reasons),
    )


def _reservoir_reasons(metrics: dict[str, float]) -> list[str]:
    reasons: list[str] = []
    raw = metrics.get("reservoir_pressure_raw")
    depth = metrics.get("reservoir_in")

    if raw is not None and raw < RESERVOIR_RAW_MIN:
        reasons.append(
            f"raw pressure {raw:.0f} below alive floor {RESERVOIR_RAW_MIN:.0f}"
        )
    elif raw is not None and raw > RESERVOIR_RAW_MAX:
        reasons.append(
            f"raw pressure {raw:.0f} above plausible ceiling {RESERVOIR_RAW_MAX:.0f}"
        )

    if depth is not None and depth < RESERVOIR_IN_MIN:
        reasons.append(f"depth {depth:.2f} in below 0")
    elif depth is not None and depth > RESERVOIR_IN_MAX:
        reasons.append(
            f"depth {depth:.2f} in above plausible ceiling {RESERVOIR_IN_MAX:.0f}"
        )

    return reasons


def _bad_message(
    location: str, metrics: dict[str, float], reasons: tuple[str, ...]
) -> str:
    raw = metrics.get("reservoir_pressure_raw")
    depth = metrics.get("reservoir_in")
    parts = [
        f"⚠ <b>{html.escape(location)}</b> sensor data rejected",
        _format_metric_line(raw, depth),
        "Reason: " + "; ".join(html.escape(r) for r in reasons),
        "Likely cause: reservoir sensor loop unplugged or analog signal fault.",
    ]
    return "\n".join(parts)


def _recovered_message(
    location: str, metrics: dict[str, float], old: str | None
) -> str:
    raw = metrics.get("reservoir_pressure_raw")
    depth = metrics.get("reservoir_in")
    prefix = "✓" if old == "bad" else "ℹ"
    return "\n".join(
        [
            f"{prefix} <b>{html.escape(location)}</b> sensor data looks valid again",
            _format_metric_line(raw, depth),
        ]
    )


def _format_metric_line(raw: float | None, depth: float | None) -> str:
    raw_text = "unknown" if raw is None else f"{raw:.0f}"
    depth_text = "unknown" if depth is None else f"{depth:.2f} in"
    return f"raw={html.escape(raw_text)} depth={html.escape(depth_text)}"


def _load_state(path: Path) -> dict[str, str]:
    try:
        raw = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {
        str(k): v for k, v in raw.items() if isinstance(v, str) and v in _VALID_STATES
    }


def _save_state(path: Path, state: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, sort_keys=True))
    tmp.replace(path)
