# Epic: Continuous Humidifier Intensity Control

Status: planning
Priority: medium
Created: 2026-04-23

## Goal

Replace the Raydrop humidifier's binary on/off control with continuous mist intensity (0–100 %), driven by a PI loop on tent VPD. Collapses three classes of operational failures observed 2026-04-23: bang-bang overshoot oscillation, fan-coupling actuator saturation, and "hidden analog dial" operational gotcha. Rationale, alternatives, and acceptance live in [wiki decision 2026-04-23](../../../wiki/decisions/2026-04-23-raydrop-mcu-mist-control.md); this epic tracks the work.

## Scope

- **In scope**
  - Open the Raydrop KC-RD03A and reverse-engineer the intensity control circuit.
  - Add a digipot / DAC driven by the existing fan-controller ESP32-C3 (already in the tent).
  - Extend `firmware/fan_controller` with `POST /mist` / `GET /mist` endpoints.
  - Shared Python client (`MistClient` or extend `FanNodeClient`).
  - Replace bang-bang in `HumidifierLoopService` with a PI controller on VPD error, with anti-windup clamp and a sub-threshold Kasa-plug cutoff.
  - Update the stuck-actuator watchdog to key off `intensity > 0 + VPD not falling` instead of `plug ON + VPD not falling`.
  - Narrow the VPD deadband once intensity control lands (currently 0.3 kPa — actuator-overshoot-sized).
  - Integrator state logged in the `humidifier` observability stream for diagnosability.
  - Revision block + per-class plan-shape update in `wiki/concepts/multi-actuator-environment-control.md` (landed in `5b8698a`).
- **Out of scope**
  - PID with derivative term — the SHT45 heater-cycle noise floor makes D unhelpful.
  - Dehumidifier integration (separate decision when the unit arrives).
  - PWM fan control philosophy (already covered by `/fan` endpoint + the multi-actuator doc).
  - Removing the Kasa plug — it stays as hard-off / power-cut authority.
  - Auto-tuning / adaptive gains. Manual tuning is enough.

## Phases

Phased rollout with a hard stop-gate after Phase 1. Each phase maps 1:1 to a GitHub issue labeled `epic:continuous-humidifier`.

1. **Phase 1 — Investigation.** Open the Raydrop. Identify the ultrasonic driver IC (chip markings → datasheet). Probe the intensity potentiometer with multimeter + scope; confirm DC voltage vs PWM vs encoded comms. Decide digipot-vs-DAC-vs-direct-PWM based on findings. Write investigation notes into `debug/raydrop-re/` and back to the decision doc as a revision block. **This is the stop gate**: if the circuit is weird (encoded comms, HV isolation, atypical driver), reassess before proceeding.
2. **Phase 2 — Hardware.** Wire the chosen control mechanism between the fan-controller ESP32 and the Raydrop's intensity input. Keep the Kasa plug in the loop for hard-off authority. Fail-to-zero on boot and on MCU crash.
3. **Phase 3 — Firmware.** `POST /mist {"intensity_pct": 0..100}` + `GET /mist` on `firmware/fan_controller`, mirroring `/fan`. Shared-client update in `apps/shared/src/dirt_shared/services/`.
4. **Phase 4 — PI control loop.** Replace bang-bang in `HumidifierLoopService`. Log integrator + output in the `humidifier` stream. Update the stuck-actuator watchdog trigger. Narrow the deadband. Tune Kp (and Ki if needed) empirically through a full lights-on/off cycle.
5. **Phase 5 — Physical cleanup (optional).** Remove or relabel the physical dial on the Raydrop if the pot was replaced fully. Hardware-page pass.

## Acceptance Criteria

- With the fan at any duty in [25, 60] %, tent VPD tracks the stage upper edge within ±0.1 kPa across a full 18-h lights-on period — no bang-bang oscillation, no sustained off-band excursions.
- Kasa-plug state transitions drop from today's ~once-per-minute to ≤ 6 per day (once-per-mode-change rather than once-per-cycle).
- The "Raydrop dial" is no longer a control input the operator has to reason about — either removed physically or overridden in software, documented on the hardware page.
- `suspected_stuck` watchdog still fires on the Raydrop low-water-latch failure mode (re-verified with a deliberate drained-tank test).
- Control-loop integrator state is visible in `var/logs/humidifier/*.jsonl` for post-hoc tuning analysis.
- `HumidifierLoopService` tests pass; at least one new property-style test covers PI output monotonicity (higher VPD error → non-decreasing commanded intensity, within saturation).

## Risks

- **Magic smoke on the Raydrop driver board.** $40 unit, have a spare on hand before opening.
- **PI tuning instability.** Mitigation: start with Kp-only, add Ki once proportional tracking is stable. Dry runs on a known-good lights cycle before letting the loop run unattended.
- **Digipot / DAC failure mode during power loss.** Design for fail-to-zero: digipot boots to 0 or last-persisted value; firmware defaults to intensity=0 on boot.

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:continuous-humidifier"`

## Related

- Decision: [wiki/decisions/2026-04-23-raydrop-mcu-mist-control.md](../../../wiki/decisions/2026-04-23-raydrop-mcu-mist-control.md)
- Architecture context: [wiki/concepts/multi-actuator-environment-control.md](../../../wiki/concepts/multi-actuator-environment-control.md)
- Current loop: [wiki/hardware/humidifier-control.md](../../../wiki/hardware/humidifier-control.md)
- Companion fan node: [wiki/hardware/ac-infinity-fan-control.md](../../../wiki/hardware/ac-infinity-fan-control.md)
