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
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncEngine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Device
from dirt_shared.models.grow_run import GrowRun
from dirt_shared.models.snapshot import Snapshot
from dirt_shared.models.zone import Zone
from dirt_shared.observability import log_event
from dirt_shared.services.daily_sensors import (
    DailySensorSnapshot,
    SensorReader,
    ValidationFailure,
)
from dirt_shared.services.daily_synthesis import SynthesisResult, SynthesisRunner
from dirt_shared.services.photos import CameraClient, stamp_exif_datetime
from dirt_shared.services.scope import DEFAULT_SITE_ID, DEFAULT_TENT_ID, resolve_scope
from dirt_shared.services.telegram import (
    TELEGRAM_HTML_WHITELIST,
    TELEGRAM_MAX_MESSAGE_CHARS,
    TelegramClient,
    TelegramError,
)

logger = logging.getLogger(__name__)

# Re-export under the historical name so tests and docs still resolve it.
MAX_TELEGRAM_BODY_CHARS = TELEGRAM_MAX_MESSAGE_CHARS

# Five photos, in delivery order. Names map straight to camera presets and
# to the on-disk filenames inside `raw/photos/<DATE>/`.
PRESET_TO_FILENAME: list[tuple[str, str]] = [
    ("overview", "overview.jpg"),
    ("plant_a", "plant-a.jpg"),
    ("plant_b", "plant-b.jpg"),
    ("plant_c", "plant-c.jpg"),
    ("plant_d", "plant-d.jpg"),
]

PRESET_TO_ZONE_ID: dict[str, str] = {
    "overview": "canopy",
    "plant_a": "plant-a",
    "plant_b": "plant-b",
    "plant_c": "plant-c",
    "plant_d": "plant-d",
}


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


class SnapshotRecorder(Protocol):
    async def record_daily_report_photo(
        self,
        *,
        file_path: Path,
        preset: str,
        captured_at: datetime,
    ) -> None: ...


class DailyReportSnapshotRecorder:
    """Persist daily-report photo metadata as scoped ``snapshot`` rows."""

    def __init__(
        self,
        engine: AsyncEngine,
        *,
        site_id: str = DEFAULT_SITE_ID,
        tent_id: str = DEFAULT_TENT_ID,
        camera_device_id: str = "obsbot-main",
    ) -> None:
        self._engine = engine
        self._site_id = site_id
        self._tent_id = tent_id
        self._camera_device_id = camera_device_id

    async def record_daily_report_photo(
        self,
        *,
        file_path: Path,
        preset: str,
        captured_at: datetime,
    ) -> None:
        zone_public_id = PRESET_TO_ZONE_ID.get(preset)
        async with AsyncSession(self._engine) as session:
            scope = await resolve_scope(
                session, site_id=self._site_id, tent_id=self._tent_id
            )
            if scope is None:
                raise RuntimeError(
                    f"missing daily-report snapshot scope "
                    f"{self._site_id}/{self._tent_id}"
                )

            device = (
                await session.exec(
                    select(Device)
                    .where(Device.site_id == scope.site_pk)
                    .where(Device.device_id == self._camera_device_id)
                    .limit(1)
                )
            ).first()
            if device is None or device.id is None:
                raise RuntimeError(
                    f"missing daily-report camera device {self._camera_device_id}"
                )

            zone_id: int | None = None
            if zone_public_id is not None:
                zone_id = (
                    await session.exec(
                        select(Zone.id)
                        .where(Zone.site_id == scope.site_pk)
                        .where(Zone.tent_id == scope.tent_pk)
                        .where(Zone.zone_id == zone_public_id)
                        .limit(1)
                    )
                ).first()

            growrun_id = (
                await session.exec(
                    select(GrowRun.id)
                    .where(GrowRun.site_id == scope.site_pk)
                    .where(GrowRun.tent_id == scope.tent_pk)
                    .where(GrowRun.is_current.is_(True))
                    .limit(1)
                )
            ).first()

            path_str = str(file_path)
            snapshot = (
                await session.exec(
                    select(Snapshot).where(Snapshot.file_path == path_str).limit(1)
                )
            ).first()
            if snapshot is None:
                snapshot = Snapshot(file_path=path_str)

            snapshot.ts = captured_at
            snapshot.site_id = scope.site_pk
            snapshot.tent_id = scope.tent_pk
            snapshot.zone_id = zone_id
            snapshot.device_id = device.id
            snapshot.growrun_id = growrun_id
            snapshot.view_id = preset
            snapshot.kind = "daily_report"
            session.add(snapshot)
            await session.commit()


