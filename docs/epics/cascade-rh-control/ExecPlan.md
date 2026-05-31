# Cascade RH control for fan and dehumidifier

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.

## Purpose / Big Picture

After this change, the main tent climate controller will treat the exhaust fan as the primary fast relative-humidity actuator and the dehumidifier as slower background drying capacity. The operator should see fewer fan jumps between floor and maximum duty while preserving quick RH and VPD recovery during lights-off and other fast humidity transients.

The observable behavior is a `climate_controller` log stream where fan targets move as a damped inner RH/VPD loop, dehumidifier state changes are driven by sustained fan burden and RH load instead of instantaneous sensor wiggles, and lights-off feedforward produces a planned fan response before VPD collapses. Acceptance is not merely passing tests: a local replay or live log window must show fewer large fan duty reversals while RH remains inside the stage/phase policy band.


## Progress

- [x] (2026-05-31Z) Drafted this ExecPlan from repository inspection, May 30-31 local telemetry, and control-theory references.
- [x] (2026-05-31Z) Add focused pure-controller tests that characterize the current fan/dehumidifier oscillation and the desired cascade behavior.
- [x] (2026-05-31Z) Refactor climate-controller demand/state diagnostics around explicit fan RH demand and dehumidifier capacity request concepts.
- [x] (2026-05-31Z) Implement the fast fan RH/VPD inner loop in `apps/hwd/src/dirt_hwd/services/climate_controller.py`.
- [x] (2026-05-31Z) Implement the slow dehumidifier outer loop in `apps/hwd/src/dirt_hwd/services/climate_controller.py`.
- [x] (2026-05-31Z) Implement bounded lights-off feedforward and dehumidifier pre-enable gating in `apps/hwd/src/dirt_hwd/services/climate_controller.py`.
- [x] (2026-05-31Z) Add replay or analysis tooling under `debug/` for before/after climate-controller behavior on recent JSONL/DB data.
- [x] (2026-05-31Z) Validate with unit tests, hwd tests, invariants, and a replay/log acceptance report.
- [x] (2026-05-31Z) Remove fan-as-cooling demand after replay showed the remaining fan oscillation was dominated by RH/VPD drying versus hard low-temperature compensation.


## Surprises & Discoveries

- Observation: The fan is the fastest observed RH mover in the current tent. On May 30 local data, large fan-up events were followed 3-8 minutes later by about `-3.4% RH`, while dehumidifier-on events were followed by about `-2.0%` to `-2.3% RH` over the same short window. This is directional rather than a controlled experiment because both actuators are usually commanded during RH spikes.
  Evidence: Local Postgres query over `sensorreading` for `homebox/main` on `2026-05-30`, comparing `fan_duty_pct` increases of at least 15 points and `dehumidifier_on` rising edges against later `humidity_pct`.
- Observation: Fan changes are not reliable precision cooling. On the same short response windows, large fan-up events moved temperature by only about `+0.16F` on average. The lung-room temperature gradient exists but is not dependable enough to treat fan as active cooling.
  Evidence: Same local Postgres response-window query using `temperature_f`.
- Observation: Current fan control already has PI-like demand terms, but fan allocation maps fan RH demand to fan duty aggressively and can bypass pacing when RH or temperature crosses emergency margins.
  Evidence: `ClimateTuning.fan_rh_duty_share = 1.0`, `fan_minimum_dwell_s = 180`, `fan_slew_step_pct = 15`, and bypass logic in `apps/hwd/src/dirt_hwd/services/climate_controller.py`.
- Observation: The operator states lung-room air is always lower humidity than tent air, even though lung-room temperature varies from roughly 70F at night to 74F during the day. This means fan exchange can be modeled as reliably drying for RH, but not reliably cooling for temperature.
  Evidence: User operational knowledge recorded in this planning thread.
- Observation: Milestone 1 characterization found that current controller behavior already satisfies the surface case where sustained elevated fan plus RH/VPD load eventually requests dehumidification, but seven desired cascade behaviors remain strict `xfail` until the controller implementation milestones.
  Evidence: `uv run pytest apps/hwd/tests/test_climate_controller.py -q` on 2026-05-31 reported `62 passed, 7 xfailed`.
- Observation: Local `climate_controller` logs contain two malformed historical JSONL lines that a replay harness must tolerate.
  Evidence: `debug/cascade-rh-control/analyze.py` skips invalid JSON at `var/logs/climate_controller/2026-05-26.jsonl:1996` and `2026-05-27.jsonl:1290` while continuing the read-only analysis.
