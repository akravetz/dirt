"""Tests for the camera-client + EXIF-stamping helpers used by the daily report.

The CameraClient takes its daemon-RPC callable by injection, so tests pass
a fake async function that returns canned responses — no socket, no daemon,
no monkeypatching.
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from dirt.services.photos import CameraClient, CameraError, stamp_exif_datetime

PRESETS = {
    "overview": {"pitch": -50.0, "yaw": -25.0, "zoom": 1.0},
    "plant_a": {"pitch": -38.0, "yaw": -55.0, "zoom": 1.5},
}


def _tiny_jpeg() -> bytes:
    """Return a real (decodable) tiny JPEG so Pillow can round-trip it."""
    im = Image.new("RGB", (4, 4), (10, 20, 30))
    buf = io.BytesIO()
    im.save(buf, format="JPEG")
    return buf.getvalue()


class FakeDaemon:
    """Pluggable daemon double for CameraClient tests.

    Records every call. capture() returns a tempfile path with `tmp_path`
    base; age_ms can be scripted per call so we can exercise the
    stale-frame retry path.
    """

    def __init__(self, tmp_path: Path, *, capture_ages_ms: list[int] | None = None):
        self.tmp_path = tmp_path
        self.calls: list[str] = []
        self._jpeg = _tiny_jpeg()
        self._capture_ages = list(capture_ages_ms) if capture_ages_ms else [50]
        self._capture_idx = 0
        # tunables for fault-injection
        self.move_status = "ok"
        self.zoom_status = "ok"
        self.capture_status = "ok"
        self.capture_path_override: str | None = None

    async def __call__(self, line: str) -> dict[str, str]:
        self.calls.append(line)
        if line.startswith("move_motor"):
            return {"_status": self.move_status}
        if line.startswith("set_zoom"):
            return {"_status": self.zoom_status}
        if line == "capture":
            if self.capture_status != "ok":
                return {"_status": self.capture_status, "msg": "fake_failure"}
            age = self._capture_ages[
                min(self._capture_idx, len(self._capture_ages) - 1)
            ]
            self._capture_idx += 1
            path = self.capture_path_override
            if path is None:
                path_obj = self.tmp_path / f"cap-{self._capture_idx}.jpg"
                path_obj.write_bytes(self._jpeg)
                path = str(path_obj)
            return {"_status": "ok", "age_ms": str(age), "path": path}
        return {"_status": "unknown_command"}


async def test_capture_at_pans_settles_then_captures(tmp_path: Path):
    fake = FakeDaemon(tmp_path)
    c = CameraClient(fake, PRESETS, settle_s=0.0, capture_retries=2)

    out = await c.capture_at("overview")

    assert out.startswith(b"\xff\xd8")  # SOI marker
    assert fake.calls == [
        "move_motor -50.00 -25.00",
        "set_zoom 1.00",
        "capture",
    ]


async def test_capture_at_retries_on_stale_frame(tmp_path: Path):
    # First capture returns age_ms=999 (stale); second returns 50 (fresh).
    fake = FakeDaemon(tmp_path, capture_ages_ms=[999, 50])
    c = CameraClient(
        fake, PRESETS,
        settle_s=0.0,
        max_capture_age_ms=400,
        capture_retries=3,
        capture_retry_delay_s=0.0,
    )

    out = await c.capture_at("overview")

    assert out.startswith(b"\xff\xd8")
    captures = [c for c in fake.calls if c == "capture"]
    assert len(captures) == 2  # one stale, one fresh


async def test_capture_at_fails_after_exhausting_retries(tmp_path: Path):
    fake = FakeDaemon(tmp_path, capture_ages_ms=[999, 999, 999])
    c = CameraClient(
        fake, PRESETS,
        settle_s=0.0,
        max_capture_age_ms=400,
        capture_retries=3,
        capture_retry_delay_s=0.0,
    )
    with pytest.raises(CameraError, match="after 3 attempts"):
        await c.capture_at("overview")


async def test_capture_at_unknown_preset_raises(tmp_path: Path):
    fake = FakeDaemon(tmp_path)
    c = CameraClient(fake, PRESETS, settle_s=0.0)
    with pytest.raises(CameraError, match="unknown preset"):
        await c.capture_at("plant_z")


async def test_capture_at_move_failure_raises(tmp_path: Path):
    fake = FakeDaemon(tmp_path)
    fake.move_status = "error"
    c = CameraClient(fake, PRESETS, settle_s=0.0)
    with pytest.raises(CameraError, match="move_motor failed"):
        await c.capture_at("overview")


async def test_capture_at_zoom_failure_does_not_raise(tmp_path: Path):
    # Wrong zoom is better than no photo — log a warning, keep going.
    fake = FakeDaemon(tmp_path)
    fake.zoom_status = "error"
    c = CameraClient(fake, PRESETS, settle_s=0.0, capture_retries=1)
    out = await c.capture_at("overview")
    assert out.startswith(b"\xff\xd8")


async def test_capture_at_limit_reached_is_treated_as_ok(tmp_path: Path):
    # Daemon returns "limit_reached" if you ask it to pan past the gimbal's
    # mechanical stops; the partial move is still a valid result.
    fake = FakeDaemon(tmp_path)
    fake.move_status = "limit_reached"
    c = CameraClient(fake, PRESETS, settle_s=0.0, capture_retries=1)
    out = await c.capture_at("overview")
    assert out.startswith(b"\xff\xd8")


def test_stamp_exif_datetime_writes_tag():
    raw = _tiny_jpeg()
    when = datetime(2026, 4, 19, 14, 0, 0)
    stamped = stamp_exif_datetime(raw, when)

    with Image.open(io.BytesIO(stamped)) as im:
        exif = im.getexif()
    assert exif.get(36867) == "2026:04:19 14:00:00"


def test_stamp_exif_datetime_keeps_decodable_jpeg():
    raw = _tiny_jpeg()
    stamped = stamp_exif_datetime(raw, datetime(2026, 4, 19, 14, 0, 0))
    with Image.open(io.BytesIO(stamped)) as im:
        im.load()  # raises if the JPEG is mangled
        assert im.size == (4, 4)
