# Epic: Continuous Humidifier Intensity Control

Status: Phase 1 hardware paused (waiting on replacement spare); Phase 4 prep landed end-to-end and live in shadow mode; production tuning blocked on Phase 1–3 hardware
Priority: medium
Created: 2026-04-23
Last touched: 2026-04-26

---

## Current state (resume point for a fresh agent — read this top-down)

The work breaks into three layers. Read them in order:

1. **Hardware (Phase 1):** PAUSED. Original spare Raydrop destroyed during disassembly. Replacement on order. Findings from the destroyed spare still apply (identical KC-RD03A unit).
2. **Phase 4 prep:** ALL 7 steps from the [test plan](phase4-test-plan.md) DONE. Controller, tests (28 property + 16 plant-in-loop), shadow-mode logging, and analyzer/replay harness are all committed and live.
3. **Live shadow data + tuning gap:** dirt-hwd is generating high-cadence shadow output. The conservative starter gains (Kc=8, Ki=0.01) are demonstrably too conservative — the analyzer shows shadow's `u` is below the 5% sub-threshold on every observed pi_active tick. **Real production tuning is blocked on Phase 2/3 hardware** (the graduated step test we'll run during acceptance is the only way to get clean continuous-input data; bang-bang data brackets gains, doesn't pin them).

### Hardware status

- Phase 1 paused. Original spare Raydrop on the bench was destroyed during disassembly. Replacement on order.
- Primary Raydrop continues to drive the live VPD bang-bang loop unchanged via the Kasa EP10 plug.
- Probe findings from the original spare (still valid for identical KC-RD03A unit): see [Phase 1 hardware findings](#phase-1-hardware-findings-from-destroyed-spare) below.

### Phase 4 prep status — all 7 steps done

| # | Step | Status | Where |
|---|---|---|---|
| 1 | Acceptance criteria + plan committed | ✅ | [phase4-test-plan.md](phase4-test-plan.md) |
| 2 | FOPDT fit script + verdict | ✅ | `debug/humidifier-fopdt/fit.py`, [findings](fopdt-fit-findings.md) |
| 3 | Property tests (red) | ✅ | `apps/hwd/tests/test_humidifier_pi.py` (29 tests) |
| 4 | Controller skeleton + property tests green | ✅ | `apps/hwd/src/dirt_hwd/services/humidifier_pi.py` |
| 5 | Shadow-mode wiring (`humidifier_shadow` stream, no actuation) | ✅ live | `apps/hwd/src/dirt_hwd/services/humidifier.py` + `var/logs/humidifier_shadow/*.jsonl` |
| 6 | Plant-in-loop tests | ✅ | `apps/hwd/tests/test_humidifier_pi_plant.py` (16 tests) |
| 7 | Analyzer + replay harness against shadow logs | ✅ | `debug/humidifier-shadow/analyze.py` |

### Live state of the shadow controller

- `dirt-hwd` is running. Shadow PI emits one `tick` event per ~30 s into `var/logs/humidifier_shadow/`.
- Conservative gains: `Kc=8.0`, `Ki=0.01`, integrator clamp 50%, sub-threshold cutoff at 5% with 1% hysteresis, night offset −0.3 kPa. (See `_SHADOW_PI_*` constants near top of `humidifier.py`.)
- Stage targets in effect: `STAGE_TARGETS` in `apps/shared/src/dirt_shared/services/grow_state.py`. Veg humidity_pct band is **(40, 70)** — mold-prevention envelope, not a VPD-coupled setpoint. See "Centralization + band fix" timeline note below.
- Bang-bang controller is unchanged and remains authoritative. Shadow does not actuate.

### What the analyzer revealed (overnight run, 1832 ticks across 15.3 h, full lights cycle)

```
Live reason distribution (config switched mid-window from old to new humidity band):
  outside_lights_window : 39%   ← captured the full dark period
  pi_active             : 33%   ← was 16% in the 5-h yesterday-only snapshot
  rh_ceiling            : 28%   ← was 84% before the band fix

Replay (current compute() against same inputs, current bands throughout):
  pi_active             : 48%
  outside_lights_window : 39%
  rh_ceiling            : 13%   ← what we'd see if all 1832 ticks ran under today's band
```

**Three findings from the overnight data:**

1. **The lights-on FOPDT fit is now trustworthy.** Per-regime split was useless yesterday (only lights-on data); now we have 1112 lights-on samples and 716 lights-off samples. Lights-on regime: **τ = 133 s, K = −0.72 kPa, V_dry_eq = 1.56, V_wet_eq = 0.84**. Physically credible: ~2-min closed-loop response with mist on producing ~0.7 kPa drop, asymptotes straddling the band edges. **First trustworthy plant fit we have**, though K here is "binary input" (mist plug ON vs OFF, not continuous u). Multiply by ~0.01 to get a starting K_per_pct. Lights-off regime has β = 0 / K = 0 — plug forced off all night, no actuator signal, expected.

2. **IMC against the new lights-on fit suggests gains 5–12× higher than current.** With τ = 133 s, L = 60 s, K = −0.72 kPa (binary), the IMC formulae give Kc ≈ 40–95, Ki ≈ 0.3–1.1 across λ ∈ [3τ, τ/2]. Current shadow gains: Kc = 8, Ki = 0.01. **Don't wire these in yet** — the binary-input fit's K is on a different scale than continuous control's K_per_pct (the Raydrop dial setting + bang-bang ON gives a fixed mist rate, which isn't the same as u=100% continuous), and the graduated step test at Phase 2/3 acceptance is the only way to pin K_per_pct cleanly. But this is a much better starting bracket than yesterday's 81-s noise-floor-dominated fit suggested.

