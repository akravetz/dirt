# VPD-First Climate Control

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, the main tent climate controller will treat vapor pressure deficit, or VPD, as the primary controlled variable instead of treating temperature as the heater's primary objective. The grower will be able to observe a night-period controller that holds VPD inside the active grow-stage band while respecting temperature and relative-humidity safety constraints, and that avoids the current pattern where the ThermoForge heater repeatedly jumps from off to high levels and back off.

The user-visible goal is stable overnight VPD without actuator chatter. When lights go off and the tent gets cold, the controller should converge toward a modest heater level or dehumidifier state that maintains VPD rather than repeatedly commanding approximately `0 -> 90 -> 0 -> 90`. The behavior will be visible in `var/logs/climate_controller/YYYY-MM-DD.jsonl` through new per-tick fields for VPD setpoint/band, VPD error, active control mode, raw PI demand, anti-windup/saturation state, actuator dwell state, and quantized actuator targets. It will also be visible in persisted metrics such as `vpd_kpa`, `temperature_f`, `humidity_pct`, `heater_heat_level`, `dehumidifier_on`, `humidifier_mist_level`, and `fan_duty_pct`.

The core design is a constrained, mode-supervised PI controller:

- VPD is the controlled variable.
- Humidifier, dehumidifier, heater, and fan are manipulated variables.
- Temperature, RH, actuator minimum dwell times, actuator saturation, and conflict rules are constraints.
- The heater may raise VPD when the air is too wet from the plant's perspective, but only inside a safe temperature envelope and with a 5 minute minimum dwell for normal heater changes.
- Temperature safety is asymmetric: the controller may use heat for VPD recovery, but it must force heater off at 80°F for pest-prevention safety.


## Progress

- [x] (2026-05-24) Reviewed `.agents/PLANS.md`, `docs/commands.md`, `docs/grow-state.md`, `docs/observability.md`, and `docs/rules/simple-clean-architecture.md`.
- [x] (2026-05-24) Reviewed current climate controller implementation in `apps/hwd/src/dirt_hwd/services/climate_controller.py`, policy in `apps/hwd/src/dirt_hwd/services/climate_policy.py`, app wiring in `apps/hwd/src/dirt_hwd/app.py`, and ThermoForge actuator boundaries in `apps/hwd/src/dirt_hwd/services/climate_actuators.py`.
- [x] (2026-05-24) Inspected recent `var/logs/climate_controller/2026-05-24.jsonl` entries and confirmed heater cycling around lights-off: the controller ramps through high ThermoForge levels, then turns off after crossing the upper/safety region, then repeats as temperature/VPD fall again.
- [x] (2026-05-24) Searched current control-theory references for PID/PI tuning, anti-windup, process lag/dead time, hysteresis, and temperature control.
- [x] (2026-05-24) Wrote this ExecPlan.
- [x] (2026-05-24 00:01 MDT) Milestone 1 complete: added VPD-first pure-controller diagnostic data and logging vocabulary, with focused tests for decision/log fields.
- [x] (2026-05-24 00:01 MDT) Milestone 2 complete: replaced temperature-primary demand selection with VPD-first split-range demand and focused tests.
- [x] (2026-05-24 00:01 MDT) Milestone 3 complete: added actuator-conditioned PI tracking, anti-windup, and bumpless handoff coverage.
- [x] (2026-05-24 00:01 MDT) Milestone 4 complete: added heater 5 minute dwell, one-level rate limiting, nearest-level quantization, and asymmetric safety behavior.
- [x] (2026-05-24 00:01 MDT) Milestone 5 complete: made low-VPD recovery ownership explicit and prevented actuator fighting.
- [x] (2026-05-24 00:01 MDT) Milestone 6 complete: audited and tightened focused VPD-first controller behavior tests.
- [x] (2026-05-24 00:02 MDT) Wired new logging fields and validated with tests.
- [x] (2026-05-24 00:02 MDT) Focused and full validation passed.
- [x] (2026-05-24 00:51 MDT) Restarted `dirt-hwd` after code/test validation, live preflight checks, and a post-restart correction.
- [x] (2026-05-24 01:01 MDT) Observed an initial dark-period control window and recorded measured outcomes.
- [x] (2026-05-24 01:18 MDT) Incorporated live grower feedback that the physical dehumidifier recovers slowly: removed the dehumidifier-ownership heater kill and validated focused controller tests.
- [x] (2026-05-24 01:20 MDT) Restarted `dirt-hwd` with the simplified heater/dehumidifier coexistence behavior and observed initial live ticks.
- [x] (2026-05-24 01:54 MDT) Added RH hysteresis for elevated drying fan: for the current `65%` flower-late RH ceiling, enter above `63.5%` and do not leave until below `61%`; restarted `dirt-hwd`.


## Surprises & Discoveries

- Observation: The current controller already has PI-like pieces for heat demand, but the surrounding hard-low-temperature boost, `ceil()` quantization, 3 minute hold, weak level hysteresis, and immediate high-temperature off rule dominate behavior.
  Evidence: `ClimateTuning` sets `heater_kp=22.0`, `heater_ki=0.04`, `heater_level_hysteresis_pct=4.0`, and `heater_minimum_hold_s=180.0` in `apps/hwd/src/dirt_hwd/services/climate_controller.py`. `_heat_p_term()` forces at least 55% output when below the hard floor; `_heat_level()` maps by `ceil(heat_pct / 10.0)`.

