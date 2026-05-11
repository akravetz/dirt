"""Shared structured-logging primitives for operational instrumentation.

Splits "logs" into two families with different contracts:

- ``sessions/<channel>/YYYY-MM-DD.jsonl`` — user-facing conversation records
  (what was said / what the agent did). Long-lived. Owned by each channel.
- ``logs/<stream>/YYYY-MM-DD.jsonl`` (this module) — operational
  instrumentation (wake scores, audio amplitude, sub-agent traces, etc.).
  Short retention by default, configurable per stream.

Every event is a single JSONL line with a common envelope:

    {"ts": "...", "conversation_id": "...", "stream": "...", "event": "...", ...}

Use :data:`CONVERSATION_ID` (a :class:`contextvars.ContextVar`) in the
channel's entry point so events fired during one user interaction are
correlated. See ``src/dirt/channels/voice.py:main`` for the pattern.
"""

from __future__ import annotations

import contextvars
import json
import os
import queue
import threading
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger

# Env-var override for `logs_dir()`. Tests set this (via the autouse fixture
# in `tests/conftest.py`) so a passing or crashing test never writes to the
# production telemetry directory. Production sets it from the composition
# root (e.g. ``os.environ.setdefault(LOGS_DIR_ENV, str(settings.data_dir / "logs"))``).
LOGS_DIR_ENV = "DIRT_LOGS_DIR"

# Fallback if neither env nor caller has set anything: <repo>/var/logs.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_LOGS_DIR = _REPO_ROOT / "var" / "logs"


def logs_dir() -> Path:
    """Where stream JSONL files land. Reads ``DIRT_LOGS_DIR`` on every call so
    test fixtures can swap it via :func:`os.environ` (or pytest's
    ``monkeypatch.setenv``) without restarting the process or touching the
    writer thread.

    Production: the composition root sets ``DIRT_LOGS_DIR`` once at startup
    from ``Settings.data_dir``. This is the env-var-authoritative model
    documented in ``docs/proposals/singleton-retirement.md`` §5.
    """
    env = os.environ.get(LOGS_DIR_ENV)
    return Path(env) if env else _DEFAULT_LOGS_DIR


# Backwards-compat alias — some external code may still reference this. New
# call sites should call :func:`logs_dir` so the env-var override works.
LOGS_DIR = _DEFAULT_LOGS_DIR

# Per-stream retention in days. Streams not listed inherit DEFAULT_RETENTION_DAYS.
# Keep the window short for high-volume instrumentation; a day of data is
# plenty for almost all debugging, and rotation is cheap when we run it.
DEFAULT_RETENTION_DAYS = 1
_RETENTION: dict[str, int] = {
    "wake_scores": 1,  # every wake-word score above WAKE_NEAR_MISS_FLOOR
    "audio_rms": 1,  # input amplitude trace, ~1 Hz
    "audio_playback": 1,  # per-turn TTS-vs-playback duration metric
    "pipecat_frames": 1,  # all pipecat control/signal frames
    "subagent_calls": 10,  # sub-agent traces — higher value, lower volume
    "humidifier": 30,  # plug state transitions — rare, useful for incident review
    # per-tick PI controller shadow output (Phase 4 prep) — high volume;
    # 14d covers tuning workflow without filling disk
    "humidifier_shadow": 14,
    "lights": 30,  # lights plug state transitions — twice-daily
    "fan_controller": 30,  # fan trim ticks + duty transitions
    "daily_report": 30,  # per-phase markers for the daily report run
    "device_status": 30,  # offline/online transitions from the device watchdog
    "metric_freshness": 30,  # per-(location, metric) dropout transitions
    "sensor_quality": 30,  # invalid sensor payload rejection/recovery transitions
    "cloud_gateway": 30,  # outbound hosted control-plane sync lifecycle
    "camera_agent": 30,  # edge camera capture/upload lifecycle
}


CONVERSATION_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "observability_conversation_id", default=None
)


def _rotate(stream_dir: Path, keep_days: int) -> None:
    """Delete stream JSONL files older than ``keep_days`` by filename date.

    Uses the ``YYYY-MM-DD.jsonl`` naming rather than filesystem mtime —
    deterministic and decoupled from clock/timezone quirks.
    """
    cutoff = date.today() - timedelta(days=keep_days)
    for path in stream_dir.glob("*.jsonl"):
        try:
            file_date = date.fromisoformat(path.stem)
        except ValueError:
            continue
        if file_date < cutoff:
            path.unlink(missing_ok=True)