3. **The −0.3 kPa night offset appears to be overcorrecting.** During the pre-lights-on ramp window (lights-off, last 30 min before lights return), the controller is `pi_active` against a setpoint of 0.9 kPa (1.2 day setpoint − 0.3 night offset). VPD naturally sits at ~0.85–0.95 kPa during this window because the tent is cool/wet. Result: error skews negative (median err = −0.133 kPa, "too wet"), integrator accumulates negative bias (median I = −5.2, range [−24.8, +2.8], well within the ±50 clamp). The controller wants to dehumidify but has no actuator to do so; the integrator is just absorbing the bias. Not a bug — bounded and harmless — but the first concrete data point that **the night offset value is probably wrong** for our tent's actual lights-off equilibrium. Worth re-tuning during Phase 4 acceptance once we have continuous control. Not urgent.

### What still hasn't changed

- **Sub-threshold cutoff still fires on every pi_active tick.** 0/601 ticks cleared the 5% threshold under either config — same as yesterday's snapshot, just with more ticks confirming. Conservative gains remain inert.
- **Plug divergence stays one-sided:** 432 cases of shadow-OFF / actual-ON, longest streak 189 ticks (94.5 min). Bang-bang fires for VPD crossings, shadow stays asleep.
- **No daemon errors over 15 h.** System is healthy.

### Where to start, as a fresh agent

- **Working on Phase 1 hardware** (replacement spare arrived): walk the user through Step 1 of [phase1-probe-checklist.md](phase1-probe-checklist.md). Findings update [the decision doc](../../../wiki/decisions/2026-04-23-raydrop-mcu-mist-control.md) as a revision block; BOM consequences captured in [bom.md](bom.md).
- **Working on tuning analysis**: run `uv run --package dirt-shared python debug/humidifier-shadow/analyze.py` against current shadow data. Compare to the snapshot above.
- **Hardware just landed (Phase 2/3 done)**: the binding next step is a **graduated step test** — hold u=25%, 50%, 75% for 20 min each in lights-on steady state. That's the only data that will pin τ and K precisely. Re-fit FOPDT against the result, derive new IMC gains (the analyzer script's `fopdt` section will do this from the new shadow logs once continuous-input data exists), update `_SHADOW_PI_*` constants in `humidifier.py`. **Sanity check against the 2026-04-26 fit**: lights-on τ should land near 130 s and K_per_pct should land near −0.005 kPa/%u (the 2026-04-26 binary-input K of −0.72 kPa, divided by ~100 + a Raydrop-dial-setting fudge). Big disagreement suggests either the dial is in a different position or the bang-bang fit was anomalous. See [phase4-test-plan.md](phase4-test-plan.md) §"Acceptance soak."
- **Tuning the night offset**: deferred until continuous control lands. Current −0.3 kPa is overcorrecting (analyzer revealed the integrator drifts negative during the ramp window). When you re-tune, look at the actual lights-off VPD equilibrium in shadow data and pick an offset that matches it.
- **Operating the shadow loop**: see "Re-running the analyzer" below.

