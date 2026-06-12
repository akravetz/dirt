---
title: Grow Overview
type: overview
sources: [raw/chat-history/all-chat-summary.md, raw/chat-history/bible.md, raw/chat-history/memory.md]
related: [wiki/index.md, wiki/grows/main-2026-03-15/README.md, wiki/grows/main-2026-03-15/plants/plant-a.md, wiki/grows/main-2026-03-15/plants/plant-b.md, wiki/grows/main-2026-03-15/plants/plant-c.md, wiki/grows/main-2026-03-15/plants/plant-d.md, wiki/grows/breeding-track-a-2026-04-28/README.md, wiki/grows/breeding-track-a-2026-04-28/plants/plant-r1.md, wiki/grows/breeding-track-a-2026-04-28/plants/plant-r2.md, wiki/grows/breeding-track-a-2026-04-28/plants/plant-r3.md, wiki/grows/breeding-track-a-2026-04-28/plants/plant-r4.md, wiki/grows/breeding-track-a-2026-04-28/plants/plant-r5.md, wiki/decisions/2026-05-05-hosted-control-plane.md]
created: 2026-04-06
updated: 2026-06-12
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
| **Grow day** | Day 88 (as of 2026-06-10) |

## Current Stage

**Late Flower — Day 38 of 12/12**. Flower start date is 2026-05-03; lights run 09:00–21:00 local tent time. Autopot has been active since Apr 15, all four plants are topped, and the SCROG net is installed; airflow, dark-cycle humidity reduction, flower-site inspection, and root-zone checks now outrank stretch training.

**Latest full photo coverage was 2026-06-10** — main overview plus Plant A/B/C/D dedicated views and the breeding overview were captured. Main-tent photos show a dense, upright, flower-heavy canopy with widespread purple-toned tops and many fresh white pistils; the wall/fan areas remain partly overexposed or obstructed, and Plant A's dedicated view is mostly fan-blocked.

**Main tent has a split VPD profile** — morning VPD is in range at 1.41 kPa, but the current reading is dry/high at 1.62 kPa with the fan already at 80%, while the overnight window remains wet/low at 1.10 kPa. Corrections should target dark-cycle clearing and flower-pocket airflow without pushing lights-on drier.

**Plant A is now on the RS485 substrate probe** — `plant-a-substrate-node` became the canonical current moisture source on 2026-06-10 evening MDT after no-USB 12 V runtime validation. Post-cutover calibrated operational readings were around 26.6% moisture, 21.5 deg C substrate temperature, 144 us/cm EC, and pH 4.5. Confirm tray fill/drawdown and leaf posture during the reservoir correction; do not top-flush again without new decline or repeated high-EC evidence.

**Plants B-D have no current moisture probe** — the old capacitive moisture nodes and raw capabilities are retired/disabled. Use hand checks, tray behavior, plant posture, media smell/weight, and runoff/slurry evidence instead of the old rough percentages until trustworthy replacement probes exist.

**Old capacitive nodes are disconnect-safe** — `plant-a-node` through `plant-d-node` are disabled in active inventory and filtered out of system status. Physical disconnect should not create stale/offline device-watchdog noise; historical readings remain in the database.

**Breeding tent is Flower Day 17 with incomplete sensor coverage** — breeding flower start date is 2026-05-24. Only a current reading is available and it exactly repeats the same wet value again: 71.92°F / 83.28% RH / 0.45 kPa with a 66.57°F dew point. The overview is tent-level only and does not resolve individual sex sites. Verify sensor freshness/exposure while checking watering timing, pot weight, fan exposure, air exchange, and R5 sex sites. Track A active plants are R1/R2/R4 confirmed male candidates plus R5 on sex watch; R3 was confirmed female and culled on 2026-06-04.

