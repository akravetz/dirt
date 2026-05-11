---
title: "Hardware — PTZ Camera (OBSBOT Tiny 2 Lite + daemon)"
type: hardware
sources: []
related: [wiki/decisions/2026-04-12-ptz-camera-selection.md, wiki/overview.md, docs/epics/ptz-camera/README.md]
created: 2026-04-15
updated: 2026-05-10
---

# PTZ Camera — OBSBOT Tiny 2 Lite

Programmable pan/tilt/zoom camera for remote plant inspection. Physical camera + vendor SDK + persistent daemon + CLI. The daemon runs as a systemd user service; `scripts/camera` is the thin client any agent, script, or human uses.

## Deployment Status

| Component | Status | Notes |
|-----------|--------|-------|
| OBSBOT Tiny 2 Lite | ✅ Deployed | USB-C via RSHTECH hub. SN RMOWLHI1203JLY, fw 6.2.7.4. |
| `dirt-camera-daemon` | ✅ Running | systemd user service, auto-restart, survives reboot via linger. |
| `scripts/camera` CLI | ✅ Available | Thin client over Unix socket. |
| Per-plant presets | ✅ Calibrated 2026-04-14/15 | A/B/C/D + overview. Stored in `~/.config/dirt/camera.json`. |
| Image capture via daemon | ❌ Not yet | Daemon does PTZ only; captures still go through OpenCV in `src/dirt/services/capture.py`. |
| MCP integration | ❌ Not yet | Planned: expose `look`, `nudge`, `where` as MCP tools. |
| Web UI PTZ panel | ❌ Not yet | Out of scope for MVP. |

## The Daily-Use Interface — `scripts/camera`

Everything an agent or human needs. Never exposes motor coordinates.

```bash
scripts/camera where                       # current state (preset match, zoom, pointing)
scripts/camera look overview               # go to a saved preset
scripts/camera look plant_a                # A/B/C/D by name
scripts/camera home                        # alias for `look overview`
scripts/camera nudge left 5                # 5° left (default step is 5°)
scripts/camera nudge left=3 up=2           # compound move, single RPC
scripts/camera zoom +0.2                   # relative zoom
scripts/camera zoom-to 1.5                 # absolute zoom
```

Directions are in user-frame (`left`/`right`/`up`/`down`). The CLI translates to motor-frame via the sign map in the config file. **Agents should prefer `look <preset>` and `nudge <direction>` over any motor-level commands.**

### Output example

```
$ scripts/camera where
pointing:      at overview
zoom:          1.00x
preset match:  overview (approx, within ~2°)
motor:         pitch=-50.0° yaw=-25.0°
```

`where --json` emits structured output for programmatic callers.

## Breeding Tent Camera — `dirt2`

`dirt2` is the LAN box for the breeding tent camera. It is reachable with `ssh dirt2` as user `akcom` using the local SSH key; see `docs/commands.md` before operating it. The attached camera is a Tinybot camera controlled from that box for breeding-tent inspection.

## Config — `~/.config/dirt/camera.json`

The CLI reads this file. Template committed at `config/camera.json.example`.

```json
{
  "sign_map": {
    "left":  {"axis": "yaw",   "sign":  1},
    "right": {"axis": "yaw",   "sign": -1},
    "up":    {"axis": "pitch", "sign":  1},
    "down":  {"axis": "pitch", "sign": -1}
  },
  "presets": {
    "overview": {"pitch": -50, "yaw": -25, "zoom": 1.0, ...},
    "plant_a":  {"pitch": -38, "yaw": -55, "zoom": 1.5, ...},
    "plant_b":  {"pitch": -60, "yaw": -22, "zoom": 1.4, ...},
    "plant_c":  {"pitch": -47, "yaw":  10, "zoom": 1.5, ...},
    "plant_d":  {"pitch": -35, "yaw": -24, "zoom": 1.5, ...}
  }
}
```

### Sign map

`sign_map` encodes the mount-dependent relationship between user-frame ("left") and motor-frame ("yaw + positive delta"). Derived empirically 2026-04-14 at the current camera mount. If the camera is physically remounted, the sign map almost certainly needs re-derivation.

### Presets

Per-plant close-up and overview gimbal coordinates, locked in during the 2026-04-14 and 2026-04-15 calibration sessions. Plant identifier stickers on pot rims (A=yellow, B=orange, C=pink, D=blue) and on the tent walls above each plant.