---

## Timeline of significant changes

- **2026-04-23**: [Decision committed](../../../wiki/decisions/2026-04-23-raydrop-mcu-mist-control.md) to replace bang-bang with continuous PI. Phase 1 began on bench.
- **2026-04-25**: Phase 1 paused; primary spare destroyed during disassembly. Phase 4 prep work proceeded in parallel: FOPDT fit script, controller, property tests, plant-in-loop tests, shadow logging all landed.
- **2026-04-25 PM**: Discovered `STAGE_TARGETS["humidity_pct"]` was internally inconsistent with `vpd_kpa` — at typical room T, the (45, 55) RH band corresponds to VPD ~1.4–1.7 kPa, well outside the (0.8, 1.2) VPD target. Reframed humidity bands as mold-prevention envelopes (not VPD-coupled targets); centralized band-comparison logic into `dirt_shared.services.grow_state` (`in_band`, `above_band`, `below_band` alongside the existing `band_status`). Refactored the voice tool's ad-hoc band check and the humidifier PI's RH-ceiling guard. Live shadow controller restarted with new bands; the constant `rh_ceiling` trigger went away (~84% → ~38% projected).
- **2026-04-25 evening**: Analyzer + replay script `debug/humidifier-shadow/analyze.py` landed. Revealed conservative gains produce `u` below threshold on every pi_active tick — production tuning will need higher Ki.
- **2026-04-26 morning**: Overnight run captured a full lights cycle (1832 ticks). Three new findings: (a) lights-on FOPDT fit is now trustworthy at τ=133 s, K=−0.72 kPa; (b) IMC against the new fit suggests gains 5–12× higher than current; (c) the −0.3 kPa night offset is probably overcorrecting, integrator drifts negative during the pre-lights-on ramp because VPD is naturally below the night-shifted setpoint. None warrant code changes pre-hardware. See "What the analyzer revealed" above + [fopdt-fit-findings.md](fopdt-fit-findings.md) §"Refit on shadow data (2026-04-26)".

---

## Re-running the analyzer

The analyzer reads `var/logs/humidifier_shadow/*.jsonl` and produces six sections:

```bash
uv run --package dirt-shared python debug/humidifier-shadow/analyze.py
  [--days N]                    # window in days (default: all available logs)
  [--section reasons,divergence,pi,ceiling,fopdt,replay]   # subset
```

Sections:

- `reasons` — distribution over `pi_active` / `rh_ceiling` / `outside_lights_window` / `failsafe_stale_sensor`. Quick health snapshot.
- `divergence` — on `pi_active` ticks only, agreement matrix between `plug_on_shadow` and `plug_on_actual`. Quantifies "would continuous control have actuated differently."
- `pi` — integrator/error/u distributions, P vs I split, sub-threshold cutoff hit rate. Catches windup or stuck-at-saturation.
- `ceiling` — when does `rh_ceiling` fire (RH/VPD/time-of-day distributions). Catches "tent structurally too humid for the stage envelope."
- `fopdt` — refit FOPDT plant model from `(vpd, plug_on_actual)` at shadow's 30s cadence. Per-regime split (lights_on vs lights_off) — better than the original `debug/humidifier-fopdt/fit.py` which couldn't separate regimes.
- `replay` — runs the *current* `compute()` against every logged tick's inputs to show what the controller would have decided under today's config. Useful after any tuning change.

The analyzer is throwaway debug code (gitignored under `debug/`). Output is stdout; redirect to a file for later comparison.

---

## Phase 1 hardware findings (from destroyed spare)

These observations are from the original spare Raydrop, taken before disassembly damage. Apply to the identical KC-RD03A unit:

