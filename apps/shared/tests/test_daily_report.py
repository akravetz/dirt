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

import pytest
from PIL import Image
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.enums import SensorLocation, SensorSource
from dirt_shared.models.sensor_calibration import SensorCalibration
from dirt_shared.models.sensor_node import SensorNode
from dirt_shared.models.sensor_reading import SensorReading
from dirt_shared.services.daily_report import (
    DailyReport,
    Phase,
    balance_html_tags,
    markdown_to_simple_html,
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
            ("temperature_f", 80.0), ("humidity_pct", 50.0),
            ("pressure_hpa", 843.0), ("vpd_kpa", 1.5), ("dew_point_f", 58.0),
        ]:
            s.add(SensorReading(
                sensornode_id=ids[TENT_LOCATION], metric=m, value=v,
                ts=fresh_ts, source=SensorSource.ARDUINO))
        for loc in PLANT_LOCATIONS:
            s.add(SensorReading(
                sensornode_id=ids[loc], metric=SOIL_METRIC, value=2500.0,
                ts=fresh_ts, source=SensorSource.ESP32))
            s.add(SensorCalibration(
                sensornode_id=ids[loc], metric=SOIL_METRIC,
                raw_low=1370.0, raw_high=3880.0))
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
    """SynthesisRunner stand-in. Writes a daily file when invoked."""
    def __init__(self, wiki_root: Path, *, succeed: bool = True,
                 error: str | None = None):
        self.wiki_root = wiki_root
        self.succeed = succeed
        self.error = error
        self.calls: list[tuple[date, list[Path], dict[str, Any]]] = []

    async def run(
        self, target_date, photo_paths, sensor_payload,
    ) -> SynthesisResult:
        self.calls.append((target_date, list(photo_paths), sensor_payload))
        if not self.succeed:
            return SynthesisResult(
                success=False, daily_file=None,
                error=self.error or "fake failure",
                duration_s=1.0, cost_usd=0.0, final_text=None,
            )
        daily = self.wiki_root / "daily" / f"{target_date.isoformat()}.md"
        daily.parent.mkdir(parents=True, exist_ok=True)
        daily.write_text(
            "---\ntitle: Daily\n---\n\n# Daily Report\n\n"
            "## Plant A\nLooking good.\n\n"
            "## Sensors\n\n| metric | value |\n|---|---|\n| temp | 80°F |\n"
        )
        return SynthesisResult(
            success=True, daily_file=daily, error=None,
            duration_s=1.0, cost_usd=0.05, final_text="done",
        )


class _FakeTelegram:
    def __init__(self, *, fail_send_message: bool = False,
                 fail_send_media: bool = False):
        self.messages: list[dict[str, Any]] = []
        self.media_groups: list[dict[str, Any]] = []
        self.fail_send_message = fail_send_message
        self.fail_send_media = fail_send_media

    async def send_message(self, chat_id, text, *, parse_mode="HTML",
                           disable_web_page_preview=True):
        if self.fail_send_message:
            from dirt_shared.services.telegram import TelegramError
            raise TelegramError("injected message failure")
        self.messages.append({
            "chat_id": chat_id, "text": text, "parse_mode": parse_mode,
        })
        return {"message_id": 1}

    async def send_media_group(self, chat_id, photo_paths, *, caption=None,
                               caption_parse_mode="HTML"):
        if self.fail_send_media:
            from dirt_shared.services.telegram import TelegramError
            raise TelegramError("injected media failure")
        self.media_groups.append({
            "chat_id": chat_id,
            "photo_paths": list(photo_paths),
            "caption": caption,
        })
        return [{"message_id": 100}]


def _build_orchestrator(
    *, engine, tmp_path, camera=None, synthesis=None, telegram=None,
) -> tuple[DailyReport, _FakeCamera, _FakeSynthesis, _FakeTelegram]:
    photos_dir = tmp_path / "raw" / "photos"
    marker_dir = tmp_path / "logs" / "daily_report"
    wiki_root = tmp_path / "wiki"
    wiki_root.mkdir(parents=True, exist_ok=True)
    cam = camera or _FakeCamera()
    synth = synthesis or _FakeSynthesis(wiki_root)
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
        "overview.jpg", "plant-a.jpg", "plant-b.jpg",
        "plant-c.jpg", "plant-d.jpg",
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
    assert "Daily Report" in tg.messages[0]["text"]
    # Marker file written
    assert (tmp_path / "logs" / "daily_report" / "2026-04-19.completed").exists()


