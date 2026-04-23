---
title: "Continuous Humidifier Intensity: Replace Raydrop Analog Potentiometer with MCU-Controlled Mist Rate"
type: decision
sources: []
related:
  - wiki/hardware/humidifier-control.md
  - wiki/hardware/ac-infinity-fan-control.md
  - wiki/concepts/multi-actuator-environment-control.md
  - wiki/decisions/2026-04-17-humidifier-kasa-ep10.md
  - wiki/decisions/2026-04-18-vpd-targeting.md
  - wiki/decisions/2026-04-22-sht45-tent-node-esp32.md
created: 2026-04-23
updated: 2026-04-23
---

# Decision: Replace Raydrop Analog Potentiometer with MCU-Controlled Mist Intensity

**Date:** 2026-04-23
**Status:** Accepted — Phase 1 (investigation) scheduled; Phases 2–4 contingent on Phase 1 findings.

## Context

The 2026-04-23 morning operational session surfaced three related issues with the current humidifier control loop:

1. **Bang-bang oscillation.** The Raydrop running for one minute drops tent VPD by ~0.45 kPa — ~4× the original 0.1 kPa deadband. Plug relay clicked once per 60 s until we widened the deadband to 0.3 kPa. See `wiki/log.md` "VPD Loop Flapping" entry.

2. **Hidden-input failure mode.** With the fan at 40 % duty and the Raydrop's analog dial turned down, the Kasa plug pinned ON continuously for 1h 40m while VPD *climbed* from 1.20 → 1.50 kPa. The software was doing exactly the right thing; the physical mist-output rate had been manually set below the exhaust rate. The loop has no visibility into the dial position, so it can't distinguish "need more mist" from "already at max mist." See `hardware/humidifier-control.md` "Coupling with fan exhaust rate."

3. **Latch-on-empty with full tank.** Separately, the Raydrop's low-water float sensor latched the red LED / disabled-ultrasonic state even with water in the tank. Caught by the new stuck-actuator watchdog. See `hardware/humidifier-control.md` "Red LED on the Raydrop = low-water sensor latch."

Root pattern across all three: the humidifier is a **binary, single-speed actuator** with a **manually-set intensity cap**. The control loop's only lever is the Kasa plug on/off; the physical knob is a second control input that software can't observe or modulate. Every class of problem above traces back to this mismatch between the discrete output we can command and the continuous output the plant actually responds to.

## Decision

Add MCU control of the Raydrop's mist intensity so the loop can modulate output continuously (0–100 %) instead of bang-banging the Kasa plug.

**Hardware path**: open the Raydrop KC-RD03A, locate the intensity potentiometer, and replace/augment it with a digital potentiometer (MCP4131 or MCP41010) or DAC output driven by the existing **fan-controller ESP32-C3 node** (already in the tent, already has WiFi + OTA + HTTP control surface). The Kasa plug stays in the loop as the hard-off / power-cut authority.

**Firmware path**: extend `firmware/fan_controller` with a `POST /mist {"intensity_pct": 0..100}` + `GET /mist` endpoint mirroring the existing `/fan` surface. Fail-to-zero on MCU crash and at boot.

**Host-side control**: replace the bang-bang in `HumidifierLoopService` with a **PI controller on VPD error** (proportional + integral, anti-windup clamp, output in [0, 100]). A sub-threshold intensity (e.g. < 5 %) commands the Kasa plug OFF entirely to avoid running the ultrasonic at useless levels. The Kasa plug remains ON whenever intensity ≥ threshold; lights-off-prep and failsafe-stale-sensor still force the plug OFF as today.

The PI loop is an **inside-class** intensity controller, not a replacement for the multi-actuator dispatch architecture — see [multi-actuator-environment-control.md](../concepts/multi-actuator-environment-control.md) for where this fits once dehumidifier + PWM fan arrive.

## Alternatives Considered

| Option | Why rejected |
|---|---|
| PWM the Kasa plug at 1 Hz with variable duty cycle | Kasa EP10 relay is mechanical, rated ~10⁴–10⁵ cycles. At 1 Hz duty-cycle we'd consume the relay's lifetime in hours. Unacceptable. |
| Replace the Raydrop with a commercial servo-controlled humidifier | $200+ vs $1 of digipot. No meaningfully better outcome — the control problem is the same either way. |
| Widen the deadband further (0.3 → 0.5 kPa) | Treats the symptom. VPD would swing wider; plants don't care much about 0.2 kPa differences but the fan/humidifier coupling failure mode stays. |
| Skip the intensity control, just add the stuck-actuator watchdog (which we already did) | The watchdog catches the stuck-on-empty case but does nothing for actuator-overshoot oscillation or the fan-coupling saturation. Necessary but not sufficient. |
| Run bigger humidifier dial + narrower deadband | Same failure mode in reverse: at higher dial setting, one pulse overshoots even further, and the deadband has to grow. The physics isn't fixable in software. |
| Do nothing until dehumidifier + PWM fan arrive, then redesign everything | Deferring one easy single-actuator win for a full-system rewrite gives up months of improved stability for no structural benefit. The multi-actuator doc explicitly accommodates continuous actuators. |

