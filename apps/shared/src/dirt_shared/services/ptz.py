"""PTZ service — thin wrapper over the dirt-camera daemon + preset config.

The daemon (``services/camera-daemon``) owns all gimbal state; this
service just issues line-protocol RPCs via
``dirt_shared.services.capture._daemon_rpc`` and reads the user-level
preset config at ``~/.config/dirt/camera.json``.

All four PTZ endpoints (``GET /api/ptz/state``, ``POST /api/ptz/preset/
{id}``, ``POST /api/ptz/look``, ``POST /api/ptz/zoom``) use this
service. It is constructor-injected with:

- ``rpc``: an async callable matching ``_daemon_rpc``'s signature
  (``(line: str) -> dict[str, str]``). Tests inject a fake to avoid
  touching the daemon socket.
- ``config_path``: path to ``camera.json``. Defaults to
  ``~/.config/dirt/camera.json``; tests point at a tmp file.
- ``sticker_colors``: override map ``preset_id → sticker_color``. The
  camera.json format does not carry sticker colors today; the API
  contract wants them for the plant presets so the SPA can render the
  colored dot next to each preset button. The default map mirrors the
  current grow labeling (A=yellow, B=orange, C=pink, D=blue).
"""

from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from dirt_shared.services.capture import _daemon_rpc as _default_rpc

# Camera motor limits — mirror the daemon's clamp. Empirically the
# OBSBOT Tiny 2 Lite yaw ranges ±150°, pitch ranges approximately
# -90°..+30°. Keeping these as module constants so /api/ptz/look
# can clamp symmetrically before the RPC round-trip.
YAW_MIN, YAW_MAX = -150.0, 150.0
PITCH_MIN, PITCH_MAX = -90.0, 30.0
ZOOM_MIN, ZOOM_MAX = 1.0, 2.0

# "At a preset" tolerance in degrees — PTZState.preset is the id if
# current yaw/pitch/zoom are within this of a preset, else null.
PRESET_TOLERANCE_DEG = 2.0
PRESET_TOLERANCE_ZOOM = 0.1

# Click-to-look motion model — normalized xy (-0.5..0.5) maps to a
# yaw/pitch delta. Field of view is wider horizontally than vertical
# on the OBSBOT, so the angular coverage differs per axis.
LOOK_YAW_RANGE_DEG = 60.0
LOOK_PITCH_RANGE_DEG = 40.0

Rpc = Callable[[str], Awaitable[dict[str, str]]]

StickerColor = Literal["yellow", "orange", "pink", "blue"]

DEFAULT_STICKER_COLORS: dict[str, StickerColor] = {
    "plant_a": "yellow",
    "plant_b": "orange",
    "plant_c": "pink",
    "plant_d": "blue",
}


@dataclass(frozen=True)
class PresetEntry:
    id: str
    label: str
    description: str
    yaw: float
    pitch: float
    zoom: float
    sticker_color: StickerColor | None = None


def _label_for(preset_id: str) -> str:
    """``plant_a`` → ``Plant A``, ``overview`` → ``Overview``."""
    return preset_id.replace("_", " ").title()


def _strip_comments(obj: object) -> object:
    """Strip underscore-prefixed keys the camera.json format uses for comments."""
    if isinstance(obj, dict):
        return {
            k: _strip_comments(v)
            for k, v in obj.items()
            if not (isinstance(k, str) and k.startswith("_"))
        }
    if isinstance(obj, list):
        return [_strip_comments(x) for x in obj]
    return obj