- Observation: Recent logs show the user-observed oscillation as controller behavior, not just UI rendering.
  Evidence: `var/logs/climate_controller/2026-05-24.jsonl` around `2026-05-24T04:38Z` through `05:09Z` shows the heater target rising from `0` to `5`, then `7`, `8`, `9`, `10`, then returning to `0`, with repeated `heater_hard_low_step_up`, `heater_level_request`, `heater_vpd_recovery_maintenance`, and `heater_safety_off` reasons.

- Observation: The current flower-early lights-off policy is narrow enough that the heater can hit the upper edge quickly.
  Evidence: `default_climate_policy()` sets flower-early lights-off temperature to `70.0-72.0°F` and VPD to `0.9-1.1 kPa` in `apps/hwd/src/dirt_hwd/services/climate_policy.py`.

- Observation: Control theory supports PI/PID only when paired with production constraints such as anti-windup, deadband, rate/dwell limits, and saturation handling.
  Evidence: NI's PID overview describes PID as a closed-loop controller that computes actuator output from setpoint error at a fixed loop rate, warns that excessive proportional gain can cause oscillation, and describes integral windup. MathWorks documents PI controllers with output saturation and internal anti-windup. Control.com recommends manual step-change tests to identify process response, lag/dead time, and hysteresis before tuning. Eurotherm notes that simple on/off temperature control causes process-variable fluctuation and needs hysteresis/deadband to reduce switching.


## Decision Log

- Decision: VPD is the primary controlled variable for the unified climate controller.
  Rationale: The user clarified that temperature in range is not sufficient if VPD is wrong. Temperature remains important, but as a plant-safety and pest-prevention constraint around VPD control rather than the heater's main optimization target.
  Date/Author: 2026-05-24 / User and Codex

- Decision: Use constrained, mode-supervised PI rather than a single monolithic PID.
  Rationale: The tent is a coupled multi-actuator system. Humidifier, dehumidifier, heater, and fan all affect VPD through different physical mechanisms and response times. A supervisor can choose the right actuator mode, then each actuator gets bounded PI-style demand and hardware-specific conditioning.
  Date/Author: 2026-05-24 / Codex

- Decision: Heater changes have a 5 minute minimum dwell during normal control.
  Rationale: The ThermoForge and tent air have thermal lag. Reconsidering heater level every 30 seconds makes the loop react before the plant has responded. A 5 minute dwell gives heat changes time to appear in canopy readings and reduces level chatter.
  Date/Author: 2026-05-24 / User

- Decision: Heater safety-off is asymmetric at 80°F.
  Rationale: The controller may intentionally allow warmer air when VPD is too low, but the grower wants an explicit pest-prevention cap. Heater safety-off at 80°F is different from the preferred night temperature band and should be enforced immediately.
  Date/Author: 2026-05-24 / User

- Decision: Add VPD deadband and hold/release behavior around the target band.
  Rationale: Noise and small VPD movement should not flip actuator modes. The controller should stop optimizing when VPD is inside the acceptable band, hold or gently decay current actuator state, and only exit a mode after a release threshold is crossed.
  Date/Author: 2026-05-24 / User and Codex

- Decision: Use anti-windup and external-reset style tracking for every actuator demand that can be clipped by constraints.
  Rationale: If the heater is capped by 80°F, the dehumidifier is held by minimum off time, or the humidifier is disabled by RH guard, integrators must track delivered output instead of accumulating impossible demand.
  Date/Author: 2026-05-24 / User and Codex

- Decision: Use bumpless handoff between actuator modes.
  Rationale: When the controller switches from heater-assisted VPD recovery to dehumidifier-owned recovery, or from lights-on to lights-off policy, stale integral state must not cause a sudden output jump.
  Date/Author: 2026-05-24 / User and Codex

- Decision: Do not add a permanent compatibility controller path.
  Rationale: This is source-owned code. Per `docs/rules/simple-clean-architecture.md`, replace the misleading temperature-primary heater allocation with the truthful VPD-primary model and update tests directly.
  Date/Author: 2026-05-24 / Codex


## Outcomes & Retrospective

- Milestone 1 completed at 2026-05-24 00:01 MDT. `ClimateDecision` now carries explicit VPD diagnostics (`active_mode`, active band, selected edge/setpoint, control VPD, signed error), raw/clipped/delivered demand diagnostics, anti-windup tracking reason vocabulary, and heater/dehumidifier allocation/limit reasons. `_log_tick()` flattens those fields into the `climate_controller` tick stream. Focused tests cover positive/negative VPD error semantics, selected VPD edge/setpoint, active mode, demand diagnostics, and log emission.

  Validation:
  - `uv run pytest apps/hwd/tests/test_climate_controller.py -q` -> 31 passed
  - `uv run ruff check apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py` -> passed

  Surprise: no behavior rewrite was needed for Milestone 1. The new diagnostics intentionally describe the current allocator behavior so later milestones can replace the temperature-primary controller against visible vocabulary.

