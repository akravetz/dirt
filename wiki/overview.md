---
title: Grow Overview
type: overview
sources: [raw/chat-history/all-chat-summary.md, raw/chat-history/bible.md, raw/chat-history/memory.md]
related: [wiki/index.md, wiki/plants/plant-a.md, wiki/plants/plant-b.md, wiki/plants/plant-c.md, wiki/plants/plant-d.md]
created: 2026-04-06
updated: 2026-04-20
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
| **Water system** | Autopot 4-Pot XL + 25-gal FlexiTank (active since Apr 15) |
| **Training** | Single top at node 4–5 → LST → SCROG |
| **Start date** | 2026-03-15 (germination) |
| **Grow day** | Day 37 (as of 2026-04-20) |

## Current Stage

**Early Veg** — Autopot active since Apr 15. **All four plants topped** (A: Apr 11; B/C/D: Apr 12) — Day 9/8 post-topping. **SCROG net installed Apr 18** at 11" above canopy / 18" above pot base. **LST is critically overdue** — begins today. Canopy is pushing toward net level.

Daytime environment is now in target for the first time: 75.04°F and 1.12 kPa VPD at the 14:00 check. Overnight profile regressed (74.37% RH / 66.84°F) — the `dirt-hwd` service restart deployed Apr 19 is still pending; restarting before tonight's lights-off is critical.

**Light schedule:** 18/6 (lights on ~05:00–23:00 MDT)
**Light intensity:** ~40% Fold-650

## Plant Status

| Plant | Nodes | Purple | Priority | Status |
|-------|-------|--------|----------|--------|
| Plant A | 5+ (topped, branching) | ✅ Confirmed genetic | 🔴 Primary | 🔴 **LST critically overdue** — Day 9 post-topping; vigorous medium-green multi-branch canopy; moisture stable ~52% |
| Plant B | — (topped, branching) | ❌ None | 🟡 Secondary | 🔴 **LST critically overdue** — Day 8 post-topping; densest/darkest canopy; autopot fed aggressively (58% at 14:00) |
| Plant C | — (topped, branching) | ⚠️ Stress-induced only | 🟡 Secondary | 🔴 **LST critically overdue** — Day 8 post-topping; compact symmetrical healthy canopy; moisture stable ~51% |
| Plant D | — (topped, branching) | ✅ Confirmed genetic | 🔴 Primary | 🔴 **LST critically overdue** — Day 8 post-topping; ⚠️ lighter green than peers — monitoring; moisture stable ~42% |

## Environment (Last Reading: Apr 20 14:00 MDT)

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Temperature (now) | 75.04°F | 74–76°F day | ✅ In range |
| Temperature (morning avg) | 74.43°F | 74–76°F day | ✅ In range |
| Temperature (overnight avg) | 66.84°F | 68–72°F night | ⚠️ Below floor (regression — service restart pending) |
| Humidity (now) | 62.37% | 55–65% | ✅ In range |
| Humidity (overnight avg) | 74.37% | 55–65% | ⚠️ Elevated (regression from 70.79%) |
| VPD (now) | 1.12 kPa | 0.8–1.2 kPa | ✅ In range |
| VPD (morning avg) | 1.41 kPa | 0.8–1.2 kPa | ⚠️ Above ceiling |
| VPD (overnight avg) | 0.57 kPa | 0.8–1.2 kPa | ⚠️ Below floor |
| pH (watering) | 5.8 (target) | 5.5–6.0 | — |
| EC (reservoir) | — | 0.8–1.0 | ⚠️ Verify at next fill |

## Active Action Items

1. **Restart `dirt-hwd` service before lights-off tonight** 🔴 — `systemctl --user restart dirt-hwd`. Lights-off feedforward and dropped safety timers (deployed Apr 19) cannot activate until restarted. This is causing overnight RH elevation and VPD undershoot.
2. **Begin LST on all 4 plants — today** 🔴 — Day 9/8 post-topping; critically overdue. Bend outward at ~45°, anchor to pot rim; tuck into SCROG net squares as shoots extend. Start with Plant A.
3. **Monitor Plant D color** 🟡 — Lighter green than peers at today's 14:00 check. Track for 2–3 more observations; if it continues or worsens, check autopot float valve flow for Plant D's pod.
4. **Verify EC before next reservoir change** 🟡 — Target window ~Apr 22–25 (7–10 days post-activation Apr 15). EC was 1.84 before activation; confirm diluted to 0.8–1.0 at refill.
5. **Continue light ramp** — Daytime environment now in target. Step from 40% → 50% once LST stress resolves (~5–7 days after LST starts).