**Breeding propagation is active** — clones from all four current plants were taken 2026-05-02 and are under a humidity dome; they were perking with 1 visible rooted clone as of 2026-05-05. Track A regulars flipped to 12/12 on 2026-05-24 for sexing and pollen production. Seven regular seeds germinated, two died during transplant to coco coir, and R3 was culled after female confirmation, leaving four active Track A plants. A 4-inch AC Infinity filtration kit has been selected for the breeding/male isolation tent, and Shelly Plus Plug US is the selected permanent controller for drip-assist pump safety. See [Track A pollen run](grows/breeding-track-a-2026-04-28/README.md), [breeding/cloning.md](breeding/cloning.md), [breeding/timeline.md](breeding/timeline.md), and [breeding/isolation.md](breeding/isolation.md).

**Reservoir reset 2026-06-10 20:00 MDT after high EC** — the Autopot reservoir EC was found well over 2.0 mS/cm, so the entire reservoir was flushed/replaced with plain Denver tap water adjusted to pH 5.8 and EC ~0.3. Let the plants drink plain water for roughly 24 hours, then rebuild feed to about EC 1.2 around 2026-06-11 20:00 MDT if posture and tray cycling remain acceptable.

**Breeding program launched 2026-04-26; narrowed 2026-05-02** — Main goal is stabilizing a dark-purple, sativa-leaning SBxBS01 expression through F2 creation, progeny-tested F3/F4+ family selection, and eventual validated feminized seed production (>90% on-target females). See [breeding/README.md](breeding/README.md), [stabilization strategy](breeding/stabilization-strategy.md), [feminized production](breeding/feminized-production.md), and [decision 2026-05-02](decisions/2026-05-02-purple-stabilization-strategy.md).

**Light schedule:** 12/12 (lights on 09:00–21:00 MDT)
**Light intensity:** ~40% Fold-650 unless already stepped

## Plant Status

| Plant | Flower | Purple | Priority | Status |
|-------|--------|--------|----------|--------|
| Plant A | Day 38 | ✅ Confirmed genetic | 🔴 Primary | Mostly fan-blocked view; visible material upright; RS485 substrate moisture is canonical after cutover — confirm tray cycling and leaf posture |
| Plant B | Day 38 | ❌ None | 🟡 Secondary | Active flower clusters visible; no current moisture probe after capacitive retirement — verify tray/media by hand |
| Plant C | Day 38 | ⚠️ Stress-induced only | 🟡 Secondary | Active wall-side flower clusters visible; no current moisture probe after capacitive retirement — keep root-zone/airflow watch |
| Plant D | Day 38 | ✅ Confirmed genetic | 🔴 Primary | Strong purple flower tops visible; no current moisture probe after capacitive retirement — verify media/tray by hand |

## Breeding Track A Plant Status

| Plant | Flower | Sex status | Current action |
|-------|--------|------------|----------------|
| R1 | Day 17 | Confirmed male expression | Evaluate male quality; check pot weight, airflow, sensor freshness, and sex sites |
| R2 | Day 17 | Confirmed male expression | Evaluate male quality; check pot weight, fan exposure, sensor freshness, and sex sites |
| R3 | Day 17 | Confirmed female; culled 2026-06-04 | Removed from active Track A pollen run |
| R4 | Day 17 | Confirmed male expression | Evaluate male quality; check pot weight, airflow, sensor freshness, and sex sites |
| R5 | Day 17 | Not confirmed in wiki | Continue sex watch; check pot weight, fan exposure, sensor freshness, and airflow |

## Environment (Last Reading: Jun 10 14:00 MDT)

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Temperature (now) | 79.81°F | 68–75°F late flower day | ⚠️ Warm |
| Temperature (morning avg) | 76.60°F | 68–75°F late flower day | ⚠️ Warm |
| Temperature (overnight avg) | 69.92°F | 62–68°F late flower night | ⚠️ Warm night |
| Humidity (now) | 53.32% | 40–45% late flower guide | ⚠️ High by RH guide |
| Humidity (overnight avg) | 55.86% | 40–45% late flower guide | ⚠️ High by RH guide |
| VPD (now) | 1.62 kPa | 1.2–1.5 kPa | ⚠️ Dry/high |
| VPD (morning avg) | 1.41 kPa | 1.2–1.5 kPa | ✅ In range |
| VPD (overnight avg) | 1.10 kPa | 1.2–1.5 kPa | ⚠️ Wet/low |
| Breeding temp/VPD (now) | 71.92°F / 0.45 kPa | Flower Day 17 small-plant watch | 🔴 Current-only wet repeat; verify sensor freshness/exposure |
| pH (reservoir) | 5.8 at 2026-06-10 20:00 MDT replacement | 5.5–6.0 | ✅ Corrected |
| EC (reservoir) | Prior >2.0; new ~0.3 at 2026-06-10 20:00 MDT | 1.2–1.4 late-flower taper | 🟡 Temporary plain-water reset; rebuild to ~1.2 after ~24h |

