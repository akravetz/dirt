---
title: Environment — Humidity
type: environment
sources: [raw/chat-history/all-chat-summary.md, raw/chat-history/bible.md, raw/chat-history/memory.md]
related: [wiki/environment/temperature.md, wiki/concepts/vpd.md, wiki/overview.md, wiki/hardware/humidifier-control.md, wiki/decisions/2026-04-17-humidifier-kasa-ep10.md]
created: 2026-04-06
updated: 2026-04-14
---

# Humidity (RH)

## Targets by Phase

| Phase | Target RH | VPD |
|-------|-----------|-----|
| Seedling | 65–75% | 0.4–0.8 kPa |
| Veg | 55–65% | 0.8–1.2 kPa |
| Early Flower | 45–55% | 1.0–1.5 kPa |
| Late Flower | 35–45% | 1.5–2.0 kPa |

**Current phase:** Early veg — target 55–65% (current readings slightly above).

**Denver note:** Denver's dry ambient air can pull tent RH down to 20–30% without active humidification. A humidifier is essential during seedling/early veg. Denver's natural dryness becomes advantageous in mid-veg through flower.

## Trend Log

| Date | Reading | Notes |
|------|---------|-------|
| 2026-03-19 | 46% (low 39%) ⚠️ | Below seedling target; humidifier not yet added |
| 2026-03-20 | 45% ⚠️ | Still low; room humidifier being added |
| 2026-03-21 | 58% (up from 39%) | Improved; spike to 89% overnight ⚠️ |
| 2026-03-21 | 81% overnight ⚠️ | Humidifier too high — damping off risk; dial back to 65–70% |
| 2026-03-23 | 49% ⚠️ | Tent RH still low; humidifier cranked |
| 2026-03-23 | 63.9% ✅ | Improved — in range |
| 2026-03-28 | 58% ✅ | Acceptable |
| 2026-04-01 | 75% ⚠️ | At ceiling of seedling target; watch damping off |
| 2026-04-02 | 76% ⚠️ | Above target; reduce |
| 2026-04-03 | 73% ⚠️ | Ceiling of acceptable range |
| 2026-04-05 | 75% ⚠️ | Consistently elevated |
| 2026-04-08 | 42% → 70% ⚠️ | VPD swing incident: humidifier off → RH dropped to 42% (VPD 2.03 kPa); restored to 70% (VPD 0.89 kPa) → [2026-04-08](../daily/2026-04-08.md) |

## Notable Events
- **2026-03-20** — Dome propped open, room humidifier added to tent after RH consistently below 50% → [2026-03-27 daily](../daily/2026-03-27.md)
- **2026-03-21** — RH spiked to 81–89% overnight from humidifier — damping off risk; dial back to 65–70%
- **Ongoing April** — RH running 70–76%, persistently at or above ceiling; reduce humidifier output or increase exhaust fan speed as plants move into veg phase
- **2026-04-08** — VPD swing incident: humidifier off caused RH to drop to 42% and VPD to spike to 2.03 kPa before recovering to 70% / 0.89 kPa. RH oscillations are more stressful than a steady suboptimal value — keep humidifier running consistently
- **2026-04-14** — Decided to move to closed-loop humidifier control (bang-bang hysteresis). Initial plan was an SSR driven by the Arduino Nano; superseded before deployment. See [original decision (superseded)](../decisions/2026-04-14-humidifier-relay-control.md).
- **2026-04-17** — Switched actuator to a **TP-Link Kasa Ultra Mini EP10 smart plug** controlled from a Python service on the `dirt` host via [`python-kasa`](https://github.com/python-kasa/python-kasa). No mains wiring, no custom enclosure; control algorithm unchanged. See [current decision](../decisions/2026-04-17-humidifier-kasa-ep10.md) and [hardware page](../hardware/humidifier-control.md).

## Planned Control System

Manual humidifier adjustments are being replaced with a bang-bang (hysteresis) controller on the `dirt` host:

- **Sensor:** existing DHT22 on the Arduino Nano tent-hub (unchanged).
- **Actuator:** Raydrop 4L ultrasonic humidifier plugged into a **TP-Link Kasa Ultra Mini EP10** smart plug. The plug is commanded over the LAN via [`python-kasa`](https://github.com/python-kasa/python-kasa).
- **Logic:** `ON` when `RH < target − deadband`, `OFF` when `RH > target + deadband`, hold otherwise. Initial target = 60% RH, deadband = ±3%.
- **Guards:** minimum off-time between switches (relay protection + let the last pulse reach the sensor) and a max-on safety timeout.
- **Failsafe:** plug forced OFF on stale or invalid DHT22 readings (prefer brief dryness over damping-off).

Phase-specific setpoints will be managed in host-side config; migration to a proper setpoint table is planned when additional tent actuators (dehumidifier, exhaust modulation, heater) come online. See the [hardware page](../hardware/humidifier-control.md) for the algorithm sketch, library notes, and safety considerations.