# --- failure modes ---


async def test_capture_failure_sends_alert_and_skips_synthesis(pg_engine, tmp_path):
    engine = pg_engine
    await _seed_clean(engine)
    cam = _FakeCamera()
    cam.raise_on = "plant_b"
    orch, _cam, synth, tg = _build_orchestrator(
        engine=engine, tmp_path=tmp_path, camera=cam,
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
    pg_engine, tmp_path,
):
    engine = pg_engine
    # seed with humidity=0 (zero-trigger)
    fresh_ts = NOW - timedelta(seconds=10)
    ids = await _node_ids(engine)
    async with AsyncSession(engine) as s:
        for m, v in [
            ("temperature_f", 80.0), ("humidity_pct", 0.0),
            ("pressure_hpa", 843.0), ("vpd_kpa", 1.5), ("dew_point_f", 58.0),
        ]:
            s.add(SensorReading(
                sensornode_id=ids[TENT_LOCATION], metric=m, value=v,
                ts=fresh_ts, source=SensorSource.ARDUINO))
        for loc in PLANT_LOCATIONS:
            s.add(SensorReading(
                sensornode_id=ids[loc], metric=SOIL_METRIC, value=2500.0,
                ts=fresh_ts, source=SensorSource.ESP32))
            s.add(SensorCalibration(
                sensornode_id=ids[loc], metric=SOIL_METRIC,
                raw_low=1370.0, raw_high=3880.0))
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
    synth = _FakeSynthesis(wiki_root, succeed=False, error="cli_not_found")
    orch, _cam, _synth, tg = _build_orchestrator(
        engine=engine, tmp_path=tmp_path, synthesis=synth,
    )

    result = await orch.run(TARGET_DATE)

    assert not result.success
    assert result.failed_phase == Phase.SYNTHESIZE
    assert "cli_not_found" in (result.error or "")
    assert len(tg.media_groups) == 0  # never reached delivery
    assert len(tg.messages) == 1
    assert "synthesize" in tg.messages[0]["text"]


async def test_telegram_failure_does_not_fail_overall_run(pg_engine, tmp_path):
    engine = pg_engine
    """Telegram is delivery, not the durable record. A send failure should
    leave the run as 'completed' with the wiki entry intact."""
    await _seed_clean(engine)
    tg = _FakeTelegram(fail_send_media=True)
    orch, _cam, _synth, _tg = _build_orchestrator(
        engine=engine, tmp_path=tmp_path, telegram=tg,
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
        engine=engine, tmp_path=tmp_path,
    )
    result = await orch.run(TARGET_DATE)

    assert result.success
    assert not (marker_dir / "2026-04-19.failed").exists()
    assert (marker_dir / "2026-04-19.completed").exists()


# --- markdown_to_simple_html ---


def test_markdown_strips_frontmatter():
    md = "---\ntitle: x\n---\n\nbody text\n"
    out = markdown_to_simple_html(md)
    assert "title:" not in out
    assert "body text" in out


def test_markdown_headings_become_bold():
    out = markdown_to_simple_html("# Hello\n\n## Sub heading\n")
    assert "<b>Hello</b>" in out
    assert "<b>Sub heading</b>" in out


def test_markdown_inline_code_and_bold():
    out = markdown_to_simple_html(
        "Use `cmd` for **important** notes."
    )
    assert "<code>cmd</code>" in out
    assert "<b>important</b>" in out


def test_markdown_table_becomes_pre():
    out = markdown_to_simple_html(
        "Stats:\n\n| metric | value |\n|---|---|\n| temp | 80 |\n"
    )
    assert "<pre>" in out
    # Contents preserved (escaped)
    assert "metric" in out
    assert "80" in out


def test_markdown_code_fence_becomes_pre():
    out = markdown_to_simple_html(
        "Example:\n\n```bash\nls -la\necho hi\n```\n"
    )
    assert "<pre>" in out
    assert "ls -la" in out
    # Inside <pre>, special chars are escaped
    assert "echo hi" in out


def test_markdown_escapes_html_specials_in_plain_text():
    out = markdown_to_simple_html("a < b & c > d")
    # < and > should be escaped
    assert "&lt;" in out
    assert "&gt;" in out
    assert "&amp;" in out


def test_markdown_does_not_break_snake_case():
    out = markdown_to_simple_html("some_var_name and other_thing here")
    assert "<i>" not in out  # the regex requires bracketing whitespace


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