- Observation: The original feedforward xfail used `54% RH` for flower-late pre-lights-off, but the accepted policy says feedforward must be zero when RH is more than `5%` below the upcoming `60%` lights-off ceiling. The test now uses `56% RH` so it exercises near-floor VPD risk without violating the dry-air block.
  Evidence: `test_cascade_lights_off_feedforward_adds_only_capped_fan_bias` now asserts a positive capped bias at `56% RH`; `test_cascade_lights_off_feedforward_is_zero_when_already_dry` keeps the dry-air block covered.
- Observation: Replay breakdown after the initial implementation showed large fan steps and reversals were dominated by alternating `hard_rh_guard` fan-up and `hard_low_temperature_guard` fan-down buckets, not temperature-high fan assist.
  Evidence: `debug/cascade-rh-control/analyze.py` large-step breakdown for the 4-day replay counted `up/lights_off/hard_rh=81` and `down/lights_off/hard_low_temp=70`.


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
- Decision: Do not model fan demand from temperature-high at all.
  Rationale: The fan is reliable drying noise from the temperature controller's perspective, not an active cooling actuator. If fan exchange lowers temperature, the heater PI loop should compensate naturally when heat is needed. Keeping a separate temperature-to-fan path adds conditional behavior and can amplify fan/heat oscillation.
  Date/Author: 2026-05-31 / Codex
- Decision: Lights-off feedforward is a bounded fan RH-bias, not an unconditional fan blast.
  Rationale: Lights-off is a predictable disturbance: temperature falls and VPD can collapse before feedback has time to recover. The fan should start drying only when pre-transition RH/VPD and trend indicate risk, and dehumidifier pre-enable should be reserved for sustained load. This preserves fast protection without creating a scheduled oscillation.
  Date/Author: 2026-05-31 / Codex


## Outcomes & Retrospective

Milestone 6 replay completed against recent local `climate_controller` JSONL, then was rerun after the fan-as-cooling cleanup. The current checked-out controller replay now reduces large fan reversals from `56 -> 0` over the last 1 day and `95 -> 1` over the last 4 days. Large fan steps also drop from `89 -> 24` over the last 1 day and `164 -> 64` over the last 4 days.

RH-in-band percentage, median absolute RH error, high-RH minutes, and high-VPD minutes are unchanged because the replay intentionally keeps the historical sensor sequence rather than simulating counterfactual tent physics. The result should be read as actuator-decision evidence, not proof that live RH/VPD will stay identical. The dehumidifier replay still shows far fewer cycles (`108 -> 0` for 1 day, `359 -> 2` for 4 days), which is directionally consistent with the sustained-burden outer loop but not precise because replay assumes each target applies on the next tick while the measured RH/VPD trajectory remains from the old controller.


## Context and Orientation

The current live climate authority is `ClimateControllerService` in `apps/hwd/src/dirt_hwd/services/climate_controller.py`. `apps/hwd/src/dirt_hwd/app.py` wires this service with `ClimateActuators`, including `FanNodeActuator`, `H7142HumidifierActuator`, `KasaDehumidifierActuator`, and `DatabaseThermoForgeHeaterActuator`.

Stage and phase targets live in `apps/hwd/src/dirt_hwd/services/climate_policy.py`. For `flower_late`, lights-on policy is VPD `1.2-1.5 kPa`, temperature `74-78F`, RH max `55%`; lights-off policy is VPD `1.1-1.3 kPa`, temperature `70-72F`, RH max `60%`.

The service logs one `climate_controller` JSONL `tick` event per control cycle under `var/logs/climate_controller/YYYY-MM-DD.jsonl`. Important tick fields include `temperature_f`, `humidity_pct`, `vpd_kpa`, `current_fan_pct`, `target_fan_pct`, `current_dehumidifier_on`, `target_dehumidifier_on`, `active_mode`, `raw_fan_rh_demand_pct`, `dehumidifier_capacity_request`, and `reasons`.

Current fan behavior is implemented in `_allocate_fan()`. It maps RH/VPD drying demand to fan duty, then applies pacing and slew through `_paced_fan_target()` and `_slew_fan_target()`. Pacing is bypassed only for RH emergency. Temperature-high does not create a fan target, and hard low temperature does not suppress RH/VPD fan drying. Current dehumidifier behavior is implemented in `_dehumidifier_capacity_requested()` and `_allocate_dehumidifier()`, using fan RH demand, RH-near-ceiling, and minimum on/off dwell.

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

