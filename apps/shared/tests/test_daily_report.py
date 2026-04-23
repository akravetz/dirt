"""Orchestrator tests — every external dependency injected as a fake.

Covers the failure → telegram alert → exit-non-zero branches plus the
happy-path delivery, the markdown→HTML helper, and idempotency via the
marker file.
"""

from __future__ import annotations

import io
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from PIL import Image
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.enums import SensorLocation, SensorSource
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.daily_report import (
    MAX_TELEGRAM_BODY_CHARS,
    DailyReport,
    Phase,
    _load_telegram_body,
    _safe_truncate_html,
    _strip_trailing_partial_tag,
    balance_html_tags,
)
from dirt_shared.services.daily_sensors import (
    PLANT_LOCATIONS,
    SOIL_METRIC,
    TENT_LOCATION,
    SensorReader,
)
from dirt_shared.services.daily_synthesis import SynthesisResult

# --- shared fixtures ---


def _tiny_jpeg() -> bytes:
    im = Image.new("RGB", (4, 4), (200, 50, 50))
    buf = io.BytesIO()
    im.save(buf, format="JPEG")
    return buf.getvalue()


# 14:30 MDT -> 20:30 UTC on Apr 19 2026
NOW = datetime(2026, 4, 19, 20, 30, 0, tzinfo=UTC)
TARGET_DATE = date(2026, 4, 19)


def _clock() -> datetime:
    return NOW


async def _node_ids(engine) -> dict[SensorLocation, int]:
    async with AsyncSession(engine) as s:
        result = await s.exec(select(SensorNode))
        return {n.location: n.id for n in result.all()}


async def _seed_clean(engine):
    fresh_ts = NOW - timedelta(seconds=10)
    ids = await _node_ids(engine)
    async with AsyncSession(engine) as s:
        for m, v in [
            ("temperature_f", 80.0),
            ("humidity_pct", 50.0),
            ("pressure_hpa", 843.0),
            ("vpd_kpa", 1.5),
            ("dew_point_f", 58.0),
        ]:
            s.add(
                SensorReading(
                    sensornode_id=ids[TENT_LOCATION],
                    metric=m,
                    value=v,
                    ts=fresh_ts,
                    source=SensorSource.ARDUINO,
                )
            )
        for loc in PLANT_LOCATIONS:
            s.add(
                SensorReading(
                    sensornode_id=ids[loc],
                    metric=SOIL_METRIC,
                    value=2500.0,
                    ts=fresh_ts,
                    source=SensorSource.ESP32,
                )
            )
            s.add(
                SensorCalibration(
                    sensornode_id=ids[loc],
                    metric=SOIL_METRIC,
                    raw_low=1370.0,
                    raw_high=3880.0,
                )
            )
        await s.commit()


class _FakeCamera:
    """CameraClient stand-in. Records preset list, returns a real JPEG."""

    def __init__(self, jpeg: bytes | None = None):
        self.jpeg = jpeg or _tiny_jpeg()
        self.calls: list[str] = []
        self.raise_on: str | None = None

    async def capture_at(self, preset: str) -> bytes:
        self.calls.append(preset)
        if self.raise_on == preset:
            from dirt_shared.services.photos import CameraError

            raise CameraError(f"injected failure at {preset}")
        return self.jpeg


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
    engine,
    tmp_path,
    camera=None,
    synthesis=None,
    telegram=None,
) -> tuple[DailyReport, _FakeCamera, _FakeSynthesis, _FakeTelegram]:
    photos_dir = tmp_path / "raw" / "photos"
    marker_dir = tmp_path / "logs" / "daily_report"
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    cam = camera or _FakeCamera()
    synth = synthesis or _FakeSynthesis(wiki_root, marker_dir)
    tg = telegram or _FakeTelegram()
    reader = SensorReader(engine, clock=_clock, max_age_s=300)
    orch = DailyReport(
        camera=cam,  # type: ignore[arg-type]
        sensor_reader=reader,
        synthesis=synth,
        telegram=tg,
        telegram_chat_id="12345",
        photos_dir=photos_dir,
        marker_dir=marker_dir,
        wiki_root=wiki_root,
        clock=_clock,
    )
    return orch, cam, synth, tg


# --- happy path ---


async def test_run_full_pipeline_happy_path(pg_engine, tmp_path):
    engine = pg_engine
    await _seed_clean(engine)
    orch, cam, synth, tg = _build_orchestrator(engine=engine, tmp_path=tmp_path)

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


# --- failure modes ---


async def test_capture_failure_sends_alert_and_skips_synthesis(pg_engine, tmp_path):
    engine = pg_engine
    await _seed_clean(engine)
    cam = _FakeCamera()
    cam.raise_on = "plant_b"
    orch, _cam, synth, tg = _build_orchestrator(
        engine=engine,
        tmp_path=tmp_path,
        camera=cam,
    )

    result = await orch.run(TARGET_DATE)

    assert not result.success
    assert result.failed_phase == Phase.CAPTURE
    assert "plant_b" in (result.error or "")
    assert synth.calls == []  # skipped
    # Failure alert sent (and only that — no media group)
    assert len(tg.media_groups) == 0
    assert len(tg.messages) == 1
    assert "Daily report failed" in tg.messages[0]["text"]
    assert "capture" in tg.messages[0]["text"]
    # Failed marker, not completed
    failed = tmp_path / "logs" / "daily_report" / "2026-04-19.failed"
    completed = tmp_path / "logs" / "daily_report" / "2026-04-19.completed"
    assert failed.exists()
    assert not completed.exists()