- Milestone 2 completed at 2026-05-24 00:01 MDT. `_compute_demand()` now uses the active VPD band plus `policy.dehumidifier.vpd_deadband_kpa` as the primary split-range mode selector. High VPD requests humidification while suppressing drying and heat except hard-low temperature protection; low VPD requests drying with dehumidifier ownership near/above the RH ceiling and heater assist under the normal dwell/rate/safety limits; in-band/deadband VPD starts no new actuator mode; and heat demand/integral are suppressed at the explicit 80°F safety cap instead of the old preferred phase high edge.

  Validation:
  - `uv run pytest apps/hwd/tests/test_climate_controller.py -q` -> 32 passed
  - `uv run ruff check apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py` -> passed

  Surprise: reused `policy.dehumidifier.rh_deadband_pct` as the near-ceiling RH selector for dehumidifier ownership instead of adding another tuning field.

- Milestone 3 completed at 2026-05-24 00:01 MDT. Humidifier, drying, heat, and cooling-fan integrators now track delivered/clipped output. Raw heat demand remains visible before 80°F and dehumidifier-ownership clipping, phase changes reset stale integrals, and service-restart startup can seed integrals from observed nonzero actuator readings for bumpless handoff.

  Validation:
  - `uv run pytest apps/hwd/tests/test_climate_controller.py -q` -> 37 passed
  - `uv run ruff check apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py` -> passed
  - `git diff --check -- apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py` -> passed

  Surprise: existing drying tracking used requested fan contribution instead of actual allocated fan output; Milestone 3 changed tracking to use delivered fan/dehumidifier output.

- Milestone 4 completed at 2026-05-24 00:01 MDT. Heater allocation now uses `heater_minimum_dwell_s = 300.0`, nearest ThermoForge level quantization with 5% boundary hysteresis, one-level-per-dwell rate limiting, immediate `80.0°F` safety-off, stale-temperature failsafe off, VPD recovery maintenance below release, and gradual step-down once heat is no longer requested.

  Validation:
  - `uv run pytest apps/hwd/tests/test_climate_controller.py -q` -> 41 passed
  - `uv run ruff check apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py` -> passed
  - `git diff --check -- apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py` -> passed

  Surprise: during dehumidifier-owned recovery, heater now steps down over dwell windows rather than hard-off immediately. That preserves the Milestone 4 dwell/rate-limit rule; full actuator conflict ownership remains Milestone 5.

- Milestone 5 completed at 2026-05-24 00:01 MDT. Low-VPD recovery ownership is explicit. High/near-ceiling RH gives dehumidifier ownership, but heater VPD assist may still run under the normal dwell/rate limits and the 80°F cap. Heat integral tracks delivered heat during dehumidifier-owned recovery. Focused tests cover dehumidifier ownership, heat-assisted low-VPD recovery, high-VPD humidifier ownership, humidifier/dehumidifier mutual exclusion, and fan/heater conflict rules.

  Validation:
  - `uv run pytest apps/hwd/tests/test_climate_controller.py -q` -> 47 passed
  - `uv run ruff check apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py` -> passed
  - `git diff --check -- apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py` -> passed

  Surprise: Live grower feedback after restart showed that treating dehumidifier ownership as a heater kill was too conservative for the actual tent because the physical dehumidifier recovers slowly. The later simplification removes that kill and lets heater assist coexist with dehumidifier recovery.

- Milestone 6 completed at 2026-05-24 00:01 MDT. Focused climate-controller tests now cover the VPD-first behaviors listed in this plan: low-VPD heater assist through the 70-72°F lights-off range, RH-ceiling dehumidifier ownership without heat windup, heater dwell/rate limits with immediate 80°F and stale-temperature safety-off, VPD deadband hold/gradual decay, bumpless phase and dehumidifier handoffs, humidifier/dehumidifier mutual exclusion, and fan/heater coexistence with cooling suppression.

  Validation:
  - `uv run pytest apps/hwd/tests/test_climate_controller.py -q` -> 49 passed
  - `uv run ruff check apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py` -> passed
  - `git diff --check -- apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py` -> passed

- Post-restart correction completed at 2026-05-24 00:51 MDT, then superseded by the 01:18 MDT simplification. Initial live observation showed that when RH/VPD gave dehumidifier ownership but the dehumidifier was held by `dehumidifier_min_off_hold`, the heater could still be held by heater dwell with `delivered_heat_pct=40.0` even though heat was clipped. That correction briefly suppressed heater VPD assist based on `demand.dehumidifier_owns_vpd`; live grower feedback then removed that suppression because the real dehumidifier recovers slowly.

  Validation:
  - `uv run pytest apps/hwd/tests/test_climate_controller.py -q` -> 50 passed
  - `uv run pytest apps/hwd/tests/test_climate_controller.py apps/hwd/tests/test_climate_policy.py apps/hwd/tests/test_climate_actuators.py -q` -> 66 passed
  - `uv run pytest apps/hwd/tests -q` -> 287 passed
  - `uv run pytest apps/tests/invariants -q` -> 112 passed
  - `uv run ruff check apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py` -> passed
  - `uv run ruff check` -> passed
  - `git diff --check -- apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py` -> passed