def _log_path(stream: str) -> Path:
    return logs_dir() / stream / f"{datetime.now(UTC).strftime('%Y-%m-%d')}.jsonl"


# All writes happen on one background thread so the hot path stays
# microseconds. High-volume callers (pipecat observer, portaudio callbacks)
# would otherwise block on file I/O inside the audio loop.
_QUEUE_MAX = 10_000
_WriteItem = tuple[str, dict[str, Any]] | None
_write_queue: queue.Queue[_WriteItem] = queue.Queue(maxsize=_QUEUE_MAX)
_dropped_since_warn = 0
_writer_started = False
_writer_lock = threading.Lock()


def _writer_loop() -> None:
    """Drain `_write_queue` and append events to disk. Runs on one daemon
    thread. Handles rotation on first write of the day per stream."""
    rotated_today: set[str] = set()
    while True:
        item = _write_queue.get()
        if item is None:
            return  # sentinel, currently unused (daemon dies with process)
        stream, envelope = item
        try:
            path = _log_path(stream)
            # Keying on full path (not just stream:filename) so per-test
            # tmp directories rotate independently and a test changing
            # DIRT_LOGS_DIR mid-process doesn't reuse the prior dir's
            # rotation cache entry.
            key = str(path)
            if key not in rotated_today:
                stream_dir = path.parent
                stream_dir.mkdir(parents=True, exist_ok=True)
                _rotate(stream_dir, _RETENTION.get(stream, DEFAULT_RETENTION_DAYS))
                rotated_today.add(key)
            with path.open("a") as f:
                f.write(json.dumps(envelope, ensure_ascii=False) + "\n")
        except Exception:
            # Don't let the writer thread die — log-write failures are not
            # critical and must not propagate into the caller's hot path.
            logger.exception(f"observability writer failed for stream={stream}")


def _ensure_writer() -> None:
    """Lazily start the writer thread on first call. Cheap re-entry."""
    global _writer_started
    if _writer_started:
        return
    with _writer_lock:
        if _writer_started:
            return
        threading.Thread(
            target=_writer_loop,
            name="observability-writer",
            daemon=True,
        ).start()
        _writer_started = True


def log_event(
    stream: str,
    event: str,
    *,
    conversation_id: str | None = None,
    **fields: Any,
) -> None:
    """Enqueue one JSONL event for ``logs/<stream>/<today>.jsonl``.

    Returns in microseconds — the actual disk write happens on a daemon
    thread. Callable from asyncio code, portaudio C-thread callbacks, and
    anywhere else; never blocks the caller.

    Args:
        stream: Named log stream (e.g. ``"wake_scores"``, ``"audio_rms"``,
            ``"pipecat_frames"``, ``"subagent_calls"``). Determines the
            directory and retention.
        event: Short event-type tag for grepping
            (e.g. ``"wake_detected"``, ``"near_miss"``, ``"rms"``).
        conversation_id: Optional explicit override. Useful when the caller
            runs outside the channel's asyncio context and can't rely on the
            :data:`CONVERSATION_ID` ContextVar (e.g. a portaudio C-thread
            callback — the ContextVar isn't propagated there).
        **fields: JSON-serializable fields merged into the envelope.

    On queue overflow (>10k events backlogged — should never happen under
    normal load) events are dropped and a periodic warning is logged.
    """
    global _dropped_since_warn
    _ensure_writer()

    cid = conversation_id if conversation_id is not None else CONVERSATION_ID.get()
    envelope = {
        "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
        "conversation_id": cid,
        "stream": stream,
        "event": event,
        **fields,
    }
    try:
        _write_queue.put_nowait((stream, envelope))
    except queue.Full:
        # Queue backlog is a sign the writer is wedged or we're producing
        # events absurdly fast. Drop, count, warn periodically rather than
        # block the caller.
        _dropped_since_warn += 1
        if _dropped_since_warn == 1 or _dropped_since_warn % 1000 == 0:
            logger.warning(
                f"observability queue full, dropped {_dropped_since_warn} events"
            )