async def test_validation_failure_sends_alert_and_skips_synthesis(
    pg_engine,
    tmp_path,
):
    engine = pg_engine
    # seed with humidity=0 (zero-trigger)
    fresh_ts = NOW - timedelta(seconds=10)
    ids = await _node_ids(engine)
    async with AsyncSession(engine) as s:
        for m, v in [
            ("temperature_f", 80.0),
            ("humidity_pct", 0.0),
            ("pressure_hpa", 843.0),
            ("vpd_kpa", 1.5),
            ("dew_point_f", 58.0),
        ]:
            s.add(
                SensorReading(
                    sensornode_id=ids[TENT_LOCATION],
                    metric=m,
                    value=v,
                    ts=fresh_ts,
                    source=SensorSource.ARDUINO,
                )
            )
        for loc in PLANT_LOCATIONS:
            s.add(
                SensorReading(
                    sensornode_id=ids[loc],
                    metric=SOIL_METRIC,
                    value=2500.0,
                    ts=fresh_ts,
                    source=SensorSource.ESP32,
                )
            )
            s.add(
                SensorCalibration(
                    sensornode_id=ids[loc],
                    metric=SOIL_METRIC,
                    raw_low=1370.0,
                    raw_high=3880.0,
                )
            )
        await s.commit()

    orch, _cam, synth, tg = _build_orchestrator(engine=engine, tmp_path=tmp_path)
    result = await orch.run(TARGET_DATE)

    assert not result.success
    assert result.failed_phase == Phase.VALIDATE
    assert "humidity_pct" in (result.error or "")
    assert synth.calls == []
    assert len(tg.messages) == 1
    assert "validate" in tg.messages[0]["text"]


async def test_synthesis_failure_sends_alert(pg_engine, tmp_path):
    engine = pg_engine
    await _seed_clean(engine)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    marker_dir = tmp_path / "logs" / "daily_report"
    synth = _FakeSynthesis(wiki_root, marker_dir, succeed=False, error="cli_not_found")
    orch, _cam, _synth, tg = _build_orchestrator(
        engine=engine,
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


async def test_sidecar_missing_delivers_photos_only(pg_engine, tmp_path):
    """Sub-agent forgot to write the Telegram HTML sidecar. Photos still
    go out, no sendMessage, run still marked completed (non-fatal)."""
    engine = pg_engine
    await _seed_clean(engine)
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    marker_dir = tmp_path / "logs" / "daily_report"
    synth = _FakeSynthesis(wiki_root, marker_dir, write_sidecar=False)
    orch, _cam, _synth, tg = _build_orchestrator(
        engine=engine, tmp_path=tmp_path, synthesis=synth
    )

    result = await orch.run(TARGET_DATE)

    assert result.success
    assert len(tg.media_groups) == 1
    assert len(tg.messages) == 0  # no body sent, no failure alert either
    assert (marker_dir / "2026-04-19.completed").exists()


async def test_telegram_failure_does_not_fail_overall_run(pg_engine, tmp_path):
    engine = pg_engine
    """Telegram is delivery, not the durable record. A send failure should
    leave the run as 'completed' with the wiki entry intact."""
    await _seed_clean(engine)
    tg = _FakeTelegram(fail_send_media=True)
    orch, _cam, _synth, _tg = _build_orchestrator(
        engine=engine,
        tmp_path=tmp_path,
        telegram=tg,
    )

    result = await orch.run(TARGET_DATE)

    assert result.success
    assert result.failed_phase is None
    # Marker says completed
    assert (tmp_path / "logs" / "daily_report" / "2026-04-19.completed").exists()


# --- idempotency ---


async def test_run_skips_when_completed_marker_exists(pg_engine, tmp_path):
    engine = pg_engine
    await _seed_clean(engine)
    marker_dir = tmp_path / "logs" / "daily_report"
    marker_dir.mkdir(parents=True, exist_ok=True)
    (marker_dir / "2026-04-19.completed").write_text("prev")

    orch, cam, synth, tg = _build_orchestrator(engine=engine, tmp_path=tmp_path)
    result = await orch.run(TARGET_DATE)

    assert result.success
    assert cam.calls == []  # no work done
    assert synth.calls == []
    assert tg.messages == []


async def test_force_overrides_completed_marker(pg_engine, tmp_path):
    engine = pg_engine
    await _seed_clean(engine)
    marker_dir = tmp_path / "logs" / "daily_report"
    marker_dir.mkdir(parents=True, exist_ok=True)
    (marker_dir / "2026-04-19.completed").write_text("prev")

    orch, cam, _synth, _tg = _build_orchestrator(engine=engine, tmp_path=tmp_path)
    result = await orch.run(TARGET_DATE, force=True)

    assert result.success
    assert len(cam.calls) == 5  # full re-run


async def test_failed_marker_cleared_on_re_run(pg_engine, tmp_path):
    engine = pg_engine
    await _seed_clean(engine)
    marker_dir = tmp_path / "logs" / "daily_report"
    marker_dir.mkdir(parents=True, exist_ok=True)
    (marker_dir / "2026-04-19.failed").write_text("capture\nold failure\n")

    orch, _cam, _synth, _tg = _build_orchestrator(
        engine=engine,
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
    # Sub-agent wrote a dangling '<pr' (would've triggered yesterday's bug).
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
