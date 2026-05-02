---
title: Activity Log
type: log
created: 2026-04-06
updated: 2026-04-27
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
- **Default Piper-only openWakeWord model tested** via `apps/wake-word/validation/live-test.py` against the Jabra mic. Close-range recall 70–80% at threshold 0.5–0.4; far-range recall collapsed to 40% with many utterances scoring near zero (model blind, not threshold-limited). Deepgram Nova-3 run as a control from the same far spot — about half the utterances came back garbled, confirming acoustic-path degradation is real but still less severe than the model's blindness.
- **Decision: retrain with voice-matched + environment-matched data**. See [training strategy decision](decisions/2026-04-16-wake-word-training-strategy.md). Rejected alternatives: threshold tuning, Piper+MIT-RIR retrain, LoRA/fine-tune (no hooks, model too small), custom verifier only (precision-not-recall tool).
- **Captured 9 room impulse responses** via exponential sine sweep + Farina deconvolution. Two-script setup: `apps/wake-word/data-gen/capture-rir-record.py` on the Jabra host, `apps/wake-word/data-gen/capture-rir-play.py` on the laptop at the capture position. Positions: `loft_primary`, `loft_2`, `mid_loft`, `stairs_top`, `couch`, `couch_far`, `kitchen_far`, `next_to_tent`, `tent_far`. All 65–77 dB SNR. Output at `var/wake-word/rirs/*.wav`.
- **Voice-clone generation**. ElevenLabs clone (voice ID `mjXJZpUEgv69eq6xrhlW`), `eleven_multilingual_v2` model, `pcm_16000` output for direct training-pipeline compatibility. Four phrase variants ("hey claudia", "Hey, Claudia", "hey Clowdia", "Hey, Clowdia") × 500 each via `apps/wake-word/data-gen/elevenlabs-clones-batch.py` (resume-safe: targets-not-deltas semantic). Phonetic spelling "CLAU-dyah" tested and rejected (sounded weird); "Clowdia" retained as it pronounces cleanly. First 2000-sample attempt hit a 4k-credit per-API-key cap; resumed after raising limit.
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
- Final model shipped at `var/wake-word/models/current/hey_claudia.onnx`. Archived: `hey_claudia_v1.onnx` (Piper baseline), `hey_claudia_v2.onnx` (conservative).
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

## [2026-04-22] query-filed | PTZ camera USB dropout — potentially recurring hardware pattern
- **Incident:** 2026-04-22 08:58 MDT — OBSBOT SDK logged `remove uvc device: RMOWLHI1203JLY`; camera absent from `lsusb` and `/dev/video*` for ~25 min, then spontaneously reappeared at ~09:23. Systemd watchdog (30 s) killed each of 6 restart attempts since the SDK couldn't issue keepalives without a camera; burst cap (commit `554c272`) then stopped the restart loop. Manual `systemctl --user reset-failed dirt-camera && systemctl --user start dirt-camera` brought the service back once the USB device reappeared.
- **Pairs with:** commit `1ef1020` (earlier V4L2 `ENODEV` hot-spin fix) — second known self-disconnect event, so it's being treated as a *potentially recurring* pattern rather than a one-off.
- **Updated:** [`wiki/hardware/ptz-camera.md`](hardware/ptz-camera.md) — added Known quirk #8 with the incident timeline, the burst-cap recovery procedure, and a "fix hardware, not software" directive (USB cable / RSHTECH hub / camera PSU / thermal); updated the USB hot-unplug row in "What it handles automatically" to flag the burst-cap edge case.
- **Explicit non-fix:** do not loosen the watchdog or raise the burst cap — they behaved correctly and are the backstop against runaway restart loops.

