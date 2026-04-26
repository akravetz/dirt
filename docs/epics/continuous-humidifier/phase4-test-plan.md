# Phase 4 — PI Loop Test Plan & Order of Operations

Companion to [README.md](README.md). Captures the development plan for Phase 4 (the PI controller swap-in) so it can proceed in parallel with the Phase 1 hardware probe — most of Phase 4's work is hardware-independent.

## Why TDD here

The control loop has two distinct kinds of correctness that need different tools:

- **Structural correctness** — output saturation, monotonicity, failsafe paths, integrator clamping, RH-ceiling guard, threshold/plug coupling, stale-sensor handling, dt invariance. These are pure functions of `(state_in, sensor_in) → command_out`. They don't change under tuning. **TDD-friendly.**
- **Dynamic correctness** — settling time, overshoot, disturbance rejection, no oscillation. These need a plant model to be meaningful; they're closer to acceptance tests than unit tests.

We use TDD for structural correctness only. We do **not** test-pin tuning numbers (Kp, Ki, threshold, deadband, anti-windup clamp). Those are empirical and any test that hardcodes them will rot the moment we re-tune. Test behaviors, not numbers.

## Order of operations

Phase 4 prep work is independent of Phase 1's hardware verdict. While the spare Raydrop ships:

1. **Acceptance criteria + this plan** committed up front (this doc).
2. **FOPDT fit script** against existing `var/logs/humidifier/*.jsonl` + `sensorreading`. Output: per-segment K / τ / L, aggregate stats, IMC-derived starting Kp / Ki. `debug/`-scoped, throwaway. **Fail-fast on whether the data even supports a fit** before sinking effort into placeholder code. **Done 2026-04-25** — see [fopdt-fit-findings.md](fopdt-fit-findings.md). Verdict: data brackets gains, doesn't pin them. Conservative starting gains carried forward; real tuning happens via shadow mode + graduated step test in Phase 2/3 acceptance.
3. **Property tests** for the controller (red).
4. **Controller skeleton** + placeholder gains → property tests green.
5. **Shadow mode wiring.** New `humidifier_shadow` log stream. Controller computes `u`, writes the would-be command, takes no action. Live bang-bang still drives the plug. Lands as soon as #4 is green so we accumulate real-data calibration during the hardware wait.
6. **Plant-in-loop tests** using fitted FOPDT params from #2. Step response, disturbance rejection, fan-coupling step, saturation soak.
7. **Replay tests** once shadow data has accumulated for ≥ 24 h.
8. **Acceptance soak** — flips from shadow to authoritative once Phase 2/3 hardware lands. Deliberate drained-tank test for the watchdog.

`#2 → #6` is the back-pressure: if the data doesn't support a fit we surface that before writing controller code, and #6's tests stay parameterized as TODOs until then.

## Test layers

### Property tests (pure-function, pytest, milliseconds)

Run on every commit. Cover structural invariants:

- **Output range:** `u ∈ [0, 100]` for arbitrary inputs.
- **Monotonicity in error:** ↑VPD error → non-decreasing `u` (within saturation). The acceptance criterion test.
- **Failsafe stale:** `now - vpd_ts > FAILSAFE_STALE_S` ⇒ `u = 0` and plug-off.
- **Lights-off prep:** in prep window ⇒ `u = 0` and plug-off.
- **RH ceiling guard:** `RH ≥ stage_rh_max` ⇒ `u = 0` regardless of VPD error (envelope guard — see [multi-actuator doc](../../../wiki/concepts/multi-actuator-environment-control.md) Principle 1).
- **Intensity threshold → plug:** `u < threshold` ⇒ plug-off; `u ≥ threshold` ⇒ plug-on. Hysteresis around threshold prevents chatter.
- **Anti-windup bounded:** integrator stays in `[-I_max, I_max]` under sustained saturation (drive 1 simulated hour of error, assert clamp).
- **Anti-windup release:** when error reverses, integrator unwinds without a transient kick.
- **Night offset applied:** lights-off shifts setpoint by `night_offset` exactly once per state transition.
- **dt invariance:** integral term scales linearly with `dt` (30s and 60s ticks integrate identically over equal wall-clock spans).
- **Clock-jump robustness:** negative `dt` (NTP step backwards) does not let the integrator grow.
- **Stage flip on next tick:** updating `flower_start_date` shifts setpoint without resetting integrator state.
- **Stuck-watchdog input upgraded:** keys off `u > 0` (not `plug.is_on`).
- **Stuck-watchdog fires once:** `u > 0` for ≥ stuck-window with `ΔVPD < min_drop` ⇒ exactly one `suspected_stuck` event per streak; suppressed until `u → 0`.
- **Log contract:** every tick log carries `kp`, `ki`, `err`, `P`, `I`, `u`, `vpd`, `vpd_age_s`, `rh`, `rh_ceiling`, `stage`, `lights_on`, `threshold_state`. Schema regression test, prevents tuning analysis from getting stuck on missing fields.

### Plant-in-loop tests (need FOPDT params from #2)

