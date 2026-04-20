"""Daily-report orchestrator.

Five sequential phases — capture photos, validate sensors, build the
windowed sensor snapshot, run the synthesis sub-agent, deliver to
Telegram. The orchestrator takes its camera, sensor reader, synthesis
runner, and telegram client by injection so the whole pipeline can be
exercised against fakes in tests without monkeypatching.

Marker files in ``logs/daily_report/<DATE>.{completed,failed}`` give
idempotency: re-running the same date without ``--force`` exits early.
"""

from __future__ import annotations

import html
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from dirt_shared.observability import log_event
from dirt_shared.services.daily_sensors import (
    DailySensorSnapshot,
    SensorReader,
    ValidationFailure,
)
from dirt_shared.services.daily_synthesis import SynthesisResult, SynthesisRunner
from dirt_shared.services.photos import CameraClient, stamp_exif_datetime
from dirt_shared.services.telegram import TelegramClient, TelegramError

logger = logging.getLogger(__name__)

# Telegram message body soft cap. Bot API hard cap is 4096; we leave headroom
# for the trailing "see wiki for full report" link.
MAX_TELEGRAM_BODY_CHARS = 3500

# Five photos, in delivery order. Names map straight to camera presets and
# to the on-disk filenames inside `raw/photos/<DATE>/`.
PRESET_TO_FILENAME: list[tuple[str, str]] = [
    ("overview", "overview.jpg"),
    ("plant_a", "plant-a.jpg"),
    ("plant_b", "plant-b.jpg"),
    ("plant_c", "plant-c.jpg"),
    ("plant_d", "plant-d.jpg"),
]


class Phase(StrEnum):
    CAPTURE = "capture"
    VALIDATE = "validate"
    SNAPSHOT = "snapshot"
    SYNTHESIZE = "synthesize"
    DELIVER = "deliver"


@dataclass(frozen=True)
class RunResult:
    success: bool
    failed_phase: Phase | None
    error: str | None


class _Bail(Exception):
    """Internal: a phase failed and we should send the failure alert + exit."""
    def __init__(self, phase: Phase, message: str):
        super().__init__(f"{phase.value}: {message}")
        self.phase = phase
        self.message = message


class _Clock(Protocol):
    def __call__(self) -> datetime: ...