Milestone 1 adds tests and a replay harness before changing behavior. Create pure tests in `apps/hwd/tests/test_climate_controller.py` that make the current desired contract explicit: fan is primary for fast RH correction, dehumidifier turns on from sustained fan burden, and temperature-high does not create fan demand. Add a throwaway analysis script under `debug/` that can replay recent `climate_controller` JSONL or DB readings and compute fan reversal counts, large step counts, RH-in-band time, and dehumidifier cycle counts.

Milestone 2 separates demand concepts inside `climate_controller.py` without adding durable compatibility layers. Keep a direct model: `fan_rh_demand` and `dehumidifier_capacity_request` are better names than one overloaded `drying_pct`. Preserve current public service boundaries and event fields unless a field becomes misleading; if new fields are needed, add explicit diagnostics and update tests.

Milestone 3 implements the fan inner loop. The fan loop should compute a continuous fan target from RH error and low-VPD pressure, with integral tracking from delivered fan elevation. Fan duty must respect floor/max, have a longer dwell or smoother rate limit than today, and reserve emergency bypass for genuinely unsafe RH excursions. Temperature-high does not produce fan demand; if fan drying affects temperature, heater compensation remains in the heater loop.

Milestone 4 implements the dehumidifier outer loop. Replace instantaneous dehumidifier requests with a sustained-burden signal: if fan elevation is high for a configured window while RH/VPD indicate drying load, request dehumidifier on. If fan returns near floor and RH/VPD remain stable for a longer window, request dehumidifier off. Keep dehumidifier minimum on/off dwell. Track delivered drying capacity for anti-windup.

Milestone 5 adds lights-off feedforward. The schedule already provides lights context through grow state. Feedforward must be concrete and bounded:

- Activation window: start evaluating `45 minutes` before scheduled lights-off and keep a post-transition decay state for `30 minutes` after lights-off.
- Risk inputs: current `rh_pct`, `vpd_kpa`, `temperature_f`, `minutes_until_off`, short RH slope over roughly `10 minutes`, and current fan burden.
- Entry condition: apply feedforward only if either RH is within `3%` of the upcoming lights-off RH ceiling, VPD is within `0.10 kPa` of the upcoming lights-off VPD floor, RH slope is rising by at least `0.5%` over 10 minutes, or fan burden has been above `floor + 20%` for at least `10 minutes`.
- Fan output shape: add a feedforward bias to the RH/VPD fan inner loop, not a separate unconditional target. Initial bias should ramp from `0` to at most `+15% fan duty` across the pre-lights-off window. If current RH is already above the current or upcoming ceiling, allow the normal RH loop to exceed this cap; the cap only limits feedforward-only demand.
- No dry-air push: if VPD is already above the current upper band or RH is more than `5%` below the upcoming ceiling, feedforward bias must be `0` so the fan does not pre-dry an already-dry tent.
- Dehumidifier pre-enable: request dehumidifier before lights-off only when fan burden has been elevated for the sustained window or RH is already above the upcoming lights-off ceiling. Do not pre-enable dehumidifier solely because lights-off is approaching.
- Decay: after lights-off, linearly decay the feedforward bias to `0` over `30 minutes`. Feedback RH/VPD demand can still keep fan elevated if the tent actually needs it.
- Safety override: hard high RH can override the feedforward cap.

Initial tuning should be `lights_off_feedforward_window_s = 2700`, `lights_off_feedforward_decay_s = 1800`, `lights_off_feedforward_max_bias_pct = 15`, `lights_off_feedforward_rh_near_ceiling_pct = 3`, `lights_off_feedforward_vpd_floor_margin_kpa = 0.10`, `lights_off_feedforward_rh_slope_pct_per_10m = 0.5`, `fan_burden_pre_enable_pct = 20`, and `fan_burden_pre_enable_s = 600`.