def _default_config_path() -> Path:
    return Path.home() / ".config" / "dirt" / "camera.json"


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class PTZService:
    """Facade over the daemon RPC + camera.json preset list."""

    def __init__(
        self,
        *,
        rpc: Rpc | None = None,
        config_path: Path | None = None,
        sticker_colors: dict[str, StickerColor] | None = None,
    ) -> None:
        self._rpc = rpc or _default_rpc
        self._config_path = config_path or _default_config_path()
        self._sticker_colors = (
            DEFAULT_STICKER_COLORS if sticker_colors is None else sticker_colors
        )

    # ---- config ----

    def load_presets(self) -> list[PresetEntry]:
        """Parse ``camera.json`` and return the preset list."""
        raw = json.loads(self._config_path.read_text())
        raw = _strip_comments(raw)
        presets = raw.get("presets") or {}
        if not isinstance(presets, dict):
            return []
        out: list[PresetEntry] = []
        for pid, p in presets.items():
            if not isinstance(p, dict):
                continue
            out.append(
                PresetEntry(
                    id=pid,
                    label=_label_for(pid),
                    description=str(p.get("description", "")),
                    yaw=float(p.get("yaw", 0.0)),
                    pitch=float(p.get("pitch", 0.0)),
                    zoom=float(p.get("zoom", 1.0)),
                    sticker_color=self._sticker_colors.get(pid),
                )
            )
        return out

    def get_preset(self, preset_id: str) -> PresetEntry | None:
        for p in self.load_presets():
            if p.id == preset_id:
                return p
        return None

    # ---- daemon state ----

    async def get_state(self) -> dict:
        """Return a PTZState-shaped payload from the daemon.

        Shape matches ``dirt_contracts.webapp_v1.models.PTZState`` —
        the endpoint just wraps this in the Pydantic model.
        """
        resp = await self._rpc("get_state")
        presets = self.load_presets()

        if resp.get("_status") != "ok":
            return {
                "connected": False,
                "yaw": 0.0,
                "pitch": 0.0,
                "zoom": 1.0,
                "preset": None,
                "presets": [self._preset_to_dict(p) for p in presets],
            }

        yaw = float(resp.get("motor_yaw", 0.0))
        pitch = float(resp.get("motor_pitch", 0.0))
        zoom = float(resp.get("zoom", 1.0))
        connected = _parse_bool(resp.get("camera_connected", "true"))
        current = _match_preset(yaw, pitch, zoom, presets)

        return {
            "connected": connected,
            "yaw": yaw,
            "pitch": pitch,
            "zoom": zoom,
            "preset": current,
            "presets": [self._preset_to_dict(p) for p in presets],
        }

    # ---- movement ----

    async def apply_preset(self, preset_id: str) -> dict:
        """Move to the named preset. Returns a PTZApplied-shaped dict."""
        preset = self.get_preset(preset_id)
        if preset is None:
            raise UnknownPresetError(preset_id)

        move_resp, zoom_resp = await asyncio.gather(
            self._rpc(f"move_motor {preset.pitch:.2f} {preset.yaw:.2f}"),
            self._rpc(f"set_zoom {preset.zoom:.2f}"),
        )

        ok = (
            move_resp.get("_status") in ("ok", "limit_reached")
            and zoom_resp.get("_status") == "ok"
        )
        yaw = float(move_resp.get("motor_yaw", preset.yaw))
        pitch = float(move_resp.get("motor_pitch", preset.pitch))
        zoom = float(zoom_resp.get("zoom", preset.zoom))
        return {
            "ok": ok,
            "yaw": yaw,
            "pitch": pitch,
            "zoom": zoom,
            "preset": preset.id if ok else None,
        }

    async def look_at_normalized(self, x: float, y: float) -> dict:
        """Click-to-look. ``x``/``y`` are normalized frame coords in [-0.5, 0.5].

        Reads the current motor position first, applies the
        ``x * LOOK_YAW_RANGE_DEG`` / ``y * LOOK_PITCH_RANGE_DEG`` deltas,
        clamps to motor limits, and issues the move.
        """
        state_resp = await self._rpc("get_state")
        if state_resp.get("_status") != "ok":
            return {
                "ok": False,
                "yaw": 0.0,
                "pitch": 0.0,
                "zoom": 1.0,
                "preset": None,
            }

        cur_yaw = float(state_resp.get("motor_yaw", 0.0))
        cur_pitch = float(state_resp.get("motor_pitch", 0.0))
        cur_zoom = float(state_resp.get("zoom", 1.0))

        new_yaw = clamp(cur_yaw + x * LOOK_YAW_RANGE_DEG, YAW_MIN, YAW_MAX)
        new_pitch = clamp(cur_pitch + y * LOOK_PITCH_RANGE_DEG, PITCH_MIN, PITCH_MAX)

        move_resp = await self._rpc(f"move_motor {new_pitch:.2f} {new_yaw:.2f}")
        ok = move_resp.get("_status") in ("ok", "limit_reached")
        return {
            "ok": ok,
            "yaw": float(move_resp.get("motor_yaw", new_yaw)),
            "pitch": float(move_resp.get("motor_pitch", new_pitch)),
            "zoom": cur_zoom,
            "preset": None,
        }

    async def zoom_to(self, value: float) -> dict:
        """Absolute zoom."""
        target = clamp(value, ZOOM_MIN, ZOOM_MAX)
        resp = await self._rpc(f"set_zoom {target:.2f}")
        ok = resp.get("_status") == "ok"
        return {"ok": ok, "zoom": float(resp.get("zoom", target))}

    async def zoom_by(self, delta: float) -> dict:
        """Relative zoom — read current zoom, apply delta, clamp."""
        state_resp = await self._rpc("get_state")
        if state_resp.get("_status") != "ok":
            return {"ok": False, "zoom": 1.0}
        cur = float(state_resp.get("zoom", 1.0))
        return await self.zoom_to(cur + delta)

    # ---- helpers ----

    def _preset_to_dict(self, p: PresetEntry) -> dict:
        return {
            "id": p.id,
            "label": p.label,
            "description": p.description,
            "yaw": p.yaw,
            "pitch": p.pitch,
            "zoom": p.zoom,
            "sticker_color": p.sticker_color,
        }


class UnknownPresetError(Exception):
    """Raised by ``apply_preset`` when the id isn't in ``camera.json``."""

    def __init__(self, preset_id: str) -> None:
        super().__init__(f"unknown preset '{preset_id}'")
        self.preset_id = preset_id


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return False


def _match_preset(
    yaw: float, pitch: float, zoom: float, presets: list[PresetEntry]
) -> str | None:
    for p in presets:
        if (
            math.isclose(yaw, p.yaw, abs_tol=PRESET_TOLERANCE_DEG)
            and math.isclose(pitch, p.pitch, abs_tol=PRESET_TOLERANCE_DEG)
            and math.isclose(zoom, p.zoom, abs_tol=PRESET_TOLERANCE_ZOOM)
        ):
            return p.id
    return None
