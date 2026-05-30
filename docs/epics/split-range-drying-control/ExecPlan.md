# Split-Range Drying Control

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, the main-tent climate controller will use one explicit drying demand to stage fan exhaust and dehumidifier power. The grower should see fewer overnight fan and dehumidifier oscillations after lights-off while preserving the late-flower target of `1.1-1.3 kPa` VPD and `60%` maximum relative humidity.

The observable problem this plan addresses appeared after the late-flower lights-off target was tightened on 2026-05-28. In the first three lights-off hours on 2026-05-28/29, `var/logs/climate_controller/2026-05-29.jsonl` showed the dehumidifier target flipping 30 times and the fan target changing 74 times. The controller was not failing outright; it was making several locally reasonable decisions from overlapping RH, VPD, fan-hysteresis, dehumidifier, and heater rules. The improved behavior should be visible in `climate_controller` log ticks: fewer dehumidifier target flips, fewer fan target changes, and reasons showing fan-first drying before binary dehumidifier boost near the low-VPD/high-RH boundary.


## Progress

- [x] (2026-05-29 00:12 MDT) Read `.agents/PLANS.md`, `docs/commands.md`, `docs/grow-state.md`, `docs/observability.md`, and `docs/rules/simple-clean-architecture.md`.
- [x] (2026-05-29 00:15 MDT) Inspected current `apps/hwd/src/dirt_hwd/services/climate_controller.py`, `apps/hwd/src/dirt_hwd/services/climate_policy.py`, and focused controller tests.
- [x] (2026-05-29 00:20 MDT) Diagnosed the lights-off oscillation from `var/logs/climate_controller/2026-05-29.jsonl`: dehumidifier target changed 30 times and fan target changed 74 times from 21:00-24:00 MDT.
- [x] (2026-05-29 00:26 MDT) Wrote this ExecPlan.
- [x] Milestone 1: Replace dehumidifier ownership with staged split-range drying demand.
- [x] Milestone 2: Pace fan allocation so fan behaves like a continuous actuator, not a threshold latch.
- [x] Milestone 3: Validate focused behavior, run hwd tests, and update this plan with results.
- [x] (2026-05-29) Implemented `dehumidifier_requested` staging from drying demand plus RH proximity to the phase ceiling.
- [x] (2026-05-29) Removed the old fan RH/VPD latch and made fan elevation consume drying demand directly.
- [x] (2026-05-29) Added fan minimum dwell state with emergency bypasses for hard-low temperature, severe RH, and high-temperature safety.
- [x] (2026-05-29) Ran focused and full hwd validation: `66 passed`, `303 passed`, Ruff check passed, and Ruff format check passed.


## Surprises & Discoveries

- Observation: The tightened late-flower lights-off policy is active and working numerically, but it exposed control-boundary chatter.
  Evidence: Post-lights-off ticks on 2026-05-29 show `vpd_low_kpa=1.1`, `vpd_high_kpa=1.3`, and `rh_max_pct=60.0`, with RH averaging `58.47%` and VPD averaging `1.09 kPa`.

- Observation: Current dehumidifier ownership is eager below the RH ceiling.
  Evidence: `_compute_demand()` sets `dehumidifier_owns_vpd = rh_guard or (vpd_too_low and _rh_high_for_dehumidifier(...))`, and `_rh_high_for_dehumidifier()` uses `rh_max_pct - 2%`. For late flower lights-off, that means dehumidifier ownership starts at `58%` RH when VPD is just below `1.05 kPa`.

- Observation: Fan RH hysteresis is independent of drying demand once the fan is elevated.
  Evidence: `_drying_fan_pct_after_hysteresis()` enters above `rh_max_pct - 1.5%` and holds until below `rh_max_pct - 4%`, which is `58.5%` and `56%` for the current late-flower night policy.

- Observation: Demand-only dehumidifier staging needs an RH gate.
  Evidence: A severe low-VPD reading with low RH can be physically inconsistent across sensors. The implemented compressor stage now requires high drying demand and RH within `2%` of the phase ceiling to turn on, while a running dehumidifier can hold until RH is more than `4%` below the ceiling or drying demand drops below the exit threshold.

- Observation: Fan pacing needs first-tick behavior to stay bumpless.
  Evidence: `ClimateState.fan_last_changed_at` defaults to `None`, so restart decisions still seed from the observed current fan duty and only apply minimum dwell after the controller has made a fan change.