- Live restart and observation completed at 2026-05-24 01:01 MDT, before the 01:18 MDT simplification. `systemctl --user status dirt-hwd --no-pager` reported `active (running)` after restart. During the initial dark-period sample, climate ticks included the new VPD-first diagnostic fields. No simultaneous humidifier/dehumidifier target appeared. At that time, dehumidifier/RH ownership held heater target at `0`; VPD moved through low-VPD dehumidifier correction, in-band cooling/hold, then RH-guard dehumidifier correction. The old high-amplitude heater `0 -> 9/10 -> 0` cycling did not appear in that observation window.

  Representative corrected observations:
  - `2026-05-24T06:58:08Z`: `active_mode=hard_rh_guard`, `target_dehumidifier_on=true`, `target_heater_level=0`, `vpd_kpa=0.8938`, `temperature_f=70.754`.
  - `2026-05-24T06:59:17Z`: `target_dehumidifier_on=true`, `target_heater_level=0`, `delivered_drying_pct=100.0`, `delivered_heat_pct=0.0`, `vpd_kpa=0.8258`.
  - `2026-05-24T06:59:51Z`: same ownership state held.
  - `2026-05-24T07:01:01Z`: `target_dehumidifier_on=true`, `target_heater_level=0`, `raw_heat_demand_pct=0.2`, `clipped_heat_demand_pct=0.0`, `delivered_heat_pct=0.0`.

  Surprise: an archive verification error for a historical timelapse date appeared in the journal during the first restart, but `dirt-hwd` remained active and continued ingesting sensor posts. This was outside the climate-controller path and did not block rollout.

- Live simplification completed at 2026-05-24 01:18 MDT. Based on grower feedback that the real dehumidifier acts slowly, the controller no longer kills heater assist just because RH/high-moisture recovery is dehumidifier-owned. Low-VPD heat can now run with the dehumidifier, subject to the same nearest-level quantization, 5 minute dwell, one-level rate limit, elevated-fan conflict handling, stale-sensor fail-safe, and immediate 80°F heater safety-off.

  Validation:
  - `uv run pytest apps/hwd/tests/test_climate_controller.py -q` -> 50 passed

  Runtime observation after restart:
  - `systemctl --user status dirt-hwd --no-pager` reported `active (running)` after the 2026-05-24 01:19 MDT restart.
  - `2026-05-24T07:19:08Z`: with `humidity_pct=67.22`, `vpd_kpa=0.822`, and dehumidifier on, the controller requested `target_heater_level=1` with `heater_allocation_reason=heater_level_request`; reasons included both `vpd_recovery_heat` and `dehumidifier_owns_vpd_recovery`.
  - `2026-05-24T07:19:44Z`: dehumidifier remained on, heater held level `1`, and VPD rose to `0.873`; no simultaneous humidifier/dehumidifier target appeared.

- Drying fan hysteresis completed at 2026-05-24 01:54 MDT. Elevated drying fan entry now uses `rh_max_pct - 1.5`, and exit uses `rh_max_pct - 4.0`; for the current flower-late `65%` RH ceiling, that means enter above `63.5%` and hold until RH drops below `61%`. The hysteresis is fan-specific; it does not change the dehumidifier or humidifier ownership thresholds.

  Validation:
  - `uv run pytest apps/hwd/tests/test_climate_controller.py -q` -> 55 passed
  - `uv run pytest apps/hwd/tests/test_climate_controller.py apps/hwd/tests/test_climate_policy.py apps/hwd/tests/test_climate_actuators.py -q` -> 71 passed
  - `uv run ruff check apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py` -> passed

  Runtime observation after restart:
  - `systemctl --user status dirt-hwd --no-pager` reported `active (running)` after the 2026-05-24 01:54 MDT restart.
  - Immediate post-restart ticks had RH around `62.5%` with fan at floor, which is below the `63.5%` entry threshold, so no new elevated fan cycle was started.

- Validation milestone completed at 2026-05-24 00:02 MDT.

  Validation:
  - `uv run pytest apps/hwd/tests/test_climate_controller.py apps/hwd/tests/test_climate_policy.py apps/hwd/tests/test_climate_actuators.py -q` -> 65 passed
  - `uv run ruff check apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/src/dirt_hwd/services/climate_policy.py apps/hwd/tests/test_climate_controller.py apps/hwd/tests/test_climate_policy.py` -> passed
  - `uv run pytest apps/hwd/tests -q` -> 286 passed
  - `uv run pytest apps/tests/invariants -q` -> 112 passed
  - `uv run ruff check` -> passed


## Context and Orientation

Repository root is `/home/akcom/code/dirt`.

Read these docs before implementation:

- `docs/commands.md` before running tests, lint, systemd commands, or service commands.
- `docs/grow-state.md` before changing stage, lights, or target policy.
- `docs/observability.md` before changing `log_event()` fields or adding log streams.
- `docs/rules/simple-clean-architecture.md` before changing controller architecture or deciding whether to preserve old code paths.
- `docs/database.md` only if the implementation changes persisted device/capability/schedule rows or SQLModel models.
- `docs/rules/boundary-contracts.md` only if the implementation changes FastAPI models, generated contracts, gateway/control-plane payloads, outbox JSON, command payloads/results, or other process/network/persistence boundaries.

Current production wiring:

- `apps/hwd/src/dirt_hwd/app.py` wires `ClimateControllerService` as a default background service.
- `ClimateControllerService` reads latest canopy `temperature_f`, `humidity_pct`, and `vpd_kpa`, plus current actuator readings, then calls pure `decide_climate()`.
- `apps/hwd/src/dirt_hwd/services/climate_controller.py` owns the current demand/allocation logic.
- `apps/hwd/src/dirt_hwd/services/climate_policy.py` owns explicit day/night climate policy.
- `apps/hwd/src/dirt_hwd/services/climate_actuators.py` owns fan, humidifier, Kasa dehumidifier, and ThermoForge heater actuator boundaries.
- `apps/hwd/tests/test_climate_controller.py` owns focused pure-controller behavior tests.
- `apps/hwd/tests/test_climate_policy.py` owns climate policy tests.
- `apps/hwd/tests/test_climate_actuators.py` owns actuator boundary tests.

Current relevant behavior in `apps/hwd/src/dirt_hwd/services/climate_controller.py`:

- `ClimateTuning.heater_minimum_hold_s` is `180.0`, which is shorter than the requested 5 minute dwell.
- `_compute_demand()` computes `heat_error` from temperature floor/high policy and VPD recovery special cases, not primarily from VPD error.
- `_heat_p_term()` forces at least `55.0` percent demand when `hard_low_temp` is true.
- `_allocate_heater()` can bypass hold when `demand.hard_low_temp and requested > current`.
- `_allocate_heater()` returns `0` at the current policy high/safety boundary, which creates sharp off transitions.
- `_updated_state()` tracks heat integral against delivered quantized heat by setting `heat_integral = delivered_pct - p_term`, which is useful but not sufficient because the demand model and allocation are still temperature-primary.

Definitions:

- VPD: vapor pressure deficit in kPa. Lower VPD means the air is wetter from the plant's perspective; higher VPD means drier air.
- Controlled variable: the measured variable the loop tries to hold in range. In this plan, it is VPD.
- Manipulated variable: an actuator output the controller can change. In this plan: humidifier intensity, dehumidifier power, heater level, and fan duty above floor.
- Constraint: a limit that bounds control action. In this plan: temperature safety cap, RH ceiling, stale sensor failsafe, actuator saturation, minimum dwell, and conflict rules.
- Deadband: a small region around the target band where no new corrective action is started.
- Dwell: a minimum time an actuator state or level must be held before normal control can change it.
- Anti-windup: logic that prevents integrators from accumulating demand that cannot be delivered because an actuator is saturated, disabled, rate-limited, or clipped by a constraint.
- Bumpless handoff: initializing or tracking integrator state so switching modes does not cause sudden output jumps.


## Plan of Work

Milestone 1: Add VPD-first controller data and logging vocabulary.

Update `apps/hwd/src/dirt_hwd/services/climate_controller.py` to make VPD control explicit in the pure decision types. Keep the code direct and local to the existing controller unless duplication becomes real.

Add or revise internal fields so a `ClimateDecision` can explain:

- active VPD band and selected VPD setpoint or edge;
- filtered/current VPD used for control;
- signed VPD error, where positive means too dry and negative means too wet;
- active mode, for example `vpd_hold`, `vpd_humidify`, `vpd_dehumidify`, `vpd_heat_assist`, `hard_rh_guard`, `hard_temperature_guard`, or `sensor_failsafe`;
- raw continuous demand before allocator clipping for humidifier, drying, heat, and cooling;
- delivered/clipped demand after constraints;
- anti-windup tracking reason;
- dwell/rate-limit reason for heater and dehumidifier.

Update `_log_tick()` so the top-level `climate_controller` log contains enough information to diagnose why the loop chose a mode and whether it was prevented from acting. Do not log secrets or provider credentials.

Milestone 2: Replace heater temperature-primary demand with VPD-first split-range demand.

Refactor `_compute_demand()` so VPD error is primary:

- If VPD is above the active upper band plus deadband, the air is too dry. Request humidifier demand. Suppress drying outputs. Keep heater off unless temperature is independently below a hard minimum.
- If VPD is below the active lower band minus deadband, the air is too wet. Request drying demand. Prefer the dehumidifier when RH is high or above the RH ceiling. Allow heater-assisted VPD recovery under the normal dwell/rate limits and the 80°F safety cap, even when the dehumidifier is also recovering slowly. Allow elevated fan drying only when temperature is safe and the fan will not fight heater recovery.
- If VPD is inside the active band or deadband, hold or gently decay active outputs. Do not create new actuator changes solely to optimize within the band.

Keep temperature as a constraint and secondary trim:

