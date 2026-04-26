# Epic: Continuous Humidifier Intensity Control

Status: in-progress — Phase 1 paused awaiting replacement spare; Phase 4 prep work proceeding in parallel
Priority: medium
Created: 2026-04-23
Last touched: 2026-04-25

## Current state (resume point for a fresh agent)

**Where we are:** Phase 1 paused — the spare Raydrop on the bench was destroyed during disassembly. New spare on order. The primary Raydrop on the Kasa plug continues to drive the live VPD loop unchanged.

**Phase 4 prep work proceeds in parallel** during the hardware wait. Plan-of-record: [phase4-test-plan.md](phase4-test-plan.md). Most of the controller, its property tests, and the FOPDT fit against existing logs are hardware-independent — they let Phase 4 land as a config-flip rather than a bring-up once Phases 2/3 complete.

### Phase 1 hardware findings so far (unit unplugged, DMM-only)

- **Pot:** silkscreen reads `B5K` — **5 kΩ linear-taper, integrated SPST power switch** (clicks off at min rotation).
- **JST topology:** 4 wires total = 3 pot pins (outer-A / wiper / outer-B) + 1 switch tab. Switch return is internally commoned to the pot's metal chassis, which ties to one of the pot outers on the PCB — so "the switch pair" that beeped in continuity mode was (switch tab) + (chassis-tied outer).
- **Resistance sweep** across the wiper + non-chassis-outer pair (DMM 200 kΩ range, unit unplugged): smooth, monotonic, **0.002 kΩ at max-mist → 2.55 kΩ at min-mist-just-before-click**. Clean rheostat behavior.
- **2.55 kΩ vs 5 kΩ label discrepancy:** most likely explained by mechanical rotation covering ~half the electrical track (switch-cam dead zone consumes the rest). Doesn't block progress — the driver IC sees 0→~2.55 kΩ as the useful control range, and firmware will map "intensity %" to the actual observed range.
- **Photos:** `debug/raydrop-re/photos/pot-front.jpg` + `pot-back.jpg`.

### Not yet done

- **Step 1 DC voltage sweep** (unit powered). This is the next action — answers the DC-analog-vs-PWM question that gates the Phase 2 part choice.
- Photograph the ultrasonic driver IC with readable markings → `debug/raydrop-re/photos/driver-ic.jpg`. Feeds Step 3 (IC identification).
- Full PCB top-down photo → `board-top.jpg`.
- Step 2 logic-analyzer capture (only if Step 1 is inconclusive).

### Immediate next actions

**Phase 1 (blocked on hardware):** when the replacement spare arrives, walk the user through **Step 1 of [phase1-probe-checklist.md](phase1-probe-checklist.md)** — powered DC voltage sweep on the 3 pot pins to determine DC-analog vs PWM-through-RC. Findings recorded in the checklist's observations log.

**Phase 4 prep (unblocked, do now):** follow [phase4-test-plan.md](phase4-test-plan.md) order of operations:

1. Acceptance criteria + plan committed (this doc + test plan). ✅
2. **FOPDT fit script** against existing humidifier logs — `debug/humidifier-fopdt/fit.py`. ✅ Verdict: data brackets gains (Kc ≈ 8–12 %u/kPa, Ki ≈ 0.01–0.02 %u/(kPa·s) at λ = 2τ–3τ) but doesn't pin them — bang-bang segments too short for clean asymptotes. Full analysis: [fopdt-fit-findings.md](fopdt-fit-findings.md). Phase 4 ships at the low end of the bracket, refines under shadow mode + a graduated step test in Phase 2/3 acceptance.
3. **Property tests (red) for the controller.** ✅ `apps/hwd/tests/test_humidifier_pi.py` — 28 tests covering output range, monotonicity in error, failsafe stale, lights-window guards (incl. pre-lights-on ramp), RH ceiling guard, threshold + hysteresis, anti-windup bounds + release, dt invariance, clock-jump robustness, stage-flip-no-reset, output contract.
4. **Controller skeleton + placeholder gains → property tests green.** ✅ `apps/hwd/src/dirt_hwd/services/humidifier_pi.py` — pure-function `compute(cfg, state, inp) → output`. Conservative starting gains: Kc=8, Ki=0.01, threshold=5%, hysteresis=1%, integrator clamp=50%, night offset=−0.3 kPa.
5. **Shadow-mode wiring (`humidifier_shadow` log stream, no actuation).** ✅ Wired into `humidifier.py` between the existing state-change emit and the stuck-watchdog. Each tick computes PI output and logs full state (u, plug_on_shadow vs plug_on_actual, setpoint, error, P/I split, integrator, reason, plus inputs). Stream registered with 14-day retention. **Activates on next `dirt-hwd` restart.** No actuator change — bang-bang still drives the plug.
6. **Plant-in-loop tests parameterized by step #2 output.** ✅ `apps/hwd/tests/test_humidifier_pi_plant.py` — 16 tests covering step response, lights-cycle transition, fan-coupling step (the specific failure mode that motivated the rewrite), and integrator-clamp saturation. Plant simulator parametrized over τ/K/V_dry_eq corners from the FOPDT bracket. Tests assert behaviors not numbers.
7. Replay tests after ≥ 24 h shadow data.