## Decision Log

- Decision: Keep the existing `ClimateControllerService` and `decide_climate()` boundary.
  Rationale: The service already owns the right hardware boundary, log stream, pure decision API, and tests. The smell is inside drying allocation, not at the application boundary.
  Date/Author: 2026-05-29 / Codex

- Decision: Replace near-ceiling dehumidifier ownership with split-range staging from one drying demand.
  Rationale: Fan exhaust is the continuous first-stage drying actuator. The dehumidifier is a slow binary boost and should not toggle just because VPD dips slightly while RH is below the hard ceiling.
  Date/Author: 2026-05-29 / Codex

- Decision: Keep hard RH guard as a dehumidifier request.
  Rationale: In late flower, RH above the explicit ceiling is a mold-risk guardrail. The dehumidifier should still turn on, subject to its minimum cycle constraints.
  Date/Author: 2026-05-29 / Codex

- Decision: Do not add a new controller abstraction or compatibility path.
  Rationale: Per `docs/rules/simple-clean-architecture.md`, this is source-owned code. The simplest truthful model is a direct replacement of the misleading fan/dehumidifier arbitration, with owned tests updated to the new contract.
  Date/Author: 2026-05-29 / Codex

- Decision: Gate dehumidifier boost on both drying demand and RH proximity to the phase ceiling.
  Rationale: The dehumidifier is a compressor-stage drying actuator, not a generic low-VPD actuator. Requiring RH near the ceiling avoids turning it on for inconsistent or low-RH VPD readings while preserving hard-RH protection.
  Date/Author: 2026-05-29 / Codex


## Outcomes & Retrospective

Implemented.

The controller now computes one `drying_pct` demand and stages it as fan-first drying plus optional dehumidifier boost. The old `dehumidifier_owns_vpd` model and `_rh_high_for_dehumidifier()` helper were removed. The dehumidifier request is now true when RH is above the hard ceiling, or when drying demand is high enough and RH is near the phase ceiling; an already-running dehumidifier uses lower exit thresholds to avoid short chatter.

The fan no longer has an independent RH/VPD hysteresis latch. It consumes drying demand directly, keeps the existing slew limit, and records `fan_last_changed_at` in `ClimateState` so ordinary fan changes obey a `180s` minimum dwell. Hard-low temperature, severe RH above `rh_max + 3%`, and high-temperature safety still bypass fan pacing.

No `dirt-hwd` restart was performed as part of this plan. Runtime acceptance still requires observing the live `climate_controller` log after the next explicit restart/deploy.


## Context and Orientation

Repository root is `/home/akcom/code/dirt`.

Read these docs before changing code or running commands:

- `docs/commands.md` for test, lint, and service commands.
- `docs/grow-state.md` for current stage and lights schedule.
- `docs/observability.md` for `climate_controller` log interpretation.
- `docs/rules/simple-clean-architecture.md` for architecture and test-shape rules.

The current control path is:

- `apps/hwd/src/dirt_hwd/app.py` wires `ClimateControllerService` as the main hardware climate loop.
- `ClimateControllerService._tick()` reads `temperature_f`, `humidity_pct`, `vpd_kpa`, current fan duty, current humidifier level, current dehumidifier state, and current ThermoForge heat level.
- `apps/hwd/src/dirt_hwd/services/climate_controller.py:decide_climate()` is the pure decision function. It returns fan duty, humidifier intensity, dehumidifier on/off, heater level, active mode, diagnostic fields, reason codes, and next controller state.
- `apps/hwd/src/dirt_hwd/services/climate_policy.py:default_climate_policy()` owns explicit day/night bands. Late flower lights-off is currently `1.1-1.3 kPa`, `70-72°F`, and `60%` RH max.
- `apps/hwd/tests/test_climate_controller.py` owns focused behavior tests for the pure controller.

Terms:

- VPD means vapor pressure deficit. Low VPD means the air is too wet from the plant's perspective.
- RH means relative humidity. RH above the stage/phase ceiling is a hard mold-prevention guard.
- Drying demand is a single percent-like controller output derived from low VPD error and high RH error.
- Split-range allocation means one demand signal is staged across multiple actuators: fan first, dehumidifier as a binary boost when fan-level demand is not enough or RH is above the hard ceiling.


## Plan of Work

Milestone 1 replaces dehumidifier ownership:

- In `ClimateTuning`, add direct staging thresholds such as `dehumidifier_drying_enter_pct`, `dehumidifier_drying_exit_pct`, and RH proximity thresholds for dehumidifier entry and exit.
- In `_compute_demand()`, compute `raw_drying_pct` first, then derive `dehumidifier_requested` from hard RH guard, sustained current dehumidifier state, RH proximity, and high drying demand. Remove `_rh_high_for_dehumidifier()` if it no longer has a truthful role.
- Preserve diagnostics and reason vocabulary where useful, but do not keep compatibility branches for the old `rh_max - 2%` behavior.

Milestone 2 makes fan allocation a paced continuous actuator:

- Let the fan consume the drying demand directly as the first-stage actuator.
- Remove the near-RH-ceiling fan latch as a separate source of truth.
- Track fan state in `ClimateState` with a last-changed timestamp so ordinary fan target changes obey a minimum dwell. Emergency RH and temperature cases may still bypass pacing.
- Keep existing fan slew limiting, but make it operate on the split-range demand rather than on threshold latch output.

Milestone 3 validates and records outcomes:

- Update focused tests in `apps/hwd/tests/test_climate_controller.py` to prove near-boundary late-flower night readings do not dehumidifier-toggle, RH above the hard ceiling still requests dehumidification, and fan changes are paced.
- Run focused hwd tests and the hwd suite.
- Update this ExecPlan with completed progress, surprises, validation, and outcomes.


## Concrete Steps

Run from the repository root:

    cd /home/akcom/code/dirt
    uv run pytest apps/hwd/tests/test_climate_controller.py apps/hwd/tests/test_climate_policy.py -q
    uv run pytest apps/hwd/tests -q
    uv run ruff check apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_controller.py

Expected result: tests pass and ruff reports no issues.

Do not restart `dirt-hwd` as part of this plan unless the user explicitly asks. Restarting the service is a live actuator-control action.


## Validation and Acceptance

The implementation is accepted when:

- Focused tests show that a late-flower lights-off sample near `58-59% RH` and `~1.04 kPa` VPD requests fan-first drying without turning the dehumidifier on.
- Focused tests show that RH above `60%` still requests the dehumidifier.
- Focused tests show ordinary fan target changes obey a minimum dwell, while severe RH or safety conditions can still bypass pacing.
- `uv run pytest apps/hwd/tests/test_climate_controller.py apps/hwd/tests/test_climate_policy.py -q` passes.
- `uv run pytest apps/hwd/tests -q` passes.

Runtime acceptance after a later restart is observable in `var/logs/climate_controller/YYYY-MM-DD.jsonl`: in the first lights-off hours, dehumidifier target transitions and fan target transitions should be materially lower than the 2026-05-28/29 baseline unless the tent genuinely remains above the hard RH ceiling.


## Idempotence and Recovery

Code and test edits are safe to repeat. Test commands are read-only with respect to production logs because the repo's test fixtures isolate observability output.

If focused tests fail, inspect `apps/hwd/tests/test_climate_controller.py` first; this change intentionally updates the behavior contract. If runtime behavior later proves too passive, tune the explicit split-range thresholds in `ClimateTuning` rather than reintroducing independent RH latch rules.

Rollback before deployment is a normal git revert of this plan's code changes. After deployment, rollback requires reverting the code and restarting `dirt-hwd`.


## Artifacts and Notes

Baseline log analysis from 2026-05-28 21:00-24:00 MDT:

    rows: 283
    RH min/max/avg: 52.35 / 63.69 / 58.47
    VPD min/max/avg: 0.90 / 1.47 / 1.09
    target_dehumidifier_on transitions: 30
    target_fan_pct transitions: 74
    target_heater_level transitions: 15


## Interfaces and Dependencies

The public Python interface remains `decide_climate(policy, state, inp, tuning=None) -> ClimateDecision`.

`ClimateState` gained `fan_last_changed_at` with a default of `None`. Tests and callers can continue constructing it directly.

No database schema, generated API contract, firmware, web UI, or hosted-control-plane interface changes are planned.


## Revision Notes

- 2026-05-29: Initial ExecPlan written after diagnosing post-lights-off fan/dehumidifier oscillation under the tightened late-flower night policy.
- 2026-05-29: Implementation completed with fan-first drying demand, dehumidifier demand/RH staging, fan minimum dwell, updated tests, and passing validation.