- If temperature is below the hard minimum, heater may run to protect the grow, but still use 5 minute dwell and rate limiting unless a future explicitly dangerous low-temperature threshold is added.
- If temperature is at or above 80°F, force heater off immediately and suppress any heat integral accumulation.
- If temperature is high but below 80°F, fan cooling may be allowed, but do not run elevated cooling fan against an active heater target.

Keep RH as a constraint and mode selector:

- If RH is above the phase/stage RH ceiling, force humidifier off.
- If low VPD coincides with high RH, let the dehumidifier own moisture removal.
- Do not kill heater assist solely because the dehumidifier owns moisture removal. The real dehumidifier recovers slowly, so heater assist may coexist with dehumidification while the 80°F cap, dwell, rate limit, and fan conflict rules prevent aggressive heat swings.

Use the existing `policy.dehumidifier.vpd_deadband_kpa` value, currently `0.05`, as the initial VPD mode deadband unless implementation evidence shows a separate tuning field is clearer. If a separate field is added to `ClimateTuning`, start with `0.05 kPa` and name it directly, for example `vpd_control_deadband_kpa`.

Milestone 3: Add actuator-conditioned PI with anti-windup and bumpless handoff.

Represent continuous PI demand for each actuator family before quantization:

- `humidifier_pct` for high VPD;
- `drying_pct` for low VPD or high RH;
- `heat_pct` for low VPD heat-assist and hard low-temperature protection;
- `cooling_fan_pct` for high temperature.

The PI integrators must update based on delivered output, not raw requested output. Preserve the existing `_track_integral()` pattern where it is correct, and extend it so every mode switch and clipped output has a clear tracking path.

Required anti-windup cases:

- Humidifier demand clipped to zero by RH ceiling, dehumidifier-on state, lights/prep guard, stale sensor, or high humidity.
- Drying demand clipped because dehumidifier is held off by minimum-off dwell, fan is capped by temperature safety, or VPD has re-entered band.
- Heat demand clipped because temperature reached 80°F, heater is held by 5 minute dwell/rate limiting, the active mode does not request heat, or stale temperature prevents safe heat.
- Cooling fan demand clipped because heater is active or fan is already at max.

Required bumpless handoff cases:

- lights-on to lights-off or lights-off to lights-on phase change;
- humidifier mode to dehumidifier mode;
- dehumidifier-owned low-VPD recovery to heater-assisted low-VPD recovery;
- heater-assisted recovery to VPD hold;
- service restart using observed current actuator readings.

Implementation guidance: when a mode is inactive, track that mode's integral to delivered output or decay it toward zero rather than carrying stale demand forward. Do not keep old temperature-primary heat integral semantics if they obscure the VPD-first model.

Milestone 4: Add heater quantization, 5 minute dwell, and asymmetric safety.

Rework `_allocate_heater()` and related helpers so the heater maps continuous VPD/temperature demand to ThermoForge levels without chatter.

Rules:

- Active ThermoForge levels remain `1..10`; `0` means off.
- Normal heater target changes must obey `heater_minimum_dwell_s = 300.0`.
- Normal heater target changes should be rate-limited to one level per dwell window unless tests show one-level stepping is too weak for recovery. Start with one level per 5 minutes because the current problem is overshoot and high-amplitude cycling.
- Heater safety-off at `80.0°F` bypasses dwell immediately.
- Stale temperature also bypasses dwell to off unless a separate fresh hard-low safety rule is active.
- The preferred lights-off temperature band may still inform comfort/logging, but it must not cause immediate off at 72°F when VPD is still below target and the 80°F safety cap is far away.
- A VPD hold/release condition should allow the heater to stay at its current modest level while VPD is still below the release threshold, rather than turning off immediately at the old temperature high edge.
- Once VPD is inside band and temperature is not below the floor, decay heat demand gradually or step down one level per dwell window.

Replace `ceil()`-biased level selection with a less aggressive quantizer. Acceptable starting approach:

- Map `heat_pct` to nearest supported level rather than always rounding up.
- Add level-boundary hysteresis wide enough to matter with 10% buckets, for example require a requested output to cross the next level boundary by 5% before changing levels.
- Keep a minimum active level only when heat demand is nonzero and the selected mode actually permits heat.

The existing `heater_level_hysteresis_pct=4.0` is too small relative to 10% levels. Either increase it or replace it with explicit level-boundary hysteresis.

Milestone 5: Keep dehumidifier and humidifier from fighting the heater.

Update allocation rules and tests so the controller has clear ownership of low-VPD recovery:

- If RH is above ceiling, dehumidifier owns moisture removal. Heater may still run for low-VPD recovery under the normal dwell/rate limits and the 80°F cap.
- If dehumidifier is on due to low VPD/high RH, the heater integral should track delivered heat, not accumulate extra heat demand.
- If VPD is low but RH is not above ceiling and temperature has headroom, heater may own recovery.
- If VPD is high, humidifier owns recovery and heater must not be used for VPD.
- Never command humidifier and dehumidifier at the same time.

Preserve the fan floor. Fan floor is baseline filtration/mixing and is not a conflict with heating. Elevated fan cooling is a conflict with heating. Elevated fan drying is allowed with heating only when high RH or very low VPD creates a safety reason, and that reason must appear in `decision.reasons` or `decision.conflicts`.