_Resolved 2026-04-20: "Daytime VPD above ceiling" — daytime VPD now 1.12 kPa ✅ at 14:00._
_Resolved 2026-04-20: "Daytime temperature too warm" — now 75.04°F ✅ at 14:00._
_Resolved 2026-04-19: "Overnight temperature" — overnight avg recovered to 68.0°F (in veg night range). Note: regressed to 66.84°F on Apr 20 overnight pending service restart._
_Resolved 2026-04-18: "Lower overnight humidifier setpoint" — humidifier loop switched to stage-dynamic VPD targeting + lights-off feedforward. See [decisions 2026-04-18](decisions/2026-04-18-vpd-targeting.md) and [2026-04-19](decisions/2026-04-19-lights-off-aware-humidifier.md)._

## Upcoming Milestones

| Milestone | Estimated Timing |
|-----------|-----------------|
| ~~Plant C diagnosis~~ | ✅ Resolved |
| ~~Topping all plants~~ | ✅ Done Apr 11–12 |
| ~~Float valve activation~~ | ✅ Done Apr 15 |
| ~~SCROG net install~~ | ✅ Done Apr 18 (11" above canopy / 18" above pot base) |
| **LST all plants** | **Critically overdue — start today** |
| First reservoir change | ~Apr 22–25 (7–10 days post-activation) |
| 12/12 flip | SCROG 70% full |
| Clone selection | Flower weeks 3–4 |
| Final pheno evaluation | Flower weeks 5–6 |

## Pheno Hunt Summary

**Primary keepers:** Plants A and D — both strong purple contenders with confirmed genetic anthocyanin expression.
- **Plant A** — vigor leader, confirmed genetic anthocyanin. Most vigorous plant overall. Standout candidate.
- **Plant D** — confirmed genetic anthocyanin (stem, petioles, cotyledons). About a day behind A in vigor; lighter green color noted Apr 20 — monitor.

**Plant C purple note:** Stress-induced purple (stems/petioles, Day 25) concurrent with worsening leaf symptoms — pH/deficiency stress, not genetic. Does not change secondary status.

**Strategy:** Run all 4 to flower weeks 5–6. Evaluate purple calyx depth, aroma, bud structure, stretch, health. Clone top candidate(s) before flower weeks 3–4 for Grow #2.

## System Status

| Component | Status | Notes |
|-----------|--------|-------|
| **Arduino Nano + BME280** | Online | Temp/humidity/pressure readings via USB serial (BME280 replaced DHT22 on 2026-04-13 — see [decision](decisions/2026-04-20-bme280-sensor-swap.md)) |
| **Plant-A ESP32-C3 node** | Online (2026-04-18, v2.0) | GPIO3 capacitive v2.0; fresh calibration; POSTs every 30s |
| **Plant-B ESP32-C3 node** | Online (2026-04-16) | v2.0 sensor; 192.168.1.243; fresh calibration |
| **Plant-C ESP32-C3 node** | Online (2026-04-16) | v2.0 sensor; 192.168.1.117; reused dev unit; fresh calibration |
| **Plant-D ESP32-C3 node** | Online (2026-04-18, v2.0) | GPIO3 capacitive v2.0; fresh calibration |
| **CO2 sensor** (MH-Z19B) | Planned | Not yet deployed |
| **Reservoir level** (XKC-Y25-T12V) | Planned | Not yet deployed |
| **Humidifier control** (Raydrop 4L + Kasa EP10 smart plug) | Online; **service restart required** | Lights-off feedforward + dropped safety timers deployed Apr 19; `dirt-hwd` restart still pending |
| **PTZ camera** (OBSBOT Tiny 2 Lite) | Online (2026-04-15) | Persistent C++ daemon + `scripts/camera` CLI. Per-plant presets calibrated. See `hardware/ptz-camera.md`. |
| **Jabra Speak 410** (voice I/O) | Connected 2026-04-15 | Full voice pipeline proven end-to-end: openWakeWord v3 (89% recall) → Deepgram Nova-3 STT → ElevenLabs "Claudia" TTS. Production `channels/voice.py` pending. See `hardware/jabra.md`. |
| **AC Infinity Cloudline LITE 6" fan control** (Arduino Nano + USB-C breakouts) | Parts ordered 2026-04-18 | Reverse-engineer the stock PWM remote over USB-C, then drive the fan from an Arduino Nano. Awaiting hardware arrival. See `hardware/ac-infinity-fan-control.md`. |

## Denver Water Notes
- Tap pH: 8.5–8.8 → GH pH Down required at every fill
- Chloramines (not free chlorine) → do NOT off-gas; use as-is after pH adjustment
- Target pH: 5.8 after nutrients; range 5.5–6.0
