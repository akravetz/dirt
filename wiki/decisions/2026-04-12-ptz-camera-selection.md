---
title: "PTZ Camera Selection: OBSBOT Tiny 2 Lite"
type: decision
sources: []
related: []
created: 2026-04-12
updated: 2026-04-12
---

# Decision: PTZ Camera Selection — OBSBOT Tiny 2 Lite

**Date:** 2026-04-12
**Status:** Accepted

## Context

The existing Logitech C920 provides a static live feed. To enable remote plant inspection — Claude autonomously looking at individual plants, capturing multi-angle photos for wiki ingestion, and responding to user requests like "show me Plant A" — we need a camera with programmatic pan, tilt, and zoom control.

## Decision

**OBSBOT Tiny 2 Lite** — 4K PTZ webcam with AI tracking.

## Key Specs

- 4K resolution, 1/2" sensor, 60fps, HDR
- Pan: +/-140 degrees, Tilt: +30 to -70 degrees
- Digital zoom (4K sensor crops to high-quality 1080p regions)
- AI tracking with gesture control (built-in)
- USB-C connection
- Official SDK (Linux/Windows/macOS) + OSC protocol for programmatic control

## Rationale

- Single USB device replaces the C920 — no separate PTZ controller or IP camera networking needed
- OBSBOT SDK and OSC protocol provide programmatic PTZ control from Python
- 4K sensor means digital zoom produces usable close-ups for plant health assessment
- AI tracking is a bonus — could auto-follow hand movements during plant work
- Well-documented, active community (including reverse-engineering projects for deeper control)
- Replaces C920 for both live feed and photo capture duties
