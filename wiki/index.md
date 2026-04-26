---
title: Index
type: index
updated: 2026-04-24
---

# Grow Wiki Index

## Overview
- [Grow Overview](overview.md) — Current status, plant table, active action items, milestones
- [Activity Log](log.md) — Append-only ingestion and update history
- [Oregon Breeding Group (OBG)](concepts/oregon-breeding-group.md) — Wayne / Serious Black / BS01 breeding-stock pack; next-grow phenotypic selection + breeding plan
- [Cannabis Genomics](concepts/cannabis-genomics.md) — bioinformatics pipeline: reference assemblies, variant calling, SnpEff, kinship/PCA, MAS workflow
- [Wake-Word Experiment Log](wake-word-experiments.md) — append-only log of every "hey Claudia" model trained: what changed, why, training config, validation results

## Plants
- [Plant A](plants/plant-a.md) — 🔴 Primary keeper; vigor leader; strong purple contender; **topped Apr 11** (Day 14 post-top); **LST Day 5** (started Apr 20); moisture stable ~57%
- [Plant B](plants/plant-b.md) — 🟡 Secondary; no purple; **topped Apr 12** (Day 13 post-top); **LST Day 5** (started Apr 20); densest dark-green canopy; moisture rising 68% → 74.6% — watch
- [Plant C](plants/plant-c.md) — 🟡 Secondary; **topped Apr 12** (Day 13 post-top); **LST Day 5** (started Apr 20); moisture stable at 84% (very high) — monitor root zone
- [Plant D](plants/plant-d.md) — 🔴 Primary keeper; strong purple contender; **topped Apr 12** (Day 13 post-top); **LST Day 5** (started Apr 20); moisture peaked 87.1% overnight; 86.0% now — monitor root zone

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
- [2026-04-19](daily/2026-04-19.md) — Day 36: overnight temp recovered (68.0°F ✅); LST overdue; daytime VPD elevated (1.51 kPa)
- [2026-04-20](daily/2026-04-20.md) — Day 37: daytime env in target (75.04°F ✅, 1.12 kPa VPD ✅); overnight RH regressed (74.37% ⚠️ — service restart pending); LST critically overdue; Plant D lighter green — monitoring
- [2026-04-21](daily/2026-04-21.md) — Day 38: photos only; no sensor data captured; all plants healthy
- [2026-04-22](daily/2026-04-22.md) — Day 39: overnight env breakthrough (RH 52% ✅, temp 70.17°F ✅ — both in target first time); reservoir change due (Day 7); Plant D color improving; Plant A overnight sensor dropout
- [2026-04-23](daily/2026-04-23.md) — Day 40: photos only; no sensor snapshot; humidifier oscillation + Raydrop red-LED latch incidents; BME280 retired → SHT45 cutover
- [2026-04-24](daily/2026-04-24.md) — Day 41: temperature fully in range all windows (first time) ✅✅; VPD clean all windows; C/D moisture 82–83% ⚠️; LST and reservoir change critically overdue
- [2026-04-25](daily/2026-04-25.md) — Day 42: afternoon VPD 0.63 kPa below floor ⚠️; temperature regression (72°F vs yesterday's 76°F); C/D moisture 84–86%; reservoir change Day 10 (overdue)

## Environment
- [Temperature](environment/temperature.md) — Trend log; targets by phase; notable events
- [Humidity](environment/humidity.md) — Trend log; Denver humidification notes
- [Nutrients & pH](environment/nutrients.md) — Canna A+B protocol; pH management; incident log

## Hardware
- [ESP32-C3 Per-Plant Nodes](hardware/esp32-plant-nodes.md) — Wireless soil moisture nodes (A/B/C/D); **all four live as of 2026-04-16** (A/D on v1.2 sensors, B/C on v2.0)
- [Humidifier Control](hardware/humidifier-control.md) — Raydrop 4L gated by a Kasa Ultra Mini EP10 smart plug, driven by a host-side Python service via `python-kasa`; bang-bang hysteresis on tent BME280-derived VPD. Plug on hand, service not yet built.
- [PTZ Camera (OBSBOT Tiny 2 Lite + daemon)](hardware/ptz-camera.md) — Programmable gimbal + zoom; persistent C++ daemon + `scripts/camera` CLI; per-plant presets calibrated
- [Jabra Speak 410](hardware/jabra.md) — USB speakerphone for voice I/O; ElevenLabs "Claudia" TTS + Nova-3 STT + openWakeWord ("hey claudia"). Device quirks, firmware, volume tuning.
- [Voice Channel (Claudia)](hardware/voice-channel.md) — Production Pipecat pipeline on top of the Jabra; `dirt-voice.service`; agent tools; session logs. **Deployed 2026-04-18.**
- [Reservoir Level (Autopot)](hardware/reservoir-level.md) — Submerged hydrostatic pressure transducer (DFRobot KIT0139) → ADS1115 → dedicated ESP32-C3 reservoir node → `reservoir_depth_cm` ingest. Planned, parts on roadmap.
- [AC Infinity Fan Control + Tent Environmental Sensor](hardware/ac-infinity-fan-control.md) — Combined ESP32-C3 SuperMini node: drives the Cloudline LITE 6" fan via 2× 2N7000 MOSFETs on D+/B5 **and** reads an Adafruit SHT45 + PTFE cap over I²C (GPIO 4/5) for tent temp/RH/VPD. **Fan D+ bring-up + SHT45 read both validated 2026-04-22.** Combined firmware at `firmware/fan_controller/`. Tach (D−) deferred. WiFi/OTA/ingest integration next.

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
- [Multi-Actuator Environment Control (future)](concepts/multi-actuator-environment-control.md) — Design principles for when the dehumidifier + PWM fan arrive: 2D (T, RH) target zones, cascaded SISO state-machine, feedforward on lights. Rejects MIMO/PID. Implementation deferred until hardware is in.
- [Control Theory Primer](concepts/control-theory-primer.md) — Walks the ladder bang-bang → P-only → PI → PI + envelope guards → PI + feedforward. Covers anti-windup, FOPDT modeling, IMC tuning (with worked numerical example), stability intuition, drone-PID vs slow-process-PI contrast, cascade vs multi-actuator dispatch. Runnable demos in `debug/control-theory-demos/`.
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
- [Wake-Word v4 Plan (2026-04-18)](decisions/2026-04-18-wake-word-v4-plan.md) — Precision-focused retraining: harvested hard negatives from deployment + mined meeting audio + synthesized phonetic neighbors + additional RIRs; near-miss audio capture live as of 2026-04-18. **Superseded by v5 2026-04-23.**
- [Wake-Word v5 Plan (2026-04-23)](decisions/2026-04-23-wake-word-v5-passive-harvest.md) — Passive-harvest mode (`DIRT_VOICE_HARVEST_ONLY=1`): operator runs dirt-voice for ~2 days without saying the wake word, every above-floor capture is a guaranteed negative — eliminates v4's manual triage. Floor lowered to 0.15; ElevenLabs positives + `max_negative_weight=800` carry forward from v4.
- [Speaker Verifier (2026-04-24)](decisions/2026-04-24-speaker-verifier.md) — ECAPA-TDNN via speechbrain as a second-stage filter after the wake model fires; rejects any voice that isn't the enrolled user's. Orthogonal to v5 retraining; addresses meeting FPs at root. Ship before v5 to re-enable dirt-voice safely without waiting on the harvest cycle.
- [Wake-Word Training Pipeline — Kaggle → RunPod (2026-04-25)](decisions/2026-04-25-runpod-migration.md) — After v9–v15 each failed on a different Kaggle-environment quirk (base-image contents, py3.12 PyPI wheels, editable-install path, locked-down package layout), abandoned Kaggle Notebooks for a self-controlled Docker image on RunPod Pods. Image bakes everything; Network Volume holds the four Kaggle datasets. The v8 architectural design carries over unchanged.
- [ESP32-C3 GPIO3 + IDF ADC (2026-04-14)](decisions/2026-04-14-esp32-c3-gpio3-adc.md) — GPIO3 over GPIO4 (JTAG conflict); `adc1_get_raw()` over Arduino `analogRead()` (WiFi instability)
- [Server-Side Auto-Calibration (2026-04-14)](decisions/2026-04-14-server-side-auto-calibration.md) — Calibration lives in DB, auto-widens extrema per (location, metric); firmware sends raw only
- [Lights-Off-Aware Humidifier Control (2026-04-19)](decisions/2026-04-19-lights-off-aware-humidifier.md) — Schedule-driven feedforward added to the humidifier loop: pre-lights-off prep window forces OFF for the last 30 min of lights-on; lights-off subtracts 0.3 kPa from the stage band. Lights schedule stored on `growstate` (user-editable); rejected derivative control in favor of feedforward on a known-periodic disturbance.
- [Drop Humidifier Safety Timers (2026-04-19)](decisions/2026-04-19-drop-humidifier-safety-timers.md) — Removed `max_on` (20 min) and `min_off` (90s) guards after 2026-04-19 logs showed `max_on_timeout` displacing the deadband as the effective setpoint. Raydrop's low-water cutoff replaces the max-on safety; hysteresis replaces min-off.
- [Humidifier VPD Targeting (2026-04-18)](decisions/2026-04-18-vpd-targeting.md) — Switched humidifier control from fixed 60% RH to stage-dynamic VPD upper-band edge; setpoint reads `dirt.services.grow_state.STAGE_TARGETS` per tick so veg→flower transitions shift automatically. Supersedes the setpoint portion of the 2026-04-17 decision.
- [Humidifier Control via Kasa EP10 (2026-04-17)](decisions/2026-04-17-humidifier-kasa-ep10.md) — Raydrop 4L gated by a WiFi smart plug + `python-kasa`; bang-bang hysteresis on host-side Python service. Supersedes the 2026-04-14 SSR approach.
- [Humidifier Closed-Loop Control (2026-04-14, superseded)](decisions/2026-04-14-humidifier-relay-control.md) — Original SSR-on-Arduino plan; superseded before deployment, kept for decision-trail history.
- [Reservoir Level Sensing (2026-04-18)](decisions/2026-04-18-reservoir-level-pressure-transducer.md) — Submerged DFRobot KIT0139 pressure transducer (4–20mA, 0–5m) → ADS1115 16-bit I²C ADC → new dedicated ESP32-C3 reservoir node. Alternatives (float, ultrasonic, capacitive strip) considered and rejected.
- [Tent-Hub Sensor Swap — DHT22 → BME280 (2026-04-20)](decisions/2026-04-20-bme280-sensor-swap.md) — Replaced the DHT22 on the Arduino Nano tent-hub with a Bosch BME280 (I²C `0x76`) after DHT22 hardware failure and for tighter drift characteristics. Topology and humidifier control loop unchanged; 0.1 kPa deadband kept. Pressure now captured as a free side channel. **Superseded 2026-04-22.**
- [Tent Sensor + Transport Swap — SHT45 on ESP32-C3 (2026-04-22)](decisions/2026-04-22-sht45-tent-node-esp32.md) — Both sensor (BME280 → Sensirion SHT45 + PTFE cap, I²C `0x44`, GPIO4/5) and host board (Arduino Nano + USB serial → ESP32-C3 SuperMini + HTTP ingest) replaced. Firmware restructured into `firmware/{plant_node, tent_node, common}/` peer projects with a shared C++ lib tree. Motivated by recurring BME280 stuck-state and the last USB-serial tether being the lone asymmetric ingest path. **Revised same day:** SHT45 integrated onto the fan-controller ESP32 instead of a dedicated tent_node board; hardware bring-up validated; `firmware/tent_node/` obsoleted.
- [Continuous Humidifier Intensity — Raydrop MCU-Controlled Mist (2026-04-23)](decisions/2026-04-23-raydrop-mcu-mist-control.md) — Replace the Raydrop KC-RD03A's analog intensity potentiometer with MCU-driven control (digipot or DAC on the fan-controller ESP32) + a host-side PI loop on VPD error. Retires today's bang-bang Kasa-plug control. Motivated by three failure modes observed 2026-04-23: actuator-overshoot oscillation, fan-coupling saturation (dial as hidden input to the control stack), and the low-water-latch red-LED failure. Kasa plug stays as hard-off authority. Tracked in [epic: continuous-humidifier](../docs/epics/continuous-humidifier/README.md). Phase 1 (investigation) is the stop-gate on Phases 2–4.
