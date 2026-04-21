---
title: Activity Log
type: log
created: 2026-04-06
updated: 2026-04-20
order: chronological — oldest entries at top, newest appended at bottom. Do NOT insert entries out of date order.
---

# Activity Log

## [2026-04-06] init | Wiki initialized
- Created folder structure and initial files
- Awaiting raw documentation seed from user

## [2026-04-06] ingest | Full initial ingestion from raw/
- **Raw materials processed:**
  - `raw/chat-history/all-chat-summary.md` — 24 chat sessions, Mar 16 – Apr 5, 2026
  - `raw/chat-history/bible.md` — Grow bible: equipment, strain, timeline, training reference
  - `raw/chat-history/first-progress.md` — Early progress log (Mar 15 – Mar 20)
  - `raw/chat-history/memory.md` — Project memory: current state, phenotype ranking, key learnings
  - `raw/photos/` — 40 JPEG photos across 8 date clusters (Mar 27, Mar 29, Mar 30, Apr 1, Apr 2, Apr 3, Apr 5, Apr 6)
  - No sensor log files found in `raw/sensor-logs/` (directory empty beyond .gitkeep)
  - No reference files found in `raw/references/` (directory empty beyond .gitkeep)
- **Daily entries created:** 9
  - wiki/daily/2026-03-27.md (Day 13 — pre-transplant)
  - wiki/daily/2026-03-29.md (Day 15 — transplant day)
  - wiki/daily/2026-03-30.md (Day 16 — post-transplant, runoff management)
  - wiki/daily/2026-03-31.md (Day 17 — purple phenotype first spotted, plants labeled A–D)
  - wiki/daily/2026-04-01.md (Day 18 — anthocyanin confirmed, priority shift)
  - wiki/daily/2026-04-02.md (Day 19 — training plan established, AirBase disc discovery)
  - wiki/daily/2026-04-03.md (Day 20 — routine check, RH/temp concerns)
  - wiki/daily/2026-04-05.md (Day 22 — nutrient burn on Plant A, Plant C flagged)
  - wiki/daily/2026-04-06.md (Day 23 — photos only, no chat session)
- **Plant pages updated:** 4 (plant-a through plant-d)
- **Environment pages created:** 3 (temperature, humidity, nutrients)
- **Concept pages created:** 6 (anthocyanin, lst, scrog, coco-coir, autopot, vpd)
- **Decision pages created:** 2 (medium-and-training, anthocyanin-priority)
- **overview.md rewritten** with current status, plant table, active action items, milestones
- **index.md updated** with all new page links
- **Linter results:** 5/6 checks passing after fixes
  - Fixed: Index sync (added log.md to index)
  - Fixed: Photo coverage (merged Mar 31 event into Mar 30 daily which has photos)
  - Acceptable known gaps: Timeline continuity — missing Mar 28, Mar 31, Apr 4 (real data gaps: no photos or chat sessions on those dates; Mar 31 merged into Mar 30 intentionally)
- **Known gaps:** No daily entries for Mar 28 (no photo/chat data), Mar 31 (merged into Mar 30), Apr 4 (no data). Photos mentioned in Chat 19 for Mar 31 were not uploaded to raw/photos/.

## [2026-04-06] query-filed | Plant training methods overview
- Created `wiki/concepts/plant-training-methods.md` — comprehensive overview of all training techniques (LST, topping, FIMing, mainlining, super cropping, SCROG, SOG) with pros/cons, relevance to this grow, research notes on stress-induced trichome development, and our training sequence table
- Source: PMC12771868 (BRC1 gene / sucrose flooding mechanism; trichome research gap)
- Added backlink from `wiki/concepts/lst.md` and `wiki/concepts/scrog.md`
- Updated `wiki/index.md` with new concept entry

## [2026-04-07] query-filed | VPD concept expanded
- Rewrote `wiki/concepts/vpd.md` — added SVP/AVP formula, correct optimal ranges by stage, current grow situation (73–76% RH / 25°C → 0.79 kPa, low for veg), low-VPD consequences, closet remediation strategies, leaf temp note, coco interaction, light interaction
- Added cross-links to `wiki/concepts/coco-coir.md` and new `wiki/concepts/dli-light-management.md`

## [2026-04-07] query-filed | Autopot float valve activation guide
- Expanded `wiki/concepts/autopot.md` — added detailed activation timing (transplant Mar 29 → window Apr 12–19), readiness signals, step-by-step transition procedure, common first-activation mistakes table, coco-specific valve cycling note

## [2026-04-07] query-filed | DLI & Light Management concept created
- Created `wiki/concepts/dli-light-management.md` — DLI formula, PPFD/DLI targets by stage, 18→12 flip math, Fold-650 ramp plan by phase, CO2 ceiling note (~900 PPFD practical max), VPD and nutrient interaction notes
- Updated `wiki/index.md` with new concept entry
- Added cross-links from VPD page to DLI page

## [2026-04-07] query-filed | Four concept pages created from internet-grounded research
- **trichome-stages.md** — Trichome types (bulbous, capitate-sessile, capitate-stalked), three ripening stages (clear/cloudy/amber), harvest timing targets by desired effect, how to check (30–60x loupe, calyx focus), pheno hunt integration, amber vs. anthocyanin visual interaction note. Sources: Oregon Hemp Flower, Blimburn Seeds, PMC8488169, Alchimia.
- **lollipopping-defoliation.md** — Lollipopping (bottom-third removal at flip, SCROG integration procedure) vs. defoliation (selective fan-leaf removal for light/airflow); timing table with week 3 hard stop; combined approach for this grow at flip. Sources: Grow Weed Easy, Royal Queen Seeds, Paradise Seeds.
- **flushing.md** — Flush debate (mixed science; anecdotal support); coco-specific protocol (3–7 days, not 2 weeks); runoff EC monitoring targets; Autopot flush procedure (close float valve, revert to hand-water); signs of successful flush (natural senescence). Sources: Coco For Cannabis, CannaCon, EatHealthy365.
- **damping-off.md** — Pathogens (Pythium, Phytophthora, Fusarium, Rhizoctonia); pre- and post-emergence symptoms; risk assessment for this grow (ELEVATED — RH 73–76%); prevention checklist; treatment (no cure; isolation + airflow). Sources: Cannoptikum, Royal Queen Seeds, Herbies Seeds, Humboldt Seeds.
- Updated wiki/index.md with all four new concept entries.

## [2026-04-12] query-filed | Reservoir stand decision recorded
- Created `wiki/decisions/2026-04-11-reservoir-stand.md` — oak step stool 6" height for FlexiTank Pro (208 lbs full, 21"×21" base); rationale (gravity-feed needs minimal head pressure for 8–10ft runs); monitoring plan (watch furthest pot tray in first 48hrs); alternatives table (plant caddies too low, wire rack too bulky, DIY unaesthetic)
- Updated `wiki/concepts/autopot.md` — added reservoir stand to Setup section with link to decision; updated related links
- Updated `wiki/index.md` — decision entry added

## [2026-04-11] daily | Day 28 — Plant A vigor leader; EC too high; topping imminent; float valve window opens
- Created `wiki/daily/2026-04-11.md` — Day 28 (Day 13 post-transplant); 4 photos (PXL_20260411_*); Plant A confirmed vigor leader with 5th node emerging; topping trigger met, recommended Apr 13–15; EC at 920 ppm (~1.84) flagged as too high for early veg; float valve activation window opens Apr 12; VPD 0.94 kPa (best reading to date)
- Updated plant timelines: plant-a.md (current state rewritten — vigor + purple leader, topping imminent), plant-b/c/d.md (timeline entries added)
- Plant C current state updated — runoff pH/EC test noted as overdue
- Plant D current state updated — A now vigor leader; D still strong primary keeper
- Updated `wiki/environment/nutrients.md` — EC incident logged (920 ppm / EC ~1.84)
- Rewrote `wiki/overview.md` — Day 28, updated plant table, EC flagged 🔴, topping milestone promoted
- Updated `wiki/index.md` — Day 28 daily entry added; Plant A description updated

