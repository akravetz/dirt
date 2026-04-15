---
title: "Audio Hardware Selection: Jabra Speak 410"
type: decision
sources: []
related: []
created: 2026-04-12
updated: 2026-04-12
---

# Decision: Audio Hardware Selection — Jabra Speak 410

**Date:** 2026-04-12
**Status:** Accepted

## Context

To enable live voice communication with Claude near the grow tent — the user speaks naturally, Claude responds audibly — we need a mic + speaker solution. The tent is in a bedroom closet in Denver, with fans running 24/7.

## Decision

**Jabra Speak 410** — USB corded speakerphone.

## Rationale

- Single USB device handles both mic and speaker (no separate components)
- Omnidirectional mic with good pickup radius, designed for conference calls
- Full-duplex audio — can hear and speak simultaneously
- Shows up as standard USB audio device on Linux, no drivers needed
- Physical mute button for privacy
- Sits outside the tent near the monitoring host (not inside — too humid)
- Portable, compact form factor
- Proven reliability (conference room staple)

## Placement

Jabra sits on the desk/shelf near the tent, outside the tent enclosure. Audio path is short (closet setup). No concerns about humidity exposure or light leaks during dark period.