Milestone 6: Focused tests for the new control behavior.

Update `apps/hwd/tests/test_climate_controller.py` with tests that would fail under the current temperature-primary heater model and pass under VPD-first control.

Required tests:

- Low VPD at lights-off with temperature `70-72°F` requests heater-assisted VPD recovery when RH is not above ceiling and temperature is below 80°F.
- Low VPD with RH above ceiling requests dehumidifier first and does not wind up heater demand.
- Heater does not turn off merely because temperature crosses the old `72°F` preferred lights-off high edge while VPD is still below target; it only forces off at 80°F or stale-temperature safety.
- Heater normal changes obey 5 minute dwell.
- Heater can safety-off immediately at 80°F despite dwell.
- Heater level changes by at most one level per dwell window during normal control.
- VPD inside the deadband does not start a new actuator mode.
- VPD returning into band causes gradual hold/decay rather than immediate high-to-off transition.
- Phase change is bumpless: no stale heat/humidity integral creates a sudden target jump.
- Dehumidifier handoff is bumpless: turning dehumidifier on causes heater integral to track delivered heat rather than continue pushing up.
- Humidifier and dehumidifier are never both requested.
- Fan floor may coexist with heater; elevated cooling fan is suppressed while heater is active.

Update `apps/hwd/tests/test_climate_policy.py` only if new explicit policy/tuning fields are added.

Milestone 7: Validation, rollout, and live observation.

Run focused validation first:

    cd /home/akcom/code/dirt
    uv run pytest apps/hwd/tests/test_climate_controller.py apps/hwd/tests/test_climate_policy.py apps/hwd/tests/test_climate_actuators.py -q
    uv run ruff check apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/src/dirt_hwd/services/climate_policy.py apps/hwd/tests/test_climate_controller.py apps/hwd/tests/test_climate_policy.py

Then run broader validation:

    cd /home/akcom/code/dirt
    uv run pytest apps/hwd/tests -q
    uv run pytest apps/tests/invariants -q
    uv run ruff check

Before live restart, inspect current sensor freshness and actuator state using DB reads or existing logs. Do not restart blindly during a sensitive condition without knowing whether temperature/RH/VPD readings are fresh.

After restart:

    systemctl --user restart dirt-hwd
    systemctl --user status dirt-hwd --no-pager

Observe logs:

    tail -f var/logs/climate_controller/$(date +%F).jsonl

During the first 10-15 minutes, verify:

- there is only one climate authority issuing decisions;
- no simultaneous humidifier/dehumidifier target appears;
- heater targets change no faster than the 5 minute dwell unless safety-off fires;
- VPD error and active mode are logged clearly;
- if the heater is capped by 80°F, held by dwell/rate limiting, or disabled by inactive mode, heat integral does not continue winding up.

During the first dark-period window after deployment, verify the user-visible goal:

- heater does not repeat high-amplitude `0 -> 9/10 -> 0` cycling;
- heater either settles at a modest level or steps down/up gradually;
- VPD moves toward or remains within the target band;
- temperature remains below 80°F;
- RH remains below the configured ceiling or dehumidifier is actively correcting it.


## Concrete Steps

1. Confirm repository context and current diff:

    cd /home/akcom/code/dirt
    git status --short

2. Edit `apps/hwd/src/dirt_hwd/services/climate_controller.py`.

   Keep edits centered on pure controller data, `_compute_demand()`, `_allocate_heater()`, `_updated_state()`, and `_log_tick()`. Avoid touching provider code unless tests expose a real actuator-boundary need.

3. Add or update focused tests:

    cd /home/akcom/code/dirt
    uv run pytest apps/hwd/tests/test_climate_controller.py -q

4. Run formatter/lint as needed:

    cd /home/akcom/code/dirt
    uv run ruff format apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py
    uv run ruff check apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py

5. Run broader validation:

    cd /home/akcom/code/dirt
    uv run pytest apps/hwd/tests -q
    uv run pytest apps/tests/invariants -q
    uv run ruff check

Expected result: all focused tests, app tests, invariants, and ruff pass. If invariants fail, fix the source code; never edit `apps/tests/invariants/`.

6. Update this ExecPlan with progress, surprises, decisions, and validation evidence.

7. Only after validation, restart `dirt-hwd` and observe logs as described in `Validation and Acceptance`.


## Validation and Acceptance

Acceptance requires both automated tests and observable runtime behavior.

Automated acceptance:

- `uv run pytest apps/hwd/tests/test_climate_controller.py apps/hwd/tests/test_climate_policy.py apps/hwd/tests/test_climate_actuators.py -q` passes.
- `uv run pytest apps/hwd/tests -q` passes.
- `uv run pytest apps/tests/invariants -q` passes.
- `uv run ruff check` passes.
- New tests prove the heater cannot normally jump from off to high levels in one short cycle and cannot normally turn high-to-off solely because the preferred night temperature band high edge was crossed.

Runtime acceptance:

