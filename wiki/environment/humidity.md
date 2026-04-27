---
title: Environment — Humidity
type: environment
sources: [raw/chat-history/all-chat-summary.md, raw/chat-history/bible.md, raw/chat-history/memory.md]
related: [wiki/environment/temperature.md, wiki/concepts/vpd.md, wiki/overview.md, wiki/hardware/humidifier-control.md, wiki/decisions/2026-04-17-humidifier-kasa-ep10.md]
created: 2026-04-06
updated: 2026-04-24
---


# Humidity (RH)

## Targets by Phase

| Phase | Target RH | VPD |
|-------|-----------|-----|
| Seedling | 65–75% | 0.4–0.8 kPa |
| Veg | 45–55% | 0.8–1.2 kPa |
| Early Flower (days 0–20 of 12/12) | 45–50% | 1.0–1.3 kPa |
| Late Flower (day 21+ of 12/12) | 40–45% | 1.2–1.5 kPa |

VPD is the control-loop setpoint; RH is informational (temperature determines what RH corresponds to a given VPD). The canonical source of truth for these bands is `dirt.services.grow_state.STAGE_TARGETS` — the humidifier loop and the voice status tool both read it. See [hardware/humidifier-control.md](../hardware/humidifier-control.md) for the deployed algorithm and [decision 2026-04-18](../decisions/2026-04-18-vpd-targeting.md) for the rationale.

**Current phase:** Early veg — target VPD 0.8–1.2 kPa.

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
| 2026-04-18 | 59.13% now ✅ / 76.95% overnight avg ⚠️ | Closed-loop service holding day period in target; overnight with lights off + temp 63°F, RH spikes to 77% (VPD 0.46 kPa — seedling range); significant day/night VPD swing 0.46 → 1.31 kPa → [2026-04-18](../daily/2026-04-18.md) |
| 2026-04-19 | 54.69% now ✅ / 70.79% overnight avg ⚠️; VPD 1.51 kPa now ⚠️ / 0.68 kPa overnight | Overnight RH improving (76.95% → 70.79%); overnight VPD improving (0.46 → 0.68 kPa); daytime VPD above 1.2 ceiling → [2026-04-19](../daily/2026-04-19.md) |
| 2026-04-20 | 62.37% now ✅ / 74.37% overnight avg ⚠️; VPD 1.12 kPa now ✅ / 0.57 kPa overnight | Daytime VPD in target at 14:00 (1.12 kPa ✅) — first time in range; overnight RH regressed (70.79% → 74.37%) — `dirt-hwd` restart still pending → [2026-04-20](../daily/2026-04-20.md) |
| 2026-04-22 | 69.19% now ⚠️ / 52.06% overnight avg ✅; VPD 0.84 kPa now ✅ / 1.21 kPa overnight ✅ | **Overnight breakthrough**: RH 74.37% → 52.06% (in 45–55% veg target); VPD 0.57 → 1.21 kPa overnight; `dirt-hwd` restart confirmed effective; afternoon RH elevated (69%) but VPD in range (0.84 kPa) due to lower temp → [2026-04-22](../daily/2026-04-22.md) |
| 2026-04-24 | 70.63% now ⚠️ / 51.81% overnight avg ✅; VPD 0.90 kPa now ✅ / 1.18 kPa overnight ✅ | Second consecutive overnight in 45–55% veg target; afternoon RH elevated (70.63%) but VPD in range (0.90 kPa) — proper tent temp (76°F) now providing the margin → [2026-04-24](../daily/2026-04-24.md) |
| 2026-04-26 | 75.63% now ⚠️ / 59.48% overnight avg ⚠️; VPD 0.68 kPa now 🔴 / 0.94 kPa overnight ✅ | Afternoon VPD below floor second consecutive day (0.68 kPa; yesterday 0.63). Overnight RH now above 45–55% veg target (59.48%) — all windows simultaneously above RH target. Temperature regression (73°F day) is compounding: cool tent + high RH = low VPD. → [2026-04-26](../daily/2026-04-26.md) |