## [2026-04-08] daily | Day 25 — Plant C worsening; VPD swing incident; topping imminent
- **Known gap:** No daily for 2026-04-07 (Day 24) — no photos or observations taken that day.
- **Pending:** 2026-04-08.md photo sources use placeholder filenames; update `sources:` frontmatter once actual photos are added to raw/photos/ and EXIF filenames are known.
- Created `wiki/daily/2026-04-08.md` — Day 25 (Day 10 post-transplant); full per-plant observations; VPD swing incident documented (42%→70% RH, 2.03→0.89 kPa); Plant C escalated with differential diagnosis table (pH lockout most likely); topping window flagged as imminent (3–7 days); light ramp recommended (30%→40%)
- Updated plant timelines and Current State: plant-a.md, plant-b.md, plant-c.md, plant-d.md
- Plant C purple signal field updated: stress-induced (concurrent with illness), NOT genetic
- Updated environment trend logs: temperature.md, humidity.md, nutrients.md
- Rewrote wiki/overview.md — updated to Day 25, new plant status table, escalated Plant C action item, revised milestones
- Updated wiki/index.md — added Day 25 daily entry, updated Plant C index description

## [2026-04-07] llm-lint | Contradiction detection, concept gap analysis, overview accuracy check

### Contradictions fixed:
- **plant-a.md**: Removed phantom Day 1 / 2026-03-15 timeline entry (no daily exists for that date; link incorrectly pointed to 2026-03-27.md; all other plants start their timelines on Mar 27)
- **plant-d.md**: Corrected Mar 30 (Day 16) timeline entry — falsely claimed "purple stem/leaf undersides noted (initial observation)." Canonical 2026-03-30 daily explicitly states "Plant D | No purple noted yet." Fixed to "no purple expression at this stage."
- **concepts/anthocyanin.md**: Corrected plant A first observation from "Day 17" → Day 16 (Mar 30). Corrected plant D first confirmation from "Day 17" → Day 18 (Apr 1).
- **concepts/plant-training-methods.md**: Training sequence table incorrectly listed Topping as "Active" and LST as "Active." Neither has been executed as of Day 23. Fixed to "Imminent" and "Planned" respectively.
- **concepts/autopot.md**: Removed stale "Estimated activation: ~1–2 weeks from April 2 (Days 20–23 range)" from AirBase Disc section — that window has passed; current estimate (Apr 12–19) is in the updated Float Valve Activation section.
- **concepts/lst.md** and **concepts/scrog.md**: Fixed broken `related` links pointing to non-existent `wiki/decisions/2026-03-16-training-approach.md`; corrected to `wiki/decisions/2026-03-16-medium-and-training.md`.

### Contradictions flagged (not auto-resolved — require user decision):
- **Float valve activation timing gap**: overview.md says "Days 24–28 (this week)" while autopot.md says "Apr 12–19" (a ~5-day difference). The autopot page's estimate is based on 2–3 weeks post-Mar 29 transplant; the overview was written Apr 6 and may be optimistic. User should confirm readiness signals before activating.
- **wiki/log.md ingest entry**: Claims `wiki/daily/2026-03-31.md (Day 17)` was created during initial ingest, but that file does not exist (events were merged into 2026-03-30.md). Log is append-only; flagged here for awareness.

### Concept gaps identified (no concept pages exist for these referenced topics):
- **Lollipopping + Defoliation** — referenced in 2026-04-02 training plan table ("Lollipopping + defoliation | Early flower") but no concept page
- **Flushing (coco)** — referenced in environment/nutrients.md EC table ("Late Flower / Flush | 0.0") but no page explaining when/how/why
- **Trichome stages** — referenced in plant-training-methods.md (stress-induced trichome development) and is a primary evaluation criterion for pheno selection; no concept page
- **Damping off** — mentioned as a risk in 5+ daily entries and environment pages but no concept page explaining symptoms, causes, prevention

### Overview accuracy:
- Overview is broadly accurate against current dailies and plant pages.
- Minor understatement: "All 4 plants healthy" in Current Stage — Plant A has cosmetic foliar burn, Plant C has unresolved lighter green/edge spotting. The Plant Status table (which is accurate) contradicts this sentence.

## [2026-04-12] structural | Wiki migrated into dirt repo; expanded for hardware tracking
- **Migration:** Grow wiki (`wiki/`, `raw/`, `outputs/`, `scripts/`) moved from standalone `marijuana` repo into the `dirt` monitoring repo. Wiki and monitoring app now live together.
- **CLAUDE.md merged:** Wiki conventions integrated into dirt's existing CLAUDE.md — single source of agent instructions for both the grow wiki and the monitoring codebase.
- **New wiki section: `wiki/hardware/`** — for documenting deployed monitoring infrastructure (sensors, cameras, controllers). Each system gets its own page with type `hardware`.
- **`concepts/` scope broadened** — now covers both growing knowledge and technical/hardware concepts relevant to the grow.
- **`overview.md` expanded** — added System Status table tracking deployed and planned monitoring components.
- **`index.md` expanded** — added Hardware section.
- **New epics scaffolded** in `docs/epics/`:
  - `ptz-camera` — Pan-tilt-zoom camera for remote plant inspection
  - `additional-sensors` — CO2, soil moisture, reservoir level sensors
  - `live-audio` — Always-on mic + speaker for voice interaction with Claude
- **Dependency added:** `pillow` added to dirt's `pyproject.toml` (required by wiki lint script for EXIF extraction).
- **Lint result:** 5/6 checks pass (same as before migration — timeline continuity gaps are pre-existing data gaps, not migration issues).

## [2026-04-12] decisions | Hardware architecture and component selections finalized
- **4 decision records created:**
  - `decisions/2026-04-12-distributed-sensor-architecture.md` — Split to ESP32-C3 per-plant nodes (soil moisture, WiFi, USB-C powered) + Arduino Nano tent-level hub (DHT22, CO2, reservoir level). Driven by cabling problem: 8+ wires across tent made plant access difficult.
  - `decisions/2026-04-12-ptz-camera-selection.md` — OBSBOT Tiny 2 Lite (4K PTZ, SDK + OSC control). Replaces static C920. Enables Claude to autonomously inspect plants.
  - `decisions/2026-04-12-audio-hardware-selection.md` — Jabra Speak 410 USB speakerphone. Single device for mic + speaker, sits outside tent.
  - `decisions/2026-04-12-telegram-mobile-interface.md` — Telegram bot for mobile Claude interaction. Lowest friction option vs WhatsApp/SMS/custom PWA.
- **Epics updated:**
  - `sensor-hardware` rewritten for distributed architecture (ESP32-C3 + Nano)
  - `additional-sensors` absorbed into `sensor-hardware` (removed as separate epic)
  - `ptz-camera` updated with OBSBOT Tiny 2 Lite specs and SDK details
  - `live-audio` updated with Jabra Speak 410 details
  - `telegram-bot` epic created for mobile chat interface
- **Hardware purchased:**
  - OBSBOT Tiny 2 Lite (4K PTZ webcam)
  - Jabra Speak 410 (USB speakerphone)
  - ESP32-C3 SuperMini 5-pack (4 per-plant + 1 spare)
  - Capacitive soil moisture sensor v1.2 x4 (already owned)
  - RSHTECH 10-port powered USB hub (60W)
  - Silicone conformal coating (120ml, for flower phase board protection)
- **wiki/index.md updated** with 4 new decision entries

## [2026-04-12] structural | Agent architecture finalized; session logging added
- **ADR 005 created:** `docs/adrs/005-agent-architecture.md` — Ephemeral agent loops via Claude Agent SDK, running inside FastAPI process. Follows OpenClaw's pattern: persistent gateway, ephemeral per-request agent loops. Wiki is the memory, not conversation history.
- **Decision record created:** `wiki/decisions/2026-04-12-agent-architecture.md`
- **Session logging introduced:** `sessions/` directory added at repo root with `telegram/` and `voice/` subdirectories. Append-only JSONL files written by the harness, readable by agent on demand. One file per day per channel (`YYYY-MM-DD.jsonl`).
- **CLAUDE.md updated:** Three-folder architecture expanded to four-layer data hierarchy (sessions → raw → wiki → outputs) with ownership table.
- **Telegram epic updated:** Reflects Agent SDK ephemeral loop pattern, session JSONL logging, channel adapter architecture. Channels are Telegram + voice only (no web chat).
- **wiki/index.md updated** with agent architecture decision entry