## Active Action Items

1. **Fix the split VPD profile** 🔴 — Main VPD is in range at 1.41 kPa morning, but now is dry/high at 1.62 kPa with fan at 80% while overnight remains wet/low at 1.10 kPa. Target dark-cycle clearing, fan programming, and airflow paths without adding broad lights-on dryness.
2. **Inspect dense flower sites and preserve airflow lanes** 🔴 — Full photos show a crowded, flower-heavy late canopy with overexposed/obstructed wall-side views and a mostly fan-blocked Plant A view. Check inner/lower flower sites manually for stagnant air or moisture pockets.
3. **Monitor Plant A after RS485 cutover and Autopot reconnection** 🔴 — A is now on direct RS485 substrate moisture, with post-cutover readings around 26.6%. Confirm tray fill/drawdown/refill behavior and leaf posture; do not top-flush again without new decline or repeated high-EC evidence.
4. **Hand-check Plants B/C/D without relying on old capacitive moisture** 🔴 — B-D have no current trusted moisture probe after capacitive retirement. Verify tray/float behavior, standing water, media smell/weight, and plant posture directly before restoring normal feed assumptions.
5. **Disconnect retired capacitive nodes** 🟡 — Old `plant-a-node` through `plant-d-node` are disabled/retired in DB/code and can be physically disconnected. Historical readings remain available; device status should stay clean.
6. **Verify breeding sensor freshness and conditions directly** 🔴 — Breeding only has a current reading today, and it exactly repeats the same wet value again: 71.92°F / 83.28% RH / 0.45 kPa. Check sensor exposure/freshness, watering timing, pot weight, fan exposure, air exchange, and R5 sex sites directly.
7. **Manage breeding propagation** 🔴 — A/B/C/D clones still need rooted backup confirmation. Track A is in sexing/pollen mode with R1/R2/R4 confirmed male candidates and R5 still on sex watch; R3 was confirmed female and culled 2026-06-04. Keep labels secure and use the male-evaluation rubric before pollen collection. The 4-inch AC Infinity filtration kit is selected for containment, and Shelly Plus Plug US is selected for unattended drip-assist pump safety. See [Track A pollen run](grows/breeding-track-a-2026-04-28/README.md), [breeding/timeline.md](breeding/timeline.md), [breeding/cloning.md](breeding/cloning.md), and [breeding/isolation.md](breeding/isolation.md).
8. **Run the high-EC reservoir correction** 🔴 — Reservoir EC was found well over 2.0 on 2026-06-10 evening, so the entire Autopot reservoir was replaced at 20:00 MDT with pH 5.8 / EC ~0.3 tap water. Let plants drink plain water for about 24 hours, then rebuild feed to roughly EC 1.2 around 2026-06-11 20:00 MDT if posture and tray cycling remain acceptable.
9. **Investigate ThermoForge T3 control deliberately** 🟡 — Heater control must fail OFF; follow the filed UIS/passive-tap investigation before any direct-control replay.

_Resolved 2026-04-28: "Govee H7140 backup arrival" — arrived._
_Resolved 2026-04-28: "Clone gear + Govee H7142 arrival" — clone gear arrived; H7142 deployed 2026-04-27._
_Resolved 2026-04-26: "Perform reservoir change" — refilled 2026-04-26 afternoon; next change window ~2026-05-03–06._
_Resolved 2026-05-02: "Confirm clones + SBxBS01 regular germination" — clones taken 2026-05-02; regular seeds germinated ~2026-04-28._
_Resolved 2026-05-05 / clarified 2026-05-30 and 2026-06-04: "Pot Track A regular seedlings into coco/perlite" — 7 total sprouted from 10 started seeds; 2 died during transplant to coco coir; R3 later confirmed female and was culled, leaving 4 active Track A plants._

