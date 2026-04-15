---
title: Grow Overview
type: overview
sources: [raw/chat-history/all-chat-summary.md, raw/chat-history/bible.md, raw/chat-history/memory.md]
related: [wiki/index.md, wiki/plants/plant-a.md, wiki/plants/plant-b.md, wiki/plants/plant-c.md, wiki/plants/plant-d.md]
created: 2026-04-06
updated: 2026-04-15
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
| **Grow day** | Day 29 (as of 2026-04-12) |

## Current Stage

**Early Veg** — Hand-watering phase (float valves closed, Day 14 post-transplant). Float valve activation window now open (Apr 12). **All four plants topped:** Plant A topped Apr 11; Plants B, C, D topped Apr 12. All in post-topping recovery. LST begins once new shoots reach 2–3 inches (~Apr 16–19). Plant C leaf issue resolved (foliar burn from splash, not pH lockout).

**Light schedule:** 18/6
**Light intensity:** ~40% Fold-650 (ramped from 30% per Apr 8 recommendation)

## Plant Status

| Plant | Nodes | Purple | Priority | Status |
|-------|-------|--------|----------|--------|
| Plant A | 5 (topped) | ✅ Confirmed genetic | 🔴 Primary | ✅ **Topped Apr 11 — recovery Day 1; LST ~Apr 16–18** |
| Plant B | — (topped) | ❌ None | 🟡 Secondary | ✅ **Topped Apr 12 — recovery Day 0; LST ~Apr 17–19** |
| Plant C | — (topped) | ⚠️ Stress-induced only | 🟡 Secondary | ✅ **Topped Apr 12 — leaf issue was foliar burn (resolved); normal recovery** |
| Plant D | — (topped) | ✅ Confirmed genetic | 🔴 Primary | ✅ **Topped Apr 12 — recovery Day 0; LST ~Apr 17–19** |

## Environment (Last Reading: Apr 11)

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Temperature | 72°F | 74–76°F | ⚠️ Slightly low |
| Humidity | 65% | 55–65% | ✅ |
| VPD | ~0.94 kPa | 0.8–1.2 kPa | ✅ Best reading to date |
| pH (watering) | 5.8 (target) | 5.5–6.0 | ⚠️ Verify — Plant C issue suggests possible drift |
| EC (nutrient solution) | ~1.84 measured | 0.8–1.0 | 🔴 Too high — dilute next feed |

## Active Action Items

1. **Dilute nutrient solution to EC 0.8–1.0** 🔴 — current 920 ppm (EC ~1.84) is too high for early veg
2. **Monitor all 4 topping recoveries** — A (Apr 11), B/C/D (Apr 12); LST begins ~Apr 16–19
5. **Float valve activation** — window now open (Apr 12); check behavioral readiness signals daily (faster drinking, accelerating nodes, upward foliage)
6. **Nudge temp to 74–76°F** — currently 72°F
7. **Continue light ramp** — at 40%; step to 50% in next few days if no stress signs

## Upcoming Milestones

| Milestone | Estimated Timing |
|-----------|-----------------|
| ~~Plant C diagnosis~~ | ✅ Resolved — foliar burn from splash, not pH lockout |
| ~~Topping Plant A~~ | ~~Apr 13–15~~ ✅ Done Apr 11 |
| ~~Topping Plant D~~ | ✅ Done Apr 12 |
| Float valve activation | Apr 12–19 (window now open) |
| **LST all plants** | **~Apr 16–19** (once new shoots reach 2–3") |
| SCROG net install | Weeks 6–8 of veg (~late April/early May) |
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
| **Plant-A ESP32-C3 node** | Online (2026-04-14) | GPIO3 capacitive v1.2; POSTs to `/api/ingest/sensors` every 30s; OTA-ready. See `hardware/esp32-plant-nodes.md`. |
| **Plant-B/C/D ESP32-C3 nodes** | Blocked | Waiting on more working sensors — current pack had 3/5 DOA |
| **CO2 sensor** (MH-Z19B) | Planned | Not yet deployed |
| **Reservoir level** (XKC-Y25-T12V) | Planned | Not yet deployed |
| **Humidifier control** (Raydrop 4L + G3MB-202P SSR) | Hardware en route (ETA 2026-04-15) | Closed-loop RH control from Arduino Nano DHT22. See `hardware/humidifier-control.md`. |
| **PTZ camera** (OBSBOT Tiny 2 Lite) | Online (2026-04-15) | Persistent C++ daemon + `scripts/camera` CLI. Per-plant presets calibrated. See `hardware/ptz-camera.md`. |
| **Live audio** | Planning | Epic: `live-audio` |

## Denver Water Notes
- Tap pH: 8.5–8.8 → GH pH Down required at every fill
- Chloramines (not free chlorine) → do NOT off-gas; use as-is after pH adjustment
- Target pH: 5.8 after nutrients; range 5.5–6.0
