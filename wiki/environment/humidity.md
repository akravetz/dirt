---
title: Environment — Humidity
type: environment
sources: [raw/chat-history/all-chat-summary.md, raw/chat-history/bible.md, raw/chat-history/memory.md]
related: [wiki/environment/temperature.md, wiki/concepts/vpd.md, wiki/overview.md, wiki/hardware/humidifier-control.md, wiki/decisions/2026-04-17-humidifier-kasa-ep10.md]
created: 2026-04-06
updated: 2026-05-08
---


# Humidity (RH)

## Targets by Phase

| Phase | Target RH | VPD |
|-------|-----------|-----|
| Seedling | 65–75% | 0.4–0.8 kPa |
| Veg | 45–55% | 0.9–1.1 kPa |
| Early Flower (days 0–20 of 12/12) | 45–50% | 1.0–1.3 kPa |
| Late Flower (day 21+ of 12/12) | 40–45% | 1.2–1.5 kPa |

VPD is the control-loop setpoint; RH is informational (temperature determines what RH corresponds to a given VPD). The canonical source of truth for these bands is `dirt.services.grow_state.STAGE_TARGETS` — the humidifier loop and the voice status tool both read it. See [hardware/humidifier-control.md](../hardware/humidifier-control.md) for the deployed algorithm and [decision 2026-04-18](../decisions/2026-04-18-vpd-targeting.md) for the rationale.