class DailyReport:
    def __init__(  # noqa: PLR0913 — orchestrator collaborators wired from the composition root; a deps dataclass would just move the same count behind an extra indirection.
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
        stamp_jpeg: Callable[[bytes, datetime], bytes] = stamp_exif_datetime,
        snapshot_recorder: SnapshotRecorder | None = None,
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
        self._stamp_jpeg = stamp_jpeg
        self._snapshot_recorder = snapshot_recorder

    # --- public entrypoints ---

    async def run(self, target_date: date, *, force: bool = False) -> RunResult:
        """Run the full pipeline for ``target_date``. Returns RunResult."""
        completed_marker = self._marker_dir / f"{target_date.isoformat()}.completed"
        failed_marker = self._marker_dir / f"{target_date.isoformat()}.failed"

        if completed_marker.exists() and not force:
            logger.info("already completed %s — pass --force to re-run", target_date)
            return RunResult(success=True, failed_phase=None, error=None)

        # Clear stale failure marker if re-running
        if failed_marker.exists():
            failed_marker.unlink(missing_ok=True)

        log_event(
            "daily_report", "run_started", date=target_date.isoformat(), force=force
        )

        try:
            photos = await self._phase_capture(target_date)
            await self._phase_validate()
            snapshot = await self._phase_snapshot(target_date)
            synth = await self._phase_synthesize(target_date, photos, snapshot)
            await self._phase_deliver(target_date, photos, synth)
        except _Bail as e:
            self._marker_dir.mkdir(parents=True, exist_ok=True)
            failed_marker.write_text(f"{e.phase.value}\n{e.message}\n")
            log_event(
                "daily_report",
                "run_failed",
                date=target_date.isoformat(),
                phase=e.phase.value,
                error=e.message,
            )
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
                captured_at = self._clock()
                stamped = self._stamp_jpeg(jpeg, captured_at)
            except Exception as e:
                raise _Bail(
                    Phase.CAPTURE,
                    f"EXIF stamping failed for {preset!r}: {e}",
                ) from e
            path = out_dir / filename
            path.write_bytes(stamped)
            if self._snapshot_recorder is not None:
                try:
                    await self._snapshot_recorder.record_daily_report_photo(
                        file_path=path,
                        preset=preset,
                        captured_at=captured_at,
                    )
                except Exception as e:
                    raise _Bail(
                        Phase.CAPTURE,
                        f"snapshot record failed for preset {preset!r}: {e}",
                    ) from e
            photos.append(path)
            logger.info("captured %s -> %s", preset, path)

        log_event(
            "daily_report",
            "capture_finished",
            date=target_date.isoformat(),
            photo_count=len(photos),
        )
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
        log_event("daily_report", "snapshot_finished", date=target_date.isoformat())
        return snap

    async def _phase_synthesize(
        self,
        target_date: date,
        photos: Sequence[Path],
        snapshot: DailySensorSnapshot,
    ) -> SynthesisResult:
        try:
            result = await self._synthesis.run(
                target_date, photos, snapshot.to_prompt_dict()
            )
        except Exception as e:
            raise _Bail(
                Phase.SYNTHESIZE,
                f"synthesis crashed: {type(e).__name__}: {e}",
            ) from e
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
        self,
        target_date: date,
        photos: Sequence[Path],
        synth: SynthesisResult,
    ) -> None:
        # Telegram failures are NON-fatal — wiki is the durable record.
        # Log and continue to mark the run completed.
        try:
            caption = self._format_caption(target_date, synth)
            body_html = _load_telegram_body(synth.telegram_html_path)
            await self._telegram.send_media_group(
                self._chat_id,
                list(photos),
                caption=caption,
            )
            if body_html is None:
                log_event(
                    "daily_report",
                    "deliver_finished",
                    date=target_date.isoformat(),
                    via="telegram",
                    body_sent=False,
                    body_missing=True,
                )
                logger.warning(
                    "no telegram sidecar for %s — delivered photos only",
                    target_date.isoformat(),
                )
                return
            await self._telegram.send_message(
                self._chat_id,
                body_html,
                parse_mode="HTML",
            )
            log_event(
                "daily_report",
                "deliver_finished",
                date=target_date.isoformat(),
                via="telegram",
                body_sent=True,
            )
        except (TelegramError, OSError, ValueError) as e:
            logger.exception("telegram delivery failed (non-fatal)")
            log_event(
                "daily_report",
                "deliver_failed",
                date=target_date.isoformat(),
                error=str(e),
            )

    # --- failure / formatting helpers ---

    async def _send_failure(
        self,
        target_date: date,
        phase: Phase,
        message: str,
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
                self._chat_id,
                text,
                parse_mode="HTML",
            )
        except Exception:
            logger.exception("could not send failure alert to telegram")

    def _format_validation_failures(
        self,
        failures: list[ValidationFailure],
    ) -> str:
        lines = []
        for f in failures:
            val = "?" if f.value is None else f"{f.value:.2f}"
            age = "?" if f.age_s is None else f"{f.age_s:.0f}s"
            lines.append(
                f"{f.subject}/{f.metric}: value={val} age={age} reason={f.reason}"
            )
        return "; ".join(lines)

    def _format_caption(
        self,
        target_date: date,
        synth: SynthesisResult,
    ) -> str:
        # Keep under 1024 chars (Telegram album caption hard limit).
        return (
            f"<b>Daily Report — {html.escape(target_date.isoformat())}</b>\n"
            "Plants A-D + overview"
        )


