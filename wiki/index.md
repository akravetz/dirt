---
title: Index
type: index
updated: 2026-04-14
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

## Environment
- [Temperature](environment/temperature.md) — Trend log; targets by phase; notable events
- [Humidity](environment/humidity.md) — Trend log; Denver humidification notes
- [Nutrients & pH](environment/nutrients.md) — Canna A+B protocol; pH management; incident log

## Hardware
- [ESP32-C3 Per-Plant Nodes](hardware/esp32-plant-nodes.md) — Wireless soil moisture nodes (A/B/C/D); plant-a live, b/c/d pending more sensors

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
- [ESP32-C3 GPIO3 + IDF ADC (2026-04-14)](decisions/2026-04-14-esp32-c3-gpio3-adc.md) — GPIO3 over GPIO4 (JTAG conflict); `adc1_get_raw()` over Arduino `analogRead()` (WiFi instability)
- [Server-Side Auto-Calibration (2026-04-14)](decisions/2026-04-14-server-side-auto-calibration.md) — Calibration lives in DB, auto-widens extrema per (location, metric); firmware sends raw only