**Caveat:** presets go stale as plants grow — the canopy that fills `plant_a`'s frame on day 30 will overflow it on day 60. Budget ~weekly recalibration.

**Plant B note:** zoom=1.4 (not 1.5 like the others) because at 1.5x the orange pot sticker falls below the pitch=-60 physical floor. A wider zoom keeps the pot in frame.

## Daemon — `services/camera-daemon/`

C++ long-lived process, ~500 LoC, vendors the OBSBOT `libdev v2.1.0_8` SDK.

### Why a daemon

Each process that opens the OBSBOT SDK pays ~3.4 s in hotplug discovery. Ten iterative gimbal moves via ephemeral binaries = 34 s of pure overhead. A persistent daemon holds the SDK session open and serves commands over a Unix socket in tens of milliseconds.

### What it handles automatically

| Surprise | How it's hidden |
|---|---|
| Partial-move quirk (large pitch jumps clamp short) | Auto-retry via step-through: move to midpoint, then target. Up to 3 retries. |
| ~3.4 s per-call SDK init overhead | Persistent session, socket IPC. |
| Pitch/yaw physical limits | Clamped at the hardware; `limit_reached` status returned. |
| Zoom soft-cap (~2.0x on Tiny 2 Lite) | Clamped to 2.0, reports `zoom_capped=true`. |
| USB hot-unplug | `setDevChangedCallback` wired; daemon re-acquires on re-plug within ~5 s. **Caveat:** if the device stays gone longer than systemd's restart-burst window (~30–45 s), the service hits the burst cap and will not auto-recover even after replug — see Known quirk #8. |
| Stale socket on restart | Daemon unlinks and rebinds. |

### Wire protocol

Line-oriented text over Unix socket (`$XDG_RUNTIME_DIR/dirt-camera.sock`, mode 0600). Commands: `ping`, `health`, `get_state`, `resync`, `move_motor <pitch> <yaw>`, `set_zoom <zoom>`. Full protocol in `services/camera-daemon/README.md`.

### Running

Systemd user service, runs on boot via `loginctl enable-linger`:

```bash
systemctl --user status dirt-camera      # status
systemctl --user restart dirt-camera     # restart (keeps linger intact)
journalctl --user -u dirt-camera -f      # SDK diagnostic output
tail -f ~/.local/state/dirt/camera.log   # structured daemon log
```

### Build (after code changes)

```bash
cd services/camera-daemon && ./build.sh
systemctl --user restart dirt-camera
```

## Hardware specs

| Parameter | Value |
|-----------|-------|
| Model | OBSBOT Tiny 2 Lite |
| Sensor | 4K, 1/2" |
| Pan range | ±120° motor (physical limit; overview is at yaw=-25°) |
| Tilt range | -90° to +90° motor (physical limit; floor observed at -60°) |
| Zoom | 1.0x to 2.0x effective (SDK advertises 4.0x) |
| Connection | USB-C |
| Mount | Hook in tent, camera hanging inverted; SDK auto-orients the image |
| Serial | RMOWLHI1203JLY |
| Firmware | 6.2.7.4 |

### Mount orientation

Camera is mounted inverted. IMU at motor (0, 0) reports roll_euler ≈ 0, pitch_euler ≈ 140°. **This mount-to-world mapping is the reason the sign map exists** — the naive "positive yaw = right" convention doesn't hold here. Empirical finding: more positive yaw shifts the scene LEFT in the image (camera pans right). Similarly more negative pitch tilts the camera DOWN (scene shifts UP in image).

### Physical limits

- **Pitch floor: ~-60°** — further-negative commands silently clamp. Discovered during plant B calibration on 2026-04-15 (earlier we thought it was -55° due to the partial-move quirk; stepping through -55° first unlocks -60°).
- **Pitch ceiling: +85°** — similar clamp behavior.
- **Yaw: approximately ±120°** — not tested to full range.

## Host configuration — udev rule for `/dev/webcam`

The capture path (`src/dirt/services/capture.py`) opens the OBSBOT at `/dev/webcam` by default. That symlink is created by a udev rule at `/etc/udev/rules.d/99-dirt-webcam.rules`:

```
SUBSYSTEM=="video4linux", ATTR{index}=="0", ATTRS{idVendor}=="3564", ATTRS{idProduct}=="fef9", SYMLINK+="webcam"
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="3564", ATTR{idProduct}=="fef9", ATTR{power/autosuspend}="-1"
```

- `3564:fef9` is the OBSBOT Tiny 2 Lite's USB vendor/product ID (confirmed via `lsusb`).
- `ATTR{index}=="0"` picks the capture node, not the metadata node (OBSBOT exposes both as `/dev/video0` and `/dev/video1`; capture is always index 0).
- The autosuspend-disable prevents idle USB disconnects.

**Historical gotcha (2026-04-15):** this rule was originally written for a Logitech C920 (`046d:08e5`) and filtered on the C920's USB IDs. When the C920 was swapped out for the OBSBOT, the rule was never updated, so it matched nothing and `/dev/webcam` silently disappeared on every reboot/replug. Manually creating the symlink worked until the next replug. **Root cause, not a recurring bug.** If we ever swap cameras again, update the vendor/product IDs in this rule.

After editing the rule:

```bash
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=video4linux
ls -la /dev/webcam   # verify
```

## `/dev/video0` sharing — daemon does NOT exclusively lock it

The `dirt-camera-daemon` holds an open fd on `/dev/video0` (the OBSBOT vendor SDK opens it internally for UVC extension-unit control), but the handle is non-streaming. OpenCV / other v4l2 clients can open the same node concurrently and stream frames. If you see `can't open camera by index` from OpenCV, suspect a **leaked worker process from a previous failed run** before blaming the daemon — check `sudo fuser /dev/video0`.

## Related files

- `services/camera-daemon/` — daemon source + vendored libdev + README
- `scripts/camera` — Python CLI thin client
- `systemd/dirt-camera.service` — user systemd unit
- `config/camera.json.example` — config template (copy to `~/.config/dirt/`)
- `config/logrotate.conf` — weekly log rotation, 4-week retention
- `debug/` — legacy one-off C++ helpers (`obsbot_move`, `obsbot_zoom`, `obsbot_probe`, `obsbot_orientation`) and calibration scripts (`find_sticker.py`, `camera_mvp.py`). Superseded by the daemon for production use but kept for reference / future calibration work.
- `wiki/decisions/2026-04-12-ptz-camera-selection.md` — why we chose this camera
- `docs/epics/ptz-camera/README.md` — epic scope and remaining integration work
## Known quirks (full list for future debugging)

1. **Partial-move** — large pitch or yaw jumps can clamp mid-travel. The daemon's step-through retry handles it transparently, but if you see `retries > 0` in a response, this is why.
2. **~3.4 s SDK hotplug discovery** — only matters on daemon cold start, not per-command.
3. **Zoom > 2.0x** — silently clamps. Never advertise >2.0x to the agent.
4. **Mount inversion** — the SDK auto-orients images correctly. Do NOT apply software rotation to captures. (An older `--rotate` flag in `debug/camera_mvp.py` is a debugging artifact and makes things worse.)
5. **Sticker-vs-plant parallax** — sticker on pot rim ≠ plant center; preset yaw values bake in the offset. If adding a new plant, center visually.
6. **Plant growth drift** — presets age as canopy grows; recalibrate every 1–2 weeks.
7. **Lights-off** — PTZ commands work in dark, but captures are unusable. Daemon doesn't check lights status; image callers must handle this.
8. **Intermittent USB dropouts (potentially recurring — investigate hardware if it recurs)** — Camera has self-disconnected from USB with no physical intervention at least twice: an earlier V4L2 `ENODEV` hot-spin fixed in commit `1ef1020`, and 2026-04-22 08:58 MDT (`remove uvc device: RMOWLHI1203JLY`; camera gone from `lsusb` / `/dev/video*` for ~25 min, reappeared spontaneously). During the outage the 30 s watchdog correctly killed each restart (no camera → no keepalives) and the burst cap (commit `554c272`) stopped the loop after 6 tries; **burst-capped services do not auto-retry**, so recovery after replug needs `systemctl --user reset-failed dirt-camera && systemctl --user start dirt-camera`. If this recurs, do NOT loosen the watchdog or raise the burst cap (they're the correct backstop against thrash) — investigate hardware root cause: USB-C cable, RSHTECH hub, camera PSU, camera thermal.
