# Cascade RH control for fan and dehumidifier

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.

## Purpose / Big Picture

After this change, the main tent climate controller will treat the exhaust fan as the primary fast relative-humidity actuator and the dehumidifier as slower background drying capacity. The operator should see fewer fan jumps between floor and maximum duty while preserving quick RH and VPD recovery during lights-off and other fast humidity transients.

The observable behavior is a `climate_controller` log stream where fan targets move as a damped inner RH/VPD loop, dehumidifier state changes are driven by sustained fan burden and RH load instead of instantaneous sensor wiggles, and lights-off feedforward produces a planned fan response before VPD collapses. Acceptance is not merely passing tests: a local replay or live log window must show fewer large fan duty reversals while RH remains inside the stage/phase policy band.


## Progress

- [x] (2026-05-31Z) Drafted this ExecPlan from repository inspection, May 30-31 local telemetry, and control-theory references.
- [ ] Add focused pure-controller tests that characterize the current fan/dehumidifier oscillation and the desired cascade behavior.
- [ ] Implement the fast fan RH/VPD inner loop and slow dehumidifier outer loop in `apps/hwd/src/dirt_hwd/services/climate_controller.py`.
- [ ] Add replay or analysis tooling under `debug/` for before/after climate-controller behavior on recent JSONL/DB data.
- [ ] Validate with unit tests, hwd tests, invariants, and a replay/log acceptance report.


## Surprises & Discoveries

- Observation: The fan is the fastest observed RH mover in the current tent. On May 30 local data, large fan-up events were followed 3-8 minutes later by about `-3.4% RH`, while dehumidifier-on events were followed by about `-2.0%` to `-2.3% RH` over the same short window. This is directional rather than a controlled experiment because both actuators are usually commanded during RH spikes.
  Evidence: Local Postgres query over `sensorreading` for `homebox/main` on `2026-05-30`, comparing `fan_duty_pct` increases of at least 15 points and `dehumidifier_on` rising edges against later `humidity_pct`.
- Observation: Fan changes are not reliable precision cooling. On the same short response windows, large fan-up events moved temperature by only about `+0.16F` on average. The lung-room temperature gradient exists but is not dependable enough to treat fan as active cooling.
  Evidence: Same local Postgres response-window query using `temperature_f`.
- Observation: Current fan control already has PI-like demand terms, but fan allocation maps drying demand to fan duty aggressively and can bypass pacing when RH or temperature crosses emergency margins.
  Evidence: `ClimateTuning.drying_fan_share = 1.0`, `fan_minimum_dwell_s = 180`, `fan_slew_step_pct = 15`, and bypass logic in `apps/hwd/src/dirt_hwd/services/climate_controller.py`.
- Observation: The operator states lung-room air is always lower humidity than tent air, even though lung-room temperature varies from roughly 70F at night to 74F during the day. This means fan exchange can be modeled as reliably drying for RH, but not reliably cooling for temperature.
  Evidence: User operational knowledge recorded in this planning thread.


## Decision Log

- Decision: Model the fan as the primary fast RH-down / VPD-up actuator, not as secondary humidity trim.
  Rationale: The fan exchanges humid tent air for drier lung-room air and local response data shows it moves RH faster than the dehumidifier. The previous "fan as secondary" mental model misclassifies the actuator.
  Date/Author: 2026-05-31 / Codex
- Decision: Model the dehumidifier as a slow outer-loop capacity actuator driven primarily by sustained fan burden plus RH/VPD context.
  Rationale: Dehumidifier response is slower and binary. It should keep background moisture load low enough that the fan does not need to remain high, while the fan handles fast disturbances.
  Date/Author: 2026-05-31 / Codex
- Decision: Keep temperature-down control out of the primary model.
  Rationale: There is no active cooling actuator. The fan may cool only when lung-room air is cooler and exchange dominates light heat load; this is unreliable. Heater remains the primary temperature-up actuator.
  Date/Author: 2026-05-31 / Codex