### BOM consequence to flag (don't order yet)

None of the three MCP4131 variants on order (10k / 50k / 100k) is a direct match for this 5 kΩ pot. **If Step 1 confirms DC-analog rheostat, we'll need MCP4131-502E/P (5 kΩ, 128-step)** — not currently in the BOM. Decision is gated on the Step 1 verdict; if the Raydrop turns out to be a PWM case, the digipot is moot and we drive directly from ESP32 LEDC.

**Do not proceed past Phase 1 without user review.** The Phase 1 → Phase 2 matrix at the bottom of [bom.md](bom.md) tells you which parts get used based on the probe verdict; if the verdict lands outside the matrix (e.g. encoded comms), stop and reassess before ordering more parts or writing firmware.

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

1. **Phase 1 — Investigation.** Open the Raydrop. Identify the ultrasonic driver IC (chip markings → datasheet). Probe the intensity potentiometer with multimeter + HiLetgo logic analyzer; confirm DC voltage vs PWM vs encoded comms. Decide digipot-vs-DAC-vs-direct-PWM based on findings. Step-by-step walkthrough: [phase1-probe-checklist.md](phase1-probe-checklist.md). Scratch artifacts (photos, `.sr` captures) go to `debug/raydrop-re/` (gitignored); final verdict pasted into the decision doc as a revision block. **This is the stop gate**: if the circuit is weird (encoded comms, HV isolation, atypical driver), reassess before proceeding.
2. **Phase 2 — Hardware.** Wire the chosen control mechanism between the fan-controller ESP32 and the Raydrop's intensity input. Keep the Kasa plug in the loop for hard-off authority. Fail-to-zero on boot and on MCU crash.
3. **Phase 3 — Firmware.** `POST /mist {"intensity_pct": 0..100}` + `GET /mist` on `firmware/fan_controller`, mirroring `/fan`. Shared-client update in `apps/shared/src/dirt_shared/services/`.
4. **Phase 4 — PI control loop.** Replace bang-bang in `HumidifierLoopService`. Log integrator + output in the `humidifier` stream. Update the stuck-actuator watchdog trigger. Narrow the deadband. Tune Kp (and Ki if needed) empirically through a full lights-on/off cycle.
5. **Phase 5 — Physical cleanup (optional).** Remove or relabel the physical dial on the Raydrop if the pot was replaced fully. Hardware-page pass.

## Acceptance Criteria

Authoritative list lives in [phase4-test-plan.md](phase4-test-plan.md) §"Acceptance criteria (refined)". Headline criteria:

1. **Tracking.** Fan duty ∈ [25, 60] %, VPD within ±0.1 kPa of upper edge across an 18-h lights-on period.
2. **Switching count.** Kasa-plug transitions ≤ 6 / day (down from ~once-per-minute today).
3. **Envelope respected.** RH never exceeds `stage_rh_max` due to controller action — RH ceiling guard verified in unit + soak.
4. **Dial retired.** No longer a control input the operator must reason about.
5. **Watchdog still works.** `suspected_stuck` fires on a deliberate drained-tank test with the upgraded `u > 0` trigger.
6. **Diagnosability.** Integrator state, P/I split, error, and `u` per-tick in `var/logs/humidifier/*.jsonl`. Replay test demonstrates `u` is re-derivable from logged inputs.
7. **Property tests pass.** Full structural-invariant suite (see test plan).
8. **Plant-in-loop tests pass.** With FOPDT params fit from real data.

## Risks

- **Magic smoke on the Raydrop driver board.** $40 unit, have a spare on hand before opening.
- **PI tuning instability.** Mitigation: start with Kp-only, add Ki once proportional tracking is stable. Dry runs on a known-good lights cycle before letting the loop run unattended.
- **Digipot / DAC failure mode during power loss.** Design for fail-to-zero: digipot boots to 0 or last-persisted value; firmware defaults to intensity=0 on boot.

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:continuous-humidifier"`

## Related

- Decision: [wiki/decisions/2026-04-23-raydrop-mcu-mist-control.md](../../../wiki/decisions/2026-04-23-raydrop-mcu-mist-control.md)
- Phase 4 test plan: [phase4-test-plan.md](phase4-test-plan.md)
- FOPDT fit findings (2026-04-25): [fopdt-fit-findings.md](fopdt-fit-findings.md)
- Architecture context: [wiki/concepts/multi-actuator-environment-control.md](../../../wiki/concepts/multi-actuator-environment-control.md)
- Current loop: [wiki/hardware/humidifier-control.md](../../../wiki/hardware/humidifier-control.md)
- Companion fan node: [wiki/hardware/ac-infinity-fan-control.md](../../../wiki/hardware/ac-infinity-fan-control.md)