- **Pot:** silkscreen reads `B5K` — **5 kΩ linear-taper, integrated SPST power switch** (clicks off at min rotation).
- **JST topology:** 4 wires total = 3 pot pins (outer-A / wiper / outer-B) + 1 switch tab. Switch return is internally commoned to the pot's metal chassis, which ties to one of the pot outers on the PCB.
- **Resistance sweep** across the wiper + non-chassis-outer pair (DMM 200 kΩ, unit unplugged): smooth, monotonic, **0.002 kΩ at max-mist → 2.55 kΩ at min-mist-just-before-click**. Clean rheostat behavior.
- **2.55 kΩ vs 5 kΩ label discrepancy:** mechanical rotation covers ~half the electrical track (switch-cam dead zone consumes the rest). Doesn't block progress — the driver IC sees 0→~2.55 kΩ as the useful control range; firmware will map "intensity %" to the actual observed range.
- **Photos:** `debug/raydrop-re/photos/pot-front.jpg` + `pot-back.jpg`.

### Phase 1 not yet done (blocked on replacement)

- **Step 1 DC voltage sweep** (unit powered) — answers DC-analog-vs-PWM, gates Phase 2 part choice.
- Photograph driver IC with readable markings → `debug/raydrop-re/photos/driver-ic.jpg` (Step 3).
- Full PCB top-down photo → `board-top.jpg`.
- Step 2 logic-analyzer capture (only if Step 1 inconclusive).

### BOM consequence (don't order yet)

None of the three MCP4131 variants on order (10k / 50k / 100k) is a direct match for the 5 kΩ pot. **If Step 1 confirms DC-analog rheostat, we'll need MCP4131-502E/P (5 kΩ, 128-step)** — not currently in the BOM. Decision is gated on the Step 1 verdict; if the Raydrop turns out to be a PWM case, the digipot is moot and we drive directly from ESP32 LEDC.

**Do not proceed past Phase 1 without user review.** The Phase 1 → Phase 2 matrix at the bottom of [bom.md](bom.md) tells you which parts get used based on the probe verdict; if the verdict lands outside the matrix (e.g. encoded comms), stop and reassess before ordering more parts or writing firmware.

---

## Goal

Replace the Raydrop humidifier's binary on/off control with continuous mist intensity (0–100%), driven by a PI loop on tent VPD. Collapses three classes of operational failures observed 2026-04-23: bang-bang overshoot oscillation, fan-coupling actuator saturation, and "hidden analog dial" operational gotcha. Rationale, alternatives, and acceptance live in [wiki decision 2026-04-23](../../../wiki/decisions/2026-04-23-raydrop-mcu-mist-control.md); this epic tracks the work.

For the conceptual primer on PI control, FOPDT models, and IMC tuning, see [`wiki/concepts/control-theory-primer.md`](../../../wiki/concepts/control-theory-primer.md).

## Scope

- **In scope**
  - Open the Raydrop KC-RD03A and reverse-engineer the intensity control circuit.
  - Add a digipot / DAC driven by the existing fan-controller ESP32-C3 (already in the tent).
  - Extend `firmware/fan_controller` with `POST /mist` / `GET /mist` endpoints.
  - Shared Python client (`MistClient` or extend `FanNodeClient`).
  - Replace bang-bang in `HumidifierLoopService` with a PI controller on VPD error, with anti-windup clamp and a sub-threshold Kasa-plug cutoff. ✅ controller + shadow done; cutover to authoritative blocked on Phases 2–3.
  - Update the stuck-actuator watchdog to key off `intensity > 0 + VPD not falling` instead of `plug ON + VPD not falling`. (One-line change at cutover.)
  - Narrow the VPD deadband once intensity control lands (currently 0.4 kPa — actuator-overshoot-sized).
  - Integrator state logged in the `humidifier_shadow` observability stream for diagnosability. ✅
  - Centralize band-comparison logic + reframe humidity bands as mold-prevention envelopes. ✅
- **Out of scope**
  - PID with derivative term — the SHT45 heater-cycle noise floor makes D unhelpful.
  - Dehumidifier integration (separate decision when the unit arrives).
  - PWM fan control philosophy (already covered by `/fan` endpoint + the multi-actuator doc).
  - Removing the Kasa plug — it stays as hard-off / power-cut authority.
  - Auto-tuning / adaptive gains. Manual tuning is enough.

## Phases

Phased rollout with a hard stop-gate after Phase 1.