## Upcoming Milestones

| Milestone | Estimated Timing |
|-----------|-----------------|
| ~~Plant C diagnosis~~ | ✅ Resolved |
| ~~Topping all plants~~ | ✅ Done Apr 11–12 |
| ~~Float valve activation~~ | ✅ Done Apr 15 |
| ~~SCROG net install~~ | ✅ Done Apr 18 (11" above canopy / 18" above pot base) |
| ~~LST all plants~~ | ✅ Started Apr 20 (all 4 plants; recovery complete Day 9) |
| ~~Reservoir change~~ | ✅ Refilled 2026-04-26 afternoon |
| ~~Light step 40% → 50%~~ | Window was Apr 25–27; **do now if not yet done** |
| ~~Govee H7140 backup arrival~~ | ✅ Arrived 2026-04-28 |
| ~~Clone gear + Govee H7142 arrival~~ | ✅ Clone gear arrived 2026-04-28; H7142 deployed 2026-04-27 |
| ~~Govee H7142 cutover (primary)~~ | ✅ Done 2026-04-27 |
| ~~Take clones from A/B/C/D~~ | ✅ Done 2026-05-02; cuttings under humidity dome; 1 visible root as of 2026-05-05 |
| ~~Start 10 SBxBS01 regulars (Track A)~~ | ✅ Started ~2026-04-28; 7 total sprouted, 5 healthy/vigorous as of 2026-05-05 |
| ~~Pot Track A sprouted regulars into coco/perlite~~ | ✅ Done 2026-05-05; all 7 sprouted seedlings potted for sexing/pollen production |
| ~~12/12 flip~~ | ✅ Done 2026-05-03; Flower Day 0 |
| Track A seedling sex watch | Active from ~2026-05-19 → 2026-05-26 from approximate 2026-04-28 germination |
| Main-tent late-flower humidity tightening | Active from Flower Day 21 onward |
| ThermoForge T3 direct-control investigation | Planned revisit 2026-05-17; fail-OFF requirements filed |
| Clone selection | Flower weeks 3–4 |
| Final pheno evaluation | Flower weeks 5–6 |
| Breeding — F2 cross | After pheno evaluation; selected purple/sativa male × A or D |
| Breeding — F3 progeny test | After F2 seed harvest; accelerated small-plant cycle per [stabilization strategy](breeding/stabilization-strategy.md) |
| Breeding — feminized production validation | After a progeny-tested family repeatedly passes target gates; reverse elite female donor and require >90% on-target female offspring |

## Pheno Hunt Summary

**Primary keepers:** Plants A and D — both strong purple contenders with confirmed genetic anthocyanin expression.
- **Plant A** — vigor leader, confirmed genetic anthocyanin. Most vigorous plant overall. Standout candidate.
- **Plant D** — confirmed genetic anthocyanin (stem, petioles, cotyledons). Color concern from Apr 20 resolved by Apr 22; medium-green healthy canopy; lighter new growth tips are sativa-leaning new shoots, not chlorosis.

**Plant C purple note:** Stress-induced purple (stems/petioles, Day 25) concurrent with worsening leaf symptoms — pH/deficiency stress, not genetic. Does not change secondary status.

**Strategy:** Run all 4 to flower weeks 5–6. Evaluate purple calyx depth, aroma, bud structure, stretch, health. Clones from all four current plants were taken 2026-05-02 and remain under a humidity dome; only 1 visible root is present as of 2026-05-05, so clone preservation is not complete yet. **Breeding program**: pollen bank selected purple/sativa SBxBS01 male(s) → F2 cross with A/D or another winner → accelerated F2/F3+ progeny testing for dark-purple, trellis-friendly consistency → validated feminized production lot once a family reliably clears the target gates. See [breeding/README.md](breeding/README.md), [stabilization strategy](breeding/stabilization-strategy.md), and [feminized production](breeding/feminized-production.md).

