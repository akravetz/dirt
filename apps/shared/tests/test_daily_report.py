"""Orchestrator tests — every external dependency injected as a fake.

Covers the failure → telegram alert → exit-non-zero branches plus the
happy-path delivery, the markdown→HTML helper, and idempotency via the
marker file.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Device
from dirt_shared.models.snapshot import Snapshot
from dirt_shared.models.tent import Tent
from dirt_shared.models.zone import Zone
from dirt_shared.services.daily_report import (
    MAX_TELEGRAM_BODY_CHARS,
    DailyReport,
    DailyReportSnapshotRecorder,
    Phase,
    _load_telegram_body,
    _safe_truncate_html,
    _strip_trailing_partial_tag,
    balance_html_tags,
)
from dirt_shared.services.daily_sensors import (
    DailySensorSnapshot,
    ValidationFailure,
    WindowAvg,
)
from dirt_shared.services.daily_synthesis import SynthesisResult

# --- shared fixtures ---


def _tiny_jpeg() -> bytes:
    return b"\xff\xd8\xff\xe0fake-daily-report-image"


# 14:30 MDT -> 20:30 UTC on Apr 19 2026
NOW = datetime(2026, 4, 19, 20, 30, 0, tzinfo=UTC)
TARGET_DATE = date(2026, 4, 19)


def _clock() -> datetime:
    return NOW


class _FakeCamera:
    """CameraClient stand-in. Records preset list, returns a real JPEG."""

    def __init__(self, jpeg: bytes | None = None):
        self.jpeg = jpeg or _tiny_jpeg()
        self.calls: list[str] = []
        self.raise_on: str | None = None
        self.raise_on_many: set[str] = set()

    async def capture_at(self, preset: str) -> bytes:
        self.calls.append(preset)
        if self.raise_on == preset or preset in self.raise_on_many:
            from dirt_shared.services.photos import CameraError

            raise CameraError(f"injected failure at {preset}")
        return self.jpeg


class _FakeSensorReader:
    def __init__(
        self,
        *,
        failures: list[ValidationFailure] | None = None,
        snapshot: DailySensorSnapshot | None = None,
    ) -> None:
        self.failures = failures or []
        self._snapshot = snapshot or DailySensorSnapshot(
            date_mdt=TARGET_DATE,
            tent={
                "temperature_f": {
                    "overnight": WindowAvg(avg=77.0, n=3),
                    "morning": WindowAvg(avg=80.0, n=2),
                    "now": 81.0,
                }
            },
            plants={
                "a": {
                    "overnight_pct": WindowAvg(avg=55.0, n=3),
                    "morning_pct": WindowAvg(avg=54.0, n=2),
                    "now_pct": 53.5,
                }
            },
        )

    async def validate(self) -> list[ValidationFailure]:
        return self.failures

    async def snapshot(self, target_date: date) -> DailySensorSnapshot:
        return self._snapshot


class _FakeSynthesis:
    """SynthesisRunner stand-in. Writes a daily file + telegram sidecar
    when invoked."""

    def __init__(
        self,
        wiki_root: Path,
        marker_dir: Path,
        *,
        succeed: bool = True,
        error: str | None = None,
        write_sidecar: bool = True,
        sidecar_body: str = "<b>Daily Report</b>\nPlant A looking good.",
    ):
        self.wiki_root = wiki_root
        self.marker_dir = marker_dir
        self.succeed = succeed
        self.error = error
        self.write_sidecar = write_sidecar
        self.sidecar_body = sidecar_body
        self.calls: list[tuple[date, list[Path], dict[str, Any]]] = []

    async def run(
        self,
        target_date,
        photo_paths,
        sensor_payload,
    ) -> SynthesisResult:
        self.calls.append((target_date, list(photo_paths), sensor_payload))
        if not self.succeed:
            return SynthesisResult(
                success=False,
                daily_file=None,
                error=self.error or "fake failure",
                duration_s=1.0,
                cost_usd=0.0,
                final_text=None,
            )
        daily = self.wiki_root / "daily" / f"{target_date.isoformat()}.md"
        daily.parent.mkdir(parents=True, exist_ok=True)
        daily.write_text(
            "---\ntitle: Daily\n---\n\n# Daily Report\n\n"
            "## Plant A\nLooking good.\n\n"
            "## Sensors\n\n| metric | value |\n|---|---|\n| temp | 80°F |\n"
        )
        sidecar = self.marker_dir / f"{target_date.isoformat()}.telegram.html"
        if self.write_sidecar:
            self.marker_dir.mkdir(parents=True, exist_ok=True)
            sidecar.write_text(self.sidecar_body)
        return SynthesisResult(
            success=True,
            daily_file=daily,
            error=None,
            duration_s=1.0,
            cost_usd=0.05,
            final_text="done",
            telegram_html_path=sidecar if self.write_sidecar else None,
        )


class _CrashingSynthesis:
    async def run(self, target_date, photo_paths, sensor_payload) -> SynthesisResult:
        raise RuntimeError("boom")


class _FakeTelegram:
    def __init__(
        self, *, fail_send_message: bool = False, fail_send_media: bool = False
    ):
        self.messages: list[dict[str, Any]] = []
        self.media_groups: list[dict[str, Any]] = []
        self.fail_send_message = fail_send_message
        self.fail_send_media = fail_send_media

    async def send_message(
        self, chat_id, text, *, parse_mode="HTML", disable_web_page_preview=True
    ):
        if self.fail_send_message:
            from dirt_shared.services.telegram import TelegramError

            raise TelegramError("injected message failure")
        self.messages.append(
            {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode,
            }
        )
        return {"message_id": 1}

    async def send_media_group(
        self, chat_id, photo_paths, *, caption=None, caption_parse_mode="HTML"
    ):
        if self.fail_send_media:
            from dirt_shared.services.telegram import TelegramError

            raise TelegramError("injected media failure")
        self.media_groups.append(
            {
                "chat_id": chat_id,
                "photo_paths": list(photo_paths),
                "caption": caption,
            }
        )
        return [{"message_id": 100}]


def _build_orchestrator(
    *,
    tmp_path,
    camera=None,
    sensor_reader=None,
    synthesis=None,
    telegram=None,
    snapshot_recorder=None,
) -> tuple[DailyReport, _FakeCamera, _FakeSensorReader, _FakeSynthesis, _FakeTelegram]:
    photos_dir = tmp_path / "raw" / "photos"
    marker_dir = tmp_path / "logs" / "daily_report"
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    cam = camera or _FakeCamera()
    reader = sensor_reader or _FakeSensorReader()
    synth = synthesis or _FakeSynthesis(wiki_root, marker_dir)
    tg = telegram or _FakeTelegram()
    orch = DailyReport(
        camera=cam,  # type: ignore[arg-type]
        sensor_reader=reader,  # type: ignore[arg-type]
        synthesis=synth,
        telegram=tg,
        telegram_chat_id="12345",
        photos_dir=photos_dir,
        marker_dir=marker_dir,
        wiki_root=wiki_root,
        clock=_clock,
        stamp_jpeg=lambda data, _now: data,
        snapshot_recorder=snapshot_recorder,
    )
    return orch, cam, reader, synth, tg


# --- happy path ---


async def test_run_full_pipeline_happy_path(tmp_path):
    orch, cam, _reader, synth, tg = _build_orchestrator(tmp_path=tmp_path)

    result = await orch.run(TARGET_DATE)

    assert result.success
    assert result.failed_phase is None
    # 5 presets in order
    assert cam.calls == ["overview", "plant_a", "plant_b", "plant_c", "plant_d"]
    # 5 photos saved with EXIF
    photos_dir = tmp_path / "raw" / "photos" / "2026-04-19"
    files = sorted(p.name for p in photos_dir.iterdir())
    assert files == [
        "overview.jpg",
        "plant-a.jpg",
        "plant-b.jpg",
        "plant-c.jpg",
        "plant-d.jpg",
    ]
    # Synthesis received the same paths
    assert len(synth.calls) == 1
    _date, paths, payload = synth.calls[0]
    assert _date == TARGET_DATE
    assert {p.name for p in paths} == set(files)
    assert "tent" in payload and "plants" in payload
    # Telegram got both calls
    assert len(tg.media_groups) == 1
    assert len(tg.messages) == 1  # body only (no failure alert)
    assert tg.messages[0]["parse_mode"] == "HTML"
    # Body comes from the sub-agent's sidecar file, not from markdown conversion.
    assert "Plant A looking good" in tg.messages[0]["text"]
    # Marker file written
    assert (tmp_path / "logs" / "daily_report" / "2026-04-19.completed").exists()


async def test_run_records_scoped_daily_report_snapshot_rows(tmp_path, app_engine):
    recorder = DailyReportSnapshotRecorder(app_engine)
    orch, cam, _reader, _synth, tg = _build_orchestrator(
        tmp_path=tmp_path,
        snapshot_recorder=recorder,
    )

    result = await orch.run(TARGET_DATE)

    assert result.success
    assert cam.calls == ["overview", "plant_a", "plant_b", "plant_c", "plant_d"]
    assert len(tg.media_groups) == 1
    assert len(tg.messages) == 1

    async with AsyncSession(app_engine) as session:
        rows = (
            await session.exec(
                select(Snapshot, Tent, Device, Zone)
                .join(Tent, Tent.id == Snapshot.tent_id)
                .join(Device, Device.id == Snapshot.device_id)
                .join(Zone, Zone.id == Snapshot.zone_id)
                .where(Snapshot.kind == "daily_report")
                .order_by(Snapshot.view_id)
            )
        ).all()

    by_view = {
        snapshot.view_id: (snapshot, tent, device, zone)
        for snapshot, tent, device, zone in rows
    }

    assert set(by_view) == {"overview", "plant_a", "plant_b", "plant_c", "plant_d"}
    assert {item[1].tent_id for item in by_view.values()} == {"main"}
    assert {item[2].device_id for item in by_view.values()} == {"obsbot-main"}
    assert by_view["overview"][3].zone_id == "canopy"
    assert by_view["plant_a"][3].zone_id == "plant-a"
    assert by_view["plant_b"][3].zone_id == "plant-b"
    assert by_view["plant_c"][3].zone_id == "plant-c"
    assert by_view["plant_d"][3].zone_id == "plant-d"
    assert all(item[0].growrun_id is not None for item in by_view.values())
    assert all(Path(item[0].file_path).exists() for item in by_view.values())


# --- failure modes ---


async def test_capture_failure_continues_with_incomplete_report(tmp_path):
    cam = _FakeCamera()
    cam.raise_on = "plant_b"
    orch, _cam, _reader, synth, tg = _build_orchestrator(
        tmp_path=tmp_path,
        camera=cam,
    )

    result = await orch.run(TARGET_DATE)

    assert result.success
    assert result.failed_phase is None
    assert cam.calls == ["overview", "plant_a", "plant_b", "plant_c", "plant_d"]
    assert len(synth.calls) == 1
    _date, paths, _payload = synth.calls[0]
    assert _date == TARGET_DATE
    assert [p.name for p in paths] == [
        "overview.jpg",
        "plant-a.jpg",
        "plant-c.jpg",
        "plant-d.jpg",
    ]
    assert len(tg.media_groups) == 1
    assert len(tg.media_groups[0]["photo_paths"]) == 4
    assert "Captured 4/5 preset photos" in tg.media_groups[0]["caption"]
    assert len(tg.messages) == 1
    assert "Daily report failed" not in tg.messages[0]["text"]
    failed = tmp_path / "logs" / "daily_report" / "2026-04-19.failed"
    completed = tmp_path / "logs" / "daily_report" / "2026-04-19.completed"
    assert not failed.exists()
    assert completed.exists()


async def test_all_capture_failures_still_generate_text_report(tmp_path):
    cam = _FakeCamera()
    cam.raise_on_many = {"overview", "plant_a", "plant_b", "plant_c", "plant_d"}
    orch, _cam, _reader, synth, tg = _build_orchestrator(
        tmp_path=tmp_path,
        camera=cam,
    )

    result = await orch.run(TARGET_DATE)

    assert result.success
    assert len(synth.calls) == 1
    _date, paths, _payload = synth.calls[0]
    assert _date == TARGET_DATE
    assert paths == []
    assert tg.media_groups == []
    assert len(tg.messages) == 1
    assert (tmp_path / "logs" / "daily_report" / "2026-04-19.completed").exists()


async def test_validation_failure_sends_alert_and_skips_synthesis(
    tmp_path,
):
    sensor_reader = _FakeSensorReader(
        failures=[
            ValidationFailure(
                subject="fan-controller",
                metric="humidity_pct",
                value=0.0,
                age_s=10.0,
                reason="zero",
            )
        ]
    )

    orch, _cam, _reader, synth, tg = _build_orchestrator(
        tmp_path=tmp_path, sensor_reader=sensor_reader
    )
    result = await orch.run(TARGET_DATE)

    assert not result.success
    assert result.failed_phase == Phase.VALIDATE
    assert "humidity_pct" in (result.error or "")
    assert synth.calls == []
    assert len(tg.messages) == 1
    assert "validate" in tg.messages[0]["text"]


async def test_synthesis_failure_sends_alert(tmp_path):
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    marker_dir = tmp_path / "logs" / "daily_report"
    synth = _FakeSynthesis(wiki_root, marker_dir, succeed=False, error="cli_not_found")
    orch, _cam, _reader, _synth, tg = _build_orchestrator(
        tmp_path=tmp_path,
        synthesis=synth,
    )

    result = await orch.run(TARGET_DATE)

    assert not result.success
    assert result.failed_phase == Phase.SYNTHESIZE
    assert "cli_not_found" in (result.error or "")
    assert len(tg.media_groups) == 0  # never reached delivery
    assert len(tg.messages) == 1
    assert "synthesize" in tg.messages[0]["text"]


async def test_synthesis_crash_sends_alert_and_failed_marker(tmp_path):
    synth = _CrashingSynthesis()
    orch, _cam, _reader, _synth, tg = _build_orchestrator(
        tmp_path=tmp_path,
        synthesis=synth,
    )

    result = await orch.run(TARGET_DATE)

    assert not result.success
    assert result.failed_phase == Phase.SYNTHESIZE
    assert "RuntimeError: boom" in (result.error or "")
    assert len(tg.media_groups) == 0
    assert len(tg.messages) == 1
    assert "synthesize" in tg.messages[0]["text"]
    failed = tmp_path / "logs" / "daily_report" / "2026-04-19.failed"
    assert failed.exists()
    assert "synthesis crashed" in failed.read_text()


async def test_sidecar_missing_delivers_photos_only(tmp_path):
    """Sub-agent forgot to write the Telegram HTML sidecar. Photos still
    go out, no sendMessage, run still marked completed (non-fatal)."""
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    marker_dir = tmp_path / "logs" / "daily_report"
    synth = _FakeSynthesis(wiki_root, marker_dir, write_sidecar=False)
    orch, _cam, _reader, _synth, tg = _build_orchestrator(
        tmp_path=tmp_path, synthesis=synth
    )

    result = await orch.run(TARGET_DATE)

    assert result.success
    assert len(tg.media_groups) == 1
    assert len(tg.messages) == 0  # no body sent, no failure alert either
    assert (marker_dir / "2026-04-19.completed").exists()


async def test_telegram_failure_does_not_fail_overall_run(tmp_path):
    """Telegram is delivery, not the durable record. A send failure should
    leave the run as 'completed' with the wiki entry intact."""
    tg = _FakeTelegram(fail_send_media=True)
    orch, _cam, _reader, _synth, _tg = _build_orchestrator(
        tmp_path=tmp_path,
        telegram=tg,
    )

    result = await orch.run(TARGET_DATE)

    assert result.success
    assert result.failed_phase is None
    # Marker says completed
    assert (tmp_path / "logs" / "daily_report" / "2026-04-19.completed").exists()


# --- idempotency ---


async def test_run_skips_when_completed_marker_exists(tmp_path):
    marker_dir = tmp_path / "logs" / "daily_report"
    marker_dir.mkdir(parents=True, exist_ok=True)
    (marker_dir / "2026-04-19.completed").write_text("prev")

    orch, cam, _reader, synth, tg = _build_orchestrator(tmp_path=tmp_path)
    result = await orch.run(TARGET_DATE)

    assert result.success
    assert cam.calls == []  # no work done
    assert synth.calls == []
    assert tg.messages == []


async def test_force_overrides_completed_marker(tmp_path):
    marker_dir = tmp_path / "logs" / "daily_report"
    marker_dir.mkdir(parents=True, exist_ok=True)
    (marker_dir / "2026-04-19.completed").write_text("prev")

    orch, cam, _reader, _synth, _tg = _build_orchestrator(tmp_path=tmp_path)
    result = await orch.run(TARGET_DATE, force=True)

    assert result.success
    assert len(cam.calls) == 5  # full re-run


async def test_failed_marker_cleared_on_re_run(tmp_path):
    marker_dir = tmp_path / "logs" / "daily_report"
    marker_dir.mkdir(parents=True, exist_ok=True)
    (marker_dir / "2026-04-19.failed").write_text("capture\nold failure\n")

    orch, _cam, _reader, _synth, _tg = _build_orchestrator(
        tmp_path=tmp_path,
    )
    result = await orch.run(TARGET_DATE)

    assert result.success
    assert not (marker_dir / "2026-04-19.failed").exists()
    assert (marker_dir / "2026-04-19.completed").exists()


# --- telegram body loader (sidecar file pattern) ---


def test_load_telegram_body_returns_none_when_path_is_none():
    assert _load_telegram_body(None) is None


def test_load_telegram_body_returns_none_when_file_missing(tmp_path):
    assert _load_telegram_body(tmp_path / "nonexistent.html") is None


def test_load_telegram_body_returns_none_for_empty_file(tmp_path):
    p = tmp_path / "empty.html"
    p.write_text("")
    assert _load_telegram_body(p) is None


def test_load_telegram_body_passes_through_short_content(tmp_path):
    p = tmp_path / "body.html"
    body = "<b>Daily</b>\n• Plant A in band\n• Humidifier stable"
    p.write_text(body)
    assert _load_telegram_body(p) == body


def test_load_telegram_body_strips_leading_trailing_whitespace(tmp_path):
    p = tmp_path / "body.html"
    p.write_text("\n\n<b>Report</b>\n\n")
    assert _load_telegram_body(p) == "<b>Report</b>"


def test_load_telegram_body_balances_unclosed_tags(tmp_path):
    p = tmp_path / "body.html"
    p.write_text("<b>Report <pre>code block")
    out = _load_telegram_body(p)
    assert out is not None
    assert "</pre>" in out
    assert "</b>" in out


def test_load_telegram_body_drops_trailing_partial_tag(tmp_path):
    p = tmp_path / "body.html"
    p.write_text("<b>Report</b> and then <pr")
    out = _load_telegram_body(p)
    assert out is not None
    assert "<pr" not in out
    assert "<b>Report</b>" in out


def test_load_telegram_body_oversize_is_truncated_at_paragraph_break(tmp_path):
    # 6 paragraphs ~= 6 * ~800 chars so we blow past MAX.
    paras = [f"<b>Section {i}</b>\n" + ("x " * 400) for i in range(6)]
    body = "\n\n".join(paras)
    assert len(body) > MAX_TELEGRAM_BODY_CHARS
    p = tmp_path / "body.html"
    p.write_text(body)
    out = _load_telegram_body(p)
    assert out is not None
    assert len(out) <= MAX_TELEGRAM_BODY_CHARS + 100  # plus the suffix
    assert "truncated" in out


# --- safe truncate ---


def test_safe_truncate_noop_when_under_limit():
    assert _safe_truncate_html("short", 100) == "short"


def test_safe_truncate_at_paragraph_boundary():
    text = "A\n\nB\n\nC\n\nD"
    out = _safe_truncate_html(text, 6)
    # Should cut at the paragraph break strictly below 6 — the "A\n\n" boundary.
    assert out.startswith("A")
    assert "truncated" in out
    # Must not include D (beyond the cap).
    assert "D" not in out.split("truncated")[0]


def test_safe_truncate_falls_back_to_hard_cut_when_no_paragraph_break():
    text = "xxxxxxxxxxxxxxxxxxxx"  # 20 chars, no \n\n
    out = _safe_truncate_html(text, 5)
    assert out.startswith("xxxxx")
    assert "truncated" in out


def test_strip_trailing_partial_tag_drops_dangling_open():
    assert _strip_trailing_partial_tag("hello <pre") == "hello"


def test_strip_trailing_partial_tag_keeps_complete_tags():
    s = "<b>hi</b>"
    assert _strip_trailing_partial_tag(s) == s


def test_strip_trailing_partial_tag_keeps_complete_open_tag():
    s = "<b>hi"
    # Trailing '<' is inside the already-closed '<b>' (last > is after last <).
    assert _strip_trailing_partial_tag(s) == s


# --- balance_html_tags ---


def test_balance_html_tags_closes_unclosed_pre():
    s = "<pre>foo bar baz"
    out = balance_html_tags(s)
    assert out == "<pre>foo bar baz</pre>"


def test_balance_html_tags_handles_multiple_unclosed():
    s = "<pre>x</pre> and <b>y and <i>z"
    out = balance_html_tags(s)
    # Surplus: 1 <b>, 1 <i>; <pre> already balanced
    assert "</b>" in out and "</i>" in out
    assert out.count("</pre>") == 1


def test_balance_html_tags_noop_when_balanced():
    s = "<b>hello</b> <pre>world</pre>"
    assert balance_html_tags(s) == s