## Notable Events
- **2026-03-20** — Dome propped open, room humidifier added to tent after RH consistently below 50% → [2026-03-27 daily](../daily/2026-03-27.md)
- **2026-03-21** — RH spiked to 81–89% overnight from humidifier — damping off risk; dial back to 65–70%
- **Ongoing April** — RH running 70–76%, persistently at or above ceiling; reduce humidifier output or increase exhaust fan speed as plants move into veg phase
- **2026-04-08** — VPD swing incident: humidifier off caused RH to drop to 42% and VPD to spike to 2.03 kPa before recovering to 70% / 0.89 kPa. RH oscillations are more stressful than a steady suboptimal value — keep humidifier running consistently
- **2026-04-14** — Decided to move to closed-loop humidifier control (bang-bang hysteresis). Initial plan was an SSR driven by the Arduino Nano; superseded before deployment. See [original decision (superseded)](../decisions/2026-04-14-humidifier-relay-control.md).
- **2026-04-17** — Switched actuator to a **TP-Link Kasa Ultra Mini EP10 smart plug** controlled from a Python service on the `dirt` host via [`python-kasa`](https://github.com/python-kasa/python-kasa). No mains wiring, no custom enclosure; control algorithm unchanged. See [current decision](../decisions/2026-04-17-humidifier-kasa-ep10.md) and [hardware page](../hardware/humidifier-control.md).
- **2026-04-18** — Overnight lights-off window: temp 63.54°F avg, RH 76.95% avg, VPD 0.46 kPa. Day period in target (53.58% morning avg, 59.13% now). Day/night VPD swing ~3× (0.46 → 1.31 kPa). Motivated the switch from fixed-RH control to VPD targeting so the humidifier stops running through cool nights automatically.
- **2026-04-18** — Switched humidifier control loop from fixed 60% RH setpoint to stage-dynamic VPD targeting (upper-band edge, 0.1 kPa deadband). VPD band reads from `dirt.services.grow_state` so veg→flower transitions shift setpoints without redeploying. See [decision 2026-04-18](../decisions/2026-04-18-vpd-targeting.md).
- **2026-04-19** — Overnight improvement continues: RH 70.79% (was 76.95%), VPD 0.68 kPa (was 0.46). Daytime VPD running above ceiling: 1.31 kPa morning, 1.51 kPa at 14:00. Lights-off-aware feedforward and dropped safety timers deployed today; should further improve overnight profile. See [decisions/2026-04-19-lights-off-aware-humidifier.md](../decisions/2026-04-19-lights-off-aware-humidifier.md) and [decisions/2026-04-19-drop-humidifier-safety-timers.md](../decisions/2026-04-19-drop-humidifier-safety-timers.md).
- **2026-04-20** — Daytime VPD reached 1.12 kPa at 14:00 — in the 0.8–1.2 veg target for the first time. Overnight profile regressed: RH 74.37% (was 70.79%), VPD 0.57 kPa (was 0.68). Regression confirms `dirt-hwd` service restart is still pending — lights-off feedforward cannot activate until restarted. → [2026-04-20](../daily/2026-04-20.md)
- **2026-04-22** — Overnight RH breakthrough: 52.06% avg (was 74.37%) — within the 45–55% veg target for the first time. Overnight VPD 1.21 kPa (was 0.57) — at the target ceiling. Both overnight metrics in veg target simultaneously for the first time this grow. Confirms `dirt-hwd` service restart activated the lights-off feedforward. Afternoon RH elevated (69.19%) but VPD (0.84 kPa) remains within target due to slightly lower tent temp (72.34°F). → [2026-04-22](../daily/2026-04-22.md)
- **2026-04-24** — Overnight RH second consecutive night in veg target (51.81%). Afternoon RH still elevated (70.63%) but VPD holds in range (0.90 kPa) because tent temperature now tracks 74–76°F properly. New steady-state pattern: overnight in target, afternoon elevated but offset by correct temperature. VPD is clean across all three windows for the second consecutive day. → [2026-04-24](../daily/2026-04-24.md)
- **2026-04-26** — Afternoon VPD below floor for second consecutive day (0.68 kPa; Apr 25: 0.63 kPa). Overnight RH drifting upward across four nights (52.06% → 51.81% → 56.68% → 59.48%) — today is the first overnight above the 45–55% veg target. All RH windows simultaneously above targets for the first time. Temperature regression (73°F daytime, below 74°F floor) is the compounding factor: cool tent limits moisture-holding capacity, so the same humidifier output produces a lower VPD. Reducing humidifier intensity during lights-on is the immediate fix. → [2026-04-26](../daily/2026-04-26.md)

## Deployed Control System

Bang-bang VPD controller on the `dirt` host:

- **Sensor:** Sensirion SHT45 (PTFE cap, I²C `0x44`, GPIO 4/5) on the combined fan-controller ESP32-C3 SuperMini. Replaced the Arduino Nano + BME280 on 2026-04-23 after the BME280 was found to be +3.5°F / +23%RH off vs a calibrated handheld reference — see [decision 2026-04-22](../decisions/2026-04-22-sht45-tent-node-esp32.md). Historical `source=arduino` tent readings prior to 2026-04-23 00:22 MDT carry a +23%RH / +3.5°F caveat. `vpd_kpa`, `temperature_f`, `dew_point_f` derived at ingest from `temperature_c + humidity_pct`.
- **Actuator:** Raydrop 4L ultrasonic humidifier plugged into a **TP-Link Kasa Ultra Mini EP10** smart plug, commanded over the LAN via [`python-kasa`](https://github.com/python-kasa/python-kasa).
- **Logic:** `ON` when `vpd > upper_band`, `OFF` when `vpd < upper_band − 0.1 kPa`. Upper band is the current stage's VPD ceiling (1.2 kPa veg / 1.3 early flower / 1.5 late flower).
- **Guards:** minimum off-time between switches (relay protection + let the last pulse reach the sensor) and a max-on safety timeout.
- **Failsafe:** plug forced OFF on stale or invalid VPD readings (prefer brief dryness over damping-off).

Full algorithm + state-logging spec: [hardware/humidifier-control.md](../hardware/humidifier-control.md).