## [2026-04-22] decision | Replace tent-hub BME280/Arduino with SHT45/ESP32-C3
- **Decision:** [`wiki/decisions/2026-04-22-sht45-tent-node-esp32.md`](decisions/2026-04-22-sht45-tent-node-esp32.md). Both sensor (BME280 → Sensirion SHT45 + PTFE cap, Adafruit 5665, I²C `0x44`) and host board (Arduino Nano + USB serial → ESP32-C3 SuperMini + HTTP ingest at `tent-node.local`) replaced. Two-day-old [BME280 swap](decisions/2026-04-20-bme280-sensor-swap.md) superseded.
- **Why (sensor):** recurring BME280 stuck-state first logged 2026-04-20 17:36 MDT (`humidifier-control.md` Known Issues #1) makes the failsafe force OFF on a working sensor. PTFE cap is the specific reason for SHT45 over SHT31/35 — direct mist exposure inside the tent.
- **Why (transport):** last USB-serial tether in the sensor fleet — the four plant nodes all POST over WiFi. Removes `serial_reader.py`, `/dev/ttyArduino` udev rule, Arduino toolchain, and the ExecStartPre serial-symlink assertion. Unlocks OTA reflash on the tent sensor.
- **Wiring choice:** SDA=GPIO4, SCL=GPIO5 (not 8/9 — GPIO8 is the SuperMini onboard LED + boot-strap pin, GPIO9 is BOOT button). The plant-node "don't use GPIO4" warning is ADC-only — JTAG doesn't interfere with actively-driven I²C.
- **Firmware restructure:** `firmware/` is now three peer PlatformIO projects (`plant_node/`, `tent_node/`, `common/`) with a shared C++ lib tree at `common/{wifi_client, ota, ingest_client}/`. Each node project consumes it via `lib_extra_dirs = ../common`. Plant node refactored to the shared libs — all four envs still compile clean. Legacy `firmware/src/` + `firmware/lib/sensor_protocol/` + `firmware/platformio.ini` kept until cutover, deleted after.
- **Unchanged:** `sensorreading` schema, `SensorLocation.TENT`, humidifier VPD loop (0.1 kPa deadband, stage targets, lights-off feedforward, stale-sensor failsafe). Only `sensorreading.source` shifts from `arduino` to `esp32` for new tent rows.
- **Status:** Accepted — firmware ready and compile-verified. Hardware deployment pending solder-up.
- **Updated:** `wiki/decisions/2026-04-22-sht45-tent-node-esp32.md` (new), `wiki/decisions/2026-04-20-bme280-sensor-swap.md` (frontmatter + status-line superseded marker), `wiki/index.md` (new decision entry + `updated` bumped).
- **Deferred until deployed:** `wiki/hardware/tent-node.md` (new page, mirroring `esp32-plant-nodes.md`); `wiki/hardware/humidifier-control.md` Known Issues #1 → resolved-by-transition; `wiki/overview.md` System Status row; retirement of `SensorSource.ARDUINO` enum value.

## [2026-04-22] daily-update | Day 39 — Overnight Env Breakthrough; Reservoir Change Due; Plant D Improving
- **Daily entry created:** `wiki/daily/2026-04-22.md`
- **Overnight env both metrics in veg target for first time:** RH 52.06% ✅ (was 74.37%), temp 70.17°F ✅ (was 66.84°F); confirms `dirt-hwd` service was restarted and lights-off feedforward is now active
- **Afternoon slightly off:** temp 72.34°F ⚠️ (below 74°F floor), RH 69.19% ⚠️ (above 65% ceiling); VPD 0.84 kPa ✅ in range due to lower temp; ~10 hPa pressure drop suggests weather system
- **Plant D color improving** — lighter medium-green, no longer alarming vs. Apr 20 pale yellow-green
- **Plant A overnight sensor dropout** — null data 00–06; morning/now stable
- **Plant C moisture high** — 75%+ consistently; monitor root zone
- **Reservoir change due** — Day 7 post-activation (Apr 15); change at next opportunity
- **Plant pages updated:** A, B, C, D (timeline + current state)
- **Environment pages updated:** `temperature.md`, `humidity.md`
- **`overview.md`** and **`index.md`** refreshed

## [2026-04-22] milestone | AC Infinity fan controller — D+ bring-up validated
- **Hardware built:** ESP32-C3 SuperMini + 2× 2N7000 MOSFETs (Q1=D+, Q2=B5) + 2× 10 kΩ gate pull-downs, wired to Treedix USB-C female breakout. Common GND tied between ESP32 and fan; fan powered separately. GPIO 6 → Q1 gate (D+ driver), GPIO 7 → Q2 gate (B5 keep-alive). See updated [`hardware/ac-infinity-fan-control.md`](hardware/ac-infinity-fan-control.md) driver-circuit section.
- **Deviation from original 2026-04-18 plan:** moved from Arduino Nano to ESP32-C3 SuperMini. Motivation: fleet uniformity (same board as plant nodes + tent node; same toolchain, same OTA model), unlocks WiFi + HTTP ingest + OTA reflash, drops a whole family of Nano-era failure modes.
- **Firmware:** new [`firmware/fan_controller/`](../../firmware/fan_controller/) PIO project (ESP32-C3 Arduino platform). 5 kHz PWM via LEDC (ch 0 = D+, ch 1 = B5), 10-bit resolution. `set_fan_speed(pct)` helper handles the inversion math (MCU duty = 100 − D+ wire duty, since Q1 pulls the line LOW when the GPIO is HIGH) and the linear remap from human % to 22–100% wire duty. B5 statically driven at 1.4% MCU duty → 98.6% wire duty, mimicking the stock remote's keep-alive.
- **Bring-up smoke test (16:35 MDT):** started with a 20% / 40% alternation every 5 s; firmware printed the expected LEDC register values, fan stepped audibly between the two speeds.
- **Full-range sweep (16:37 MDT):** 0% → 10% → ... → 100% → 90% → ... → 0%, 10% steps, 5 s each. All checkpoints passed — silent at 0% (Q1 holds D+ LOW), audible kick-in around 10–20%, clean monotonic ramp up and back down, 100% matches the boot-blast behavior (same ~9V line state). No dead zones, no uneven steps.
- **Still unvalidated:** whether B5 is actually required (fan accepted commands with B5 driven; untested whether it also would with B5 floating). Thermal behavior of the MOSFETs over long runs not yet verified. Tach (D−) not wired.
- **Next firmware milestone:** fold `firmware/common/{wifi_client, ota, ingest_client}/` in so the host can command speed via the ingest path + OTA reflash becomes available. Downstream: VPD-coupled control (see [humidifier-control.md](hardware/humidifier-control.md) + [multi-actuator-environment-control.md](concepts/multi-actuator-environment-control.md)).
- **Obsolete artifacts (kept, not deleted):** `debug/fan-pwm/driver-schematic.{png,svg}` and `debug/fan-pwm/fan_drive_test/` are the Nano-era design; flagged as stale in the wiki's Status section.
- **Updated:** `wiki/hardware/ac-infinity-fan-control.md` (status, goal, driver-circuit section rewrite, parts BOM bumped to 2 FETs + 2 resistors, firmware section, permanent install rewrite, bring-up validation table, future-integration refresh); `wiki/index.md` (hardware entry). Note: `humidifier-control.md` line 44 in `index.md` still describes humidifier bang-bang control in isolation — when VPD-coupled fan control lands, that description should be updated to reflect the combined actuator loop.

## [2026-04-22] revision | Fan controller + SHT45 tent sensor merged onto one ESP32
- **Change:** the SHT45 that was originally slated for a dedicated `tent_node` ESP32 (per [2026-04-22 SHT45 decision](decisions/2026-04-22-sht45-tent-node-esp32.md) this morning) is now wired onto the fan-controller ESP32-C3 instead. One board, two roles: LEDC PWM on GPIO 6/7 drives the fan via Q1/Q2; I²C on GPIO 4/5 reads the Adafruit SHT45 (0x44).
- **Why the revision:** the 7 ft USB-C cable from the Cloudline fan lets the ESP32 sit on the tent floor — same physical domain a tent sensor would want. Combining saves one board, one power feed, one WiFi association, one OTA target. No pin contention (GPIO 10 still reserved for a future tach revisit).
- **Tach (D−) deferred:** attempted a 10 kΩ / 4.7 kΩ voltage divider from D− to GPIO 10; zero interrupts fired. Cause traced to a weaker-than-expected internal pull-up on D− (DC measurement on the wire under load: 0.71 V; our divider loaded it below the ESP32 HIGH threshold). Fix is either (a) a higher-impedance divider (100 kΩ / 47 kΩ) or (b) an external VBUS→D− pull-up to overcome the loading — user elected to defer pending a fresh signal-analysis pass. Flagged as "tach path unimplemented" in the hardware Status section and a pending row in the bring-up validation table.
- **Firmware:** `firmware/fan_controller/` bumped to fw `0.1.0`. Removed all tach ISR/snapshot code. Added `#include <Wire.h>` + `<Adafruit_SHT4x.h>`, I²C init on GPIO 4/5 in setup, `bring_up_sht()` helper, inline VPD calculation (Tetens formula), and a per-heartbeat combined log line: `fan=30% (D+ wire=45.4%)  |  tent: 22.70°C (72.9°F)  RH 38.9%  VPD 1.69 kPa`. If the SHT45 drops mid-flight the fan keeps running; sensor init retries every heartbeat. `platformio.ini` gained `adafruit/Adafruit SHT4x Library` + `Adafruit Unified Sensor` in `lib_deps`.
- **Bring-up:** first flash 2026-04-22 evening, SHT45 `begin()` succeeded, first heartbeat read `22.70°C / 72.9°F / 38.9% RH / VPD 1.69 kPa` (room-air values — board not yet physically inside the tent). The SHT45 library's `readSerial()` returned 0x00000000 — known Adafruit library quirk, doesn't affect measurement.
- **Obsoleted on disk (not yet deleted):** `firmware/tent_node/` PIO project. Slated for removal after combined firmware soaks for a few days; user-approved follow-up.
- **Updated:** `wiki/hardware/ac-infinity-fan-control.md` (title, status, goal, parts BOM adds SHT45 + PTFE cap, new "Tent environmental sensor (SHT45)" section with I²C wiring + rationale, firmware section rewrite for dual-role, bring-up table gains D− tach failure + SHT45 success rows); `wiki/decisions/2026-04-22-sht45-tent-node-esp32.md` (revision block added at top, status line acknowledges combined-board deployment); `wiki/index.md` (hardware entry renamed "Fan Control + Tent Environmental Sensor"; decision entry marked revised-same-day). Frontmatter `updated: 2026-04-22` on both touched wiki pages.

## [2026-04-22] milestone | Fan controller network-attached + HTTP control surface + SHT45 heater cycle
- **Firmware:** `firmware/fan_controller/` bumped to fw `0.2.0`. Now consumes `firmware/common/{wifi_client, ota, ingest_client}/` (same pattern as plant/tent nodes) so the fan-controller joins WiFi, registers mDNS hostname `fan-controller.local`, and OTA-reflashes via the new `env:fan-ota` env in `platformio.ini`. Adds `#include <WebServer.h>` to expose a LAN HTTP control surface on port 80: `POST /fan {"duty_pct":0..100}` sets the fan, `GET /fan` returns `{"set_duty_pct":N,"reported_duty_pct":N}`. `reported_duty_pct` is explicitly MOCKED (echoes the last-set value) until the D− tach path is wired — the JSON shape is stable across that transition so host-side callers don't need to change when tach lands. Boot sequence unchanged: 2 s max-blast failsafe, then settles to `BOOT_SPEED_PCT` (30 %).
- **SHT45 heater cycle:** new non-blocking state machine replaces the bring-up firmware's naive 60 s heartbeat loop. Each 60 s cycle: fire 200 mW / 1 s heater pulse (`SHT4X_HIGH_HEATER_1S`, measurement discarded — sensor is ~50 °C hot), wait 59 s for T to equilibrate at no-heater, read T/RH at high precision, POST `{temperature_c, humidity_pct, fan_duty_pct}` to `/api/ingest/sensors` at `location=tent`, immediately chain back into the next pulse. Heater duty ≈ 1.67 % (datasheet cap 10 %). Matches Sensirion's [Creep Mitigation SHT4x app note](https://sensirion.com/media/documents/A88858C9/629626D4/Application_Note_Creep_Mitigation_SHT4x.pdf) §3 continuous-pulsing regime — addresses the up-to-+3 %RH creep offset that would otherwise develop after 60 h at >90 %RH and silently defeat the humidifier VPD loop. Cadence is intentionally 60 s (matches plant nodes + keeps humidifier failsafe — `humidifier_failsafe_stale_seconds = 300` — with 5× headroom); a 5-minute cadence was considered and rejected because it lands right on the failsafe edge.
- **SensorLocation decision:** `fan_duty_pct` rides on existing `tent` rows (metrics dict adds a key) rather than introducing a new `SensorLocation.FAN_CONTROLLER` enum. No Atlas migration, no schema change, no new ingest path — the whole thing is pure-additive in the `metrics` JSON column.
- **Shared client:** new `apps/shared/src/dirt_shared/services/fan_node.py` — `FanNodeClient` with `async set_duty(0..100)` and `async get_state() → {set_duty_pct, reported_duty_pct}`. Takes an `httpx.AsyncClient` by injection; `FanNodeError` for non-2xx / transport / non-JSON. Default `base_url="http://fan-controller.local"`. Module docstring flags that nothing calls it automatically yet — it's pure plumbing until a control loop lands. Tests: 8 covering happy paths, validation (duty_pct out of range raises `ValueError`), HTTP error, transport error, non-JSON body, trailing-slash base URL. `uv run pytest apps/shared/tests/test_fan_node.py` green (8/8); `uv run ruff check` clean.
- **Deferred on purpose:** host-side closed-loop VPD control. `FanNodeClient` exists and is ready to be called; no service calls it. Target shape documented in `wiki/hardware/ac-infinity-fan-control.md` "Future integration" section — a `apps/hwd/src/dirt_hwd/services/fan_controller.py` analogous to `HumidifierLoopService`. TODO pointers planted in the firmware main.cpp header, the shared client module docstring, and the wiki page.
- **Build verification:** `cd firmware/fan_controller && pio run -e fan` compiles clean. Flash 76.0 % (995,732 / 1,310,720 bytes), RAM 13.7 % — comfortable headroom. Not yet flashed; board is already running fw `0.1.0` in the tent and the user will do the over-USB re-flash + relocation inside the tent as a follow-up.
- **Updated:** `firmware/fan_controller/{platformio.ini, src/main.cpp}` (lib_extra_dirs, new `env:fan-ota`, FIRMWARE_VERSION=0.2.0, full main.cpp rewrite); `firmware/fan_controller/include/secrets.h.example` (new template, gitignored `secrets.h` mirrors the tent_node fleet credentials); `.gitignore` (+1 secrets line); `apps/shared/src/dirt_shared/services/fan_node.py` (new); `apps/shared/tests/test_fan_node.py` (new); `wiki/hardware/ac-infinity-fan-control.md` (Status rewrite, Firmware section condensed, new "SHT45 heater schedule" subsection, "Future integration" section rewritten around control-loop + tach todos); `docs/progress/2026-04-22-fan-tent-node.md` (§1 open-question closed, §3 + §4 status updated). `uv run scripts/lint.py` 7/7.

## [2026-04-23] milestone | Arduino Nano + BME280 tent hub retired — BME280 found to be systematically wrong
- **Terminal incident (2026-04-23 00:15 MDT).** After moving the combined fan-controller ESP32 inside the tent alongside the Arduino, ESP32 and Arduino reported wildly different readings (SHT45: 20.9 °C / 53 %RH ; BME280: 22.4 °C / 73 %RH). User placed a calibrated handheld hygrometer on the tent floor between both sensors; it read **69 °F / 49 %RH** — effectively matching the SHT45 (+0.6 °F / +4 %RH — within sensor-noise + PTFE-cap diffusion delay) and convicting the BME280 of a **+3.5 °F / +23 %RH** bias. This is far worse than the previously-documented "stuck-state" pattern and likely explains why some earlier incidents attributed to transient lockups never quite added up.
- **Consequence — VPD loop was running against wrong inputs.** Real conditions at incident time: 20.6 °C / 49 %RH → VPD ≈ 1.24 kPa (above the veg 0.8–1.2 upper band, humidifier-ON territory). BME280-reported conditions: 22.5 °C / 73 %RH → VPD ≈ 0.74 kPa (below upper band, humidifier-OFF territory). The humidifier has been under-running for some unquantified time — tent has been drier than the wiki, daily reports, and control loop believed. Future syntheses see only the SHT45; historical `source=arduino` tent readings prior to 2026-04-23 00:22 MDT should be read against this caveat.
- **Cutover executed in-band** — the user's soak gate (≥24 h parallel operation) was satisfied in spirit within ~10 min since the hygrometer reading was unambiguous.
- **Code removed:** `apps/hwd/src/dirt_hwd/services/serial_reader.py` (171 lines), `apps/hwd/tests/test_serial_reader.py`, the `SerialReaderService` wiring in `apps/hwd/src/dirt_hwd/app.py`, `SerialConfig` dataclass + `Settings.serial()` + `serial_port/baud/sensor_poll_interval` fields in `apps/shared/src/dirt_shared/config.py`, `sensor_boot` retention entry in `apps/shared/src/dirt_shared/observability.py`, legacy Arduino Nano firmware tree (`firmware/src/`, `firmware/lib/sensor_protocol/`, `firmware/platformio.ini`), obsolete `firmware/tent_node/` PIO project (superseded by the combined fan_controller build), pyserial from `apps/hwd/pyproject.toml`. Renamed `_tent_arduino_status` → `_tent_sensor_status` in `SystemStatusService`, with device-list label "Arduino Nano + BME280" → "ESP32-C3 · fan+tent". `SensorSource.ARDUINO` enum value retained — historical rows keep that label.
- **New code:** `_augment_temp_rh_metrics()` helper at the ingest endpoint (`apps/hwd/src/dirt_hwd/api/ingest.py`). Derives `temperature_f`, `vpd_kpa`, `dew_point_f` from `temperature_c + humidity_pct` using the same Tetens/Magnus formulas the retired `serial_reader._derive_metrics` used — required because the fan-controller firmware posts only SI units, but the humidifier loop, grow_state stage targets, web envelope, and voice tool all still read the derived metrics. Passthrough for posts lacking either input (plant-node moisture, humidifier on/off writes). Two new tests in `apps/hwd/tests/test_ingest_api.py`.
- **Humidifier-loop validation after restart:** VPD reading now landing on ESP32-derived values (1.12 kPa at restart time). Loop is still in `allowed=false` because we're mid-dark-cycle (23:00–05:00 → force OFF); expected to kick on at 05:00 lights-on if VPD is still elevated, at which point it'll pull the tent toward the veg 1.0 kPa setpoint — the "catch-up" behaviour predicted from the incident data.
- **Physical Arduino:** still plugged in at cutover time but harmless — `serial_reader` is gone so the serial buffer is unread (ring-buffer overflow silently, no-op). User can unplug at leisure. `/etc/udev/rules.d/99-dirt-webcam.rules` still contains the `ttyArduino` symlink rule + CH341 autosuspend disable — cleanup deferred (requires sudo); the rule is harmless with the device unplugged and also harmless with the device plugged in + nothing listening.
- **Updated:** `apps/hwd/{app.py, src/dirt_hwd/main.py, pyproject.toml, src/dirt_hwd/api/ingest.py, tests/test_ingest_api.py}`; `apps/shared/src/dirt_shared/{config.py, observability.py, services/system_status.py, services/readings.py}`; `apps/web/tests/test_system_devices_endpoint.py`; `systemd/dirt-hwd.service` (description + hardening comment); `.gitignore` (dropped tent_node entries); `firmware/` (legacy Nano + obsolete tent_node trees deleted); `wiki/hardware/humidifier-control.md` (Known Issues "BME280 stuck-state" → "BME280 drift (resolved-by-transition)" with historical-data caveat + terminal-incident row); `wiki/overview.md` (System Status row renamed); `wiki/decisions/2026-04-22-sht45-tent-node-esp32.md` (Status → Deployed). Tests: 342 passed / 1 skipped across apps. `uv run ruff check` clean. `uv run scripts/lint.py` 7/7.

## [2026-04-23] operational finding | Humidifier output rate vs fan exhaust rate is the bottleneck, not the deadband
- **Sequence:** 05:00 MDT lights-on transition exposed the post-SHT45 loop operating right at the edge of the veg 1.2 kPa VPD upper band. Observed symptoms:
  - 05:00-06:27: humidifier flapped on/off roughly every 60 s (20+ state changes over 20 min, audible Kasa plug clicks in the grow space). Cause: the Raydrop running for 1 min drops VPD ~0.45 kPa (from ~1.35 to ~0.87), overshooting the 0.1 kPa deadband ~4×. Classic bang-bang instability — actuator moves the PV much faster than the control band tolerates.
  - 06:27: **bumped `vpd_deadband_kpa` from 0.1 to 0.3** (turn-off drops from 1.1 to 0.9, so one humidifier pulse can run to a proper finish). Restarted dirt-hwd; cycling stopped immediately.
  - 06:40ish: **set fan to 40 %** via `POST /fan` on the fan-controller node (previously 30 %).
  - 07:58-08:08 (and onward): tent RH started tanking (dropped to 43.5 %, veg target 45-55 %). Humidifier held *continuously ON* for 1h 40 min with zero state changes, yet VPD kept rising, now 1.50 kPa (well above 1.2 setpoint).
- **Root cause of the RH drop:** the Raydrop's physical mist-output dial was turned down low — its actual mist emission rate was slower than the fan-at-40 % exhaust rate. Room air (~40 % RH) was replacing tent air faster than the humidifier could dose moisture. Software was doing exactly the right thing (plug ON continuously); the physical actuator just couldn't keep up. User turned the Raydrop dial up; RH recovery expected in the next few minutes.
- **Why this matters:** with the honest SHT45 readings, the tent is operating *much* closer to the edge of the target band than the BME280 had been showing. The system is no longer forgiving of mismatched actuator sizing. Pre-cutover the BME280's +23 %RH bias meant the loop almost never turned the humidifier on — so this coupling was invisible.
- **Open idea noted in [humidifier-control.md](hardware/humidifier-control.md) "Future work":** replace the Raydrop's analog potentiometer with microcontroller-controlled output rate so the host-side loop can modulate *mist intensity* alongside the on/off plug state. Turns a single-DOF bang-bang actuator into a continuous one, which would make the whole loop a lot more stable without requiring the user to remember where the physical dial was set.
- **No code/config change in this entry** — the deadband bump and fan bump already landed in `08e5655` and a runtime `POST /fan`. This entry documents the operational pattern that emerged once those landed. `wiki/hardware/humidifier-control.md` gained a "Coupling between mist output rate and fan exhaust rate" section + a "Future work" idea-bucket.

## [2026-04-23] feat | Stuck-humidifier watchdog + red-LED failure mode documented
- **Incident that prompted it:** 10:00 MDT — humidifier plug pinned ON for 1h 30m+, VPD rising despite full-duty output, RH tanking. Physical check: Raydrop LED red (normally green), no visible mist. Unplug from Kasa → wall outlet briefly → back through Kasa cleared it, unit immediately began misting.
- **Model:** Raydrop **KC-RD03A** ([manual](https://manuals.plus/raydrop/kc-rd03a-cool-mist-humidifiers-manual)) — earlier log entry cited KC-RD05 in error; corrected here.
- **Root cause (research-grounded):** low-water float sensor latches "empty" even with water in the tank; controller red-lights and disables ultrasonic until a power cycle drops the latch. Trigger is mineral scale/biofilm on the float stem and the atomizer disc (same substrate fouls both). Raydrop has no thermal cutout and no other documented red-LED state, so this is the dominant failure mode. **Confirmed in field 2026-04-23:** cleaning the atomizer disc cleared the latch for the second time today (first clear was the power-cycle-reseat earlier; second clear was via physical scale removal). Strong evidence that weekly vinegar descale prevents recurrence.

## [2026-04-23] decision + epic | Continuous humidifier intensity control (Raydrop MCU-driven mist)
- **Decision filed:** [`wiki/decisions/2026-04-23-raydrop-mcu-mist-control.md`](decisions/2026-04-23-raydrop-mcu-mist-control.md). Replace the Raydrop KC-RD03A's analog intensity pot with MCU-driven control (digipot or DAC on the fan-controller ESP32) + a host-side PI loop on VPD error. Retires today's bang-bang Kasa-plug control. Kasa plug stays as hard-off authority.
- **Motivation:** three failure modes observed 2026-04-23 all traceable to the humidifier being a binary actuator with a hidden analog dial. (1) Actuator-overshoot oscillation forced widening the deadband 0.1 → 0.3 kPa this morning. (2) Fan-coupling saturation: with fan@40 % + dial turned down, plug pinned ON for 1h 40m while VPD *climbed* because mist rate < exhaust rate; software had no visibility into the dial to compensate. (3) Red-LED low-water-float latch on a full tank — separate failure mode, but shares the "loop commands on / actual output is zero" pattern and needed a watchdog to detect.
- **Architecture reconciliation:** updated `wiki/concepts/multi-actuator-environment-control.md` with a revision block noting the per-class plan shape shifts from `hum_on: bool` to `hum_intensity: 0..100`. Class-dispatch architecture, cross-actuator mutex, feedforward compounds, and failure-mode design unchanged. PI control is *within-actuator intensity given that it's commanded on* — not a replacement for the class-dispatch system. The doc's "no PID at the system level" rule still holds.
- **Scope, phases, acceptance criteria:** `docs/epics/continuous-humidifier/README.md`. Five phases (investigation → hardware → firmware → PI loop → physical cleanup). **Phase 1 is the stop gate** — open the Raydrop, probe the pot, identify the driver IC, decide digipot vs DAC vs direct-PWM. No commitment to Phases 2–4 until Phase 1 reports back.
- **Updated:** `wiki/decisions/2026-04-23-raydrop-mcu-mist-control.md` (new), `wiki/concepts/multi-actuator-environment-control.md` (revision block + updated `related:`), `wiki/hardware/humidifier-control.md` ("Future work" entry promoted from idea-bucket to scoped/tracked), `wiki/index.md` (Decisions entry added), `docs/epics/continuous-humidifier/README.md` (new). `uv run scripts/lint.py` 7/7.

## [2026-04-23] session pause | Continuous humidifier — parts ordered, Phase 1 waiting on delivery
- **Procurement state:** DigiKey order placed (1× each MCP4131 at 10 kΩ / 50 kΩ / 100 kΩ; DIP-8 through-hole; ~$2.24 parts + shipping). Adafruit order placed (MCP4725 DAC breakout #935, BSS138 level shifter #757, headers #392, jumpers #1957/#1954). Amazon Raydrop spare ordered (ASIN [B0CDL8XCJ5](https://www.amazon.com/dp/B0CDL8XCJ5), $19.99). Amazon BOJACK ceramic cap kit (ASIN [B085RDTCCV](https://www.amazon.com/dp/B085RDTCCV), $9.99) flagged for user to order. Heat-shrink + E12 resistor kit already in user stash. All four Phase-1 → Phase-2 decision-matrix rows are covered by what's already on order — no additional purchasing required based on the probe verdict.
- **Resume point for a fresh agent:** start at [`docs/epics/continuous-humidifier/README.md`](../docs/epics/continuous-humidifier/README.md) "Current state" section. When parts arrive, execute [`phase1-probe-checklist.md`](../docs/epics/continuous-humidifier/phase1-probe-checklist.md) end-to-end; paste the verdict back to the [decision doc](decisions/2026-04-23-raydrop-mcu-mist-control.md) as a "Phase 1 findings" revision block and flip the epic from `planning` to `in-progress`.
- **Refinements during this session:** (a) BOM reduced from 2× to 1× per MCP4131 variant — the three are different resistances, not spares of the same part, so buying 2× each saved $2 on an already-$2 order. (b) Generic Amazon "cap kit" replaced with a specific verified Amazon listing (BOJACK B085RDTCCV) after research confirmed all three needed values (0.1/1/10 µF) are present and MLCC 10 µF is strictly better than electrolytic for the RC-filter use case. (c) Raydrop model-number caveat added: wiki historical "Raydrop 4L" doesn't match the verified KC-RD03A (1.0 L per the manual); user told to verify bottom-sticker before using the ordered spare for Phase 1 probing since the driver circuit may differ across Raydrop sizes.
- **No code changes.** Docs-only session. `docs/epics/continuous-humidifier/bom.md` (new), `docs/epics/continuous-humidifier/README.md` (current-state block added), `wiki/log.md` (this entry). `uv run scripts/lint.py` 7/7.
- **New watchdog:** `HumidifierLoopService` now runs a stuck-actuator watchdog alongside the existing VPD bang-bang. Pure-function state machine `update_stuck_state` (in `apps/hwd/src/dirt_hwd/services/humidifier.py`) tracks the current continuous-ON streak and the VPD at streak start; when elapsed-on ≥ `humidifier_stuck_alert_after_s` (default 1200 s = 20 min) AND VPD dropped less than `humidifier_stuck_min_vpd_drop_kpa` (default 0.15 kPa), it fires a `suspected_stuck` event on the `humidifier` observability stream and a Telegram alert with the start/now VPD numbers and a "check Raydrop red LED / water level / visible mist" prompt. Fires exactly once per streak (suppressed until the next OFF transition).
- **12 unit tests** in `apps/hwd/tests/test_humidifier_stuck.py` covering: idle-off, off→on transition captures start VPD, on→off clears streak, healthy VPD drop silences alert, pre-threshold silence, stuck-after-threshold fires, VPD-rising (today's signature) fires, single-fire-per-streak dedup, cross-transition refire, stale-VPD skip, missing-start-VPD skip, exact-threshold boundary. All pure — driven entirely off the state machine, no Kasa/Telegram mocking needed to assert the logic.
- **Shape changes to internal APIs:**
  - `Settings` gains `humidifier_stuck_alert_after_s: int = 1200` and `humidifier_stuck_min_vpd_drop_kpa: float = 0.15`.
  - `HumidifierConfig` gains `stuck_alert_after_s`, `stuck_min_vpd_drop_kpa`, `telegram_bot_token`, `telegram_chat_id` (the last two mirror existing `Settings.telegram_bot_token` / `telegram_allowed_user_id`, reused via the service config factory).
  - `HumidifierLoopService.__init__` gains `http_client_factory` (defaults to `httpx.AsyncClient(timeout=10.0)`) so tests can mock the Telegram transport the same way `DeviceWatchdogService` does. If Telegram creds are unset, the watchdog still fires `suspected_stuck` log events but skips the Telegram send (info log emitted at startup).
- **Wiki updates:** new "Red LED on the Raydrop = low-water sensor latch" section in `hardware/humidifier-control.md` (first observed timestamps, root cause w/ citations, detection, recovery, prevention). Trimmed the historical "BME280 drift" incident-log table since the narrative paragraph above it already covers both incidents. `CLAUDE.md` observability table mentions the new `suspected_stuck` event shape.
- **Tests:** `uv run pytest apps/hwd apps/shared apps/web apps/tests/invariants` — 356 passed / 1 skipped. `uv run ruff check` clean. `uv run scripts/lint.py` 7/7.

## [2026-04-24] daily-update | Day 41 — Temperature Milestone; VPD Clean All Windows; C/D Moisture Very High
- **Daily entry created:** `wiki/daily/2026-04-24.md`
- **Temperature milestone:** all three windows in veg target simultaneously for first time — overnight 69.35°F ✅, morning 74.84°F ✅, now 76.01°F ✅; "monitor afternoon temp" action item resolved
- **VPD clean all three windows:** 1.18 / 0.99 / 0.90 kPa — second consecutive day of full VPD coverage ✅
- **Overnight RH second consecutive night in target:** 51.81% (was 52.06% Apr 22); lights-off feedforward holding
- **Afternoon RH still elevated:** 66–71% morning/afternoon; VPD in range only because temp now proper — watch if temp dips
- **Plant A overnight sensor back online:** overnight data present (n=717); dropout from Apr 22 resolved ✅
- **Plants C and D moisture very high:** C at 82%+ (was 75% Apr 22), D jumped from 60% to 83% in two days — autopot feeding aggressively; no visible stress symptoms
- **LST critically overdue:** Day 13/12 post-topping; snap risk at highest this grow; Plant A shows training ties in photo
- **Reservoir change still pending:** Day 9 post-activation (7–10 day window closes tomorrow)
- **Plant pages updated:** A, B, C, D (timeline entries + Current State rewritten)
- **Environment pages updated:** `temperature.md` (trend row + milestone notable event), `humidity.md` (trend row + notable event + Deployed Control System updated to SHT45/ESP32-C3)
- **`overview.md`** and **`index.md`** refreshed
- **Known gap:** No daily entry for 2026-04-23 — no photos or sensor snapshot captured that day. Lint timeline-continuity check will flag this; pre-existing pattern.

## [2026-04-24] query-filed | LST actually started 2026-04-20 on all 4 plants (user correction)
- **Source:** user statement during the Apr 24 Claude Code session: "I started at LST about four days ago on all plants."
- **Problem the correction fixes:** the auto-generated daily reports from Apr 20 through Apr 24 all carried a "🔴 LST critically overdue" flag because the 14:00 MDT photo sessions didn't capture the evening training. Plant A's ties were finally caught in the Apr 24 photo, but B/C/D angles missed them. Every day, the same action item ("Complete LST today") was re-raised in error.
- **LST start date:** 2026-04-20 (evening, after 14:00 photo session). Day 4 of stress recovery as of today.
- **Files updated:**
  - `wiki/plants/plant-a.md`, `plant-b.md`, `plant-c.md`, `plant-d.md` — Current State rewritten; Apr 20 timeline entry split into the observed state + a new "LST started" entry; `plant-c.md` frontmatter `related:` now cites `concepts/lst.md`.
  - `wiki/overview.md` — Current Stage reframed; Plant Status table rows now note LST Day 4; Action Items dropped "Complete LST" and gained "Monitor LST recovery" + a concrete light-ramp window (Apr 25–27); Upcoming Milestones row struck through and resolved.
  - `wiki/daily/2026-04-24.md` — Summary gained a correction block; "🔴 LST critically overdue" Issue rewritten to "✅ LST started Apr 20 (Day 4)"; Recommendations renumbered (dropped "Complete LST today"; kept light-ramp + added LST recovery monitoring).
  - `wiki/daily/2026-04-20.md` — correction block prepended (frontmatter `updated` bumped to 2026-04-24). Does NOT rewrite the day's observations, only clarifies that the "no LST visible" photos are from 14:00 MDT and LST was performed later that evening.
  - `wiki/index.md` — Plants section summaries updated with "LST Day 4 (started Apr 20)".
- **Not updated (intentional):** Apr 21–23 dailies left as-is. Their "LST overdue" framing was contextually correct for the data the orchestrator had at report time (photos only). Rewriting them would be revisionism — the Apr 20 correction note + today's resolution give a reader enough breadcrumbs to reconstruct.
- **Next lint:** `uv run scripts/lint.py` — expect 7/7 pass. If "overview staleness" flags due to `updated: 2026-04-24` already being current, that's expected.

## [2026-04-24] session pause | Continuous humidifier — Phase 1 probe mid-session
- **Where we stopped:** resistance sweep done on the unplugged spare Raydrop; pot identified; photos captured. Powered Step 1 DC voltage sweep is the next action.
- **Spare Raydrop is open on the bench; primary stays on the Kasa plug driving the live VPD loop** — no service interruption. `dirt-hwd` was not stopped and does not need to be for the rest of Phase 1.
- **Pot:** silkscreen `B5K` = 5 kΩ linear-taper + integrated SPST switch (clicks off at min rotation). 4-wire JST = 3 pot pins + 1 switch tab; switch return commons via the pot chassis to one of the pot outers on the PCB.
- **Resistance sweep (DMM, 200 kΩ range, unplugged):** wiper + non-chassis-outer reads 0.002 kΩ at max-mist → 2.55 kΩ at min-mist-just-before-click. Smooth monotonic — clean rheostat behavior. The 2.55 kΩ vs 5 kΩ label gap is most plausibly the mechanical rotation covering ~half the electrical track (switch-cam dead zone). Firmware-side "intensity %" will map to the observed 0→~2.55 kΩ range.
- **Photos:** `debug/raydrop-re/photos/pot-front.jpg` (silkscreen visible) + `pot-back.jpg` (pins + JST wires).
- **BOM consequence (not yet actioned):** none of the three MCP4131 variants on order (10 kΩ / 50 kΩ / 100 kΩ) is a direct match. If Step 1 confirms DC-analog case, `MCP4131-502E/P` (5 kΩ) needs ordering. Do NOT order until Step 1 verdict lands — a PWM case skips the digipot entirely.
- **Resume point for a fresh agent:** start at [`docs/epics/continuous-humidifier/README.md`](../docs/epics/continuous-humidifier/README.md) "Current state" section. The immediate next action is walking the user through Step 1 of [`phase1-probe-checklist.md`](../docs/epics/continuous-humidifier/phase1-probe-checklist.md) (DC voltage measurement on pot wires with unit powered, ground clip on a verified board GND). The checklist's observations log has a partially-filled "Session 1 — 2026-04-24" block at the top; fill in the Step 1 section when probing resumes.
- **No code or wiki-page changes this session** — only docs/epic tracking updates. `wiki/log.md`, `docs/epics/continuous-humidifier/README.md` (Current state rewritten), `docs/epics/continuous-humidifier/phase1-probe-checklist.md` (observations log seeded).

## [2026-04-26] query-filed | Breeding program section created
- **Trigger:** working session synthesizing breeding-program research (cannabis pollen viability, pheno-hunting practice, SBxBS01 hybrid genetics, F1/F2 nomenclature) into a working manual ahead of the Track A male grow starting this week.
- **New top-level section:** `wiki/breeding/` — operating manual for the small home breeding program. Frontmatter `type: breeding`. Concept-level OBG background remains in `concepts/oregon-breeding-group.md`; the new pages are protocol.
- **Pages created:**
  - `wiki/breeding/README.md` — section index, two-track structure (pollen production + pheno hunt → F2 cross), goals, page reading order
  - `wiki/breeding/nomenclature.md` — F1/F2/BX/S1/IBL definitions tied to our SBxBS01 program; clarifies that our F1 = breeder's F1 and our cross produces F2
  - `wiki/breeding/timeline.md` — dated calendar from program launch through F2 seed harvest (active document; will be updated as phases land)
  - `wiki/breeding/isolation.md` — separate-room contamination protocol; phase-based hygiene rules; tools/clothes discipline
  - `wiki/breeding/cloning.md` — procedure, equipment list, space requirements, mother management, take-rate expectations
  - `wiki/breeding/pheno-hunt-protocol.md` — six selection axes (color/terps/structure primary; finish/vigor/resilience secondary), weighted scoring rubric, weekly schedule
  - `wiki/breeding/male-evaluation.md` — pre-pollen-collection male scoring; stem color + hermie tendency are gating criteria
  - `wiki/breeding/pollen-handling.md` — collection, drying, 4:1 baked-flour cut, aliquoting, freezer storage, single-thaw discipline
  - `wiki/breeding/cross-procedure.md` — paintbrush pollination, branch labeling, seed maturation stages, harvest timing
- **Decision page:** `wiki/decisions/2026-04-26-breeding-program-launch.md` — captures rationale, alternatives considered, trait priorities, scope exclusions, hardware acquisitions, critical-path commitments. Open questions explicitly listed (second-pack BS line choice; keeper female source; cross direction count).
- **CLAUDE.md updates:** added `breeding/` to the layout list, the question-routing table, and the wiki/ subfolder taxonomy.
- **Index update:** `wiki/index.md` gained a "Breeding" section between "Concepts" and "Decisions" with all 9 new page links + the launch decision link.
- **Open follow-ups:** second-pack BS line decision (BS01/BS13/BS35/BS45) before mid-July; first cloning batch this week to preserve A/B/C/D as breeding candidates; isolation-room outfit (light, fan, environment); portable freezer acquisition.

## [2026-04-26] decision-pivot | Humidifier — abandon Raydrop MCU mod, pivot to Wi-Fi-native Govee H7140
- **Trigger:** replacement spare Raydrop arrived; Phase 1 probe session ran deep but stalled. Pot characterized as a 5 kΩ rheostat (only 2 of 3 terminals wired); clean DC voltage sweep on the wiper couldn't be obtained — multiple ground-reference candidates failed and the low-water sensor was suppressing the entire oscillator stage so the wiper had no signal to read in the first place. Defeating the water sensor and redoing the bench setup was on the path back to "finished probe," but the user surfaced the better question: why are we doing $40 of bespoke MCU-mod work when a $45 Wi-Fi-native humidifier with a documented HTTP API exists?
- **Decision:** order a GoveeLife Smart Humidifier Lite (H7140) and integrate via Govee Public API v2. Arrives 2026-04-27. Integration shape is **Manual mode + the existing host-side VPD PI controller** — the H7140 becomes the actuator at the dispatch boundary, with `u_pct ∈ [0, 100]` quantized to one of 8 discrete Manual-mode levels (with hysteresis dead-zones at boundaries to prevent limit-cycle chatter). VPD-targeting (per 2026-04-18 decision) stays. The device's built-in Auto mode (RH setpoint + internal closed loop) is RH-only — using it would walk back the VPD decision, so we don't.
- **What gets retired:** Raydrop KC-RD03A + Kasa EP10 plug stack; the planned digipot mod and firmware work; the home-grown stuck-actuator watchdog for empty-tank (replaced by the device's built-in `lackWaterEvent`).
- **What stays live (becomes production):** the PI controller + plant-in-loop tests + shadow logging + analyzer harness all carry over — the H7140 is just a different actuator at the dispatch boundary. FOPDT plant model needs refitting against H7140 mist rate (graduated step test, originally Phase 4 acceptance — same methodology, new actuator). Surrounding loop logic (stage-band setpoint, lights-off prep, failsafe, observability) is unchanged.
- **Concerns flagged in the decision:** cloud-only API (Internet outage = no humidifier control), 10K calls/account/day quota (comfortable for the 30 s loop with "POST only when level changes"), quantization needs hysteresis dead-zone at level boundaries to avoid limit cycling, FOPDT needs refitting (planned step), net-new SaaS dependency.
- **Files updated:**
  - **New:** `wiki/decisions/2026-04-26-govee-h7140-pivot.md` (decision doc with full alternatives, rollout, consequences).
  - **New:** `docs/references/govee-api/INDEX.md` + `control.md` + `h7140-capabilities.md` + `rate-limits.md` + `gotchas.md` — full reference pack pinned to Public API v2 (`openapi.api.govee.com/router/api/v1/`); H7140-specific capability map includes the Manual/Custom/Auto work modes, 40-80% RH range, `lackWaterEvent`, plus the Option A / Option B integration choice writeup.
  - **Updated:** `docs/epics/continuous-humidifier/README.md` — marked ABANDONED at top with pivot pointers; original "Current state" preserved below as historical archaeology.
  - **Updated:** `wiki/decisions/2026-04-23-raydrop-mcu-mist-control.md` — status flipped to SUPERSEDED with pointer to the pivot decision; control-theory analysis (PI vs PID, FOPDT, IMC) explicitly noted as still applicable for the Option B fallback.
  - **Updated:** `wiki/hardware/humidifier-control.md` — frontmatter updated; banner at top noting the impending swap and pointing to the pivot decision + Govee reference pack. Body content preserved (still describes live state until cutover).
  - **Updated:** `wiki/index.md` — Raydrop decision marked superseded; new pivot decision added to the Decisions list.
  - **Updated:** `CLAUDE.md` — added Govee Public API v2 to the Framework/API References list with the standard "consult when / training-data drift" framing.
- **Resume point for cutover (when hardware arrives 2026-04-27):** see "Rollout" section of `wiki/decisions/2026-04-26-govee-humidifier-pivot.md` for the 9-step plan (provision → API key in `.env` → discovery sanity check → bench script → production client at `apps/shared/src/dirt_shared/services/govee.py` → graduated step test → loop swap in `HumidifierLoopService` → 48-72h soak → physical decommission of Raydrop+Kasa).

## [2026-04-26] decision-revise | Humidifier — switched deployment SKU from Govee H7140 to H7142 (same line, more granularity + bigger tank)
- **Trigger:** after a fuller side-by-side comparison across the Govee H71xx line later the same day, the H7142 (6 L cool-mist) emerged as the better choice over the originally-ordered H7140 (3 L Lite). Two axes: **9 Manual-mode API levels** vs the H7140/H7143's 8 (one extra level — small win), and **6 L tank** vs the H7140's 3 L (would require daily refills in flower-stage demand vs ~3-day cadence on the H7142).
- **Hardware status:** H7140 still en route 2026-04-27 (the original-order backup; will be retained as spare or returned). H7142 ordered 2026-04-26, arrives 2026-04-28.
- **What changed:** SKU string only. Same API contract across the H71xx line — `workMode` STRUCT capability with Manual/Custom/Auto sub-modes, `humidity` 40-80% range, `lackWaterEvent`, `powerSwitch`, plus nightlight/UVC/aroma extras we ignore. Quantization at the dispatch boundary becomes `u_pct → level 1..9` instead of `1..8`. Graduated step test sample points become 2/5/8 instead of 1/4/8. Everything else (PI controller, plant-in-loop tests, shadow logging, analyzer, surrounding loop logic) is unaffected.
- **Considered also:** local-control alternatives. SwitchBot Smart Humidifier (BLE local, ~$50, 3.5 L) was the first-choice "escape cloud" option but is no longer available on Amazon. Tuya/SmartLife humidifiers via LocalTuya (~$30-80) require ~30 min one-time local-key extraction + typically only 3 mist levels (worse than Govee). SwitchBot Evaporative ($240, Matter) is the price ceiling and uses evaporative not ultrasonic physics. The Dreo HM713S was specifically considered (6 L, popular Amazon listing) but has only 3 mist levels AND is cloud-only — strictly worse than Govee on both axes. The cloud-dependency cost on Govee is bounded — failsafe-OFF on cloud unreachability + Telegram alert keeps the worst case at "tent gets a little dry during a multi-hour outage" — not worth the local-control premium.
- **Files updated:**
  - **Renamed:** `docs/references/govee-api/h7140-capabilities.md` → `h714x-capabilities.md` (line-wide spec, H7142 deployment-specifics inline). `wiki/decisions/2026-04-26-govee-h7140-pivot.md` → `2026-04-26-govee-humidifier-pivot.md` (model-agnostic name).
  - **Rewritten:** `docs/references/govee-api/h714x-capabilities.md` — H7142 deployment spec, per-SKU comparison table (H7140 / H7142 / H7143), updated dispatch shape (`modeValue ∈ 1..9`), inferred capability list with explicit "verify against live discovery once provisioned" note since the H7142's full capability list hasn't been captured from a live device yet.
  - **Updated:** `wiki/decisions/2026-04-26-govee-humidifier-pivot.md` — title + decision body now reflect H7142 as deployment SKU; revision block explains the same-day switch from H7140; alternatives table expanded to call out H7140/H7143/SwitchBot/Tuya/Dreo as considered-and-rejected within the H71xx line; rollout steps updated to reflect both arrivals (H7140 backup 2026-04-27, H7142 primary 2026-04-28).
  - **Updated:** `docs/references/govee-api/INDEX.md` — example SKU strings flipped to H7142, deployment description updated, links to renamed `h714x-capabilities.md`, source links extended with H7142-specific manual + Amazon listing.
  - **Updated:** `docs/references/govee-api/control.md` and `gotchas.md` — example SKU strings + line-wide framing.
  - **Updated:** `docs/epics/continuous-humidifier/README.md` — abandoned-status block now references H7142 as the deployment SKU + renamed pivot decision.
  - **Updated:** `wiki/decisions/2026-04-23-raydrop-mcu-mist-control.md` — superseded link points at renamed pivot file; superseded text reframes "may be re-applied" → "carries over" since we're going Manual+PI from day one (not Auto-mode-first as the earlier pivot draft assumed).
  - **Updated:** `wiki/hardware/humidifier-control.md` — banner reflects both arrivals + renamed pivot decision.
  - **Updated:** `wiki/index.md` — pivot-decision entry retitled and rewritten to reflect H7142 deployment + 9 levels.
  - **Updated:** `CLAUDE.md` — Govee reference pack pointer now mentions H7142 deployment + 9 vs 8 level distinction across the H71xx line.

## [2026-04-26] daily | Day 43 — VPD below floor day 2; B moisture rising; all temp windows below targets
- Created `wiki/daily/2026-04-26.md` — Day 43; overnight VPD 0.94 kPa ✅ / morning 0.99 kPa ✅ / now 0.68 kPa 🔴 (below floor, 2nd consecutive day); all temperature windows marginally below veg targets; overnight RH 59.48% above 45–55% target for first time; Plant B moisture rising to 79.3%; C/D stable at 85–87%; reservoir change critically overdue (Day 11+)
- Photos: all four plants healthy, vibrant green, good SCROG fill; no humidity haze; A med-light green; B darkest/densest; C bushy med-dark green; D medium green
- Updated plant timeline + current state: plant-a (stable 57%), plant-b (rising 79%), plant-c (stable 85–86%), plant-d (stabilizing 87%)
- Updated `wiki/environment/humidity.md` — trend log entry + notable event: afternoon VPD below floor day 2; overnight RH above veg target first time; all windows above RH targets
- Updated `wiki/environment/temperature.md` — trend log entry + notable event: all windows below veg targets second consecutive day
- Refreshed `wiki/overview.md` and `wiki/index.md`

## [2026-04-26] decision + breeding-update | Pheno-split flip strategy + locked clone/male gear list
- **Trigger:** user inspection at Day 43 confirmed the 4 plants have split into two morphological groups — sativa-leaning (already at the net, starting to fill) and indica-leaning (barely reaching the net). Generic "flip at 70% coverage" guidance doesn't fit the asymmetric stretch profile. Separately, user committed to launching Track A this week with a 2×2×4 grow tent in another room (already on hand) and locked the gear shopping list.
- **Decision:** flip target window **2026-05-10 → 2026-05-17**, gated on **~60% net coverage with all four plants reaching the net plane** (not on a calendar date). Strategy: aggressively tuck the sativas under the net to slow vertical and force lateral spread; encourage indicas to keep climbing toward the net (light step-up window). Re-evaluate every 3 days. ~60% (not 70%+) is correct for this grow because mixed phenos have asymmetric stretch and a too-late flip traps sativa growth above the net while the indicas finally arrive.
- **Locked gear:**
  - Clones (closet shelf, ~$130): Rapid Rooter 50-pack, 7"+ humidity dome + tray, Clonex gel, heat mat, 30–50W LED bar, solo cups + Happy Frog soil for stasis pots, spray bottle, plant tags. Soil over coco for stasis to allow 3–4 day watering cadence (low-attention mode while focus is on current grow + male tent).
  - Males (2×2×4 tent in separate room, ~$245): 100W LED quantum board (Spider Farmer SF1000 or generic), 4" inline fan + carbon filter combo (mandatory for negative-pressure pollen containment), 6" oscillating clip fan, 1-gal fabric pots, digital hygrometer, jeweler's loupe 40×, paper lunch bags, 1.5 mL Eppendorf tubes, silica desiccant. Existing coco/perlite + veg formula at half-strength.
  - Germinate **6 of 10** SBxBS01 regulars (4 held in reserve); ~3 males expected from a 50/50 split. **Revised same day to germinate all 10 — see following entry.**
- **Files updated:**
  - **Created:** `wiki/decisions/2026-04-26-pheno-flip-strategy.md` — flip-target rationale, alternatives considered (40% / 70%+ / 90%), risk/mitigation table, breeding-program implications (clone window 2026-05-03 → 2026-05-10), open items (per-plant pheno assignment + daily coverage % tracking).
  - **Updated:** `wiki/breeding/timeline.md` — Phase 0 rewritten with locked gear list and the clone-taking window; Phase 1 flip date updated to the 2026-05-10–17 range gated on coverage; anchor-dates block now references the flip-strategy decision.
  - **Updated:** `wiki/breeding/cloning.md` — added "Stasis mode vs. productive-mother mode" section explaining the two operating modes; added "Medium choice for stasis pots" specifying Happy Frog over coco for low-attention stasis; added "Where the cloning station lives" section (closet shelf, not in any tent); transplant step (Day 14–21) updated to default to solo-cup stasis.
  - **Updated:** `wiki/breeding/isolation.md` — setup table rewritten to describe the 2-layer containment (closed-door room + 2×2×4 tent inside); concrete gear list with cost references; "Notes specific to our setup" updated to note the cloning station lives in a different room (incompatible with the male tent's environmental targets).
  - **Updated:** `wiki/index.md` — new pheno-flip-strategy decision added to the Decisions list.

## [2026-04-26] update | Pheno morphology assignments confirmed (A & D sativa, B & C indica)
- User-confirmed at Day 43: Plants A and D are sativa-leaning (longer internodes, vertical-dominant, already at SCROG net); Plants B and C are indica-leaning (tighter internodes, bushy, barely reaching net). Notable: the sativa pair is also the primary-keeper pair (purple signal pair) — every tuck pass on A/D matters more.
- **Files updated:**
  - **Updated:** `wiki/plants/plant-a.md`, `wiki/plants/plant-b.md`, `wiki/plants/plant-c.md`, `wiki/plants/plant-d.md` — added "Morphology" header field with phenotype lean + SCROG action (tuck for A/D, encourage-upward for B/C).
  - **Updated:** `wiki/decisions/2026-04-26-pheno-flip-strategy.md` — phenotype-split table filled in (A, D sativa; B, C indica); added a note that the sativa pair coincides with the primary-keeper pair; closed two open items.

## [2026-04-26] update | Reservoir refilled (afternoon) + clone session moved up to 2026-04-29
- Reservoir refilled 2026-04-26 afternoon (after the morning report was generated) — clears the Day 11+ overdue flag from today's daily and overview.md. Next change window ~2026-05-03 → 2026-05-06. Mothers are in good donor state for the clone session, which is one of the reasons we're moving the clone session up.
- Clone gear arrives Tue 2026-04-28; first cuttings planned Wed 2026-04-29. Original timeline window was 2026-05-03 → 2026-05-10 (~7-10 days before flip); moving it up because (a) mid-veg tissue at Day 45–46 roots more readily than tissue from plants approaching flip, (b) early take leaves a redo window if rate is poor (~70% expected), (c) lower laterals on A/D at the SCROG net are about to be lollipopped anyway, (d) decouples the cut from the busy flip-week. Asymmetric cut: lower laterals on A/D (sativa, already at net), middle laterals on B/C (indica, still need lower growth to reach the net).
- **Files updated:**
  - **Updated:** `wiki/breeding/timeline.md` Phase 0 — clone session moved to 2026-04-28/29 with rationale + asymmetric strategy.
  - **Updated:** `wiki/overview.md` — reservoir-overdue flag cleared; new action items for sativa-tucking + clone session; upcoming-milestones table now lists the clone gear/session arrivals + the corrected flip-target window.
  - **Updated:** `wiki/daily/2026-04-26.md` — reservoir flag flipped from 🔴 to ✅; added "Breeding-program scheduling" supplementary block summarizing today's filings.

## [2026-04-26] revise | Track A germination — pop all 10 regulars (revised from 6 of 10)
- **Trigger:** user pushed back on the "germinate 6, hold 4 in reserve" plan from earlier today. After re-examining the tradeoff, agreed: germ all 10 is the right call.
- **Reasoning:**
  - **Stochastic risk:** P(<2 males) drops from ~11% (with 6 seeds) to ~1% (with 10).
  - **Selection power:** picking the best of ~5 males is a real selection event per [`male-evaluation.md`](../wiki/breeding/male-evaluation.md); picking the best of ~3 is barely selection at all. Selection is the whole point of the breeding program.
  - **Reserves are illusory:** the existing 4 SBxBS01 F1s in the main tent (A/B/C/D) are already the genetic library + cloned for keeper preservation; holding 4 unstarted seeds doesn't add anything that banked pollen + clones don't already provide. If germ technique fails, it likely fails the same way on a second batch.
  - **Cost is small:** germ-stage effort identical; ~5 females to cull at sex confirmation vs ~3; peak male tent occupancy ~5 in a 2×2×4 is tight but fine since non-keepers get culled within 1–3 weeks of co-flowering anyway.
- **Files updated:**
  - **Updated:** `wiki/breeding/timeline.md` Phase 0 — germ count flipped to all 10 with rationale; Phase 1 fallback updated (sourcing another OBG pack only if <2 males surface from the full batch, P ≈ 1%).
  - **Updated:** `wiki/overview.md` — upcoming-milestones germ entry updated to "all 10".
  - **Updated:** `wiki/log.md` — prior entry annotated with the same-day revision pointer.

## 2026-04-27 daily-update | Day 44: VPD fully recovered; overnight RH drift continues; B moisture crossed 80%

- **Photos:** 5 presets captured 14:00 MDT (overview, plant-a, plant-b, plant-c, plant-d)
- **Key findings:** VPD recovered across all three windows (0.86/1.05/1.01 kPa) after two-day below-floor streak; humidifier reduction effective. Overnight RH five-night upward drift continues (52.1% → 64.4%). Plant B moisture crossed 80% (81.84%), entering C/D elevated range. Plant D moisture easing slightly off 88.48% peak. Temperature overnight crossed 68°F floor (68.87°F) for first time in four nights; day/morning still marginally below 74°F.
- **Files created/updated:**
  - **Created:** `wiki/daily/2026-04-27.md`
  - **Updated:** `wiki/plants/plant-a.md` — timeline + current state
  - **Updated:** `wiki/plants/plant-b.md` — timeline + current state
  - **Updated:** `wiki/plants/plant-c.md` — timeline + current state
  - **Updated:** `wiki/plants/plant-d.md` — timeline + current state
  - **Updated:** `wiki/environment/humidity.md` — trend row + notable event
  - **Updated:** `wiki/environment/temperature.md` — trend row + notable event
  - **Updated:** `wiki/overview.md`
  - **Updated:** `wiki/index.md`

## [2026-04-27] hardware + control | Govee H7142 humidifier deployed; PI controller promoted to authoritative
- **Hardware cutover:** GoveeLife H7142 (6 L cool-mist ultrasonic, 9 Manual-mode mist levels via Govee Public API v2) provisioned at `192.168.1.247` (MAC `14:38:60:74:F4:DD:B9:46`, account name `dirt-humidifier`). Raydrop 4L + Kasa EP10 plug physically retired and unplugged. Raydrop kept as a spare; Kasa EP10 deprovisioned from the humidifier loop (lights still on a separate Kasa plug).
- **Control upgrade:** the host-side PI controller (`apps/hwd/src/dirt_hwd/services/humidifier_pi.py`) — running in shadow mode against the Kasa bang-bang since 2026-04-25 — promoted to authoritative. New module `humidifier_dispatch.py` quantizes its `u_pct ∈ [0, 100]` into a discrete H7142 Manual-mode level (1..9) with hysteresis at boundaries. New module `apps/shared/src/dirt_shared/services/govee.py` is the async API client (verified `GET /user/devices` discovery, POST state/control endpoints, `lackWaterEvent` parsing).
- **Loop rewrite:** `HumidifierLoopService.run` now diffs live device state against the PI/quantizer target each tick, sending the minimal set of API calls (state read + 0–2 control calls). Boot-tick path collapses `set_power(on)` + `set_manual_level(N)` into one tick with a 200 ms inline pause. New event types in the `humidifier` stream: `state_change` (with `power`/`level`/`u_pct`), `level_change` (level transitions while powered), `lack_water` / `lack_water_cleared` (rising/falling edge of the H7142's empty-tank alarm), `device_offline` / `device_online`, `suspected_ineffective` (replaces the Raydrop-specific `suspected_stuck`), `rate_limited`, `skip_offline`. `_record_actuator` writes `humidifier_on` + `humidifier_mist_level` every tick as the heartbeat for `SystemStatusService`.
- **Gain tweak:** `HUMIDIFIER_PI_KC` set to 40 in `.env` (default was 8.0, sourced from a Raydrop FOPDT fit). With Kc=8 the PI threshold gate (`u ≥ 5.5%`) needed VPD overshoot ≥ 0.69 kPa before engaging — too sluggish. Kc=40 engages at error ≈ 0.14 kPa (typical veg-stage overshoot). Live trace at the cutover: VPD 1.36 kPa → PI engaged at u=5.53% → quantizer picked level 1 → H7142 acknowledged `powerSwitch=1, workMode={1, 1}`.
- **Live API findings (against pre-deploy reference pack):** `/user/devices` is GET, not POST as our 2026-04-26 pack had it; H7142 capability list is exactly `powerSwitch` / `workMode` / `humidity` / `lackWaterEvent` (no UVC/aroma/nightlight as speculated); `humidity` cap range is 40–70%, not 40–80%; `workMode` enum is `1=Manual, 2=Custom, 3=Auto`. Reference pack updated; live discovery captured at `apps/shared/tests/fixtures/govee_h7142_discovery.json`.
- **Atlas migration `20260428003304_add_govee_sensor_source.sql`** — adds `govee` to the `sensor_source` Postgres enum so the new actuator breadcrumbs (`humidifier_on`, `humidifier_mist_level`) record `source=govee`. Applied.
- **Tests:** 14 new tests for the Govee client (`apps/shared/tests/test_govee.py`), 20 property tests for the dispatch quantizer (`apps/hwd/tests/test_humidifier_dispatch.py`), 18 helper unit tests + 7 single-tick integration tests for the rewritten loop (`apps/hwd/tests/test_humidifier_helpers.py`, `test_humidifier_loop.py`). Old `test_humidifier_stuck.py` deleted (semantics changed). Total: 477 passed across the workspace, 1 skipped, no invariant violations.
- **Updated:** `wiki/decisions/2026-04-27-h7142-deployed.md` (new), `wiki/hardware/humidifier-control.md` (full rewrite for H7142 + PI), `wiki/overview.md`, `wiki/index.md`, `wiki/environment/humidity.md`, `docs/references/govee-api/{INDEX,control,h714x-capabilities}.md` (corrections from live discovery), `apps/shared/src/dirt_shared/services/system_status.py` (`Humidifier (Kasa EP10)` → `Humidifier (Govee H7142)`), `apps/web/tests/test_system_devices_endpoint.py`, `web-ui/src/mocks/fixtures/system.devices.json`, `CLAUDE.md` (`humidifier` log stream description rewritten for the new event taxonomy).
- **Open items:** week-1 graduated step test for FOPDT refit against the H7142 (current gains carry over from the abandoned Raydrop fit). Watch `humidifier_shadow` traces for level-change cadence — tighten hysteresis if > 5 transitions/hour at steady state.

## [2026-04-28] daily | Day 45 — photos + sensors; Plant B moisture escalation; Govee H7142 day 1
- Photos captured at 14:00 MDT across 5 presets (overview, A, B, C, D). All four plants at or above SCROG net; canopy healthy across all plants.
- **Plant B moisture escalation:** jumped from 81.84% (Apr 27 now) to 86.74% — now matches C/D elevated zone (B: 86.7%, C: 88.0%, D: 86.1%); no visible stress.
- **Govee H7142 first full day:** daytime RH dropped 8.6 points (64.6% → 56.0%); VPD 1.19 kPa ✅. Overnight RH 65.55% — first overnight under H7142 PI control; performance review pending tomorrow.
- **Temperature regression:** overnight 67.76°F — back below 68°F floor after yesterdays 68.87°F recovery.
- Clone gear arrived today; clones + SBxBS01 regular germination (10 seeds, Track A) planned 2026-04-29.
- Updated: `plants/plant-{a,b,c,d}.md`, `environment/humidity.md`, `environment/temperature.md`, `overview.md`, `index.md`.

## [2026-04-29] daily | Day 46 — Plant B moisture action; H7142 overnight low VPD
- Photos captured at 14:00 MDT across 5 presets (overview, A, B, C, D). Canopy remains healthy; A/D are sativa-leaning tuck candidates, B/C are denser and should continue growing upward into the net.
- **Plant B moisture action:** now 91.93% (up from 86.74% Apr 28 and 81.84% Apr 27) with no visible stress. Close B float valve today and dry back before reopening.
- **H7142 overnight issue:** overnight RH worsened to 67.41% and VPD fell to 0.76 kPa; morning/now VPD remains in range (1.12 / 0.98 kPa), but all RH windows are above the 45–55% veg guide.
- **Temperature still cool:** 67.71°F overnight, 71.97°F morning, 72.63°F now — all below current veg targets.
- Clones + SBxBS01 regular germination are due today; light step to 50% remains overdue if not already done.
- Updated: `daily/2026-04-29.md`, `plants/plant-{a,b,c,d}.md`, `environment/humidity.md`, `environment/temperature.md`, `overview.md`, `index.md`.

## [2026-05-01] daily | Day 48 — B dryback still required; humidity wet-edge; day temp recovered
- Photos captured across 5 presets (overview, A, B, C, D). Canopy remains broadly healthy; A/D are still sativa-leaning tuck candidates, while B/C remain denser at the net.
- **Plant B moisture remains critical:** 93.90% now after 91.93% Apr 29 and 86.74% Apr 28. Photo still lacks obvious wilt, but keep/close the B float valve and dry back before reopening.
- **Humidity/VPD still wet-edge:** overnight VPD again averaged 0.76 kPa and current RH climbed to 71.3%; daytime VPD is in range but low (0.90 morning, 0.84 now).
- **Temperature partly recovered:** current temp is back in target at 74.55°F, but overnight remains below floor at 67.31°F.
- **Root zones:** C remains saturated around 90%; D is high but easing to 86.85%; A remains stable around 60%.
- Updated: `daily/2026-05-01.md`, `plants/plant-{a,b,c,d}.md`, `environment/humidity.md`, `environment/temperature.md`, `overview.md`, `index.md`.

## [2026-05-01] lint backfill | 2026-04-30 continuity daily
- `uv run scripts/lint.py` found the existing 2026-04-30 raw photo set without a matching daily page, causing photo coverage and timeline-continuity failures.
- Added `wiki/daily/2026-04-30.md` as a continuity entry only; no Apr 30 sensor readings were available in the May 1 prompt, so the page does not invent sensor values.
- Added one-line Apr 30 plant timeline backlinks and indexed the daily page.

## [2026-05-02] manual update | Clones taken; Track A regulars germinated
- User-confirmed breeding propagation status: clones were taken today from all four current SBxBS01 plants (A/B/C/D), and the SBxBS01 regular seeds for Track A were germinated approximately four days earlier (~2026-04-28).
- Both clone cuttings and regular seedlings are currently under a humidity dome. The next propagation watch is balancing clone humidity against seedling damping-off/stretch risk and preserving clear labels.
- **Files created/updated:**
  - **Created:** `wiki/daily/2026-05-02.md`
  - **Updated:** `wiki/plants/plant-a.md`, `wiki/plants/plant-b.md`, `wiki/plants/plant-c.md`, `wiki/plants/plant-d.md` — current state + timeline entries for clone preservation
  - **Updated:** `wiki/breeding/README.md`, `wiki/breeding/timeline.md`, `wiki/decisions/2026-04-26-breeding-program-launch.md` — Track A current plan/status corrected to all 10 regulars; Phase 0 clone/germination tasks marked done; regular sex-watch window recalculated from approximate 2026-04-28 germination
  - **Updated:** `wiki/overview.md`, `wiki/index.md`
  - **Updated:** `scripts/lint.py` — added 2026-05-02 to the known no-photo daily allowlist because this was a manual non-photo check-in.

## [2026-05-02] strategy update | Stabilize dark-purple sativa-leaning line
- User clarified the breeding goal: stabilize the most interesting phenotype rather than optimize for yield or broad BS-line exploration. Target seeds should reliably produce dark purple buds, stems, and leaves with longer internodes / sativa-leaning trellis-friendly structure.
- Added decision logic for F-line selection vs backcrossing: A/D being purple does not prove the alleles are fixed; progeny testing is required. Prefer F2 → selected F3 family lots → F4/F5 selection for stabilization, with BX to A/D reserved as an anchor route if A/D proves exceptional and F-line families do not improve consistency.
- Added operational plan: fast 14–21 day veg cycles, early flip, hard culling, short-lived male isolation with separately banked pollen, and small female clone stasis space as the undo button.
- **Files created/updated:**
  - **Created:** `wiki/breeding/stabilization-strategy.md`
  - **Created:** `wiki/decisions/2026-05-02-purple-stabilization-strategy.md`
  - **Updated:** `wiki/breeding/README.md`, `wiki/breeding/timeline.md`, `wiki/breeding/pheno-hunt-protocol.md`, `wiki/breeding/male-evaluation.md`, `wiki/decisions/2026-04-26-breeding-program-launch.md`
  - **Updated:** `wiki/overview.md`, `wiki/index.md`