## [2026-04-12] llm-lint | Contradiction fixes and concept gap fills
### Contradictions fixed:
- **plant-a.md, plant-d.md, overview.md, index.md:** Fixed A/D purple language. Both are now described as "strong purple contenders" with confirmed genetic anthocyanin. Neither is called "leader" or "strongest" — they are co-equal contenders. A is the vigor leader; D is about a day behind A in vigor.
- **plant-c.md:** Title changed from "Most Vigorous, Monitor pH" to "Secondary, Monitor pH" — A and D are the most vigorous as of Day 28, not C.
- **plant-b.md:** Current State updated to reference Day 28 (Apr 11) instead of stale Day 25 reference.
- **plant-a.md:** Day 22 timeline entry fixed — removed confusing "UPGRADED to confirmed" language. Purple was confirmed on Day 18; Day 22 entry now reads "Purple expression continuing (new growth tips + petioles showing color)."
### Concept pages created (4):
- **topping.md** — HST technique, procedure, timing for this grow (Plant A imminent Apr 13–15), risks, position in training sequence
- **ph-lockout.md** — Mechanism, symptoms, pH ranges for coco, diagnosis via runoff testing, correction procedure, Plant C relevance
- **nutrient-burn.md** — Symptoms, causes, EC targets by stage, diagnosis vs other issues, correction, current EC situation
- **ec.md** — Units/conversion, targets by stage (Canna A+B), measurement protocol, interaction with VPD/pH, current reading (920 ppm / EC 1.84)
- **wiki/index.md updated** with 4 new concept entries

## [2026-04-12] daily | Day 29 — Both primaries topped
- **Plant A topped Apr 11** (Day 28) — cut above node 4; recovery monitoring begins; LST target ~Apr 16–18
- **Plant D topped Apr 12** (Day 29) — cut above node 4, one day after A; LST target ~Apr 17–19
- Updated `wiki/daily/2026-04-11.md` — title changed, topping recorded, action item checked off
- Created `wiki/daily/2026-04-12.md` — Day 29 daily with topping event and recovery monitoring
- Updated `wiki/plants/plant-a.md` — current state reflects topped status, timeline entry added
- Updated `wiki/plants/plant-d.md` — current state reflects topped status, timeline entry added
- Rewrote `wiki/overview.md` — Day 29, both primaries topped, milestones updated, action items revised (topping replaced with recovery monitoring)
- Updated `wiki/index.md` — daily entries and plant descriptions updated
- **Plants B and C also topped Apr 12** — all four plants now in recovery
- Updated `wiki/daily/2026-04-12.md` — expanded to cover all four toppings
- Updated `wiki/plants/plant-b.md` — topped status, timeline entry added
- Updated `wiki/plants/plant-c.md` — topped while under pH stress, recovery flagged as high-risk
- Updated `wiki/overview.md` — all four topped, Plant C risk highlighted, milestones consolidated
- Updated `wiki/index.md` — B and C descriptions updated
- **Plant C leaf issue resolved** — diagnosed as foliar nutrient burn from accidental solution splash on leaves, not systemic pH lockout. Same mechanism as Plant A's Day 22 incident. Runoff test confirmed no pH drift. All "overdue runoff test" action items cleared. Plant C page title updated, overview/index updated to reflect resolved status.

## [2026-04-14] decision | Agent runtime: Claude Code CLI shell-out (uses Max subscription)
- Discovered Claude Agent SDK explicitly prohibits Pro/Max subscription credentials — requires separate API key with pay-per-token billing.
- **Decided:** shell out to `claude -p` from Python. Uses user's Max subscription (already authenticated locally). Same agent loop, tools, and CLAUDE.md awareness as the SDK.
- Architecture unchanged — still ephemeral agent loops per-request, wiki as memory, JSONL session logs. Only the invocation mechanism differs.
- Created `wiki/decisions/2026-04-14-agent-runtime-shell-out.md` with full rationale + migration path
- Updated `docs/adrs/005-agent-architecture.md` with runtime update note
- Updated `docs/epics/telegram-bot/README.md` to reflect CLI shell-out approach
- Updated `wiki/index.md` with new decision entry

