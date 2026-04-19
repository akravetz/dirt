---
title: Grow Overview
type: overview
sources: [raw/chat-history/all-chat-summary.md, raw/chat-history/bible.md, raw/chat-history/memory.md]
related: [wiki/index.md, wiki/plants/plant-a.md, wiki/plants/plant-b.md, wiki/plants/plant-c.md, wiki/plants/plant-d.md]
created: 2026-04-06
updated: 2026-04-18
---

# Grow Overview

## Setup

| Parameter | Detail |
|-----------|--------|
| **Strain** | Sirius Black (Reversed) x BS01 — Feminized |
| **Goal** | Dark purple phenotype, terpene complexity, exceptional bag appeal |
| **Location** | Bedroom closet, Denver CO |
| **Tent** | VIVOSUN S448 4x4 (48"×48"×80") |
| **Light** | Medic Grow Fold-650 (650W LED) |
| **Medium** | Coco/Perlite 60/40 |
| **Nutrients** | Canna Coco A+B (sole product) |
| **Water system** | Autopot 4-Pot XL + 25-gal FlexiTank (hand-watering phase; activation window opens Apr 12) |
| **Training** | Single top at node 4–5 → LST → SCROG |
| **Start date** | 2026-03-15 (germination) |
| **Grow day** | Day 35 (as of 2026-04-18) |

## Current Stage

**Early Veg** — Autopot system active since Apr 15 (reservoir filled, float valves open). **All four plants topped** (A: Apr 11; B/C/D: Apr 12) and fully recovered — Day 6–7 post-topping. **SCROG net installed Apr 18** at 11" above canopy / 18" above pot base (VIVOSUN 4x4 trellis; matches plan spec). **LST pending** — starts once the two new main shoots per plant clear ~2" (expected within 1–3 days). Overnight environment flag: lights-off temp drops to ~63°F, RH spikes to ~77% — humidifier nighttime setpoint reduction recommended.

**Light schedule:** 18/6
**Light intensity:** ~40% Fold-650 (ramped from 30% per Apr 8 recommendation)

## Plant Status

| Plant | Nodes | Purple | Priority | Status |
|-------|-------|--------|----------|--------|
| Plant A | 5+ (topped, branching) | ✅ Confirmed genetic | 🔴 Primary | 🟡 **LST pending** — Day 7 post-topping; vigorous multi-branch canopy; waiting for main shoots to size up (~2") |
| Plant B | — (topped, branching) | ❌ None | 🟡 Secondary | 🟡 **LST pending** — Day 6 post-topping; most vigorous canopy; morning moisture dip (autopot cycle) |
| Plant C | — (topped, branching) | ⚠️ Stress-induced only | 🟡 Secondary | 🟡 **LST pending** — Day 6 post-topping; compact healthy canopy; moisture stable ~40% |
| Plant D | — (topped, branching) | ✅ Confirmed genetic | 🔴 Primary | 🟡 **LST pending** — Day 6 post-topping; healthy canopy; v2.0 sensor installed today |

## Environment (Last Reading: Apr 18 14:00 MDT)

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Temperature (now) | 73.85°F | 74–76°F | ⚠️ Slightly low |
| Temperature (overnight avg) | 63.54°F | 68–72°F night | ⚠️ Well below target |
| Humidity (now) | 59.13% | 55–65% | ✅ |
| Humidity (overnight avg) | 76.95% | 55–65% | ⚠️ Too high |
| VPD (now) | 1.17 kPa | 0.8–1.2 kPa | ✅ |
| VPD (overnight avg) | 0.46 kPa | 0.8–1.2 kPa | ⚠️ Too low (seedling range) |
| pH (watering) | 5.8 (target) | 5.5–6.0 | — |
| EC (reservoir) | — | 0.8–1.0 | ⚠️ Verify at next fill |

## Active Action Items

1. **Begin LST on all 4 plants — as soon as main shoots size up** 🔴 — Day 35, Day 6–7 post-topping. SCROG net is in; waiting on new shoots to reach ~2" (expected 1–3 days). Then gently bend outward at ~45° and anchor to pot rim; tuck into nearest net squares as shoots extend. Start with Plant A (longest recovery)
2. **Lower overnight humidifier setpoint** 🟡 — overnight RH 76.95%, VPD 0.46 kPa; reduce bang-bang nighttime target to ~55% or schedule humidifier OFF during lights-off
3. **Address overnight temperature** 🟡 — 63.54°F overnight avg; reduce exhaust fan speed at lights-off or add space heater on a timer; target 68–72°F night
4. **Verify EC in reservoir** — was 1.84 before activation (Apr 15); confirm diluted to 0.8–1.0 at next reservoir change
5. **Continue light ramp** — at 40%; step to 50% once LST stress resolves (~5–7 days)

## Upcoming Milestones

| Milestone | Estimated Timing |
|-----------|-----------------|
| ~~Plant C diagnosis~~ | ✅ Resolved |
| ~~Topping all plants~~ | ✅ Done Apr 11–12 |
| ~~Float valve activation~~ | ✅ Done Apr 15 |
| ~~SCROG net install~~ | ✅ Done Apr 18 (11" above canopy / 18" above pot base) |
| **LST all plants** | **1–3 days (as shoots reach ~2")** |
| First reservoir change | ~Apr 22–25 (7–10 days post-activation) |
| 12/12 flip | SCROG 70% full |
| Clone selection | Flower weeks 3–4 |
| Final pheno evaluation | Flower weeks 5–6 |

## Pheno Hunt Summary

**Primary keepers:** Plants A and D — both strong purple contenders with confirmed genetic anthocyanin expression.
- **Plant A** — vigor leader, confirmed genetic anthocyanin. Most vigorous plant overall. Standout candidate.
- **Plant D** — confirmed genetic anthocyanin (stem, petioles, cotyledons). About a day behind A in vigor, healthy.

**Plant C purple note:** Stress-induced purple (stems/petioles, Day 25) concurrent with worsening leaf symptoms — pH/deficiency stress, not genetic. Does not change secondary status.

**Strategy:** Run all 4 to flower weeks 5–6. Evaluate purple calyx depth, aroma, bud structure, stretch, health. Clone top candidate(s) before flower weeks 3–4 for Grow #2.

## System Status

| Component | Status | Notes |
|-----------|--------|-------|
| **Arduino Nano + DHT22** | Online | Temp/humidity readings via USB serial |
| **Plant-A ESP32-C3 node** | Online (2026-04-14) | GPIO3 capacitive v1.2; POSTs every 30s; OTA-ready |
| **Plant-B ESP32-C3 node** | Online (2026-04-16) | v2.0 sensor; 192.168.1.243; fresh calibration |
| **Plant-C ESP32-C3 node** | Online (2026-04-16) | v2.0 sensor; 192.168.1.117; reused dev unit; fresh calibration |
| **Plant-D ESP32-C3 node** | Online (2026-04-14) | GPIO3 capacitive v1.2; POSTs every 30s; OTA-ready |
| **CO2 sensor** (MH-Z19B) | Planned | Not yet deployed |
| **Reservoir level** (XKC-Y25-T12V) | Planned | Not yet deployed |
| **Humidifier control** (Raydrop 4L + Kasa EP10 smart plug) | Plug on hand; service not yet built | Closed-loop RH control via host-side Python service + `python-kasa` (supersedes the earlier SSR plan). See `hardware/humidifier-control.md`. |
| **PTZ camera** (OBSBOT Tiny 2 Lite) | Online (2026-04-15) | Persistent C++ daemon + `scripts/camera` CLI. Per-plant presets calibrated. See `hardware/ptz-camera.md`. |
| **Jabra Speak 410** (voice I/O) | Connected 2026-04-15 | Full voice pipeline proven end-to-end: openWakeWord v3 (89% recall) → Deepgram Nova-3 STT → ElevenLabs "Claudia" TTS. Production `channels/voice.py` pending. See `hardware/jabra.md`. |

## Denver Water Notes
- Tap pH: 8.5–8.8 → GH pH Down required at every fill
- Chloramines (not free chlorine) → do NOT off-gas; use as-is after pH adjustment
- Target pH: 5.8 after nutrients; range 5.5–6.0