✅ **Landed 2026-04-25** — `apps/hwd/tests/test_humidifier_pi_plant.py`, 16 tests (3 plant self-tests + 4 design tests × 4 plant-param corners + 1 saturation). Pure stdlib FOPDT plant simulator; controller drives plant; assert behaviors not numbers.

Plant param bracket (from [fopdt-fit-findings.md](fopdt-fit-findings.md)):
- τ ∈ [300, 1200] s, |K| ∈ [0.02, 0.06] kPa/%u, V_dry_eq ∈ [1.3, 1.7].
- Each design test parametrized over 4 corner/midpoint combos.

Tests:

- **`test_step_response_settles_within_envelope`** — plant starts at V_dry_eq, controller drives VPD down, after 6 h tail-30-min average within ±0.1 of setpoint and max-dev within ±0.2. Envelope is intentionally looser than the production criterion (±0.10) — conservative starter gains are sluggish by design; tightening happens during real-hardware tuning.
- **`test_lights_off_does_not_blow_up_integrator`** — full lights cycle (90 min on → 6 h dark → 6 h on). Asserts integrator bounded throughout, core dark period 100% in `OUTSIDE_LIGHTS_WINDOW`, post-return tail within ±0.2 of setpoint.
- **`test_fan_duty_step_response_directionally_correct`** — steady state at fan=25%, step to fan=50% (mist authority halves). Asserts peak deviation inside 0.4 kPa envelope, u rises post-step, integrator grows post-step. Does NOT assert "settles to setpoint" — at conservative Ki=0.01 this can take hours, captured in the test docstring. **This is the failure-mode test the rewrite was built for.**
- **`test_unreachable_plant_pegs_integrator_at_clamp_and_recovers`** — fan=400% (simulated overpowered exhaust). Asserts integrator pegs at clamp (anti-windup), stays pegged without escape, u stays bounded; on fan recovery, integrator unwinds. Reframed from "u saturates at 100" because at conservative gains the relevant saturation is the integrator clamp, not the u-ceiling.

**Stuck-watchdog firing under saturation:** still keys off `plug.is_on`, will cut over to `u > 0` atomically with Phase 4 going authoritative. Test `test_saturation_soak_fires_watchdog` will land then.

### Replay tests (need shadow data)

After ≥ 24 h of shadow mode, snapshot the controller's `u` trajectory against historical sensor input and regression-test it. Catches unintended behavior changes during refactors.

### Acceptance soak (live system, post-Phase 2/3)

The criteria below run as a 24-h authoritative trial. Failure rolls back to bang-bang.

## Acceptance criteria (refined)

Replaces the section in README.md once this plan lands. Source of truth lives there; this is the rationale.

1. **Tracking.** With the fan at any duty in [25, 60] %, tent VPD tracks the stage upper edge within ±0.1 kPa across a full 18-h lights-on period. No bang-bang oscillation, no sustained off-band excursions.
2. **Switching count.** Kasa-plug state transitions drop from ~once-per-minute (today's bang-bang) to ≤ 6 per day. Plug only switches at mode boundaries (failsafe, lights-off prep, sub-threshold cutoff), not on every cycle.
3. **Envelope respected.** RH never exceeds `stage_rh_max` due to controller action — verified in plant-in-loop tests *and* in the soak-trial logs.
4. **Dial retired.** The Raydrop dial is no longer a control input the operator has to reason about — either removed physically or overridden in software, documented on `wiki/hardware/humidifier-control.md`.
5. **Watchdog still works.** `suspected_stuck` fires on a deliberate drained-tank test (real Raydrop, not simulated) with the upgraded `u > 0` trigger.
6. **Diagnosability.** Integrator state, P/I split, error, and `u` are visible per-tick in `var/logs/humidifier/*.jsonl`. Replay test demonstrates we can re-derive `u` from logged inputs.
7. **Property tests pass.** All structural invariants in the list above.
8. **Plant-in-loop tests pass.** With FOPDT params fit from real data, step response and fan-coupling tests pass at chosen tuning.

## What we are explicitly NOT testing

- **Tuning values.** No test asserts "Kp == 12.3". Behavior over numbers.
- **Long-tail dynamic behavior.** Settling-time bounds use `N · τ` not absolute seconds — they re-validate after re-fits.
- **Hardware faults.** A digipot SPI bus error is firmware territory, not control-loop territory. Simulated as `actuator.set_intensity()` raising; loop's contract is to fail safe (u=0) and surface the error event.
- **Tuning convergence.** Plant-in-loop tests verify *structural correctness against a simplified plant.* They are necessary but not sufficient — soak-trial data on real hardware (criterion #1, ±0.1 kPa over 18 h) remains the binding criterion. Don't over-trust green plant-in-loop tests as evidence the gains are right.
- **RH ceiling guard under plant dynamics.** Already covered in property tests with synthetic inputs. Plant-in-loop disables the ceiling (sets `stage_rh_max=99`) to isolate the dynamics under test from the guard's force-off path.
- **Multi-actuator dispatch.** Single-actuator only — multi-actuator design waits on dehumidifier hardware.

## Plan-rot prevention

If we change the controller shape (e.g. add a feedforward term for lights-on prep), this doc gets a revision block. If we add a test, it goes in the property-test list above. If we drop a test, justify why in this doc — not just in the diff.