## [2026-04-14] plant-a node deployed
- First ESP32-C3 plant-node live. Reads GPIO3 every 30s, POSTs to `/api/ingest/sensors`.
- Auto-calibration tracking extrema: currently raw_low=458, raw_high=2805 (from the live sensor's first wet/dry cycle).
- 2/5 sensors from the current Amazon pack (B0BTHL6M19) working; 3 dead (AOUT stuck at 0V). Need more stock before plants b/c/d can deploy.
- New hardware page: `hardware/esp32-plant-nodes.md`.
- Decisions filed: `decisions/2026-04-14-esp32-c3-gpio3-adc.md` (GPIO3 over GPIO4, ESP-IDF driver over Arduino analogRead) and `decisions/2026-04-14-server-side-auto-calibration.md`.
- Concept page: `concepts/capacitive-soil-moisture.md` — how the 555-timer sensor works, failure modes, multimeter diagnostic.
- Battery power for plant nodes re-evaluated and declined again: deep-sleep math would make 4+ month runtime feasible on a small USB power bank (Voltaic V50 class or cheap bank + firmware keep-alive pulse), but USB-C wall power is simpler given the tent has a powered USB hub already.

## [2026-04-14 evening] camera presets — overview + 4 plant close-ups (partial)
- User applied colored stickers to pots and tent walls above each plant: A=yellow, B=orange, C=pink, D=blue.
- User repositioned the OBSBOT camera (pushed further back in tent, raised higher). Motor↔world-frame mapping changed from 2026-04-14; new motor pitch floor ≈ -55° (was -45°). Plants are now on the negative-yaw side (overview at yaw=-25; old mount had them at yaw=-90).
- Created `debug/find_sticker.py` — HSV-based sticker detector. Reports centroid, normalized offset, image-thirds position, and pixel count. Enables automated preset tuning without visual review of every frame.
- Created `debug/presets.json` with 5 entries: `overview`, `plant_a`, `plant_b`, `plant_c`, `plant_d`.
- Reference captures saved as `debug/plant_<a|b|c|d>_final.jpg`.
- **Status of presets:**
  - `overview` (pitch=-50, yaw=-25, zoom=1.0) — ✅ confirmed, all 4 plants + sticker IDs visible.
  - `plant_a` (pitch=-38, yaw=-55, zoom=1.5) — ✅ user-approved. Canopy fills frame; yellow sticker touches bottom edge (y_norm=0.974).
  - `plant_b` (pitch=-55, yaw=-25, zoom=1.5) — ⚠ needs refinement. Orange detector false-positives on a red/orange sensor connector; Plant B's actual orange sticker not confirmed in frame.
  - `plant_c` (pitch=-42, yaw=-11, zoom=1.5) — ⚠ needs refinement. Sticker at bottom edge but plant canopy drifted off-frame left; nudge yaw to -7 or -8.
  - `plant_d` (pitch=-43, yaw=-25, zoom=1.5) — ⚠ partial. Pot visible with small blue sticker, wall marker just off top. Sticker too small for auto-detection (<30 px).
- Session ended when grow lights cut off mid-Plant B capture (lights-off schedule). Resume documented in `debug/README.md` under "Open Work / Resume Checklist".

## [2026-04-14 evening] decision | Humidifier closed-loop control ordered
- Ordered Raydrop 4L ultrasonic humidifier + Omron G3MB-202P solid-state relay (arriving 2026-04-15).
- Approach: the Raydrop has only a potentiometer knob (no digital control), so gate its mains power with the SSR. Control loop lives on the Arduino Nano tent-hub, using the existing DHT22 reading. Bang-bang hysteresis with target 60% / ±3% deadband; failsafe forces OFF on stale sensor data.
- Motivation: RH has been chronically off-target (70–76% persistently, with occasional 81–89% overnight spikes and the 2026-04-08 off-state dropout to 42% / VPD 2.03 kPa). Manual knob adjustment does not scale and produces stress-inducing oscillations.
- New wiki pages: [`hardware/humidifier-control.md`](hardware/humidifier-control.md), [`decisions/2026-04-14-humidifier-relay-control.md`](decisions/2026-04-14-humidifier-relay-control.md).
- Updated: `environment/humidity.md` (control plan section), `overview.md` (system status row), `index.md` (catalog entries).
- Alternative deferred: ESP32-based tent-hub controller with server-side setpoints — will revisit once additional actuators (dehumidifier / exhaust modulation / heater) join the control surface.

## [2026-04-15] PTZ camera: daemon + CLI deployed; per-plant presets locked
- **Per-plant gimbal presets recalibrated** (following physical sticker repositioning and the realization that centering on the sticker ≠ centering on the plant due to pot-radius parallax):
  - overview: pitch=-50, yaw=-25, zoom=1.0
  - plant_a: pitch=-38, yaw=-55, zoom=1.5
  - plant_b: pitch=-60, yaw=-22, zoom=1.4 (zoom reduced because at 1.5 the pot sticker falls below the pitch=-60 floor)
  - plant_c: pitch=-47, yaw=+10, zoom=1.5
  - plant_d: pitch=-35, yaw=-24, zoom=1.5
- **Pitch floor finding:** Previously thought to be -55°; actual physical floor is -60°. Apparent -55° floor was the partial-move quirk — commanding -60° directly from +85° clamps at -55°, but stepping through (-35 → -55 → -60) reaches -60° cleanly.
- **Shipped `dirt-camera-daemon`** (C++, ~500 LoC) at `services/camera-daemon/`. Persistent OBSBOT SDK session over Unix socket. Handles partial-move auto-retry (step-through via midpoint), hotplug recovery, zoom soft-cap. Vendored libdev_v2.1.0_8 is now version-controlled under `services/camera-daemon/vendor/libdev/`.
- **Shipped `scripts/camera` CLI** — thin Python client. User-frame commands: `look <preset>`, `nudge <direction> <degrees>`, `zoom <delta>`, `where`. Compound `nudge left=3 up=2` supported (single roundtrip). Never exposes motor coordinates to the agent.
- **Config** at `~/.config/dirt/camera.json` (template at `config/camera.json.example`): sign map + presets. Sign map encodes mount-specific axis-sign conventions, derived empirically during calibration.
- **systemd user service** (`systemd/dirt-camera.service`) enabled + started. `loginctl enable-linger akcom` set so the daemon runs at boot without login. User-crontab entry added for weekly `logrotate` (Sundays 03:00, 4-week retention, copytruncate-safe).
- New hardware page: [`hardware/ptz-camera.md`](hardware/ptz-camera.md). Documents the CLI, daemon, protocol, known quirks, and physical specs.

## [2026-04-15] Jabra Speak 410 deployed; voice pilot proven end-to-end
- Jabra plugged into the RSHTECH USB hub. Appears as ALSA card 2, sounddevice index 6.
- PCM volume maxed to 100% (was 55% out of the box); persisted via `sudo alsactl store 2`.
- Pilot script `debug/deepgram_roundtrip.py` ships: Nova-3 streaming STT from Jabra mic → hardcoded Aura-2 TTS response. Deliberately NOT wired to `claude -p` yet per user direction (agent shape under review).
- Transcripts are clean over tent fan noise — no noise suppression layer needed for the pilot.
- New deps: `deepgram-sdk`, `sounddevice`. System package `libportaudio2` also required.
- `DEEPGRAM_API_KEY` slot added to `.env.example`.
- **Three gotchas discovered, all filed:**
  - Deepgram SDK v6 wants string literals `"true"`/`"false"` for bool-shaped query params; Python `True`/`False` causes HTTP 400.
  - Jabra Speak 410 firmware bug (Red Hat bugzilla #766714): hardware always clocks at 48 kHz regardless of negotiated rate. Sending 16 kHz plays 3× fast. Workaround: always 48 kHz on playback side.
  - Jabra playback is stereo-only (FL/FR) while mic is mono. TTS output must be duplicated to stereo before `sd.play`.
- New pages: [`hardware/jabra.md`](hardware/jabra.md) (operator-facing) and [`debug/jabra.md`](../debug/jabra.md) (agent handoff for productionizing `channels/voice.py`).

## [2026-04-15] query-filed | Autopot ongoing drainage cadence (drydown + reservoir change + top-flush)
- User asked about "drain cadence" on the autopot. Autopot has zero runoff by design, so three distinct maintenance cycles are needed that hand-watering never required. Previously undocumented in the concept page.
- **Tray drydown — weekly.** Close float valves 24–48h once/week so trays go dry and roots get oxygen. Continuous wet tray = anaerobic root zone = root rot risk.
- **Reservoir change — 7–10 day cycle.** Full drain + refill, not just top-off. pH drifts, nutrients precipitate, biology grows, selective uptake skews the ratio.
- **Top-water flush — every 2–4 weeks.** 500ml plain pH 5.8 water per pot from above to push accumulated salts out. Measure runoff EC to detect buildup.
- Suggested weekly rhythm: Mon reservoir change → Tue–Sat drinking → Sun drydown → Mon next change.
- Updated: [`concepts/autopot.md`](concepts/autopot.md).

## [2026-04-15] query-filed | Autopot reservoir pH/EC targets + TDS-3 factor resolved
- User confirmed autopot activation today (reservoir filled, valves about to open).
- **Resolved pending question from 2026-04-11:** TDS-3 meter uses NaCl / 500 scale (factor 0.5). HM Digital ships all pocket TDS meters with this baked in; no toggle on the unit. So `EC (mS/cm) = ppm / 500`. The 920 ppm reading on 2026-04-11 = EC 1.84 (correct).
- **Reframed EC targets as autopot reservoir targets.** Continuous feed means reservoir EC ≈ effective root-zone EC, where hand-feed EC runs 20–30% higher (flush-through dilutes). Existing target (0.8–1.0 for early veg) was already autopot-safe.
- Added post-stress guidance: sit at low end of band during topping / LST / transplant recovery — plants repairing tissue don't tolerate hot nutrients.
- Added Canna mix-order clarifier: A first, stir, then B. Never combine undiluted (calcium phosphate precipitation). pH correction happens **after** Canna is mixed, not before.
- Updated: [`environment/nutrients.md`](environment/nutrients.md), [`concepts/ec.md`](concepts/ec.md).

## [2026-04-16] plant-b + plant-c nodes deployed; all 4 plants live
- Flashed fresh ESP32-C3 SuperMini units with plant-node firmware fw 0.1.1 for plant-b (MAC AC:A7:04:BB:C3:38 → 192.168.1.243) and plant-c (MAC AC:A7:04:BB:D7:B4 → 192.168.1.117, reused from the 2026-04-14 GPIO debugging dev unit). `platformio.ini` got `plant-b`/`plant-b-ota` and `plant-c`/`plant-c-ota` env blocks following the existing pattern.
- Both units got v2.0 capacitive moisture sensors (user had exhausted the original v1.2 Amazon pack). Plant-a and plant-d stay on v1.2 — fleet now mixed, but auto-calibration normalizes over the generation difference.
- **Calibration cleanup:** after bring-up, plant-b and plant-c's `sensorcalibration` rows had inflated `raw_high` values (~3800) that were initially suspected as floating-pin spikes. Turned out to be **legitimate ESP32-C3 ADC non-linearity** near the rail — multimeter-verified 2.76 V on AOUT reads as raw ~3800 via `adc1_get_raw()` (no `esp_adc_cal` correction). Still did a clean wipe of plant-b and plant-c calibration + historical readings (backed up `dirt.db` first) so fresh calibrations seeded from measured wet/dry transitions. Current clean values: plant-b 1378/3806, plant-c 1383/3874 — tightly matched, both v2.0 sensors from the same pack behave identically.
- **New quirks filed:** v1.2 vs v2.0 sensor differences (reseller "2.3V ceiling" claim doesn't match our hardware — ours outputs 2.76V); ESP32-C3 ADC over-reports by 200–400 counts above ~2.5V input; pyserial default DTR assertion resets ESP32-C3 on port open (fix: `s.dtr = False; s.rts = False` before `open()`).
- New scratch tool: `debug/moisture_report.py` — per-plant snapshot of raw, calibration bounds, and normalized wet%.
- Updated: [`hardware/esp32-plant-nodes.md`](hardware/esp32-plant-nodes.md), [`concepts/capacitive-soil-moisture.md`](concepts/capacitive-soil-moisture.md), [`overview.md`](overview.md), [`index.md`](index.md).

## [2026-04-16] decision | Voice pipeline: ElevenLabs TTS + openWakeWord wake phrase
- **TTS provider selected:** ElevenLabs `eleven_multilingual_v2` replaces Deepgram Aura-2. Voice persona is "Claudia" (bilingual English/Spanish). Settings: stability=0.55, similarity_boost=1.0, speed=1.08, +12 dB gain for Jabra playback.
- **Wake word engine selected:** openWakeWord (Apache 2.0). Custom "hey claudia" model currently being trained via synthetic data. Always-on listener gates STT/LLM/TTS to avoid idle API costs.
- **STT unchanged:** Deepgram Nova-3 retained.
- **Architecture:** Jabra mic → openWakeWord (always-on) → trigger → Deepgram STT → LLM → ElevenLabs TTS → Jabra speaker.
- Pilot: `debug/elevenlabs_tts.py` — ElevenLabs streaming TTS through Jabra proven end-to-end.
- Dependency added: `elevenlabs` Python SDK.
- New decision record: [`decisions/2026-04-16-voice-pipeline-selections.md`](decisions/2026-04-16-voice-pipeline-selections.md).
- Updated: [`hardware/jabra.md`](hardware/jabra.md), [`overview.md`](overview.md), [`index.md`](index.md).

## [2026-04-16] wake-word | Pipeline investigation, diagnostics, retraining strategy
- **Default Piper-only openWakeWord model tested** via `debug/wake_word_test.py` against the Jabra mic. Close-range recall 70–80% at threshold 0.5–0.4; far-range recall collapsed to 40% with many utterances scoring near zero (model blind, not threshold-limited). Deepgram Nova-3 run as a control from the same far spot — about half the utterances came back garbled, confirming acoustic-path degradation is real but still less severe than the model's blindness.
- **Decision: retrain with voice-matched + environment-matched data**. See [training strategy decision](decisions/2026-04-16-wake-word-training-strategy.md). Rejected alternatives: threshold tuning, Piper+MIT-RIR retrain, LoRA/fine-tune (no hooks, model too small), custom verifier only (precision-not-recall tool).
- **Captured 9 room impulse responses** via exponential sine sweep + Farina deconvolution. Two-script setup: `debug/capture_rir_record.py` on the Jabra host, `debug/capture_rir_play.py` on the laptop at the capture position. Positions: `loft_primary`, `loft_2`, `mid_loft`, `stairs_top`, `couch`, `couch_far`, `kitchen_far`, `next_to_tent`, `tent_far`. All 65–77 dB SNR. Output at `debug/rirs/ir/*.wav`.
- **Voice-clone generation**. ElevenLabs clone (voice ID `mjXJZpUEgv69eq6xrhlW`), `eleven_multilingual_v2` model, `pcm_16000` output for direct training-pipeline compatibility. Four phrase variants ("hey claudia", "Hey, Claudia", "hey Clowdia", "Hey, Clowdia") × 500 each via `debug/elevenlabs_clone_batch.py` (resume-safe: targets-not-deltas semantic). Phonetic spelling "CLAU-dyah" tested and rejected (sounded weird); "Clowdia" retained as it pronounces cleanly. First 2000-sample attempt hit a 4k-credit per-API-key cap; resumed after raising limit.
- **Three training iterations** in Colab:
  - **v1**: default Piper-only baseline — rejected (poor recall).
  - **v2**: voice clones + our RIRs + train/test split. Validation 70% recall, real-world 71% (5/7 at threshold 0.4). Better but conservative.
  - **v3** (shipped): same data, plus `max_negative_weight=500` (was 1500), `target_recall=0.85` (was 0.25), training_steps=20000. Validation 79% recall, **real-world 89% (8/9)** at threshold 0.4. Clean fires consistently peak 0.95–0.99. Validation FP/hr jumped from ~1.3 → 6.6, but threshold has headroom to raise for deployment precision.
- **Key training lessons learned**:
  - Training config's `n_samples` is a trigger for Piper generation, not a deltas semantic — pre-populating `positive_train/` to ≥95% of `n_samples` short-circuits it. Same trick works for `positive_test/`.
  - **Validation on held-out clones is required** — initial v1 validation measured cross-speaker recall on LibriTTS voices (11%) which was alarming but mostly cosmetic. Moving to an in-distribution train/test split (1500/500 of our voice clones) flipped the number to 70% without changing the model.
  - Comma in `target_phrase` crashes `generate_adversarial_texts` phoneme lookup. Strip punctuation from targets; commas are only meaningful for ElevenLabs pause insertion.
  - `--augment_clips` guard only checks `positive_features_train.npy`. If that file exists but the other three don't (crash mid-augment), re-running does nothing — use `--augment_clips --overwrite`.
  - Two different toolchains convert ONNX to TFLite (`onnx_tf` and `onnx2tf`). Colab's `onnx_tf` path errors but the `onnx2tf` path further down succeeds — ignore the scary `ModuleNotFoundError: No module named 'onnx_tf'` if the `.tflite` file is produced.
- **Two new concept pages**:
  - [`concepts/wake-word-detection.md`](concepts/wake-word-detection.md) — openWakeWord three-stage architecture (melspec → pretrained embedding → tiny classifier), why synthetic training works, frame-burst behavior, diagnostic protocol, custom verifier alternative.
  - [`concepts/room-impulse-response.md`](concepts/room-impulse-response.md) — What IRs are and aren't, why they're useful for augmentation, Farina's sine sweep method, capture setup, caveats (speaker coloration, mouth directivity).
- **New deps added**: `openwakeword` (also pulled in `onnxruntime`, `scipy`, `scikit-learn`, `protobuf`, etc.).
- Final model shipped at `debug/hey_claudia.onnx`. Archived: `hey_claudia_v1.onnx` (Piper baseline), `hey_claudia_v2.onnx` (conservative).
- Updated: [`hardware/jabra.md`](hardware/jabra.md), [`index.md`](index.md), [`decisions/2026-04-16-wake-word-training-strategy.md`](decisions/2026-04-16-wake-word-training-strategy.md).

## [2026-04-17] sensors | plant-d moisture dropouts diagnosed and cleaned
- **Symptom investigated**: `plant-d` `soil_moisture_raw` showing daily clusters of sub-100 raw values (~25% of samples, vs 0–0.7% on a/b/c). Values of 1–6 are below plant-d's calibrated `raw_low=105` — sensor output collapse, not real readings.
- **Pattern**: dropouts cluster at 04:00–09:00 and 19:00 — the hours where tent temperature / humidity are *transitioning*, not the peak-heat hours (10:00–14:00 had zero dropouts). Signal aligns with dew-point crossings rather than lights/heat.
- **Likely cause**: plant-d is a v1.2 sensor from the first Amazon pack (40% DOA rate). Hypothesis is marginal conformal coating letting moisture wick into the 555-timer traces during high-RH transitions, collapsing the oscillator. plant-a (also v1.2) does not show this failure, so it's a unit-level defect, not a generational issue.
- **Data cleanup**: deleted 2,165 rows matching `metric='soil_moisture_raw' AND location='plant-d' AND value < 105` from `dirt.db`. Backup at `dirt.db.bak-before-plantd-cleanup-1776489309`. Post-cleanup plant-d trends coherently: 27.9% → 34.3% → 38.3% wet over 04-16/04-17/04-18.
- **Open issue**: [#20](https://github.com/akravetz/dirt/issues/20) — fix is to swap plant-d's sensor for a v2.0 unit (matches b/c).

## [2026-04-17] decision | Humidifier actuator switched from SSR to Kasa EP10 smart plug
- **What changed**: dropped the 2026-04-14 plan to control the Raydrop 4L via a G3MB-202P SSR on the Arduino Nano. Replaced with a **TP-Link Kasa Ultra Mini EP10** smart plug driven from a host-side Python service via [`python-kasa`](https://github.com/python-kasa/python-kasa). No mains wiring, no custom enclosure, no GPIO.
- **What didn't change**: the control algorithm. Still bang-bang with hysteresis (target 60% RH, ±3% deadband), with a minimum off-time for relay protection and a max-on safety timeout. PID reconfirmed as the wrong tool here — binary actuator, asymmetric transfer function, big dead time, finite relay switch-cycle budget, plants don't need ±1% precision.
- **Why the switch**: the SSR approach was accepted on 2026-04-14 but hardware was never deployed — installing mains-switching safely (enclosure + strain relief + fused outlet) is higher-friction than a UL-listed sealed smart plug. Same control topology, lower activation energy.
- **Bonus from the EP10**: energy monitoring. Wattage reporting gives a free ground-truth signal when the humidifier has been unplugged, run dry, or hit its own cutoff despite the plug reporting ON.
- **Deliverables**: new decision record at [`decisions/2026-04-17-humidifier-kasa-ep10.md`](decisions/2026-04-17-humidifier-kasa-ep10.md); old [`decisions/2026-04-14-humidifier-relay-control.md`](decisions/2026-04-14-humidifier-relay-control.md) marked Superseded; [`hardware/humidifier-control.md`](hardware/humidifier-control.md) fully rewritten for the EP10 path; [`environment/humidity.md`](environment/humidity.md), [`index.md`](index.md), and [`overview.md`](overview.md) updated to match.
- **Next**: onboard the EP10 (Kasa app + DHCP reservation), then scope the control service on the `dirt` host.

## 2026-04-18 — Production voice channel deployed

First pass at the voice agent (`channels/voice.py`) shipped and running as `dirt-voice.service`. Pipecat v1.0 pipeline: wake-word (openWakeWord) → Deepgram Nova-3 STT → Claude Haiku 4.5 (with 3 tools: `get_current_status`, `get_sensor_trend`, `ask_wiki`) → ElevenLabs `eleven_turbo_v2_5` TTS → Jabra. Custom `SoundDeviceTransport` in callback mode (portaudio ring buffer) to get `latency='low'` + instant barge-in on our asymmetric-endpoint Jabra. Session transcripts append to `sessions/voice/YYYY-MM-DD.jsonl`. PID file at `logs/voice.pid` for reliable external stop.

- New pages: `wiki/hardware/voice-channel.md` (pipeline), `docs/references/pipecat/` (v1.0 anchor pack).
- Updated: `wiki/hardware/jabra.md` (marked production voice channel deployed, linked out to voice-channel.md), `wiki/index.md`, `CLAUDE.md` (new "Voice Channel (Claudia)" commands block).

## 2026-04-18 — Wake-word v4 plan filed; near-miss audio capture live

v3 (shipped 2026-04-16) solved the far-field recall problem but exposed the next one: precision. In the wild we've seen a meeting false positive (score 0.74 on Zoom audio during a real meeting) and ambiguous-zone misses (legitimate "hey Claudia" attempts scoring 0.47–0.49 from positions further than v3's training RIRs covered). v3's negatives were generic LibriTTS — no environment match.

v4 plan is precision-focused retraining: add in-situ hard negatives, mine meeting audio + transcripts for phonetic neighbors, synthesize more phonetic-neighbor samples via ElevenLabs, capture additional far-field RIRs, and bump `max_negative_weight` 500 → 800 once negatives are representative. Also has runtime-only fallbacks (double-hit confirmation, tiny speaker verifier) if retraining schedule slips.

- New page: `wiki/decisions/2026-04-18-wake-word-v4-plan.md`.
- Shipped now: `src/dirt/channels/voice.py` keeps a 1.9 s audio ring buffer and dumps a WAV on every wake event and every near-miss with score ≥ 0.3. Lands in `logs/wake_audio/`, intentionally not auto-rotated so we can accumulate for 1–2 weeks before training.
- Updated: `wiki/index.md` (v4 plan link under Decisions).

## 2026-04-18 — Humidifier closed-loop control deployed

Kasa EP10 smart plug provisioned as `dirt-humidifier` (DHCP-reserved `192.168.1.220`). New service `src/dirt/services/humidifier.py` runs from the FastAPI lifespan and drives the plug via `python-kasa` based on tent DHT22 RH — bang-bang with a ±3% deadband around 60% target, plus 90s min-off, 20-min max-on safety, and failsafe-OFF on stale (>5 min) readings. Per-poll `humidifier_on` (0/1) rows land in `sensorreading` (graphable alongside `humidity_pct`); state transitions land in `logs/humidifier/` with reason + RH.

One snag: stock `python-kasa` 0.10.2 fails KLAP v2 auth on our firmware (1.1.1 Build 250908). Pinned to the fork branch in [PR #1580](https://github.com/python-kasa/python-kasa/pull/1580) until that merges. Also worth knowing: "Remote Control" must be enabled in the Kasa app for LAN auth to work — cloud registration is what provisions the KLAP credentials the plug checks locally.

- Updated: `wiki/hardware/humidifier-control.md` (deployment status, known-issues section, state-logging section), `CLAUDE.md` (new `humidifier` stream in the observability table).

## 2026-04-18 — Reservoir-level sensing planned (submerged pressure transducer)

Net-new design (no prior reservoir-level page existed). For the 25-gal Autopot FlexiTank Pro: submerged hydrostatic pressure transducer (DFRobot KIT0139, 4–20mA, 0–5m, IP68) → 4-20mA-to-voltage converter → ADS1115 16-bit I²C ADC → new dedicated ESP32-C3 SuperMini node (working name `dirt-reservoir.local`, location label `reservoir`) → existing `/api/ingest/sensors` endpoint as `reservoir_depth_cm` at 30 s cadence. ADS1115 chosen over the C3's native ADC because the C3 over-reports near the rail (already-documented quirk) and absolute-accuracy depth conversion can't tolerate that systematic error.

Decision record covers alternatives (float switch, multi-stage float ladder, ultrasonic, capacitive strip, eTape) and why submerged pressure won. Notable trade-off accepted: 0–5m probe on a ~0.5m tank gives ±25 mm absolute accuracy (~5% of tank depth) — fine for "days-until-empty" but worth recording so we don't pretend to mm-class precision later.

Status: parts on roadmap, none assembled yet; firmware project (`firmware/reservoir_node/`) doesn't exist yet. Open items: 4-20mA conversion path (SEN0262 module vs discrete shunt), 12V supply source, lid grommet for cable strain relief.

- New pages: `wiki/hardware/reservoir-level.md`, `wiki/decisions/2026-04-18-reservoir-level-pressure-transducer.md`.
- Updated: `wiki/index.md` (added under Hardware and Decisions), `wiki/concepts/autopot.md` (new "Reservoir Level Telemetry" section linking out).

Also today: plant-A and plant-D moisture sensors swapped to v2.0; both calibrated via 30-min water soak + air-dry, calibration rows reset (sentinel-then-relearn) to wet ~1370–1376 / dry ~3883–3887. Old v1.2 readings purged from `sensorreading` (8,734 rows) so historical curves don't mix sensor generations.

## [2026-04-18] daily | Day 35 — LST window open; overnight temp/RH flags; A/D sensors upgraded to v2.0

- Created `wiki/daily/2026-04-18.md` — Day 35 (Day 6–7 post-topping recovery); 5 photos (overview + 4 plants, 14:00 MDT); windowed sensor data (overnight/morning/now); all plants healthy and branching; LST due now; overnight temp 63.54°F avg and overnight RH 76.95% avg flagged; Plant B morning drydown (3.57%) noted; A/D sensor gaps explained (v1.2 purged, v2.0 fresh)
- Updated `wiki/plants/plant-a.md` — timeline entry + Current State rewritten (LST due now)
- Updated `wiki/plants/plant-b.md` — timeline entry + Current State rewritten (LST due now; morning drydown noted)
- Updated `wiki/plants/plant-c.md` — timeline entry + Current State rewritten (LST due now; stable moisture)
- Updated `wiki/plants/plant-d.md` — timeline entry + Current State rewritten (LST due now; v2.0 sensor)
- Updated `wiki/environment/temperature.md` — trend row + notable event for overnight lights-off dip (63.54°F avg)
- Updated `wiki/environment/humidity.md` — trend row + notable event for overnight RH spike + day/night VPD swing
- Rewrote `wiki/overview.md` — Day 35, LST due flag, overnight env flags, plant status table updated, environment last reading updated
- Updated `wiki/index.md` — Day 35 daily entry added
- **Known gap:** No daily entries for 2026-04-13 through 2026-04-17 (no photos or sensor snapshots taken on those dates). Pre-existing pattern; lint timeline-continuity check will flag this gap.

## [2026-04-18] query-filed | AC Infinity Cloudline LITE 6" fan control — reverse-engineering plan + hardware ordered

- User wants to remove AC Infinity's proprietary stock wired remote from the loop and drive the Cloudline LITE 6" inline fan from an Arduino Nano (controlled by the Dirt stack) for programmatic speed / scheduled ramps / closed-loop VPD pairing with the humidifier.
- **Signaling confirmed as PWM** via the back label of the stock wired speed controller. Working assumption: single PWM line on the fan's USB-C connector (most likely SBU1/SBU2; fallback CC1/CC2; least-likely D+/D−). Duty cycle encodes speed; no multi-byte protocol.
- **Approach:** (1) multimeter pre-flight to confirm no pin >5V and narrow candidates to the pin whose DC-averaged voltage changes with knob position; (2) HiLetgo 8-channel logic analyzer + PulseView to identify the PWM pin, measure frequency and duty-cycle range; (3) permanent install on a perma-proto board with a socketed Arduino Nano driving a Treedix female USB-C breakout.
- **Hardware ordered 2026-04-18** (all in transit):
  - minidodoca USB-C M/F passthrough test board × 2 (B0FLX671VF) — analysis tap
  - Treedix vertical female USB-C breakout × 2 (B0D31GG6WD) — permanent install interface
  - HiLetgo USB logic analyzer 24 MHz 8CH (B077LSG5P2)
  - ElectroCookie prototype solderable PCBs 5+1 (B07ZYNWJ1S)
  - Lonely Binary female header assortment kit, 160 pc (B0FFM2RBMB)
- **New page:** `wiki/hardware/ac-infinity-fan-control.md` — full context, shopping list, reverse-engineering stages, permanent install plan, open questions.
- Updated: `wiki/index.md` (added under Hardware), `wiki/overview.md` (System Status row added).

## [2026-04-18] training | SCROG net installed; LST start deferred 1–3 days

- User installed VIVOSUN 4x4 trellis net today at **11" above canopy / 18" above pot base** — matches the plan spec in `wiki/concepts/scrog.md` (18" above pots) and sits in the standard 8–12" above-canopy range. Install is ~1–2 weeks ahead of the original weeks-6–8 estimate; acceptable tradeoff — the net becomes an anchor plane for LST ties rather than a later overhead constraint.
- **LST not started today** — user reports the two new main shoots per plant aren't yet sized up enough to bend confidently; will begin once each clears ~2" (expected 1–3 days).
- Updated: `wiki/daily/2026-04-18.md` (title, summary, added Training Action Today section, Recommendation #1 rewritten for net-installed + LST-pending state), `wiki/overview.md` (Current Stage, Plant Status rows, Active Action Items #1, Upcoming Milestones — SCROG marked done), `wiki/concepts/scrog.md` ("In This Grow" with actual install date + measurements).
- Q&A context: user asked whether LST and SCROG are mutually exclusive (no — sequence is Top → LST → SCROG per `wiki/concepts/plant-training-methods.md`), when to install the net, what height, and whether indica/sativa changes the answer. Answer was in-chat; the concept pages already cover the rationale, so no new concept page needed.

## [2026-04-18] decision | Humidifier control switched to stage-dynamic VPD targeting

- **Motivated by 2026-04-18 overnight data:** fixed 60% RH setpoint produced healthy daytime VPD (~1.3 kPa at 75°F) but collapsed to 0.46 kPa overnight (seedling range) when the tent cooled to 63°F and the humidifier kept topping off. The control loop needed to be temperature-aware; VPD already is.
- **Decision:** humidifier now targets the **upper edge of the stage-appropriate VPD band** read from `dirt.services.grow_state.STAGE_TARGETS`, with a 0.1 kPa deadband. ON when `vpd > upper_band`, OFF when `vpd < upper_band − deadband`. Stage band shifts automatically across veg / early flower / late flower as `grow_state.flower_start_date` is written.
- **Grow identity modeled in DB:** new `grow_state` singleton table (`germination_date`, `flower_start_date`), seeded from `config.GROW_START` on first boot. Future frontend will PATCH this row; the flower-start flip drives the veg→flower transition without a service restart.
- **Single source of truth for stage targets:** Claudia's voice status tool (`src/dirt/tools/sensors.py`) now reads the same `STAGE_TARGETS` dict, so "out of range" flagging matches the humidifier setpoint exactly. Stage bands sourced from converging cannabis cultivation guidance (gorillagrowtent.com, athenaag.com, advancednutrients.com, growerIQ, royalqueenseeds, questclimate — all consulted 2026-04-18).
- **Hardware / safety guards unchanged:** Kasa EP10 actuator, min-off 90s, max-on 20min, stale-sensor failsafe 5min, failsafe-OFF on ambiguity — all carry over from [2026-04-17 decision](decisions/2026-04-17-humidifier-kasa-ep10.md). Only the setpoint definition changed.
- **Config cleanup:** `humidity_target_pct` and `humidity_deadband_pct` removed; replaced by `vpd_deadband_kpa = 0.1`. `grow_week()` moved from `config.py` to `services/grow_state.py` (now async, reads germination_date from DB); callers in `channels/voice.py` and `tools/wiki.py` updated.
- **Resolved action item from overview:** "Lower overnight humidifier setpoint" — VPD targeting handles this automatically (cool nights drop VPD naturally, loop stops running without a schedule).
- **New page:** [`wiki/decisions/2026-04-18-vpd-targeting.md`](decisions/2026-04-18-vpd-targeting.md). Updated: `wiki/hardware/humidifier-control.md` (Control Logic + State Logging + Acceptance sections rewritten), `wiki/environment/humidity.md` (Targets by Phase table + Deployed Control System section), `CLAUDE.md` (observability table: `humidifier` stream fields now `vpd`, `vpd_age_s`, `stage`, `upper_band_kpa`, `lower_band_kpa`), `wiki/overview.md` (removed resolved action item).
- **Tests:** 13 new in `tests/test_grow_state.py` — stage math, week math, target lookup, singleton seeding idempotency. 131 tests passing.

## [2026-04-19] decision | Drop humidifier max-on and min-off safety timers
- **Decision:** [`wiki/decisions/2026-04-19-drop-humidifier-safety-timers.md`](decisions/2026-04-19-drop-humidifier-safety-timers.md). Removed `humidifier_max_on_seconds` (20 min) and `humidifier_min_off_seconds` (90s) from `apps/shared/src/dirt_shared/config.py` and from the loop in `apps/hwd/src/dirt_hwd/services/humidifier.py`. Only safety retained: `humidifier_failsafe_stale_seconds` (5 min).
- **Why:** 2026-04-19 log analysis (`var/logs/humidifier/2026-04-19.jsonl`) showed four consecutive on-phases between 13:34–14:55 UTC terminating on `max_on_timeout` at VPD values (1.65, 1.36, 1.22) still well above the hysteresis turn-off edge (1.10). The 20-min safety had become the *primary* termination criterion, making the effective setpoint non-deterministic and burning relay cycles against the deadband. 90s `min_off` was redundant with the VPD deadband (hysteresis already prevents chatter).
- **Safety reasoning:** Raydrop 4L has its own low-water cutoff, so a stuck-high VPD reading self-limits by reservoir exhaustion rather than by the `max_on` timer. Relay lifetime is cycle-limited, not duty-limited — dropping these guards *reduces* cycles.
- **Updated:** `wiki/hardware/humidifier-control.md` (Control Logic pseudocode, "Why these choices" bullets, State-change reasons list, Acceptance criteria, relay-lifetime note), `wiki/index.md` (new decision entry), `CLAUDE.md` (observability table: `humidifier` stream `reason` values enumerated).
- **Tests:** No tests referenced the removed settings; no env / systemd overrides existed.

## [2026-04-19] decision | Lights-off-aware humidifier feedforward (A + B)
- **Decision:** [`wiki/decisions/2026-04-19-lights-off-aware-humidifier.md`](decisions/2026-04-19-lights-off-aware-humidifier.md). Added two rules to `humidifier_loop`:
  - **A.** Pre-lights-off prep window: force OFF in the last `lights_off_prep_minutes` (30) of lights-on.
  - **B.** Lights-off band offset: subtract `vpd_lights_off_offset_kpa` (−0.3) from the stage band during dark period. Preserves deadband width.
- **Schema:** added `lights_on_local` and `lights_off_local` (`TIME`) columns to `growstate`. Seeded `(05:00, 23:00)` for veg 18/6. Migration is idempotent `ALTER TABLE ADD COLUMN ... DEFAULT` in `init_db()` — existing production row auto-populated.
- **Why:** lights-off crash is a *scheduled, periodic* disturbance, so feedforward (clock-based) strictly dominates derivative feedback (DHT22-noise-limited). Measured steady-state overshoot after clean shutoff is only ~0.004 kPa and ~15 s — nighttime VPD collapse is the disturbance itself, not control-loop lag. Night band (0.5–0.9 veg; 0.7–1.0 flower_early; 0.9–1.2 flower_late) sits inside the published "0.2–0.4 kPa below day" industry range.
- **Files:** `apps/shared/src/dirt_shared/models/grow_state.py` (two new `time` fields), `apps/shared/src/dirt_shared/db.py` (column migration), `apps/shared/src/dirt_shared/services/grow_state.py` (`TENT_TZ`, `LightsState`, async `lights_state()`), `apps/shared/src/dirt_shared/config.py` (two new knobs), `apps/hwd/src/dirt_hwd/services/humidifier.py` (decision block).
- **Observability:** new reason `lights_off_prep`; every state_change now carries `lights_on`, `minutes_until_off`, `band_offset_kpa`.
- **Updated:** `wiki/hardware/humidifier-control.md` (Control Logic rewritten, new "Why" bullets, State Logging reasons), `wiki/index.md`, `CLAUDE.md` (observability table, + new "Current grow" section pinning germination 2026-03-15 and the stage-derivation rule for agents without DB access).
- **Tests:** 5 new in `apps/shared/tests/test_grow_state.py` covering `lights_state` across on/off/prep-window/schedule-override cases. 113 tests passing across invariants + shared + hwd suites.
- **Pending user action:** `systemctl --user restart dirt-hwd` to pick up the new loop (+ the earlier drop-timers change). Service has NOT been restarted yet.

## [2026-04-19] query-filed | Multi-actuator environment control design principles
- **New page:** [`wiki/concepts/multi-actuator-environment-control.md`](concepts/multi-actuator-environment-control.md). Captures the design discussion from 2026-04-19 for how to structure the control loop once the dehumidifier (second Kasa EP10) and PWM exhaust fan are provisioned.
- **Key decisions (principles, not code yet):** target 2D (T, RH) zones rather than scalar VPD; cascaded SISO state-machine with priority over true MIMO; assign actuators by dominant authority (fan → T, humidifier/dehumidifier → RH ±); feedforward on the lights schedule is the main lever; rejected PID / LQR / derivative estimation as over-engineering for a sparse actuator-output matrix. Failure modes called out up front: actuator mutex, dehumidifier saturation detection via wattage, fan baseline floor, dehumidifier compressor min-off.
- **Status:** explicitly future work. Nothing to implement until hardware arrives. Migration path documented.
- **Updated:** `wiki/index.md` (new concept entry flagged as "future").

## [2026-04-19] daily | Day 36 — Overnight temp recovered; LST overdue; daytime VPD elevated

- Created `wiki/daily/2026-04-19.md` — Day 36 (Day 8/7 post-topping); 5 photos (overview + 4 plants, 14:00 MDT); windowed sensor data; all plants healthy and vigorous; overnight temp recovered to 68.0°F ✅ (first time in veg night range); overnight RH still elevated at 70.79% (improving trend); daytime VPD above ceiling at 1.31–1.51 kPa ⚠️; LST overdue (Day 8/7 post-topping); Plant A moisture rising to 56% (autopot active); B/D stable ~26–27%
- Updated `wiki/plants/plant-a.md` — timeline entry (Day 36, LST overdue) + Current State rewritten
- Updated `wiki/plants/plant-b.md` — timeline entry (Day 36, LST overdue) + Current State rewritten
- Updated `wiki/plants/plant-c.md` — timeline entry (Day 36, LST overdue) + Current State rewritten
- Updated `wiki/plants/plant-d.md` — timeline entry (Day 36, LST overdue) + Current State rewritten
- Updated `wiki/environment/temperature.md` — trend row for Apr 19 (overnight in range for first time); notable event added
- Updated `wiki/environment/humidity.md` — trend row for Apr 19 (overnight improving; daytime VPD above ceiling); notable event added
- Rewrote `wiki/overview.md` — Day 36, overnight temp resolved, daytime VPD new flag, LST overdue, plant status and environment readings updated
- Updated `wiki/index.md` — Day 36 daily entry added

## [2026-04-20] decision | Swap tent-hub temp/RH sensor DHT22 → BME280
- **Decision:** [`wiki/decisions/2026-04-20-bme280-sensor-swap.md`](decisions/2026-04-20-bme280-sensor-swap.md). Replaced the DHT22 on the Arduino Nano tent-hub with a Bosch BME280 (I²C `0x76`). Sensor physically deployed ~2026-04-13; documentation catch-up today.
- **Why:** DHT22 hardware failure (stale / invalid reads) + want less long-term cal drift under a VPD-targeted control loop where temp error compounds into VPD error.
- **Unchanged:** tent-hub topology (Nano outside the tent, USB serial to host), ingest schema, humidifier control loop (VPD setpoint, 0.1 kPa deadband, feedforward, failsafes). Control loop is sensor-agnostic — reads VPD from DB.
- **Bonus:** barometric pressure now captured as a free side channel. Not wired to any controller.
- **Historical decisions kept intact:** `decisions/2026-04-12-distributed-sensor-architecture.md`, `decisions/2026-04-14-humidifier-relay-control.md`, `decisions/2026-04-17-humidifier-kasa-ep10.md`, `decisions/2026-04-18-reservoir-level-pressure-transducer.md`, `decisions/2026-04-19-lights-off-aware-humidifier.md`, `decisions/2026-04-19-drop-humidifier-safety-timers.md` — DHT22 references preserved; rationale still sound under BME280. New decision record is the authoritative supersede pointer.
- **Updated:** `wiki/overview.md` (System Status row), `wiki/index.md` (humidifier blurb + new decision entry + `updated` bumped), `wiki/environment/humidity.md` (Deployed Control System sensor line), `wiki/hardware/humidifier-control.md` (pipeline description + deadband rationale + "Why these choices" bullets), `wiki/concepts/multi-actuator-environment-control.md` (room-sensor references).
- **Out of scope wiki-side:** `apps/shared/src/dirt_shared/services/system_status.py` and any other code-side user-facing strings still mentioning "DHT22" — flagged for a follow-up pass.

## [2026-04-20] daily | Day 37 — Daytime environment in target; overnight RH regressed; LST still outstanding

- Created `wiki/daily/2026-04-20.md` — Day 37 (Day 9/8 post-topping); 5 photos (overview + 4 plants, 14:00 MDT); windowed sensor data; daytime temp in target (75.04°F ✅) and VPD in target at 14:00 (1.12 kPa ✅) for first time; overnight RH regressed to 74.37% ⚠️ and overnight VPD dropped to 0.57 kPa ⚠️ — `dirt-hwd` restart still pending; all plants healthy and vigorous; Plant D lighter green than peers — monitoring; LST critically overdue (Day 9/8); Plant B moisture spiked to 58% at 14:00 (autopot afternoon feeding)
- Updated `wiki/plants/plant-a.md` — timeline entry (Day 37, LST critically overdue, Day 9 post-topping) + Current State rewritten
- Updated `wiki/plants/plant-b.md` — timeline entry (Day 37, moisture spike 58%, LST critically overdue) + Current State rewritten
- Updated `wiki/plants/plant-c.md` — timeline entry (Day 37, compact healthy canopy, LST critically overdue) + Current State rewritten
- Updated `wiki/plants/plant-d.md` — timeline entry (Day 37, ⚠️ lighter green — monitoring, LST critically overdue) + Current State rewritten
- Updated `wiki/environment/temperature.md` — trend row for Apr 20 (daytime in target; overnight regression); notable event added
- Updated `wiki/environment/humidity.md` — trend row for Apr 20 (daytime VPD in target; overnight regression confirmed); notable event added
- Rewrote `wiki/overview.md` — Day 37, daytime environment resolved, overnight regression new flag, LST critically overdue, plant status and environment readings updated
- Updated `wiki/index.md` — Day 37 daily entry added
- Updated `wiki/hardware/humidifier-control.md` — added "BME280 stuck-state (recurring)" subsection under Known Issues with pattern description, detection cue, fix (`systemctl --user restart dirt-hwd`), and incident log table (entry 1: 2026-04-20 17:36 MDT)
- Updated `wiki/daily/2026-04-20.md` — added "BME280 stuck-state incident at 17:36 MDT" flag under Issues & Flags