- `var/logs/climate_controller/YYYY-MM-DD.jsonl` includes VPD-first diagnostic fields for each tick.
- In a dark-period low-VPD condition, heater level changes obey 5 minute dwell except for 80°F safety-off or stale-sensor safety.
- Heater does not repeatedly oscillate between `0` and `9/10` while trying to recover VPD.
- If RH is above ceiling, dehumidifier ownership is visible in the reasons and heater assist remains bounded by dwell/rate limiting plus the 80°F cap.
- If VPD is in the configured deadband, the controller does not start new corrective actuator modes.
- At or above 80°F, heater target is `0` immediately and the log reason is explicit.

Human-observable success:

- Overnight charts show smoother `heater_heat_level` with fewer large on/off swings.
- `vpd_kpa` spends more time inside the active stage/phase band.
- `temperature_f` stays under 80°F.
- Actuator logs and UI no longer show repeated high-amplitude heater bouncing at lights-off.


## Idempotence and Recovery

Pure code edits and tests are safe to repeat.

Running `uv run pytest ...` and `uv run ruff check` is safe to repeat. Formatting with `uv run ruff format ...` is safe to repeat.

The service restart is the only live action in this plan:

    systemctl --user restart dirt-hwd

If the controller behaves unexpectedly after restart:

1. Stop active observation and capture the relevant `climate_controller` log excerpt.
2. Revert only the implementation changes made for this plan, preserving unrelated user work.
3. Restart `dirt-hwd`.
4. Confirm `systemctl --user status dirt-hwd --no-pager` is healthy.
5. Record the rollback and log evidence in this ExecPlan.

Do not use `git reset --hard` or destructive checkout commands unless the user explicitly asks for them. Do not edit human-owned invariant tests. Do not leave two climate authority loops commanding the same actuator as a rollback strategy.


## Artifacts and Notes

Control-theory sources used while writing this plan:

- NI, "The PID Controller & Theory Explained", updated March 7, 2025: https://www.ni.com/en/shop/labview/pid-theory-explained.html
- MathWorks, "PI Controller with Integral Anti-Windup": https://www.mathworks.com/help/sps/ref/picontrollerwithintegralantiwindupdiscreteorcontinuous.html
- Control.com textbook, "Self-regulating, Integrating, and Runaway Process Characteristics": https://control.com/textbook/process-dynamics-and-pid-controller-tuning/process-characteristics/
- Eurotherm, "PID Control made easy": https://www.eurotherm.com/temperature-control/pid-control-made-easy/
- Control Guru, "PI Control of the Heat Exchanger": https://controlguru.com/pi-control-of-the-heat-exchanger/

Representative current log pattern from `var/logs/climate_controller/2026-05-24.jsonl`:

    2026-05-24T04:38:41Z temp=70.03 vpd=0.826 current_heater=0 target_heater=5 reasons=vpd_recovery_heat|vpd_split_dry|heater_level_request
    2026-05-24T04:41:01Z temp=69.85 vpd=0.803 current_heater=8 target_heater=9 reasons=hard_low_temperature_guard|heater_hard_low_step_up
    2026-05-24T04:45:08Z temp=71.40 vpd=0.872 current_heater=9 target_heater=10 reasons=vpd_recovery_heat|heater_level_request
    2026-05-24T04:48:03Z temp=72.64 vpd=0.965 current_heater=10 target_heater=0 reasons=temperature_trim_cool|heater_safety_off

This is the behavior the implementation must eliminate.


## Interfaces and Dependencies

Expected code interfaces after implementation:

- `apps/hwd/src/dirt_hwd/services/climate_controller.py`
  - `ClimateTuning` includes a 300 second heater dwell setting and any explicit VPD deadband/rate-limit fields needed for readability.
  - `ClimateInput`, `ClimateState`, and `ClimateDecision` remain pure dataclass-style value objects.
  - `decide_climate(policy, state, inp, tuning)` remains the pure controller entry point.
  - `_compute_demand()` computes VPD-first demand.
  - `_allocate_heater()` enforces quantization, 5 minute dwell, rate limiting, deadband/hold behavior, and 80°F safety-off.
  - `_updated_state()` performs anti-windup/external-reset tracking for clipped or inactive modes.
  - `_log_tick()` emits VPD-first diagnostic fields.

- `apps/hwd/src/dirt_hwd/services/climate_policy.py`
  - Existing phase/stage policy remains the explicit source of VPD, temperature, RH, fan, stale-sensor, and dehumidifier-cycle policy.
  - Add policy fields only if a value is genuinely policy rather than controller tuning.

- `apps/hwd/tests/test_climate_controller.py`
  - Covers VPD-first behavior, 5 minute heater dwell, 80°F safety-off, deadband, anti-windup, bumpless handoff, and actuator conflict prevention.

No new third-party dependencies are expected.

No API contract, hosted browser contract, gateway payload, outbox JSON, or database schema change is expected for the first implementation. If implementation discovers that policy must become persisted or API-visible, stop and read `docs/database.md` and `docs/rules/boundary-contracts.md`, then update this plan before changing boundary contracts.


## Revision Notes

- 2026-05-24: Initial ExecPlan written from the user's VPD-first objective and explicit constraints: 5 minute heater dwell, 80°F asymmetric safety cap, deadband, anti-windup, and bumpless handoff.