# --- Telegram body loader (reads the sub-agent's sidecar file) ---


def _load_telegram_body(sidecar: Path | None) -> str | None:
    """Read the Telegram-ready HTML from the sidecar, applying defensive
    cleanup. Returns None when the file is absent or empty so the
    orchestrator can deliver photos-only."""
    if sidecar is None:
        return None
    try:
        text = sidecar.read_text().strip()
    except FileNotFoundError:
        return None
    except OSError:
        logger.exception("could not read telegram sidecar %s", sidecar)
        return None
    if not text:
        return None
    text = _safe_truncate_html(text, MAX_TELEGRAM_BODY_CHARS)
    text = _strip_trailing_partial_tag(text)
    return balance_html_tags(text)


def _safe_truncate_html(text: str, max_chars: int) -> str:
    """Truncate at the last paragraph break below ``max_chars`` rather
    than at a byte offset that could land mid-tag."""
    if len(text) <= max_chars:
        return text
    cut = text.rfind("\n\n", 0, max_chars)
    if cut == -1:
        cut = max_chars
    return text[:cut].rstrip() + "\n\n<i>... truncated; full report in the wiki.</i>"


def _strip_trailing_partial_tag(text: str) -> str:
    """Remove a trailing ``<foo`` with no matching ``>`` — protects
    Telegram's HTML parser from the mid-tag truncation class of bug."""
    last_lt = text.rfind("<")
    last_gt = text.rfind(">")
    if last_lt > last_gt:
        return text[:last_lt].rstrip()
    return text


def balance_html_tags(s: str) -> str:
    """Append closing tags for any unclosed Telegram-whitelisted tags.

    Belt-and-suspenders: the sub-agent writes complete HTML, but if a
    truncation trimmed partway through a nested region, pair up opens and
    closes count-wise so Telegram's parser doesn't reject the message with
    "Can't find end tag corresponding to start tag".
    """
    closers: list[str] = []
    for tag in TELEGRAM_HTML_WHITELIST:
        opens = len(re.findall(rf"<{tag}\b[^>]*>", s))
        closes = len(re.findall(rf"</{tag}>", s))
        closers.extend([f"</{tag}>"] * (opens - closes))
    if not closers:
        return s
    return s + "".join(reversed(closers))