## System Status

| Component | Status | Notes |
|-----------|--------|-------|
| **ESP32-C3 · fan+tent** (SHT45) | Online (2026-04-23, fw 0.2.0) | Retired Arduino Nano + BME280 2026-04-23. Combined fan-controller node drives the Cloudline fan + reads tent T/RH + exposes HTTP `POST/GET /fan`. See [hardware/ac-infinity-fan-control.md](hardware/ac-infinity-fan-control.md). |
| **Plant A RS485 substrate node** | Online (2026-06-10, fw 0.1.0-rs485-substrate) | `plant-a-substrate-node.local` / 192.168.1.40; canonical Plant A moisture plus calibrated substrate temp/EC/pH. Runs on RS485 board 12 V power with USB unplugged. See [hardware/rs485-substrate-sensors.md](hardware/rs485-substrate-sensors.md). |
| **A-D capacitive ESP32-C3 plant nodes** | Retired/disabled 2026-06-11 | `plant-a-node` through `plant-d-node` and their `soil_moisture_raw` capabilities are disabled in active inventory. Safe to physically disconnect; no current plant moisture derives from them. |
| **CO2 sensor** (MH-Z19B) | Planned | Not yet deployed |
| **Reservoir level** (XKC-Y25-T12V) | Planned | Not yet deployed |
| **Humidifier** | **GoveeLife H7142** (6 L cool-mist, 9 Manual-mode levels via Govee Public API v2) — deployed 2026-04-27 evening; first full day 2026-04-28. H7140 (3 L backup) arrived 2026-04-28. See [decisions/2026-04-27-h7142-deployed.md](decisions/2026-04-27-h7142-deployed.md) and [hardware/humidifier-control.md](hardware/humidifier-control.md). |
| **PTZ camera** (OBSBOT Tiny 2 Lite) | Online (2026-04-15) | USB self-disconnect incident 2026-04-22 08:58 MDT (resolved ~09:23). See [hardware/ptz-camera.md](hardware/ptz-camera.md). |
| **Hosted control plane** (`control-plane-api` + `web-ui`) | Online (2026-05-05) | Railway-hosted web UI/API for remote inspection of synced state, freshness, recent private photos, and PTZ-only command intent. Cloud does not talk directly to hardware. See [hosted control-plane decision](decisions/2026-05-05-hosted-control-plane.md). |
| **Local cloud gateway** (`dirt-gateway`) | Online (2026-05-05) | Outbound-only sync process. Reads local state/assets, uploads the cloud projection, polls PTZ-only command intent, validates locally, and reports results; local automation continues if stopped. |
| **Thermal imaging** (PureThermal Mini Pro + FLIR Lepton 3.5) | Planned | Fixed canopy sensor for leaf-air delta, leaf-temperature-aware VPD, and hotspot maps. See [hardware/thermal-imaging.md](hardware/thermal-imaging.md). |
| **Jabra Speak 410** (voice I/O) | Connected 2026-04-15 | Voice pipeline `dirt-voice.service` deployed 2026-04-18; v5 wake-word passive-harvest mode active. |
| **AC Infinity Cloudline LITE 6" fan control** | Online (fw 0.2.0, 2026-04-22) | WiFi + HTTP control surface live; VPD-coupled closed-loop deferred. |
| **AC Infinity ThermoForge T3** | Online via local BLE climate control | `ClimateControllerService` owns heater targets alongside fan, humidifier, and dehumidifier control; the old schedule-driven heater rows are retired. UIS direct-control notes remain as a future fallback investigation in [hardware/ac-infinity-thermoforge-control.md](hardware/ac-infinity-thermoforge-control.md). |

## Denver Water Notes
- Tap pH: 8.5–8.8 → GH pH Down required at every fill
- Chloramines (not free chlorine) → do NOT off-gas; use as-is after pH adjustment
- Target pH: 5.8 after nutrients; range 5.5–6.0
