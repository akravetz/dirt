---
title: Index
type: index
updated: 2026-04-18
---

# Grow Wiki Index

## Overview
- [Grow Overview](overview.md) — Current status, plant table, active action items, milestones
- [Activity Log](log.md) — Append-only ingestion and update history

## Plants
- [Plant A](plants/plant-a.md) — 🔴 Primary keeper; vigor leader; strong purple contender; **topped Apr 11**, recovery → LST ~Apr 16–18
- [Plant B](plants/plant-b.md) — 🟡 Secondary; no purple; **topped Apr 12**, recovery → LST ~Apr 17–19
- [Plant C](plants/plant-c.md) — 🟡 Secondary; **topped Apr 12**; leaf issue resolved (foliar burn); recovery → LST ~Apr 17–19
- [Plant D](plants/plant-d.md) — 🔴 Primary keeper; strong purple contender; **topped Apr 12**, recovery → LST ~Apr 17–19

## Daily Logs
- [2026-03-27](daily/2026-03-27.md) — Day 13: Pre-transplant; 2–3 leaf sets
- [2026-03-29](daily/2026-03-29.md) — Day 15: Transplant day (into Autopot XL)
- [2026-03-30](daily/2026-03-30.md) — Day 16: Runoff management; purple phenotype spotted; plants labeled A–D
- [2026-04-01](daily/2026-04-01.md) — Day 18: Anthocyanin confirmed; A & D elevated to primary
- [2026-04-02](daily/2026-04-02.md) — Day 19: Training plan sequenced; AirBase disc discovery
- [2026-04-03](daily/2026-04-03.md) — Day 20: Routine check; RH/temp monitoring
- [2026-04-05](daily/2026-04-05.md) — Day 22: Nutrient burn (Plant A, foliar); Plant C flagged
- [2026-04-06](daily/2026-04-06.md) — Day 23: Photos only; monitoring
- [2026-04-08](daily/2026-04-08.md) — Day 25: Plant C worsening (brown/rust spots); VPD swing incident; topping imminent
- [2026-04-11](daily/2026-04-11.md) — Day 28: **Plant A topped**; vigor leader confirmed; EC too high (920 ppm); float valve window opens Apr 12
- [2026-04-12](daily/2026-04-12.md) — Day 29: **All four plants topped** (B, C, D today; A yesterday); all in recovery; LST ~Apr 16–19
- [2026-04-18](daily/2026-04-18.md) — Day 35: LST window open (all 4 due now); overnight temp/RH flags; A/D sensors upgraded to v2.0

## Environment
- [Temperature](environment/temperature.md) — Trend log; targets by phase; notable events
- [Humidity](environment/humidity.md) — Trend log; Denver humidification notes
- [Nutrients & pH](environment/nutrients.md) — Canna A+B protocol; pH management; incident log

