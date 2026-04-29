---
title: Grow Overview
type: overview
sources: [raw/chat-history/all-chat-summary.md, raw/chat-history/bible.md, raw/chat-history/memory.md]
related: [wiki/index.md, wiki/plants/plant-a.md, wiki/plants/plant-b.md, wiki/plants/plant-c.md, wiki/plants/plant-d.md]
created: 2026-04-06
updated: 2026-04-28
---

# Grow Overview

## Setup

| Parameter | Detail |
|-----------|--------|
| **Strain** | Serious Black (Reversed) × BS01 — Feminized ([Oregon Breeding Group](concepts/oregon-breeding-group.md)) |
| **Goal** | Dark purple phenotype, terpene complexity, exceptional bag appeal |
| **Location** | Bedroom closet, Denver CO |
| **Tent** | VIVOSUN S448 4x4 (48"×48"×80") |
| **Light** | Medic Grow Fold-650 (650W LED) |
| **Medium** | Coco/Perlite 60/40 |
| **Nutrients** | Canna Coco A+B (sole product) |
| **Water system** | Autopot 4-Pot XL + 25-gal FlexiTank (active since Apr 15) |
| **Training** | Single top at node 4–5 → LST → SCROG |
| **Start date** | 2026-03-15 (germination) |
| **Grow day** | Day 45 (as of 2026-04-28) |

## Current Stage

**Early Veg** — Autopot active since Apr 15. **All four plants topped** (A: Apr 11; B/C/D: Apr 12) — Day 17/16 post-topping. **SCROG net installed Apr 18** at 11" above canopy / 18" above pot base. **LST started Apr 20 on all 4 plants** — Day 8 of LST, recovery complete.

**Govee H7142 first full 24-hour cycle** (deployed 2026-04-27 evening) — daytime RH improved 8.6 points (64.6% → 56.0%); VPD 1.19 kPa ✅. Overnight under the new PI controller with -0.3 kPa night offset was the first real test; overnight RH 65.55% still above target, overnight VPD 0.80 kPa (at floor). Review tomorrow.

**VPD in target across all three windows** (0.80/1.16/1.19 kPa). Overnight RH continued elevated (65.55%); all windows above 45–55% veg target. Temperature overnight regressed to 67.76°F (below 68°F floor) after yesterday's 68.87°F recovery.

**Clone gear arrived 2026-04-28** — first cuttings (8 total) + SBxBS01 regular germination planned tomorrow (2026-04-29).

**Reservoir refilled 2026-04-26 afternoon** — next change window ~2026-05-03–06.

**Breeding program launched 2026-04-26** — Two-track SBxBS01 F2 program: pollen banking (Track A) + pheno hunt → F2 cross (Track B). See [breeding/README.md](breeding/README.md) and [decision 2026-04-26](decisions/2026-04-26-breeding-program-launch.md).

**Light schedule:** 18/6 (lights on ~05:00–23:00 MDT)
**Light intensity:** ~40% Fold-650 (**step to 50% overdue — window was Apr 25–27**)

## Plant Status

| Plant | Post-top | Purple | Priority | Status |
|-------|----------|--------|----------|--------|
| Plant A | Day 17 | ✅ Confirmed genetic | 🔴 Primary | Medium-light green; above SCROG net; vigorous upward shoots; moisture stable ~59%; tuck candidate |
| Plant B | Day 16 | ❌ None | 🟡 Secondary | Densest dark-green canopy; moisture jumped to 86.74% — now in C/D elevated zone; no stress visible |
| Plant C | Day 16 | ⚠️ Stress-induced only | 🟡 Secondary | Dense medium-dark green bushy canopy; moisture stable ~88% (6+ days very high); no visible stress |
| Plant D | Day 16 | ✅ Confirmed genetic | 🔴 Primary | Medium-light green; above SCROG net; lighter new growth tips (sativa shoots); moisture ~86%; tuck candidate |

## Environment (Last Reading: Apr 28 14:00 MDT)

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Temperature (now) | 72.37°F | 74–76°F day | ⚠️ Below floor |
| Temperature (morning avg) | 71.83°F | 74–76°F day | ⚠️ Below floor |
| Temperature (overnight avg) | 67.76°F | 68–72°F night | ⚠️ Below floor (regression from 68.87°F yesterday) |
| Humidity (now) | 56.0% | 45–55% veg | ⚠️ Elevated (improved from 64.6% Apr 27) |
| Humidity (overnight avg) | 65.55% | 45–55% veg | ⚠️ Above target |
| VPD (now) | 1.19 kPa | 0.8–1.2 kPa | ✅ In range |
| VPD (morning avg) | 1.16 kPa | 0.8–1.2 kPa | ✅ In range |
| VPD (overnight avg) | 0.80 kPa | 0.8–1.2 kPa | ✅ At floor |
| pH (watering) | 5.8 (target) | 5.5–6.0 | — |
| EC (reservoir) | — | 0.8–1.0 | ⚠️ Verify at next reservoir change |

## Active Action Items

1. **Step light 40% → 50% NOW (overdue)** 🔴 — Window was Apr 25–27; if not yet done, do immediately. No stress signs across all four plants.
2. **Take 8 clones + germinate SBxBS01 regulars TOMORROW (Apr 29)** 🔴 — Clone gear arrived today (2026-04-28). 2 cuttings per plant (lower laterals on A/D, middle laterals on B/C). Germinate all 10 SBxBS01 regulars (Track A) alongside. See [breeding/cloning.md](breeding/cloning.md) and [breeding/README.md](breeding/README.md).
3. **Tuck sativa-leaning canopy (A, D)** 🟡 — Per [pheno-flip-strategy](decisions/2026-04-26-pheno-flip-strategy.md): bend tallest A/D growth horizontally back under SCROG net; re-evaluate every 3 days; flip target ~60% net coverage.
4. **Monitor Plant B moisture** 🟡 — Jumped to 86.74% overnight; now matches C/D elevated zone. Close B float valve briefly if moisture exceeds 88% or stress appears.
5. **Monitor Plants B, C, D root zones** 🟡 — B at 86.7%, C at 88.0%, D at 86.1% (all high); no visible stress across any plant; watch for yellowing, wilting, drooping, or sour smell.
6. **Monitor H7142 overnight performance** 🟡 — First full day today; daytime RH improved; assess tomorrow morning's overnight RH window to confirm PI controller is reducing overnight saturation.
7. **Monitor Plant D lighter growth tips** 🟡 — Lighter/yellow-green new growth visible in upper photo; consistent with fast sativa-leaning new shoots, not chlorosis. Watch for progression.
8. **Reduce exhaust fan speed** 🟡 — Overnight temp oscillating below 68°F floor for five days (67.76°F last night); fan speed reduction during lights-on may recover 1–2°F.

_Resolved 2026-04-28: "Govee H7140 backup arrival" — arrived today._
_Resolved 2026-04-28: "Clone gear + Govee H7142 arrival" — clone gear arrived today; H7142 deployed 2026-04-27._
_Resolved 2026-04-27: "Reduce humidifier output during lights-on" — daytime VPD recovered (1.01 kPa Apr 27, 1.19 kPa Apr 28) ✅. H7142 now manages this automatically._
_Resolved 2026-04-26: "Perform reservoir change" — refilled 2026-04-26 afternoon; next change window ~2026-05-03–06._
_Resolved 2026-04-25: "LST Day 5 — light ramp window open" → ramp window open; step to 50% due Apr 27 (last day of window)._
_Resolved 2026-04-24: "Complete LST today" — user confirmed LST was started Apr 20 on all 4 plants ✅_
_Resolved 2026-04-24: "Monitor afternoon temperature" — milestone Apr 24 (all windows in target); regression began Apr 25._
_Resolved 2026-04-24: "Verify Plant A sensor node" — overnight data present (n=717), node stable ✅_
_Resolved 2026-04-22: "Restart `dirt-hwd` service" — service confirmed restarted; overnight env now in target._
_Resolved 2026-04-22: "Monitor Plant D color" — color improved; Apr 24 photo shows medium-green healthy canopy._

## Upcoming Milestones

| Milestone | Estimated Timing |
|-----------|-----------------|
| ~~Plant C diagnosis~~ | ✅ Resolved |
| ~~Topping all plants~~ | ✅ Done Apr 11–12 |
| ~~Float valve activation~~ | ✅ Done Apr 15 |
| ~~SCROG net install~~ | ✅ Done Apr 18 (11" above canopy / 18" above pot base) |
| ~~LST all plants~~ | ✅ Started Apr 20 (all 4 plants; recovery complete Day 8) |
| ~~Reservoir change~~ | ✅ Refilled 2026-04-26 afternoon |
| ~~Light step 40% → 50%~~ | Window was Apr 25–27; **do now if not yet done** |
| ~~Govee H7140 backup arrival~~ | ✅ Arrived 2026-04-28 |
| ~~Clone gear + Govee H7142 arrival~~ | ✅ Clone gear arrived 2026-04-28; H7142 deployed 2026-04-27 |
| ~~Govee H7142 cutover (primary)~~ | ✅ Done 2026-04-27 |
| **Take 8 clones (A/B/C/D × 2)** | **TOMORROW 2026-04-29** |
| **Germinate all 10 SBxBS01 regulars (Track A)** | **TOMORROW ~2026-04-29** |
| 12/12 flip | ~60% SCROG coverage with all four at net plane; window 2026-05-10 → 2026-05-17 (per [pheno-flip-strategy](decisions/2026-04-26-pheno-flip-strategy.md)) |
| Clone selection | Flower weeks 3–4 |
| Final pheno evaluation | Flower weeks 5–6 |
| Breeding — F2 cross | After pheno evaluation; best male × A or D |

## Pheno Hunt Summary

**Primary keepers:** Plants A and D — both strong purple contenders with confirmed genetic anthocyanin expression.
- **Plant A** — vigor leader, confirmed genetic anthocyanin. Most vigorous plant overall. Standout candidate.
- **Plant D** — confirmed genetic anthocyanin (stem, petioles, cotyledons). Color concern from Apr 20 resolved by Apr 22; medium-green healthy canopy; lighter new growth tips are sativa-leaning new shoots, not chlorosis.

**Plant C purple note:** Stress-induced purple (stems/petioles, Day 25) concurrent with worsening leaf symptoms — pH/deficiency stress, not genetic. Does not change secondary status.

**Strategy:** Run all 4 to flower weeks 5–6. Evaluate purple calyx depth, aroma, bud structure, stretch, health. Clone top candidate(s) before flower weeks 3–4 for Grow #2. **Breeding program** (launched 2026-04-26): pollen bank the reversed SB male (Track A) → F2 cross with winner of pheno hunt (Track B). See [breeding/README.md](breeding/README.md).

## System Status

| Component | Status | Notes |
|-----------|--------|-------|
| **ESP32-C3 · fan+tent** (SHT45) | Online (2026-04-23, fw 0.2.0) | Retired Arduino Nano + BME280 2026-04-23. Combined fan-controller node drives the Cloudline fan + reads tent T/RH + exposes HTTP `POST/GET /fan`. See [hardware/ac-infinity-fan-control.md](hardware/ac-infinity-fan-control.md). |
| **Plant-A ESP32-C3 node** | Online (2026-04-18, v2.0) | Overnight dropout 2026-04-22 resolved — full overnight data nominal |
| **Plant-B ESP32-C3 node** | Online (2026-04-16) | v2.0 sensor; 192.168.1.243 |
| **Plant-C ESP32-C3 node** | Online (2026-04-16) | v2.0 sensor; 192.168.1.117 |
| **Plant-D ESP32-C3 node** | Online (2026-04-18, v2.0) | GPIO3 capacitive |
| **CO2 sensor** (MH-Z19B) | Planned | Not yet deployed |
| **Reservoir level** (XKC-Y25-T12V) | Planned | Not yet deployed |
| **Humidifier** | **GoveeLife H7142** (6 L cool-mist, 9 Manual-mode levels via Govee Public API v2) — deployed 2026-04-27 evening; first full day 2026-04-28. H7140 (3 L backup) arrived 2026-04-28. See [decisions/2026-04-27-h7142-deployed.md](decisions/2026-04-27-h7142-deployed.md) and [hardware/humidifier-control.md](hardware/humidifier-control.md). |
| **PTZ camera** (OBSBOT Tiny 2 Lite) | Online (2026-04-15) | USB self-disconnect incident 2026-04-22 08:58 MDT (resolved ~09:23). See [hardware/ptz-camera.md](hardware/ptz-camera.md). |
| **Jabra Speak 410** (voice I/O) | Connected 2026-04-15 | Voice pipeline `dirt-voice.service` deployed 2026-04-18; v5 wake-word passive-harvest mode active. |
| **AC Infinity Cloudline LITE 6" fan control** | Online (fw 0.2.0, 2026-04-22) | WiFi + HTTP control surface live; VPD-coupled closed-loop deferred. |

## Denver Water Notes
- Tap pH: 8.5–8.8 → GH pH Down required at every fill
- Chloramines (not free chlorine) → do NOT off-gas; use as-is after pH adjustment
- Target pH: 5.8 after nutrients; range 5.5–6.0