## Consequences

- **Humidifier VPD response becomes smooth.** PI output tracks VPD setpoint within ±0.05 kPa (estimate) instead of the current ±0.3 kPa sawtooth. No audible relay clicks except at mode boundaries.
- **Deadband can shrink.** The 0.3 kPa value was sized for bang-bang overshoot, not sensor noise. After MCU control lands, the deadband reverts toward sensor-noise-sized (~0.05–0.1 kPa).
- **The "turn the Raydrop dial" operational gotcha disappears.** Dial setting is either removed entirely (pot replaced with digipot) or relegated to a "master gain" that the MCU overrides; no more hidden input to the control stack.
- **Fan-coupling failure mode collapses.** If fan duty changes, the PI integrator absorbs the new steady-state automatically rather than requiring a human to notice and retune.
- **Red-LED latch still possible.** MCU intensity control does not fix the float-sensor latch — that's a Raydrop firmware issue. Watchdog stays in place.
- **Stuck-actuator watchdog needs a small tweak.** Today it fires on `plug ON + VPD not falling`. After intensity control it should fire on `intensity > 0 + VPD not falling` — same logic, one input variable change.
- **Multi-actuator env-control doc's actuator model shifts.** `hum_on: bool` becomes `hum_intensity: 0..100`. Dispatch classes and cross-actuator invariants are unchanged. See the 2026-04-23 revision block on `concepts/multi-actuator-environment-control.md`.
- **Warranty void on the Raydrop.** $40 unit. Have a spare on hand before opening.
- **Control-loop complexity +1.** PI loop has two gains (Kp, Ki) to tune plus an anti-windup clamp. Mitigations: tune empirically (Ziegler-Nichols step response or manual crank-until-oscillates), log integrator state in the `humidifier` observability stream for diagnosability, start with Kp only and add Ki once proportional tracking is stable.

## Rollout

See [epic: continuous-humidifier](../../docs/epics/continuous-humidifier/README.md) for the tracked phase breakdown and issues.

**Phase 1 — Investigation (1 evening).** Open the Raydrop. Identify the driver IC (chip markings → datasheet). Probe the pot with multimeter + scope; confirm whether the intensity input is DC voltage (digipot territory), PWM duty cycle (drive directly from ESP32), or something encoded. **Stop gate:** if the circuit turns out to be weird (encoded comms, HV isolation, etc.), reassess before proceeding. No commitment to Phases 2-4 until Phase 1 reports back.

**Phase 2 — Hardware (1 evening).** Based on Phase 1 findings, wire digipot or DAC between the fan-controller ESP32 and the Raydrop's intensity input. Keep the Kasa plug for hard-off authority. Add a reasonable fail-to-zero on boot.

**Phase 3 — Firmware (half a day).** Extend `firmware/fan_controller` with `POST /mist` and `GET /mist` endpoints. Mirror the `/fan` patterns. Update `FanNodeClient` → `MistClient` (or extend) in `apps/shared`.

**Phase 4 — PI control loop (1–2 days incl. tuning).** Replace bang-bang in `HumidifierLoopService` with PI. Integrator state in `humidifier` observability stream. Stuck-actuator watchdog threshold updated. Deadband reduced. End-to-end test through a lights-on/lights-off cycle.

**Phase 5 — Retire the physical dial (optional).** If the pot is replaced fully (not just augmented), remove the knob or mark it "unused — software-controlled." Documentation pass on hardware page.

## Not in Scope

- **PID (with derivative).** D term on a VPD signal with the SHT45's heater-cycle noise floor is not going to be useful. PI only.
- **Dehumidifier integration.** Separate decision when the dehumidifier arrives.
- **PWM fan control philosophy.** The fan already supports PWM via `/fan`; how it integrates into the multi-actuator loop is the `multi-actuator-environment-control.md` doc's problem.
- **Auto-tuning / adaptive gains.** Manual tuning is fine for a problem this small.
- **Removing the Kasa plug.** The plug remains as the hard-off authority — MCU can modulate intensity, but the plug is still how we cut power completely (failsafe, lights-off, alert response).