**Current phase:** Early flower — target VPD 1.0–1.3 kPa.

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
| 2026-04-27 | 64.57% now ⚠️ / 64.41% overnight avg ⚠️; VPD 1.01 kPa now ✅ / 0.86 kPa overnight ✅ | VPD fully recovered across all three windows (0.86/1.05/1.01 kPa) — major reversal from two-day below-floor streak. Recovery driven by ~11% daytime RH drop (75.6% → 64.6%) following humidifier reduction. Overnight RH five-night upward drift continues (52.1% → 64.4%); all windows still above 45–55% veg target. → [2026-04-27](../daily/2026-04-27.md) |
| 2026-04-28 | 56.0% now ⚠️ / 65.55% overnight avg ⚠️; VPD 1.19 kPa now ✅ / 0.80 kPa overnight ✅ | **Govee H7142 first full day**: daytime RH dropped 8.6 points (64.57% → 56.0%) vs. prior day; VPD improved to 1.19 kPa ✅. Overnight RH 65.55% — still above veg target but represents first overnight under H7142 PI control; assess tomorrow. Overnight VPD 0.80 kPa — at the floor of the 0.8–1.2 veg band. → [2026-04-28](../daily/2026-04-28.md) |
| 2026-04-29 | 64.04% now ⚠️ / 67.41% overnight avg ⚠️; VPD 0.98 kPa now ✅ / 0.76 kPa overnight ⚠️ | **H7142 second overnight needs tuning**: overnight RH worsened 65.55% → 67.41%, and overnight VPD slipped below the 0.8 kPa floor. Morning/now VPD remains in range, but visible mist + 64% now RH means the tent is still wetter than the veg RH guide. → [2026-04-29](../daily/2026-04-29.md) |
| 2026-05-01 | 71.3% now ⚠️ / 66.79% overnight avg ⚠️; VPD 0.84 kPa now ✅ / 0.76 kPa overnight ⚠️ | Humidity remains high and now climbed to 71.3% by the current reading. VPD is technically in range during lights-on but near the wet edge; overnight remains below the 0.8 kPa floor. H7142/night gating and clearing behavior still need review. → [2026-05-01](../daily/2026-05-01.md) |
| 2026-05-02 | 68.05% now ⚠️ / 70.95% overnight avg ⚠️; VPD 1.07 kPa now ✅ / 0.62 kPa overnight 🔴 | Overnight regressed hard: RH 70.95% with VPD 0.62 kPa, the wettest/coldest lights-off profile since the H7142 cutover. Day VPD recovered only because temperature rose to 77-79°F. Prioritize night off-gate/clearing and keeping lights-off temperature above 68°F. → [2026-05-02](../daily/2026-05-02.md) |
| 2026-05-03 | 73.88% now 🔴 / 73.75% overnight avg 🔴; VPD 0.84 kPa now 🔴 / 0.61 kPa overnight 🔴 | Flower flip day tightened the target to 1.0-1.3 kPa VPD and 45-50% RH guide; all windows are now too wet for early flower despite acceptable temperature. Prioritize drying/clearing and humidifier off-gate behavior. → [2026-05-03](../daily/2026-05-03.md) |
| 2026-05-04 | 62.56% now ⚠️ / 63.96% overnight avg ⚠️; VPD 1.33 kPa now ⚠️ / 0.76 kPa overnight 🔴 | Lights-on VPD improved into/near the early-flower band (morning 1.12 kPa, now 1.33 kPa), but overnight remains too wet. Control goal shifts to smoothing the day/night profile: dry the 00-06 window without pushing lights-on above 1.3 kPa. → [2026-05-04](../daily/2026-05-04.md) |
| 2026-05-05 | 63.19% now ⚠️ / 72.75% overnight avg 🔴; VPD 1.13 kPa now ✅ / 0.56 kPa overnight 🔴 | Overnight regressed sharply wetter after yesterday's partial improvement, while lights-on VPD stayed in range at the floor-to-mid band (morning 1.00 kPa, now 1.13 kPa). The priority is drying/clearing the 00-06 window without adding lights-on mist. → [2026-05-05](../daily/2026-05-05.md) |
| 2026-05-06 | 65.18% now ⚠️ / 73.36% overnight avg 🔴; VPD 0.95 kPa now 🔴 / 0.51 kPa overnight 🔴 | Early-flower VPD missed target in all windows: overnight stayed cold/wet, morning only recovered to 0.90 kPa, and the current reading remained below the 1.0 kPa floor. Prioritize lights-off clearing and passive-intake verification before adding humidity. → [2026-05-06](../daily/2026-05-06.md) |
| 2026-05-07 | 61.46% now ⚠️ / 69.16% overnight avg 🔴; VPD 1.07 kPa now ✅ / 0.61 kPa overnight 🔴 | RH improved in every window and lights-on VPD recovered to target (morning 1.01, now 1.07 kPa). The remaining miss is still the 00-06 window, which is too cool/wet for early flower despite improving from May 6. → [2026-05-07](../daily/2026-05-07.md) |
| 2026-05-08 | 68.78% now 🔴 / 76.95% overnight avg 🔴; VPD 0.82 kPa now 🔴 / 0.45 kPa overnight 🔴 | Wet regression: VPD missed the early-flower target in every window, with RH high all day and the overnight window back near seedling-level VPD. Treat airflow/clearing and humidifier off-gate verification as urgent. → [2026-05-08](../daily/2026-05-08.md) |

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
- **2026-04-27** — VPD recovered to target across all three windows (0.86/1.05/1.01 kPa) after two-day below-floor streak. Recovery driven primarily by humidifier output reduction (~11% daytime RH drop: 75.6% → 64.6%). Overnight RH five-night upward drift continues (52.1% → 64.4%); all windows still above 45–55% veg target. Day temperature 73.7°F still below 74°F floor but recovering. → [2026-04-27](../daily/2026-04-27.md)
- **2026-04-27 evening** — Humidifier hardware cutover: Raydrop 4L + Kasa EP10 retired; **GoveeLife H7142** (6 L, 9 Manual-mode levels via Govee Public API v2) deployed as the new actuator. PI controller (live in shadow mode since 2026-04-25) promoted to authoritative; bang-bang retired. PI gain `Kc` bumped from 8.0 → 40.0 to engage at typical veg overshoot levels. See [decision 2026-04-27](../decisions/2026-04-27-h7142-deployed.md).
- **2026-04-28** — Govee H7142 first full 24-hour cycle. Daytime RH dropped 8.6 points (64.57% → 56.0%) vs. prior day; VPD held at 1.19 kPa ✅. Overnight RH 65.55% — above veg target but representing the first overnight under H7142 PI control with -0.3 kPa night offset; performance assessment pending tomorrow. → [2026-04-28](../daily/2026-04-28.md)
- **2026-04-29** — Second H7142 overnight underperformed: RH rose to 67.41% and VPD fell to 0.76 kPa. Daytime VPD remains acceptable, so review controller logs/night offset/off-gate behavior before changing hardware. → [2026-04-29](../daily/2026-04-29.md)
- **2026-05-01** — Wet-edge pattern persists: overnight VPD again averaged 0.76 kPa and current RH rose to 71.3%. Daytime VPD is barely acceptable, so prioritize drier control behavior and clearing before adding any humidification. → [2026-05-01](../daily/2026-05-01.md)
- **2026-05-02** — Overnight VPD fell further to 0.62 kPa while RH averaged 70.95%. Morning/current VPD recovered to 1.09/1.07 kPa because the tent warmed to 77-79°F, not because RH returned to the veg guide. The problem has narrowed to lights-off humidity clearing plus low night temperature. → [2026-05-02](../daily/2026-05-02.md)
- **2026-05-03** — Day 0 of 12/12 exposes the humidity problem under early-flower targets: RH 70-74% and VPD 0.61-0.91 kPa are all wetter than target. Temperature is acceptable, so the actionable lever is drying/clearing rather than adding heat. → [2026-05-03](../daily/2026-05-03.md)
- **2026-05-04** — First post-flip improvement: RH dropped about 11 points from yesterday and morning VPD reached 1.12 kPa, but overnight VPD is still only 0.76 kPa and the current reading slightly overshoots at 1.33 kPa. This is now a control-profile problem rather than a simple "more dry" problem. → [2026-05-04](../daily/2026-05-04.md)
- **2026-05-05** — Overnight VPD regressed to 0.56 kPa with 72.75% RH, the wettest early-flower overnight since the flip. Lights-on VPD remained usable (1.00 morning, 1.13 now), so the next control step is targeted lights-off drying/clearing, plus the planned 6-inch low passive intake duct with a light-trap bend on 2026-05-06. → [2026-05-05](../daily/2026-05-05.md)
- **2026-05-06** — VPD stayed below early-flower target across all windows (0.51 overnight, 0.90 morning, 0.95 now). This is worse than May 5's lights-on recovery and confirms the issue is not limited to the dark window; airflow/clearing and the low passive intake need verification against the next cycle. → [2026-05-06](../daily/2026-05-06.md)
- **2026-05-07** — Lights-on VPD recovered to target after May 6's all-window miss: morning 1.01 kPa and now 1.07 kPa. Overnight improved but remains too wet at 0.61 kPa, so the control problem has narrowed back to lights-off clearing/temperature rather than daytime humidity addition. → [2026-05-07](../daily/2026-05-07.md)
- **2026-05-08** — The May 7 lights-on recovery did not hold. VPD fell below target in all windows (0.45 overnight, 0.67 morning, 0.82 now), with RH 68.78-76.95%. This reopens the daytime clearing problem and makes passive intake/exhaust verification urgent before the next dark window. → [2026-05-08](../daily/2026-05-08.md)