class DailyReport:
    def __init__(
        self,
        *,
        camera: CameraClient,
        sensor_reader: SensorReader,
        synthesis: SynthesisRunner,
        telegram: TelegramClient,
        telegram_chat_id: str,
        photos_dir: Path,
        marker_dir: Path,
        wiki_root: Path,
        clock: _Clock = lambda: datetime.now(UTC),
    ) -> None:
        if not telegram_chat_id:
            raise ValueError("telegram_chat_id is required")
        self._camera = camera
        self._reader = sensor_reader
        self._synthesis = synthesis
        self._telegram = telegram
        self._chat_id = telegram_chat_id
        self._photos_root = photos_dir
        self._marker_dir = marker_dir
        self._wiki_root = wiki_root
        self._clock = clock

    # --- public entrypoints ---

    async def run(self, target_date: date, *, force: bool = False) -> RunResult:
        """Run the full pipeline for ``target_date``. Returns RunResult."""
        completed_marker = self._marker_dir / f"{target_date.isoformat()}.completed"
        failed_marker = self._marker_dir / f"{target_date.isoformat()}.failed"

        if completed_marker.exists() and not force:
            logger.info("already completed %s — pass --force to re-run",
                        target_date)
            return RunResult(success=True, failed_phase=None, error=None)

        # Clear stale failure marker if re-running
        if failed_marker.exists():
            failed_marker.unlink(missing_ok=True)

        log_event("daily_report", "run_started",
                  date=target_date.isoformat(), force=force)

        try:
            photos = await self._phase_capture(target_date)
            await self._phase_validate()
            snapshot = await self._phase_snapshot(target_date)
            synth = await self._phase_synthesize(target_date, photos, snapshot)
            await self._phase_deliver(target_date, photos, synth)
        except _Bail as e:
            self._marker_dir.mkdir(parents=True, exist_ok=True)
            failed_marker.write_text(f"{e.phase.value}\n{e.message}\n")
            log_event("daily_report", "run_failed",
                      date=target_date.isoformat(),
                      phase=e.phase.value, error=e.message)
            await self._send_failure(target_date, e.phase, e.message)
            return RunResult(success=False, failed_phase=e.phase, error=e.message)

        self._marker_dir.mkdir(parents=True, exist_ok=True)
        completed_marker.write_text(self._clock().isoformat())
        log_event("daily_report", "run_completed", date=target_date.isoformat())
        return RunResult(success=True, failed_phase=None, error=None)

    # --- phases ---

    async def _phase_capture(self, target_date: date) -> list[Path]:
        """Pan to each preset, capture, EXIF-stamp, save under
        ``raw/photos/<DATE>/<preset>.jpg``. Bail on first failure.
        """
        out_dir = self._photos_root / target_date.isoformat()
        out_dir.mkdir(parents=True, exist_ok=True)
        photos: list[Path] = []

        for preset, filename in PRESET_TO_FILENAME:
            try:
                jpeg = await self._camera.capture_at(preset)
            except Exception as e:  # CameraError or anything else
                raise _Bail(
                    Phase.CAPTURE,
                    f"capture failed at preset {preset!r}: {e}",
                ) from e
            try:
                stamped = stamp_exif_datetime(jpeg, self._clock())
            except Exception as e:
                raise _Bail(
                    Phase.CAPTURE,
                    f"EXIF stamping failed for {preset!r}: {e}",
                ) from e
            path = out_dir / filename
            path.write_bytes(stamped)
            photos.append(path)
            logger.info("captured %s -> %s", preset, path)

        log_event("daily_report", "capture_finished",
                  date=target_date.isoformat(), photo_count=len(photos))
        return photos

    async def _phase_validate(self) -> None:
        failures = await self._reader.validate()
        if not failures:
            log_event("daily_report", "validate_finished", failure_count=0)
            return
        msg = self._format_validation_failures(failures)
        raise _Bail(Phase.VALIDATE, msg)

    async def _phase_snapshot(self, target_date: date) -> DailySensorSnapshot:
        snap = await self._reader.snapshot(target_date)
        log_event("daily_report", "snapshot_finished",
                  date=target_date.isoformat())
        return snap

    async def _phase_synthesize(
        self, target_date: date, photos: Sequence[Path],
        snapshot: DailySensorSnapshot,
    ) -> SynthesisResult:
        result = await self._synthesis.run(
            target_date, photos, snapshot.to_prompt_dict()
        )
        if not result.success:
            raise _Bail(
                Phase.SYNTHESIZE,
                f"synthesis failed: {result.error}",
            )
        if result.daily_file is None or not result.daily_file.exists():
            raise _Bail(
                Phase.SYNTHESIZE,
                "synthesis returned success but daily file missing",
            )
        return result

    async def _phase_deliver(
        self, target_date: date, photos: Sequence[Path],
        synth: SynthesisResult,
    ) -> None:
        # Telegram failures are NON-fatal — wiki is the durable record.
        # Log and continue to mark the run completed.
        try:
            caption = self._format_caption(target_date, synth)
            assert synth.daily_file is not None  # noqa: S101  phase_synthesize guarantees
            body_html = self._format_body(synth.daily_file)
            await self._telegram.send_media_group(
                self._chat_id, list(photos), caption=caption,
            )
            await self._telegram.send_message(
                self._chat_id, body_html, parse_mode="HTML",
            )
            log_event("daily_report", "deliver_finished",
                      date=target_date.isoformat(), via="telegram")
        except (TelegramError, OSError, ValueError) as e:
            logger.exception("telegram delivery failed (non-fatal)")
            log_event("daily_report", "deliver_failed",
                      date=target_date.isoformat(), error=str(e))

    # --- failure / formatting helpers ---

    async def _send_failure(
        self, target_date: date, phase: Phase, message: str,
    ) -> None:
        try:
            text = (
                f"<b>⚠ Daily report failed</b>\n"
                f"Date: {html.escape(target_date.isoformat())} "
                f"({html.escape(self._clock().strftime('%H:%M %Z'))})\n"
                f"Phase: <code>{html.escape(phase.value)}</code>\n\n"
                f"<pre>{html.escape(message)[:1500]}</pre>\n\n"
                "Check <code>journalctl --user -u dirt-daily-report</code> "
                "for full context."
            )
            await self._telegram.send_message(
                self._chat_id, text, parse_mode="HTML",
            )
        except Exception:
            logger.exception("could not send failure alert to telegram")

    def _format_validation_failures(
        self, failures: list[ValidationFailure],
    ) -> str:
        lines = []
        for f in failures:
            val = "?" if f.value is None else f"{f.value:.2f}"
            age = "?" if f.age_s is None else f"{f.age_s:.0f}s"
            lines.append(
                f"{f.location}/{f.metric}: value={val} age={age} "
                f"reason={f.reason}"
            )
        return "; ".join(lines)

    def _format_caption(
        self, target_date: date, synth: SynthesisResult,
    ) -> str:
        # Keep under 1024 chars (Telegram album caption hard limit).
        return (
            f"<b>Daily Report — {html.escape(target_date.isoformat())}</b>\n"
            "Plants A-D + overview"
        )

    def _format_body(self, daily_file: Path) -> str:
        try:
            md = daily_file.read_text()
        except OSError as e:
            return f"<i>Could not read daily file: {html.escape(str(e))}</i>"
        body_html = markdown_to_simple_html(md)
        if len(body_html) > MAX_TELEGRAM_BODY_CHARS:
            body_html = (
                body_html[:MAX_TELEGRAM_BODY_CHARS]
                + "\n\n<i>... truncated; full report in the wiki.</i>"
            )
        return balance_html_tags(body_html)