- Decision: Use control-system concepts directly: cascade control, split-range allocation, feedforward for scheduled disturbances, and anti-windup/bumpless tracking around actuator limits.
  Rationale: Control.com describes cascade control as nested loops where the secondary loop responds faster; it also notes the secondary process must be faster-responding than the primary. Split-range control describes allocating one controller output across multiple final control elements. Anti-windup is needed when actuator saturation or binary dwell prevents delivered output from matching requested output.
  Date/Author: 2026-05-31 / Codex


## Outcomes & Retrospective

Not implemented yet. The intended outcome is a damped cascade controller where fan duty settles instead of repeatedly jumping from floor to 80 and back, while dehumidifier state reflects sustained moisture load rather than every sensor excursion. Record measured before/after fan reversal counts, RH-in-band percentage, and dehumidifier cycle counts here after implementation.


## Context and Orientation

The current live climate authority is `ClimateControllerService` in `apps/hwd/src/dirt_hwd/services/climate_controller.py`. `apps/hwd/src/dirt_hwd/app.py` wires this service with `ClimateActuators`, including `FanNodeActuator`, `H7142HumidifierActuator`, `KasaDehumidifierActuator`, and `DatabaseThermoForgeHeaterActuator`.

Stage and phase targets live in `apps/hwd/src/dirt_hwd/services/climate_policy.py`. For `flower_late`, lights-on policy is VPD `1.2-1.5 kPa`, temperature `74-78F`, RH max `55%`; lights-off policy is VPD `1.1-1.3 kPa`, temperature `70-72F`, RH max `60%`.

The service logs one `climate_controller` JSONL `tick` event per control cycle under `var/logs/climate_controller/YYYY-MM-DD.jsonl`. Important tick fields include `temperature_f`, `humidity_pct`, `vpd_kpa`, `current_fan_pct`, `target_fan_pct`, `current_dehumidifier_on`, `target_dehumidifier_on`, `active_mode`, `raw_drying_demand_pct`, `raw_cooling_fan_demand_pct`, and `reasons`.

Current fan behavior is implemented in `_allocate_fan()`. It combines drying fan demand and cooling fan demand, then applies pacing and slew through `_paced_fan_target()` and `_slew_fan_target()`. Pacing can be bypassed by hard low temperature, RH emergency, or high temperature. Current dehumidifier behavior is implemented in `_dehumidifier_requested_from_drying_demand()` and `_allocate_dehumidifier()`, using drying demand, RH-near-ceiling, and minimum on/off dwell.

Control theory grounding:

- Cascade control: a primary controller sends a setpoint to a secondary controller, and the secondary loop must be faster responding. Source: https://control.com/textbook/basic-process-control-strategies/cascade-control/
- Split-range control: one controller output is divided across multiple final control elements. Source: https://control.com/textbook/control-valves/split-ranging/
- Anti-windup: PID integral state must be handled carefully when actuator saturation prevents requested output from being delivered. Source: https://control.com/technical-articles/intergral-windup-method-in-pid-control/
- Feedforward control: scheduled or measured disturbances can be acted on before feedback error fully appears. In Dirt, lights-off is the known disturbance.

Definitions for this plan:

- Inner loop: the fast fan duty loop that responds to tent RH/VPD error every climate tick.
- Outer loop: the slower dehumidifier capacity loop that responds to sustained fan burden and RH/VPD load over minutes.
- Fan burden: a smoothed measure of how hard the fan has been working above floor, for example a moving average of `target_fan_pct - fan_floor_pct` or delivered fan elevation.
- Drying capacity: available moisture-removal effort from fan exchange plus dehumidifier operation.
- Bumpless tracking: seeding or updating integrator state from delivered actuator output so restarts, saturation, and binary dwell do not cause large output jumps.


## Plan of Work

Milestone 1 adds tests and a replay harness before changing behavior. Create pure tests in `apps/hwd/tests/test_climate_controller.py` that make the current desired contract explicit: fan is primary for fast RH correction, dehumidifier turns on from sustained fan burden, and temperature-high can request modest fan cooling but not dominate humidity control. Add a throwaway analysis script under `debug/` that can replay recent `climate_controller` JSONL or DB readings and compute fan reversal counts, large step counts, RH-in-band time, and dehumidifier cycle counts.

