"""Photo capture for the daily report.

Two pieces:

- :class:`CameraClient` — pans the gimbal to a preset, waits for settle,
  pulls a fresh frame from the dirt-camera daemon (validates ``age_ms`` so
  we don't accidentally serve a frame from before the pan), and returns the
  raw JPEG bytes. Takes its daemon-RPC callable and preset map by
  injection so tests can swap them without monkeypatching.

- :func:`stamp_exif_datetime` — writes ``DateTimeOriginal`` (EXIF tag
  36867) into a JPEG byte buffer using Pillow. The wiki lint
  (``scripts/lint.py``) reads this tag to verify photo-coverage; without it
  every fresh photo would be flagged as uncovered.
"""

from __future__ import annotations

import asyncio
import io
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)

DaemonRPC = Callable[[str], Awaitable[dict[str, str]]]


class CameraError(RuntimeError):
    """Daemon RPC failed, frame not ready, or age check exhausted retries."""


class CameraClient:
    def __init__(  # noqa: PLR0913 — rpc+presets are the collaborators; the four trailing kwargs are capture-retry tuning knobs with sensible defaults, kept flat so tests can override one at a time.
        self,
        rpc: DaemonRPC,
        presets: dict[str, dict[str, float]],
        *,
        settle_s: float = 1.5,
        max_capture_age_ms: int = 400,
        capture_retries: int = 3,
        capture_retry_delay_s: float = 0.3,
    ) -> None:
        """
        Args:
            rpc: async callable that issues one daemon command line and
                returns the parsed ``{_status: ..., key: val, ...}`` dict.
                Real impl is ``dirt.services.capture._daemon_rpc``.
            presets: preset map (``{name: {pitch, yaw, zoom}}``) — usually
                loaded from ``~/.config/dirt/camera.json``.
            settle_s: seconds to sleep after the daemon's ``move_motor``
                returns. The daemon already blocks until the gimbal stops
                moving (sdk_wrapper.cpp), but the v4l2 latest-frame
                buffer may still be from before the pan, and the OBSBOT's
                continuous AF needs a beat to lock on the new framing.
            max_capture_age_ms: reject ``capture`` responses whose
                reported ``age_ms`` exceeds this — guarantees the frame
                we return came from after the pan.
            capture_retries: how many times to retry a stale capture
                before giving up.
            capture_retry_delay_s: sleep between capture retries.
        """
        self._rpc = rpc
        self._presets = presets
        self._settle_s = settle_s
        self._max_age_ms = max_capture_age_ms
        self._retries = capture_retries
        self._retry_delay_s = capture_retry_delay_s

    async def capture_at(self, preset: str) -> bytes:
        """Pan to ``preset``, settle, capture a fresh frame, return JPEG bytes."""
        if preset not in self._presets:
            raise CameraError(
                f"unknown preset {preset!r}; known: {sorted(self._presets)}"
            )
        p = self._presets[preset]

        mr = await self._rpc(f"move_motor {p['pitch']:.2f} {p['yaw']:.2f}")
        status = mr.get("_status")
        if status not in ("ok", "limit_reached"):
            raise CameraError(f"move_motor failed for {preset!r}: {mr}")

        zr = await self._rpc(f"set_zoom {p['zoom']:.2f}")
        if zr.get("_status") != "ok":
            # Not fatal — wrong zoom is better than no photo.
            logger.warning("set_zoom failed for %r: %s", preset, zr)

        await asyncio.sleep(self._settle_s)

        last_err: dict[str, str] | None = None
        for _ in range(self._retries):
            cr = await self._rpc("capture")
            if cr.get("_status") != "ok":
                last_err = cr
                await asyncio.sleep(self._retry_delay_s)
                continue
            try:
                age_ms = int(cr.get("age_ms", "0"))
            except (TypeError, ValueError):
                age_ms = 0
            if age_ms > self._max_age_ms:
                last_err = {
                    "_status": "stale_frame",
                    "age_ms": str(age_ms),
                    "max_age_ms": str(self._max_age_ms),
                }
                logger.info(
                    "capture stale for %r (age=%dms > %dms), retrying",
                    preset,
                    age_ms,
                    self._max_age_ms,
                )
                await asyncio.sleep(self._retry_delay_s)
                continue
            path = cr.get("path")
            if not path:
                raise CameraError(f"capture response missing path: {cr}")
            return await asyncio.to_thread(Path(path).read_bytes)
        raise CameraError(
            f"capture failed for {preset!r} after {self._retries} attempts: {last_err}"
        )


def stamp_exif_datetime(jpeg_bytes: bytes, when: datetime) -> bytes:
    """Return ``jpeg_bytes`` with EXIF ``DateTimeOriginal`` (tag 36867) set
    to ``when`` (formatted as ``"YYYY:MM:DD HH:MM:SS"`` per the EXIF spec).

    Re-encodes the JPEG via Pillow. The wiki lint reads tag 36867 to verify
    photo-coverage, so this stamp is required for the file to be picked up.
    """
    with Image.open(io.BytesIO(jpeg_bytes)) as im:
        # 36867 = DateTimeOriginal. EXIF format: "YYYY:MM:DD HH:MM:SS".
        exif = im.getexif()
        exif[36867] = when.strftime("%Y:%m:%d %H:%M:%S")
        out = io.BytesIO()
        # Preserve quality; "keep" defers to source quantization tables.
        im.save(out, format="JPEG", exif=exif, quality="keep")
        return out.getvalue()