## Hardware
- [ESP32-C3 Per-Plant Nodes](hardware/esp32-plant-nodes.md) — Wireless soil moisture nodes (A/B/C/D); **all four live as of 2026-04-16** (A/D on v1.2 sensors, B/C on v2.0)
- [Humidifier Control](hardware/humidifier-control.md) — Raydrop 4L gated by a Kasa Ultra Mini EP10 smart plug, driven by a host-side Python service via `python-kasa`; bang-bang hysteresis on tent DHT22 RH. Plug on hand, service not yet built.
- [PTZ Camera (OBSBOT Tiny 2 Lite + daemon)](hardware/ptz-camera.md) — Programmable gimbal + zoom; persistent C++ daemon + `scripts/camera` CLI; per-plant presets calibrated
- [Jabra Speak 410](hardware/jabra.md) — USB speakerphone for voice I/O; ElevenLabs "Claudia" TTS + Nova-3 STT + openWakeWord ("hey claudia"). Device quirks, firmware, volume tuning.
- [Voice Channel (Claudia)](hardware/voice-channel.md) — Production Pipecat pipeline on top of the Jabra; `dirt-voice.service`; agent tools; session logs. **Deployed 2026-04-18.**
- [Reservoir Level (Autopot)](hardware/reservoir-level.md) — Submerged hydrostatic pressure transducer (DFRobot KIT0139) → ADS1115 → dedicated ESP32-C3 reservoir node → `reservoir_depth_cm` ingest. Planned, parts on roadmap.
- [AC Infinity Cloudline LITE 6" Fan Control](hardware/ac-infinity-fan-control.md) — Reverse-engineer the stock wired PWM controller on the fan's USB-C port, then drive the fan from an Arduino Nano. Parts ordered 2026-04-18, capture/wiring pending.

## Concepts
- [Anthocyanin](concepts/anthocyanin.md) — Purple expression: genetic vs. environmental
- [Autopot System](concepts/autopot.md) — Operation guide; hand-watering phase; float valve activation
- [Coco Coir](concepts/coco-coir.md) — Medium mix; pH target; transplanting notes
- [LST](concepts/lst.md) — Low Stress Training technique
- [Plant Training Methods](concepts/plant-training-methods.md) — Overview of all training techniques: LST, topping, FIMing, mainlining, super cropping, SCROG, SOG; research notes; our training sequence
- [SCROG](concepts/scrog.md) — Screen of Green technique
- [Damping Off](concepts/damping-off.md) — Fungal disease; symptoms, prevention, current risk assessment (RH elevated)
- [DLI & Light Management](concepts/dli-light-management.md) — Daily Light Integral, PPFD targets, Fold-650 ramp plan
- [Flushing (Coco)](concepts/flushing.md) — Pre-harvest flush protocol; coco timing (5–7 days); Autopot procedure
- [Lollipopping & Defoliation](concepts/lollipopping-defoliation.md) — Flip-day techniques; SCROG integration; week 3 hard stop
- [Trichome Stages](concepts/trichome-stages.md) — Harvest timing; clear/cloudy/amber; pheno hunt evaluation criteria
- [VPD](concepts/vpd.md) — Vapor Pressure Deficit: formula, targets by stage, current situation, coco interaction
- [Topping](concepts/topping.md) — HST technique: cut apical meristem at node 4–5 to create two main stems; imminent for Plant A
- [pH Lockout](concepts/ph-lockout.md) — Nutrient unavailability from root zone pH drift; active diagnosis for Plant C
- [Nutrient Burn](concepts/nutrient-burn.md) — Excess salt damage from high EC; symptoms, diagnosis, correction
- [EC (Electrical Conductivity)](concepts/ec.md) — Measuring nutrient concentration; targets by stage; TDS-3 meter usage
- [Capacitive Soil Moisture Sensors](concepts/capacitive-soil-moisture.md) — How v1.2 sensors work; voltage ranges; failure modes; multimeter diagnostic
- [Wake-Word Detection](concepts/wake-word-detection.md) — openWakeWord architecture, training data, FRR diagnostics, threshold tuning, custom verifier models
- [Room Impulse Response (RIR)](concepts/room-impulse-response.md) — What an IR is; exponential sine sweep capture (Farina method); using IRs as training augmentation

## Decisions
- [Medium, Nutrients & Training (2026-03-16)](decisions/2026-03-16-medium-and-training.md) — Coco/perlite, Canna A+B, single top → LST → SCROG
- [Anthocyanin Priority Shift (2026-04-01)](decisions/2026-04-01-anthocyanin-priority.md) — Plants A & D elevated to primary keeper candidates
- [Reservoir Stand (2026-04-11)](decisions/2026-04-11-reservoir-stand.md) — Oak step stool 6" height for FlexiTank Pro gravity feed; alternatives considered
- [Distributed Sensor Architecture (2026-04-12)](decisions/2026-04-12-distributed-sensor-architecture.md) — ESP32-C3 per-plant nodes + Arduino Nano tent hub; USB-C powered, WiFi
- [PTZ Camera Selection (2026-04-12)](decisions/2026-04-12-ptz-camera-selection.md) — OBSBOT Tiny 2 Lite for programmatic pan/tilt/zoom plant inspection
- [Audio Hardware Selection (2026-04-12)](decisions/2026-04-12-audio-hardware-selection.md) — Jabra Speak 410 USB speakerphone for voice interaction
- [Mobile Chat Interface (2026-04-12)](decisions/2026-04-12-telegram-mobile-interface.md) — Telegram bot for on-the-go Claude interaction
- [Agent Architecture (2026-04-12)](decisions/2026-04-12-agent-architecture.md) — Ephemeral agent loops via Claude Agent SDK; wiki as memory; JSONL session logs
- [Agent Runtime — Shell-Out to Claude Code CLI (2026-04-14)](decisions/2026-04-14-agent-runtime-shell-out.md) — Use `claude -p` subprocess to leverage Max subscription instead of API billing
- [Voice Pipeline Selections (2026-04-16)](decisions/2026-04-16-voice-pipeline-selections.md) — ElevenLabs TTS ("Claudia" voice) + openWakeWord wake phrase + Deepgram STT
- [Wake-Word Training Strategy (2026-04-16)](decisions/2026-04-16-wake-word-training-strategy.md) — Retrain openWakeWord with voice-clone positives + captured RIRs to fix far-field recall
- [Wake-Word v4 Plan (2026-04-18)](decisions/2026-04-18-wake-word-v4-plan.md) — Precision-focused retraining: harvested hard negatives from deployment + mined meeting audio + synthesized phonetic neighbors + additional RIRs; near-miss audio capture live as of 2026-04-18
- [ESP32-C3 GPIO3 + IDF ADC (2026-04-14)](decisions/2026-04-14-esp32-c3-gpio3-adc.md) — GPIO3 over GPIO4 (JTAG conflict); `adc1_get_raw()` over Arduino `analogRead()` (WiFi instability)
- [Server-Side Auto-Calibration (2026-04-14)](decisions/2026-04-14-server-side-auto-calibration.md) — Calibration lives in DB, auto-widens extrema per (location, metric); firmware sends raw only
- [Humidifier VPD Targeting (2026-04-18)](decisions/2026-04-18-vpd-targeting.md) — Switched humidifier control from fixed 60% RH to stage-dynamic VPD upper-band edge; setpoint reads `dirt.services.grow_state.STAGE_TARGETS` per tick so veg→flower transitions shift automatically. Supersedes the setpoint portion of the 2026-04-17 decision.
- [Humidifier Control via Kasa EP10 (2026-04-17)](decisions/2026-04-17-humidifier-kasa-ep10.md) — Raydrop 4L gated by a WiFi smart plug + `python-kasa`; bang-bang hysteresis on host-side Python service. Supersedes the 2026-04-14 SSR approach.
- [Humidifier Closed-Loop Control (2026-04-14, superseded)](decisions/2026-04-14-humidifier-relay-control.md) — Original SSR-on-Arduino plan; superseded before deployment, kept for decision-trail history.
- [Reservoir Level Sensing (2026-04-18)](decisions/2026-04-18-reservoir-level-pressure-transducer.md) — Submerged DFRobot KIT0139 pressure transducer (4–20mA, 0–5m) → ADS1115 16-bit I²C ADC → new dedicated ESP32-C3 reservoir node. Alternatives (float, ultrasonic, capacitive strip) considered and rejected.