Milestone 6 validates, tunes, and reports the replay analysis. Run unit tests, hwd tests, shared tests if changed, invariants, and replay. Compare before/after metrics over the last 1 day and the last 4 days. The milestone is not complete until the implementer writes a concise report into `Artifacts and Notes` with the replay command, date ranges, before/after metrics, interpretation, and any tuning follow-up. Commit only after the plan's acceptance criteria are satisfied.


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
- Temperature-high alone leaves the fan at the RH/VPD-derived target.
- High VPD or low RH humidifies or holds the fan near floor rather than drying harder.
- Hard low temperature does not suppress RH/VPD fan drying; heater compensation is allowed to run alongside elevated drying fan.
- Lights-off feedforward creates at most the configured fan bias when RH/VPD risk is present, creates zero bias when the tent is already dry/high-VPD, and decays to zero after lights-off.
- Dehumidifier pre-enable before lights-off happens only from sustained fan burden or RH already above the upcoming lights-off ceiling.

Replay acceptance should compare current behavior against new behavior using recent local telemetry. A successful run should show:

- Fewer large fan duty reversals, defined as a change of at least 30 percentage points followed by an opposite change of at least 30 percentage points within 10 minutes.
- Similar or better RH-in-band percentage for the relevant stage/phase.
- Similar or better time spent below unsafe high-RH margins.
- Dehumidifier cycles that respect dwell and do not increase materially without improving fan burden.

Replay reporting is required for two windows:

- Last 1 day, ending at replay time.
- Last 4 days, ending at replay time.

For each window, report at least: total ticks, large fan steps, large fan reversals, median absolute RH error, RH-in-band percentage, high-RH exceedance minutes, high-VPD exceedance minutes, dehumidifier cycles, humidifier/dehumidifier conflict avoidance events, and any hard safety overrides. Include both baseline/current-controller metrics and new-controller replay metrics in the same table so the reviewer can see the tradeoffs.

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
- Latest `2026-05-31` ramp-up reasons were dominated by `hard_rh_guard` and `hard_temperature_guard`; after cleanup, fan-elevated reasons are drying-only in the new controller replay.

Milestone 1 validation:

- `uv run pytest apps/hwd/tests/test_climate_controller.py -q`: `62 passed, 7 xfailed`.
- `uv run ruff check apps/hwd/tests/test_climate_controller.py apps/hwd/src/dirt_hwd/services/climate_controller.py debug/cascade-rh-control/analyze.py`: passed.
- `uv run python debug/cascade-rh-control/analyze.py`: read-only replay succeeded, skipping two malformed historical JSONL lines.

Milestone 1 baseline replay output from `uv run python debug/cascade-rh-control/analyze.py`:

```text
window  start              end                ticks  large_fan_steps  large_fan_reversals  rh_in_band_pct  median_abs_rh_error  high_rh_min  high_vpd_min  dehumidifier_cycles  conflict_avoidance  hard_safety_overrides
------  -----------------  -----------------  -----  ---------------  -------------------  --------------  -------------------  -----------  ------------  -------------------  ------------------  ---------------------
1d      2026-05-30T05:03Z  2026-05-31T05:03Z  2381   80               47                   61.8            1.7                  551.3        230.7         109                  1129                1067
4d      2026-05-27T05:03Z  2026-05-31T05:03Z  9541   149              83                   61.6            2.5                  2211.9       450.2         354                  4124                4879
```

Milestone 2 refactor outcome:

- `apps/hwd/src/dirt_hwd/services/climate_controller.py` now uses explicit source-owned names for fan RH demand and dehumidifier capacity request. The public service boundary stayed unchanged and later cascade behaviors were not implemented.
- `climate_controller` tick diagnostics now use truthful fields such as `raw_fan_rh_demand_pct`, `delivered_rh_drying_capacity_pct`, and `dehumidifier_capacity_request`; `docs/observability.md` was updated for those fields.
- Validation: `uv run pytest apps/hwd/tests/test_climate_controller.py -q` passed with `62 passed, 7 xfailed`; `uv run ruff check apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py` passed.
- Simplify pass used the local fallback because no subagent-spawn tool is available. Reuse review found no existing helper to reuse; quality review removed stale state/tuning names and one unreachable fan-allocation branch; efficiency review found no added hot-path or IO concern.

Milestone 3 fan inner-loop outcome:

