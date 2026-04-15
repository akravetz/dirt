# Epic: PTZ Camera Integration

Status: partial — camera control shipped; FastAPI/MCP/UI integration remaining
Priority: high
Created: 2026-04-12
Last updated: 2026-04-15

## What's Shipped

- **OBSBOT Tiny 2 Lite** deployed and operational (SN RMOWLHI1203JLY, fw 6.2.7.4).
- **`dirt-camera-daemon`** at `services/camera-daemon/` — persistent C++ SDK wrapper. Auto-retry for partial-move, hotplug recovery, runs as systemd user service, vendored libdev version-controlled.
- **`scripts/camera`** CLI — user-frame commands (`look`, `nudge`, `zoom`, `where`). Config at `~/.config/dirt/camera.json`.
- **Per-plant presets** calibrated (A/B/C/D + overview) with colored-sticker identification.
- See [`wiki/hardware/ptz-camera.md`](../../../wiki/hardware/ptz-camera.md) for the full operational spec.

## What's Still Out

- **Image capture via the daemon** — currently captures still use the OpenCV path in `src/dirt/services/capture.py`. The daemon does PTZ only.
- **FastAPI integration** — no endpoint wraps the daemon yet. Web clients can't pan/tilt/zoom through the app.
- **MCP tools** — `go_to_preset`, `move_camera`, `get_camera_position`, `capture_photo` not yet exposed to Claude Desktop.
- **Web UI PTZ panel** — no directional pad, no preset buttons, no live preview coupled to PTZ.
- **Automated daily capture at presets** — cycle through all 5 presets once per day, drop frames into `raw/photos/` with preset-named filenames for wiki ingestion.

## Goal

Replace the static Logitech C920 webcam with an OBSBOT Tiny 2 Lite PTZ camera that Claude can control programmatically — enabling remote plant inspection, automated photo capture from multiple angles, and on-demand close-ups for health assessment.

## Hardware

| Component | Model | Specs |
|-----------|-------|-------|
| PTZ Camera | OBSBOT Tiny 2 Lite | 4K, 1/2" sensor, 60fps, HDR, AI tracking |
| Connection | USB-C | Via RSHTECH 10-port hub |

**PTZ Range:**
- Pan: +/-140 degrees
- Tilt: +30 to -70 degrees
- Zoom: digital zoom (4K sensor crops to 1080p regions)

**Control Interfaces:**
- OBSBOT SDK (official, request from obsbot.com/sdk — supports Linux/Windows/macOS)
- OSC (Open Sound Control) protocol for real-time PTZ commands
- Gesture control (built-in, AI-powered)
- Community reverse-engineering projects exist for direct USB control

## Scope

### Camera Control Service
- Python service wrapping OBSBOT SDK or OSC protocol
- Pan, tilt, zoom commands with absolute positioning
- Query current position state
- Preset positions: per-plant views (A, B, C, D), canopy overview, close-up macro

### Web UI
- PTZ control panel (directional pad, zoom slider)
- Preset position buttons (one per plant + overview)
- Live preview while adjusting

### MCP Integration
- MCP tools for Claude Desktop: `move_camera`, `get_camera_position`, `capture_photo`, `go_to_preset`
- Claude can autonomously inspect plants by cycling through presets

### Automated Capture
- Scheduled photo capture at all presets (e.g., daily at lights-on)
- Photos saved to `raw/photos/` with EXIF metadata for wiki ingestion
- Filename convention includes preset name: `PXL_YYYYMMDD_HHMMSS_plant-a.jpg`

### Wiki Integration
- `wiki/hardware/ptz-camera.md` documenting the deployed system, presets, mounting
- Daily photos from automated capture feed into wiki ingestion workflow

## Acceptance Criteria

- Camera can pan, tilt, and zoom via software commands from Python
- Web UI provides manual PTZ controls with live preview
- MCP server exposes PTZ control tools
- At least 5 preset positions defined (one per plant + canopy overview)
- Automated daily capture at presets produces photos usable for wiki updates
- Camera position state is queryable
- Replaces C920 for both live feed and photo capture

## References

### OBSBOT Tiny 2 Lite
- [OBSBOT Tiny 2 Lite product page](https://www.obsbot.com/obsbot-tiny-2-lite-4k-webcam) — official specs, features
- [OBSBOT SDK portal](https://www.obsbot.com/sdk) — request access to official SDK (Linux/Windows/macOS)
- [OBSBOT Tiny 2 Lite review (MakeUseOf)](https://www.makeuseof.com/obsbot-tiny-2-lite-review/) — real-world PTZ performance review
- [obsbot-controller (GitHub)](https://github.com/broody/obsbot-controller) — community Linux controller for OBSBOT devices
- [OBSBOT UVC to NDI VISCA Control Guide](https://www.obsbot.com/explore/accessories/uvc-to-ndi-adapter-visca-control-guide) — VISCA protocol control reference

### PTZ Control Protocols
- [OBSBOT Tiny 2 Lite OSC control overview](https://supabase.probono.net/data-say/obsbot-tiny-2-lite-features-osc-control-and-more-1764797057) — OSC (Open Sound Control) for real-time PTZ commands
- [obsbot_tiny_reversing (GitHub)](https://github.com/taxfromdk/obsbot_tiny_reversing) — reverse-engineering project for direct USB control

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:ptz-camera"`