Milestone 2 separates demand concepts inside `climate_controller.py` without adding durable compatibility layers. Keep a direct model: `fan_rh_demand`, `fan_cooling_demand`, and `dehumidifier_capacity_request` are better names than one overloaded `drying_pct` if the implementation needs them. Preserve current public service boundaries and event fields unless a field becomes misleading; if new fields are needed, add explicit diagnostics and update tests.

Milestone 3 implements the fan inner loop. The fan loop should compute a continuous fan target from RH error and low-VPD pressure, with integral tracking from delivered fan elevation. Fan duty must respect floor/max, have a longer dwell or smoother rate limit than today, and reserve emergency bypass for genuinely unsafe RH excursions. Cooling fan demand should be capped or deprioritized when it conflicts with RH/VPD behavior because fan is not reliable active cooling.

Milestone 4 implements the dehumidifier outer loop. Replace instantaneous dehumidifier requests with a sustained-burden signal: if fan elevation is high for a configured window while RH/VPD indicate drying load, request dehumidifier on. If fan returns near floor and RH/VPD remain stable for a longer window, request dehumidifier off. Keep dehumidifier minimum on/off dwell. Track delivered drying capacity for anti-windup.

Milestone 5 adds lights-off feedforward. The schedule already provides lights context through grow state. Before lights-off, modestly raise the fan setpoint or bias the fan RH loop if RH/VPD trend suggests the temperature drop will push VPD low. Optionally pre-enable dehumidifier only when sustained fan burden or RH trend is already high. After the transition, let feedback take over and decay the feedforward bias.

Milestone 6 validates and tunes. Run unit tests, hwd tests, shared tests if changed, invariants, and replay. Compare before/after metrics over at least one recent day. Commit only after the plan's acceptance criteria are satisfied.


## Concrete Steps

1. Inspect current code and tests:

    cd /home/akcom/code/dirt
    sed -n '1,220p' docs/commands.md
    sed -n '1,220p' docs/observability.md
    sed -n '1,260p' apps/hwd/src/dirt_hwd/services/climate_controller.py
    sed -n '1,260p' apps/hwd/src/dirt_hwd/services/climate_policy.py
    rg -n "fan_elevated|dehumidifier_requested|drying_fan|heater_level_hysteresis" apps/hwd/tests apps/hwd/src

2. Add characterization tests in `apps/hwd/tests/test_climate_controller.py`. Start with pure `decide_climate()` cases. Tests should assert behavior, not exact operator-owned policy literals.

3. Add replay tooling under `debug/cascade-rh-control/`. The script may read `var/logs/climate_controller/*.jsonl` and emit a small table:

    date, ticks, large_fan_steps, fan_reversals, rh_in_band_pct, median_abs_rh_error, dehumidifier_cycles

   `debug/` is intentionally for scratch tooling and must not be imported by app code.

4. Refactor `apps/hwd/src/dirt_hwd/services/climate_controller.py` around explicit control concepts. Prefer direct dataclass fields over generic dictionaries. Do not keep compatibility wrappers for old internal names if source-owned tests can be updated in the same change.

5. Implement the fan inner loop and dehumidifier outer loop. Keep changes inside `climate_controller.py` unless a value belongs in `ClimateTuning` or `climate_policy.py`.

6. Update `docs/observability.md` if any `climate_controller` log fields or reason codes change.

7. Run targeted validation:

    uv run pytest apps/hwd/tests/test_climate_controller.py -q

8. Run broader validation:

    uv run pytest apps/hwd/tests -q
    uv run pytest apps/tests/invariants -q
    uv run ruff check

9. Run replay and paste concise before/after output into `Artifacts and Notes`.

10. Before committing, run the repository formatter/fixer:

    make fix


## Validation and Acceptance

Acceptance has three layers.

Pure controller tests must show:

- High RH above the phase ceiling raises fan as the first fast correction.
- Sustained fan burden requests dehumidifier on after the configured window.
- Dehumidifier stays on through minimum dwell and does not toggle on single-tick RH dips.
- Fan decays smoothly after RH/VPD recovery instead of jumping directly from max to floor unless a safety condition requires it.
- High VPD with RH below ceiling humidifies or holds fan near floor rather than drying harder.
- Temperature-high can request cooling fan assist, but not override hard RH/VPD safety logic.

Replay acceptance should compare current behavior against new behavior using recent local telemetry. A successful run should show:

- Fewer large fan duty reversals, defined as a change of at least 30 percentage points followed by an opposite change of at least 30 percentage points within 10 minutes.
- Similar or better RH-in-band percentage for the relevant stage/phase.
- Similar or better time spent below unsafe high-RH margins.
- Dehumidifier cycles that respect dwell and do not increase materially without improving fan burden.

Live acceptance after deployment should use:

    jq -r 'select(.event=="tick") | [.ts,.active_mode,.humidity_pct,.vpd_kpa,.current_fan_pct,.target_fan_pct,.target_dehumidifier_on,(.reasons|join(";"))] | @tsv' var/logs/climate_controller/YYYY-MM-DD.jsonl

Expected shape: fan targets move gradually around RH/VPD error, dehumidifier turns on after sustained fan burden, and lights-off transition does not produce repeated floor-to-max-to-floor oscillations.


## Idempotence and Recovery

Unit tests and replay scripts are safe to run repeatedly. The replay script must be read-only and must not write outside `debug/` unless explicitly given an output path.

The implementation is source-owned and can use direct cutover. If a partial implementation worsens behavior, revert the source changes from the branch before deployment rather than adding a feature flag. Do not edit human-owned invariant tests under `apps/tests/invariants/`; fix the code if invariants fail.

No database migration is expected. If implementation later requires persisted tuning or new control-state storage, pause and read `docs/database.md`, `docs/references/atlas/INDEX.md`, and `docs/rules/boundary-contracts.md` before changing schema or persistence contracts.

Do not restart `dirt-hwd` or command hardware during implementation unless the operator explicitly asks for live deployment. Development validation should use pure tests and read-only replay.


## Artifacts and Notes

Initial evidence from May 30-31 local analysis:

- `fan_duty_pct` changed 442 times between `2026-05-30 00:01 MDT` and `2026-05-30 21:41 MDT`, average absolute change about `17.5` percentage points.
- Large fan-up events were followed by about `-3.4% RH` over the 3-8 minute window and about `+0.16F` temperature change.
- Dehumidifier-on events were followed by about `-2.0%` to `-2.3% RH` over the same short window.
- Latest `2026-05-31` ramp-up reasons were dominated by `hard_rh_guard` and `hard_temperature_guard`; fan-elevated reasons included both drying and cooling.

Source references used while drafting:

- Control.com cascade control: https://control.com/textbook/basic-process-control-strategies/cascade-control/
- Control.com split-range control: https://control.com/textbook/control-valves/split-ranging/
- Control.com PID integral windup article: https://control.com/technical-articles/intergral-windup-method-in-pid-control/
- Control Engineering cascade overview: https://www.controleng.com/fundamentals-of-cascade-control/


## Interfaces and Dependencies

The main implementation interface is `decide_climate()` and its supporting dataclasses in `apps/hwd/src/dirt_hwd/services/climate_controller.py`. The service boundary remains `ClimateControllerService`, which reads sensor values through `ReadingsService`, grow/lights context through `GrowStateService`, and dispatches through `ClimateActuators`.

Expected internal data after implementation:

- `ClimateTuning` includes explicit tuning for fan RH loop, fan cooling loop, fan burden windows, dehumidifier burden thresholds, and lights-off feedforward bias.
- `ClimateState` stores enough state to support fan/dehumidifier cascade behavior: fan integral or tracked burden, dehumidifier dwell state, and any feedforward decay state that must persist across ticks.
- `climate_controller` logs include enough fields to diagnose fan RH demand, fan cooling demand, sustained fan burden, dehumidifier outer-loop request, and delivered actuator output.

No new external service or package dependency is expected.


## Revision Notes

- 2026-05-31: Initial ExecPlan drafted for review.