- Fan allocation now computes `fan_rh_target = floor + rh_vpd_inner_loop_output` without a temperature-derived fan target.
- Mild RH above the phase ceiling now raises the fan first and reserves immediate dehumidifier request for emergency RH or existing sustained burden behavior; the slow dehumidifier outer loop remains open for milestone 4.
- Low temperature no longer suppresses RH/VPD drying fan demand; the heater loop compensates independently.
- Validation: `uv run pytest apps/hwd/tests/test_climate_controller.py -q` passed with `68 passed, 3 xfailed`; `uv run ruff check apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py` passed.
- Simplify pass used the local fallback because no subagent-spawn tool is available. Reuse review found no existing helper to reuse; quality review replaced a hard-coded 12-hour dark period with countdown-derived timing and removed stale temperature-bypass plumbing; efficiency review found no added hot-path or IO concern.

Milestone 4 slow dehumidifier outer-loop outcome:

- Dehumidifier requests now come from an explicit sustained fan-burden timer: observed fan elevation at least `25%` above floor for `600s` while RH/VPD indicate drying load. Emergency RH can still request immediately.
- Dehumidifier turn-off now requires the fan to remain near floor and RH/VPD to remain stable for `900s`; a single recovered tick no longer turns the dehumidifier off. Existing minimum on/off dwell still gates physical transitions.
- `ClimateState` now tracks `dehumidifier_fan_burden_started_at` and `dehumidifier_stable_off_started_at`; tick diagnostics include the matching elapsed seconds alongside `dehumidifier_capacity_request` and delivered drying capacity for anti-windup.
- Validation: `uv run pytest apps/hwd/tests/test_climate_controller.py -q` passed with `70 passed, 2 xfailed`; `uv run ruff check apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py` passed.
- Simplify pass used the local fallback because no subagent-spawn tool is available. Reuse review found no existing helper to reuse; quality review tightened request decisions so stale burden/stable timers cannot cause a one-tick transition after current conditions changed; efficiency review found no added IO or hot-path concern.

Milestone 5 bounded lights-off feedforward outcome:

- `ClimateTuning` now includes the explicit lights-off feedforward knobs from the plan: `2700s` pre-window, `1800s` decay, `15%` max fan bias, RH/VPD risk margins, RH slope threshold, an explicit `5%` dry-air margin, and a separate `floor + 20% for 600s` fan-burden pre-enable threshold.
- Feedforward is added as a bounded bias inside the fan RH/VPD inner loop. It ramps during the 45-minute pre-lights-off window, decays for 30 minutes after lights-off, logs `lights_off_feedforward_bias_pct` and `lights_off_feedforward_rh_slope_pct_per_10m`, and stays zero for high-VPD or dry-air conditions.
- Pre-lights-off dehumidifier request is now gated to sustained fan burden or RH above the upcoming lights-off ceiling; approaching lights-off alone no longer pre-enables it.
- Review correction: the sustained fan-burden predicate now requires current fan elevation as well as elapsed timer state, so a stale `fan_burden_pre_enable_started_at` cannot create feedforward bias or pre-enable the dehumidifier for one tick after burden clears.
- Validation: `uv run pytest apps/hwd/tests/test_climate_controller.py -q` passed with `77 passed`; `uv run ruff check apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py` passed.
- Simplify pass used the local fallback because no subagent-spawn tool is available. Reuse review replaced duplicated lights-off elapsed math with `_minutes_since_lights_off`; quality review kept feedforward's `5%` dry-air threshold separate from other margins; efficiency review found no added IO, broad scans, or hot-path concern.

Milestone 6 replay/report outcome:

- `debug/cascade-rh-control/analyze.py` now reports logged baseline metrics and new-controller pure replay metrics in the same table for the required last-1-day and last-4-day windows. It remains read-only by default: it reads `var/logs/climate_controller/*.jsonl`, prints to stdout, and only writes a report when `--output PATH` is explicitly supplied.
- Replay command: `uv run python debug/cascade-rh-control/analyze.py`.
- Replay window anchor after fan-as-cooling cleanup: latest local tick at `2026-05-31T06:16Z`; windows `2026-05-30T06:16Z..2026-05-31T06:16Z` and `2026-05-27T06:16Z..2026-05-31T06:16Z`.
- Replay output:

```text
window  source                 start              end                ticks  large_fan_steps  large_fan_reversals  rh_in_band_pct  median_abs_rh_error  high_rh_min  high_vpd_min  dehumidifier_cycles  conflict_avoidance  hard_safety_overrides
------  ---------------------  -----------------  -----------------  -----  ---------------  -------------------  --------------  -------------------  -----------  ------------  -------------------  ------------------  ---------------------
1d      logged_baseline        2026-05-30T06:16Z  2026-05-31T06:16Z  2379   89               56                   62.0            1.7                  548.8        233.1         108                  1135                1085
1d      new_controller_replay  2026-05-30T06:16Z  2026-05-31T06:16Z  2379   24               0                    62.0            1.7                  548.8        233.1         0                    2379                1085
4d      logged_baseline        2026-05-27T06:16Z  2026-05-31T06:16Z  9536   164              95                   61.3            2.5                  2229.1       452.6         359                  4183                4895
4d      new_controller_replay  2026-05-27T06:16Z  2026-05-31T06:16Z  9536   64               1                    61.3            2.5                  2229.1       452.6         2                    9526                5825
```

- Interpretation: removing fan-as-cooling and low-temperature fan suppression materially simplifies actuator decisions in replay. The old alternating `hard_rh_guard` up / `hard_low_temperature_guard` down pattern is almost gone. RH/VPD exposure remains unchanged under the historical sensor trace, so this does not prove final deployed RH/VPD control.
- Tuning follow-up: after deployment, inspect live `climate_controller` logs around lights-off for (1) whether emergency RH bypass still creates abrupt fan moves, (2) whether the dehumidifier outer loop stays latched too long under cold/high-RH night conditions, and (3) whether the high conflict-avoidance count simply reflects dehumidifier-on humidifier suppression or points to overactive dehumidifier capacity request.
- Validation: `uv run pytest apps/hwd/tests/test_climate_controller.py -q` passed with `77 passed`; `uv run pytest apps/hwd/tests -q` passed with `325 passed`; `uv run pytest apps/tests/invariants -q` passed with `41 passed`; `uv run ruff check` passed; `uv run python debug/cascade-rh-control/analyze.py` passed while skipping the two known malformed historical JSONL lines.
- Simplify pass used the local fallback because no subagent-spawn tool is available. Reuse review kept the analyzer aligned with the existing `debug/humidifier-shadow/analyze.py` local import pattern; quality review fixed line-length and argument-count issues; efficiency review found no hardware, DB, service, or broad-write concern.

Source references used while drafting:

- Control.com cascade control: https://control.com/textbook/basic-process-control-strategies/cascade-control/
- Control.com split-range control: https://control.com/textbook/control-valves/split-ranging/
- Control.com PID integral windup article: https://control.com/technical-articles/intergral-windup-method-in-pid-control/
- Control Engineering cascade overview: https://www.controleng.com/fundamentals-of-cascade-control/


## Interfaces and Dependencies

The main implementation interface is `decide_climate()` and its supporting dataclasses in `apps/hwd/src/dirt_hwd/services/climate_controller.py`. The service boundary remains `ClimateControllerService`, which reads sensor values through `ReadingsService`, grow/lights context through `GrowStateService`, and dispatches through `ClimateActuators`.

Expected internal data after implementation:

- `ClimateTuning` includes explicit tuning for fan RH loop, fan burden windows, dehumidifier burden thresholds, and lights-off feedforward bias.
- `ClimateTuning` includes lights-off feedforward window, decay duration, maximum fan bias, RH/VPD risk margins, RH slope threshold, and fan-burden pre-enable threshold/window.
- `ClimateState` stores enough state to support fan/dehumidifier cascade behavior: fan integral or tracked burden, dehumidifier dwell state, and any feedforward decay state that must persist across ticks.
- `climate_controller` logs include enough fields to diagnose fan RH demand, sustained fan burden, dehumidifier outer-loop request, and delivered actuator output.

No new external service or package dependency is expected.


## Revision Notes

- 2026-05-31: Initial ExecPlan drafted for review.
- 2026-05-31: Removed the earlier fan-as-cooling policy after replay breakdown showed hard RH fan-up versus hard low-temperature fan-down was the dominant oscillation path.
- 2026-05-31: Reran replay after removing fan-as-cooling; large fan reversals dropped to `0` over 1 day and `1` over 4 days in the read-only replay.
- 2026-05-31: Released dehumidifier capacity immediately when VPD is above the phase high edge and RH is not in guard, so humidification is no longer blocked by a stale dehumidifier stable-off timer.
- 2026-05-31: Added concrete lights-off feedforward policy after operator review.
- 2026-05-31: Added required last-1-day and last-4-day replay report for milestone 6.