## Deployed Control System

PI-driven continuous-intensity VPD controller on the `dirt` host (deployed 2026-04-27 on the **GoveeLife H7142** Wi-Fi humidifier — see [decision 2026-04-27](../decisions/2026-04-27-h7142-deployed.md) and [hardware/humidifier-control.md](../hardware/humidifier-control.md)):

- **Sensor:** Sensirion SHT45 (PTFE cap, I²C `0x44`, GPIO 4/5) on the combined fan-controller ESP32-C3 SuperMini. Replaced the Arduino Nano + BME280 on 2026-04-23 after the BME280 was found to be +3.5°F / +23%RH off vs a calibrated handheld reference — see [decision 2026-04-22](../decisions/2026-04-22-sht45-tent-node-esp32.md). Historical `source=arduino` tent readings prior to 2026-04-23 00:22 MDT carry a +23%RH / +3.5°F caveat. `vpd_kpa`, `temperature_f`, `dew_point_f` derived at ingest from `temperature_c + humidity_pct`.
- **Actuator:** **GoveeLife H7142** (6 L cool-mist ultrasonic, 9 Manual-mode mist levels via Govee Public API v2). Wi-Fi-native; cloud-only API. Replaced the Raydrop 4L + Kasa EP10 stack 2026-04-27.
- **Logic:** Pure-function PI controller emits `u_pct ∈ [0, 100]`; a 9-bucket quantizer with hysteresis at level boundaries maps that to a discrete H7142 Manual-mode level. Threshold cutoff (with hysteresis) gates `u_pct → OFF` below ~5%. Setpoint = stage VPD upper band, with -0.3 kPa night offset.
- **Guards:** Failsafe `u=0` on stale/missing VPD, outside-lights-window, or RH-ceiling envelope guard (mold prevention). Anti-windup integrator clamp at ±50%.
- **Watchdogs:** `lackWaterEvent` (rising-edge Telegram alert when the H7142 reports tank empty) + `suspected_ineffective` (commanded mist for ≥20 min with VPD drop <0.15 kPa).
- **Failsafe:** device commanded OFF on any ambiguity (prefer brief dryness over damping-off).

Full algorithm + state-logging spec: [hardware/humidifier-control.md](../hardware/humidifier-control.md).