_BALANCEABLE_TAGS = ("pre", "code", "b", "i", "u", "s")


def balance_html_tags(s: str) -> str:
    """Append closing tags for any unclosed Telegram-whitelisted tags.

    Truncating the body in the middle of a `<pre>...</pre>` block produces
    "Bad Request: Can't find end tag corresponding to start tag" from
    Telegram. Conservatively balance: for each tag in
    :data:`_BALANCEABLE_TAGS`, count opens vs closes and append one
    ``</tag>`` per surplus open. Order is best-effort (count-based scheme
    can't perfectly recover nesting), but Telegram's HTML parser is
    permissive enough that this clears the validation.
    """
    closers: list[str] = []
    for tag in _BALANCEABLE_TAGS:
        opens = len(re.findall(rf"<{tag}\b[^>]*>", s))
        closes = len(re.findall(rf"</{tag}>", s))
        for _ in range(opens - closes):
            closers.append(f"</{tag}>")
    if not closers:
        return s
    return s + "".join(reversed(closers))


# --- pure helpers (testable in isolation) ---

_FRONTMATTER_RE = re.compile(r"^---\n.*?\n---\n", re.DOTALL)


def markdown_to_simple_html(md: str) -> str:
    """Convert a subset of markdown to Telegram-flavoured HTML.

    Telegram's HTML mode supports a small whitelist:
    ``<b>``, ``<i>``, ``<u>``, ``<s>``, ``<code>``, ``<pre>``, ``<a>``.
    No headers, no lists, no tables. We map ``# heading`` to ``<b>``,
    strip frontmatter, convert ``**bold**`` and ``*italic*`` and inline
    ``` `code` ``` to their HTML equivalents, and pass tables through as
    monospace ``<pre>`` blocks (preserves alignment in mobile fonts).

    Everything not on the whitelist is HTML-escaped to keep Telegram from
    rejecting the message.
    """
    md = _FRONTMATTER_RE.sub("", md, count=1)

    out_lines: list[str] = []
    in_code_block = False
    code_lang = ""
    code_buffer: list[str] = []
    in_table = False
    table_buffer: list[str] = []

    def flush_table() -> None:
        nonlocal in_table, table_buffer
        if table_buffer:
            out_lines.append(
                "<pre>" + html.escape("\n".join(table_buffer)) + "</pre>"
            )
        table_buffer = []
        in_table = False

    def flush_code() -> None:
        nonlocal in_code_block, code_buffer, code_lang
        if code_buffer:
            out_lines.append(
                "<pre>" + html.escape("\n".join(code_buffer)) + "</pre>"
            )
        code_buffer = []
        code_lang = ""
        in_code_block = False

    for raw in md.splitlines():
        if raw.strip().startswith("```"):
            if in_code_block:
                flush_code()
            else:
                in_code_block = True
                code_lang = raw.strip().removeprefix("```").strip()
            continue
        if in_code_block:
            code_buffer.append(raw)
            continue

        # Tables: any line with `|` and a non-blank rest counts as a row.
        if "|" in raw and raw.strip():
            in_table = True
            table_buffer.append(raw)
            continue
        if in_table:
            flush_table()

        # Headings -> <b>
        if raw.startswith("#"):
            text = raw.lstrip("#").strip()
            out_lines.append(f"<b>{html.escape(text)}</b>")
            continue

        # Inline transforms on plain lines
        line = html.escape(raw)
        # `code`
        line = re.sub(r"`([^`]+)`", r"<code>\1</code>", line)
        # **bold** (greedy non-newline)
        line = re.sub(r"\*\*([^*\n]+)\*\*", r"<b>\1</b>", line)
        # _italic_ (only when bracketed by spaces/punct, to avoid mangling
        # snake_case identifiers — keep it simple: require leading whitespace
        # or start-of-line, trailing whitespace/punctuation)
        line = re.sub(
            r"(^|\s)_([^_\n]+)_(?=\s|[.,;:!?]|$)", r"\1<i>\2</i>", line
        )
        out_lines.append(line)

    if in_code_block:
        flush_code()
    if in_table:
        flush_table()

    # Collapse runs of >2 blank lines
    text = "\n".join(out_lines)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