1. **Phase 1 — Investigation.** Open the Raydrop. Identify the ultrasonic driver IC (chip markings → datasheet). Probe the intensity potentiometer with multimeter + HiLetgo logic analyzer; confirm DC voltage vs PWM vs encoded comms. Decide digipot-vs-DAC-vs-direct-PWM based on findings. Step-by-step walkthrough: [phase1-probe-checklist.md](phase1-probe-checklist.md). **CURRENT STATUS: paused on hardware (destroyed spare).**
2. **Phase 2 — Hardware.** Wire the chosen control mechanism between the fan-controller ESP32 and the Raydrop's intensity input. Keep the Kasa plug in the loop for hard-off authority. Fail-to-zero on boot and on MCU crash.
3. **Phase 3 — Firmware.** `POST /mist {"intensity_pct": 0..100}` + `GET /mist` on `firmware/fan_controller`, mirroring `/fan`. Shared-client update in `apps/shared/src/dirt_shared/services/`.
4. **Phase 4 — PI control loop.** ✅ prep landed; cutover blocked on hardware. Replace bang-bang in `HumidifierLoopService` with the PI controller already shadow-running. Update the stuck-actuator watchdog trigger (`plug.is_on` → `u > 0`). Narrow the deadband. Tune gains empirically using the **graduated step test** (the binding next-step) through a full lights-on/off cycle.
5. **Phase 5 — Physical cleanup (optional).** Remove or relabel the physical dial on the Raydrop if the pot was replaced fully. Hardware-page pass.

## Acceptance Criteria

Authoritative list lives in [phase4-test-plan.md](phase4-test-plan.md) §"Acceptance criteria (refined)". Headline criteria:

1. **Tracking.** Fan duty ∈ [25, 60]%, VPD within ±0.1 kPa of upper edge across an 18-h lights-on period.
2. **Switching count.** Kasa-plug transitions ≤ 6 / day (down from ~once-per-minute today).
3. **Envelope respected.** RH never exceeds the stage humidity band's upper edge due to controller action — RH ceiling guard verified in unit + soak.
4. **Dial retired.** No longer a control input the operator must reason about.
5. **Watchdog still works.** `suspected_stuck` fires on a deliberate drained-tank test with the upgraded `u > 0` trigger.
6. **Diagnosability.** Integrator state, P/I split, error, and `u` per-tick in `var/logs/humidifier_shadow/*.jsonl` (already true for shadow; carries to authoritative logs after cutover). Replay test demonstrates `u` is re-derivable from logged inputs.
7. **Property tests pass.** Full structural-invariant suite (see test plan).
8. **Plant-in-loop tests pass.** With FOPDT params fit from real (post-step-test) data.

## Risks

- **Magic smoke on the Raydrop driver board.** $40 unit, have a spare on hand before opening. (Already burned one — be more careful.)
- **PI tuning instability.** Mitigation: shadow-mode + analyzer in place; we'll see oscillation in shadow data before it becomes operational. Start with Kp-only at the cutover, add Ki once proportional tracking is stable.
- **Conservative starter gains too conservative.** Already observed via analyzer — `u` below threshold on every pi_active tick. At cutover, re-tune from the graduated step test data; don't ship the current `_SHADOW_PI_*` constants as production values without retuning.
- **Digipot / DAC failure mode during power loss.** Design for fail-to-zero: digipot boots to 0 or last-persisted value; firmware defaults to intensity=0 on boot.

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:continuous-humidifier"`

## Related

- Decision: [wiki/decisions/2026-04-23-raydrop-mcu-mist-control.md](../../../wiki/decisions/2026-04-23-raydrop-mcu-mist-control.md)
- Phase 4 test plan: [phase4-test-plan.md](phase4-test-plan.md)
- FOPDT fit findings (2026-04-25): [fopdt-fit-findings.md](fopdt-fit-findings.md)
- Architecture context: [wiki/concepts/multi-actuator-environment-control.md](../../../wiki/concepts/multi-actuator-environment-control.md)
- Conceptual primer: [wiki/concepts/control-theory-primer.md](../../../wiki/concepts/control-theory-primer.md)
- Current loop: [wiki/hardware/humidifier-control.md](../../../wiki/hardware/humidifier-control.md)
- Companion fan node: [wiki/hardware/ac-infinity-fan-control.md](../../../wiki/hardware/ac-infinity-fan-control.md)
