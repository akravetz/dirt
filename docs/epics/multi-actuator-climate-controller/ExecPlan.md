# Multi-Actuator Climate Controller

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, Dirt will control the main tent climate with one coordinated controller instead of separate loops for humidification and fan trim. The controller will treat vapor pressure deficit, or VPD, as the primary plant-respiration target while respecting hard safety envelopes for temperature and relative humidity. It will command four actuator classes:

- humidifier: adds water vapor and lowers VPD;
- dehumidifier on a Kasa plug: removes water vapor and raises VPD;
- exhaust fan: provides baseline filtration/air exchange and, above baseline, cools and dries the tent;
- heater: raises temperature and, at constant absolute moisture, raises VPD by lowering relative humidity.

The user-visible outcome is that the main tent can hold stage-specific day/night VPD policy without independent loops fighting each other. A grower can observe the new behavior in `var/logs/climate_controller/YYYY-MM-DD.jsonl`, in persisted actuator readings such as `fan_duty_pct`, `humidifier_on`, `humidifier_mist_level`, `dehumidifier_on`, `heater_on`, and `heater_heat_level`, and in the plant-facing sensor history for `temperature_f`, `humidity_pct`, and `vpd_kpa`.

The controller must preserve baseline fan operation. Fan floor is air filtration and mixing, not a conflict with heating. The conflict to avoid is heater plus elevated cooling demand. A normal low-temperature decision may run the heater while keeping fan at the configured floor, for example 20%.


## Progress

- [x] (2026-05-21) Read `.agents/PLANS.md`, `docs/commands.md`, `docs/database.md`, `docs/observability.md`, `docs/grow-state.md`, `docs/rules/simple-clean-architecture.md`, and `docs/rules/boundary-contracts.md`.
- [x] (2026-05-21) Reviewed existing controller code in `apps/hwd/src/dirt_hwd/services/humidifier_pi.py`, `apps/hwd/src/dirt_hwd/services/humidifier.py`, and `apps/hwd/src/dirt_hwd/services/fan_controller.py`.
- [x] (2026-05-21) Ran historical regression in `debug/fan_temp_regression.py`; steady lights-on/heater-off data supports using fan increases as a modest cooling actuator.
- [x] (2026-05-21) Searched current greenhouse/control-theory references for multivariable climate control, split-range PI, constrained control, day/night temperature/VPD policy, and anti-windup.
- [x] (2026-05-21) Wrote this ExecPlan.
- [x] (2026-05-21 21:43 MDT) Confirmed the dehumidifier Kasa plug identity: alias `tent-dehumidifier`, MAC `58:04:4F:10:3D:19`, IP `192.168.1.208`.
- [x] (2026-05-21 21:44 MDT) Added and applied Atlas seed migration `20260522032000_seed_main_dehumidifier.sql`, creating DB device `kasa-dehumidifier-main` under `homebox/main/canopy` with capability `power -> dehumidifier_on`.
- [x] (2026-05-21 22:10 MDT) Defined pure, typed climate policy defaults in `apps/hwd/src/dirt_hwd/services/climate_policy.py` with focused tests in `apps/hwd/tests/test_climate_policy.py`.
- [x] (2026-05-21 22:20 MDT) Implemented pure climate demand/allocation logic in `apps/hwd/src/dirt_hwd/services/climate_controller.py` with focused tests in `apps/hwd/tests/test_climate_controller.py`.
- [x] (2026-05-21 22:30 MDT) Added explicit fan, humidifier, dehumidifier, and ThermoForge heater actuator command boundaries in `apps/hwd/src/dirt_hwd/services/climate_actuators.py` with focused tests in `apps/hwd/tests/test_climate_actuators.py`.
- [x] (2026-05-22) Removed schedule-driven heater ownership before dispatch cutover.
- [ ] Cut over directly to the new climate controller as the sole climate actuator authority, with guarded live validation. Code portion completed on 2026-05-22: `ClimateControllerService` is app-wired as the only default climate authority and old fan/humidifier/ThermoForge authority loops are no longer default services. Remaining: human-confirmed live rollout actions and first-run validation.
- [ ] Retire obsolete humidifier/fan authority paths and update documentation.


## Surprises & Discoveries

- Observation: Historical fan changes are usable as a cooling signal, but fan level by itself is weaker because the current controller changes fan duty in response to humidity/VPD conditions.
  Evidence: `debug/fan_temp_regression.py` estimated, in the steady lights-on/heater-off segment, that a +10 percentage point fan increase over the prior 5 minutes predicts roughly -0.43°F at 5 minutes, -0.42°F at 10 minutes, -0.45°F at 15 minutes, and -0.48°F at 30 minutes.

- Observation: The current `humidity_pct` stage band is documented as an envelope, not a setpoint.
  Evidence: `apps/shared/src/dirt_shared/services/grow_state.py` states that VPD and temperature are primary targets, while RH is a horticultural envelope because RH and VPD are mathematically coupled.

- Observation: The current fan loop treats fan as humidity/VPD trim, not temperature authority.
  Evidence: `apps/hwd/src/dirt_hwd/services/fan_controller.py` increases fan for RH above ceiling or VPD below floor, and decreases fan when VPD is too high. It does not consume `temperature_f`.

- Observation: The humidifier PI module already has useful controller mechanics that should be reused as patterns, not as the final top-level architecture.
  Evidence: `apps/hwd/src/dirt_hwd/services/humidifier_pi.py` is a pure function with bounded integral state, threshold hysteresis, stale-sensor failsafe, and `track_delivered_output()` external-reset tracking.

- Observation: The main ThermoForge heater is a discrete staged actuator with off plus heat levels 1 through 10, not a continuous actuator.
  Evidence: `apps/hwd/src/dirt_hwd/services/thermoforge_protocol.py:level_body()` accepts levels `0 <= level <= 10` and rejects `-1` and `11`; status decoding returns `level=(frame[48] & 0x3c) >> 2`; `apps/shared/tests/test_config.py` validates `THERMOFORGE_NIGHT_LEVEL` and documents the current default as `4`; `apps/hwd/tests/test_thermoforge_protocol.py` verifies captured writes for levels `1`, `4`, and `7` plus a captured running level `4` status frame.

- Observation: The dehumidifier Kasa plug is discoverable on the LAN and matches the user-provided MAC.
  Evidence: `uv run --package dirt-hwd kasa --username "$KASA_USERNAME" --password "$KASA_PASSWORD" --target 192.168.1.255 --discovery-timeout 8 discover` found alias `tent-dehumidifier`, host `192.168.1.208`, model `EP10`, firmware `1.1.1 Build 250908 Rel.112508`, and MAC `58:04:4F:10:3D:19`.

- Observation: Published greenhouse control work treats this as a coupled multivariable temperature/humidity problem and uses PI, split-range control, decoupling, anti-windup, and day/night scheme transfer.
  Evidence: ScienceDirect open-access article "A practical solution for multivariable control of temperature and humidity in greenhouses" says nighttime control uses heating and dehumidification, daytime control uses ventilation, dehumidification, and humidification, and the design uses PI, anti-windup, bumpless transfer, and split-range humidity control. Source: https://www.sciencedirect.com/science/article/pii/S094735802400027X.

- Observation: Actuator saturation and allocator clipping are expected, not edge cases.
  Evidence: MathWorks' anti-windup documentation describes integrator windup under actuator saturation and recommends back-calculation, clamping, or tracking mode when the effective actuator output differs from the raw PID output. Source: https://www.mathworks.com/help/simulink/slref/anti-windup-control-using-a-pid-controller.html.

- Observation: Day/night temperature policy is normal in greenhouse control, but aggressive drops are not required for this tent.
  Evidence: Greenhouse temperature references describe day/night differential and DIP techniques; this plan uses only a modest lights-off target drop with a hard 70°F minimum, not an aggressive pre-dawn DIP. Source: https://www.greenhouse-management.com/greenhouse_management/managing_temperature_greenhouse_crops/temperature_drop_dip_greenhouse_crops.htm.

- Observation: The architecture invariants treat even immutable-looking module-level dataclass construction as hidden singleton instantiation.
  Evidence: `uv run pytest apps/tests/invariants -q` initially failed on `ClimateTuning()`, `ClimatePolicyDefaults()`, and `tuple(range(11))` in the new climate modules. The fix moved dataclass defaults into function/constructor bodies and made ThermoForge supported levels a literal tuple; the full invariant suite then passed.


## Decision Log

- Decision: Build a new unified `ClimateControllerService` and retire top-level authority from `HumidifierLoopService` and `FanTrimLoopService`.
  Rationale: The real domain is now coupled. Fan, heater, humidifier, and dehumidifier all affect VPD and temperature. Independent loops will fight or need increasingly fragile cross-guards. Direct cutover matches `docs/rules/simple-clean-architecture.md`.
  Date/Author: 2026-05-21 / Codex

- Decision: Reuse hardware dispatch and PI mechanics, not the old controller topology.
  Rationale: Govee H7142 quantization, Kasa plug actuation patterns, fan-node API calls, ThermoForge control, anti-windup clamps, and external-reset tracking are valuable. The outdated part is having separate climate authorities.
  Date/Author: 2026-05-21 / Codex

- Decision: Treat VPD as the primary plant target; treat RH maximum and temperature minimum as hard constraints.
  Rationale: VPD is the plant-respiration target requested by the user and already represented in `STAGE_TARGETS`. RH maximum protects disease/condensation risk; temperature minimum protects cold stress and controller-induced overcooling.
  Date/Author: 2026-05-21 / User/Codex

- Decision: Use separate lights-on and lights-off policy for temperature and VPD.
  Rationale: At lights off, photosynthesis and transpiration demand are lower and the lights no longer add heat. A modest night temperature drop is natural and desirable, but VPD must not collapse into a saturated, disease-prone environment.
  Date/Author: 2026-05-21 / Codex

- Decision: Do not force fan off when heating.
  Rationale: Fan floor is baseline filtration, air exchange, and mixing. It can remain active with the heater. The controller should suppress only elevated fan cooling demand while heating, except when RH/VPD safety requires drying.
  Date/Author: 2026-05-21 / User/Codex

- Decision: Model ThermoForge heater dispatch as staged output: off plus levels 1 through 10.
  Rationale: The BLE protocol and tests show the device supports discrete levels `0..10`. The climate PI may compute continuous heat demand internally, but actuator dispatch must quantize that demand to a supported level with hysteresis and minimum hold times.
  Date/Author: 2026-05-21 / User/Codex

- Decision: Retire schedule-driven heater authority when the climate controller takes over.
  Rationale: The current heater path is schedule-driven (`schedule.kind='heater'`) and effectively uses an explicit night window. That was correct for the first ThermoForge release, but climate heat should now be controlled by temperature/VPD/RH policy, not by a fixed schedule. Keep scheduled Kasa control for lights; remove heater schedules or disable their service path so there is one heater authority.
  Date/Author: 2026-05-21 / User/Codex

- Decision: Implement a constrained split-range PI supervisor before considering full MPC.
  Rationale: Model predictive control is common in greenhouse literature, but this tent does not yet have identified dehumidifier dynamics. A split-range PI supervisor is inspectable, testable, and consistent with the existing codebase. Historical actuator data can later support MPC if needed.
  Date/Author: 2026-05-21 / Codex

- Decision: Do not run a shadow-mode rollout for the first climate controller release.
  Rationale: The user is actively monitoring the tent and current VPD is concerningly low, so the improved control path should become authoritative immediately. The implementation must still be guarded by focused tests, startup safety checks, explicit live validation, and clear rollback instructions.
  Date/Author: 2026-05-21 / User/Codex


## Outcomes & Retrospective

Milestone 1 outcome: the main-tent dehumidifier is now registered as a DB-known Kasa actuator. Migration `migrations/20260522032000_seed_main_dehumidifier.sql` upserts `device_id='kasa-dehumidifier-main'` under `homebox/main/canopy`, with `controller='kasa'`, `provider_uid_kind='mac'`, `provider_uid='58:04:4F:10:3D:19'`, `ip='192.168.1.208'`, and metadata from Kasa discovery. It also upserts capability `capability_id='power'`, `metric_name='dehumidifier_on'`, `unit='bool'`, `source='kasa'`. Validation: `atlas migrate apply --env local --dry-run` showed one pending migration with two SQL statements; `pg_dump` backup `var/db-backups/dirt-20260521-214419-pre-main-dehumidifier.sql` was taken; `atlas migrate apply --env local` applied the migration; `atlas migrate status --env local` reported current version `20260522032000` with zero pending files; SQL verification showed the expected device and capability rows.

Milestone 2 outcome: pure climate policy now lives in `apps/hwd/src/dirt_hwd/services/climate_policy.py`. It defines frozen dataclasses for stage/phase bands, hard temperature minimum, RH max envelopes, fan limits, ThermoForge supported levels, stale sensor limits, and dehumidifier deadbands/minimum cycle durations. `default_climate_policy()` exposes the initial explicit values through `ClimatePolicyDefaults`, and `ClimatePolicy.for_stage_phase()` selects phase-specific stage policy. No controller allocation, dispatch, service wiring, migrations, or live rollout changes were made. Validation: `uv run pytest apps/hwd/tests/test_climate_policy.py -q` passed with 10 tests; `uv run ruff check apps/hwd/src/dirt_hwd/services/climate_policy.py apps/hwd/tests/test_climate_policy.py` passed. Cleanup: the simplify pass used the local fallback because no subagent-spawn tool is available; it tightened duplicate-stage validation in `ClimatePolicy.__post_init__` and added a regression test.

Milestone 3 outcome: pure climate demand/allocation now lives in `apps/hwd/src/dirt_hwd/services/climate_controller.py`. It defines internal dataclass value types for `ClimateInput`, `ClimateState`, `ClimateDecision`, and `ClimateTuning`, consumes `ClimatePolicy`, and implements sensor failsafe, hard low-temperature guard, hard RH guard, VPD split-range control, temperature trim, dehumidifier minimum on/off cycling, staged ThermoForge heater output, heater/fan conflict handling, bumpless phase transfer, and external-reset style integrator tracking for clipped humidifier, drying, and heat outputs. No actuator command boundaries, app wiring, migrations, live DB work, or service restarts were added. Validation: `uv run pytest apps/hwd/tests/test_climate_policy.py apps/hwd/tests/test_climate_controller.py -q` passed with 24 tests; `uv run ruff check apps/hwd/src/dirt_hwd/services/climate_policy.py apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_policy.py apps/hwd/tests/test_climate_controller.py` passed. Cleanup: the simplify pass used the local fallback because no subagent-spawn tool is available; reuse review found no suitable existing pure allocator to reuse without coupling to obsolete loop topology, quality review removed an unused tuning field and tightened the heater/elevated-fan cooling test, and efficiency review found no resource-use issues.

Milestone 4 outcome: explicit climate actuator boundaries now live in `apps/hwd/src/dirt_hwd/services/climate_actuators.py`. `ClimateActuators` composes four direct fields: fan, humidifier, dehumidifier, and heater. `FanNodeActuator` reads and sets duty through the existing fan-node client. `H7142HumidifierActuator` reuses the H7142 quantizer and dispatch planner, with the old `_plan_dispatch()` preserved as a private compatibility entry point for existing agent-owned tests and `plan_dispatch()` exposed for the new boundary. `KasaDehumidifierActuator` loads the DB-known natural ID `kasa-dehumidifier-main` without schedule rows, resolves the plug with the existing Kasa inventory verifier, commands power, and records `dehumidifier_on` via `ReadingsService`. `ThermoForgeHeaterActuator` accepts validated `ThermoForgeHeaterTarget` values of off or heat levels 1..10 and delegates BLE command convergence to the existing ThermoForge `reconcile()` target path. No `app.py` wiring, old authority shutdown, heater schedule removal, migrations, live DB work, service restarts, or hardware calls were performed. Validation: `uv run pytest apps/hwd/tests/test_climate_policy.py apps/hwd/tests/test_climate_controller.py apps/hwd/tests/test_climate_actuators.py -q` passed with 30 tests; `uv run pytest apps/hwd/tests/test_humidifier_helpers.py -q` passed with 21 tests; `uv run ruff check apps/hwd/src/dirt_hwd/services/climate_actuators.py apps/hwd/src/dirt_hwd/services/humidifier.py apps/hwd/src/dirt_hwd/services/climate_policy.py apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_actuators.py apps/hwd/tests/test_climate_policy.py apps/hwd/tests/test_climate_controller.py` passed. Cleanup: the simplify pass used the local fallback because no subagent-spawn tool is available; reuse review confirmed the new code already reuses the existing fan-node, H7142 dispatch, Kasa inventory, readings, and ThermoForge BLE target boundaries; quality review kept the explicit four-field composition and found no generic registry or compatibility wrapper to remove; efficiency review accepted per-command DB/connection work for this unwired milestone and identified caching as a later service-loop concern only if the dispatch cadence proves it necessary.

Milestone 4b outcome: migration `migrations/20260522120000_disable_climate_heater_schedules.sql` disables enabled `schedule.kind='heater'` rows for actuator devices controlled by `kasa` or `ac_infinity_ble`, which covers `main-thermoforge-night` and `breeding-heater-night` without deleting heater devices or capabilities. Light schedules remain enabled. `ScheduledKasaActuatorService` now defaults to `DEFAULT_SCHEDULE_KINDS = ("lights",)`, so production default scheduled Kasa ownership is lights-only. ThermoForge BLE client/status/power/level/reconcile code was left intact for the climate heater actuator, and no new `app.py` wiring, live DB apply, service restart, or hardware command was performed. Validation: `atlas migrate hash --env local` updated `migrations/atlas.sum`; `atlas migrate apply --env local --dry-run` reported one pending migration with one `UPDATE` statement; `uv run pytest apps/hwd/tests/test_kasa_schedule.py apps/hwd/tests/test_thermoforge.py -q` passed with 24 tests; `uv run ruff check apps/hwd/src/dirt_hwd/services/kasa_schedule.py apps/hwd/tests/test_kasa_schedule.py` passed. `atlas migrate lint --env local --latest 1` could not run because this local Atlas CLI reports migrate lint is Atlas Pro-only. Cleanup: the simplify pass used the local fallback because no subagent-spawn tool is available; reuse and efficiency review found no change needed, and quality review simplified the new DB assertions.

Milestone 5 code outcome: `ClimateControllerService` now wraps the pure `decide_climate()` allocator in a background loop that reads current main-tent canopy `temperature_f`, `humidity_pct`, and `vpd_kpa`, reads grow stage/lights context, carries `ClimateState` across ticks, logs top-level `climate_controller` decisions with reason codes/current targets/command targets, and dispatches fan, humidifier, dehumidifier, and ThermoForge heater commands through `ClimateActuators`. The service dispatch boundary refuses simultaneous humidifier and dehumidifier commands and turns the humidifier off before energizing the dehumidifier. `apps/hwd/src/dirt_hwd/app.py` now wires this service as the only default climate authority; `HumidifierLoopService`, `FanTrimLoopService`, and `ScheduledThermoForgeService` are no longer default background services, while scheduled Kasa control remains for lights. The `climate_controller` log stream has 30-day retention. Validation: `uv run pytest apps/hwd/tests/test_app_composition.py apps/hwd/tests/test_climate_controller.py apps/hwd/tests/test_climate_actuators.py apps/hwd/tests/test_climate_policy.py -q` passed with 33 tests; `uv run pytest apps/hwd/tests -q` passed with 262 tests; `uv run pytest apps/shared/tests -q` passed with 172 tests; `uv run pytest apps/tests/invariants -q` passed with 112 tests after fixing import-time singleton violations; `uv run ruff check` passed. No live DB migration, systemd restart, hardware command, sensor freshness check, or log tailing was performed. Cleanup: the simplify pass used the local fallback because no subagent-spawn tool is available; reuse review found the implementation already reuses existing fan-node, Govee, Kasa, readings, and ThermoForge boundaries; quality review fixed the humidifier current-reading capability id from the command capability to the persisted `humidifier_mist_level` capability, cached the lazy Govee client, and removed module-level singleton construction flagged by invariants; efficiency review cached the DB-resolved ThermoForge actuator device after first load.


## Context and Orientation

Repository root is `/home/akcom/code/dirt`.

Read these docs before implementation:

- `docs/commands.md` before running tests, lint, service commands, or dependency commands.
- `docs/database.md` before adding dehumidifier capabilities, metrics, migrations, or seed rows.
- `docs/observability.md` before adding the `climate_controller` stream or changing actuator logs.
- `docs/grow-state.md` before changing stage, lights, or target policy.
- `docs/rules/simple-clean-architecture.md` before choosing between direct cutover and compatibility.
- `docs/rules/boundary-contracts.md` before adding any JSON policy shape that crosses a persistence, process, API, gateway, or command boundary.
- `docs/references/atlas/INDEX.md` before running Atlas migration commands.

Current relevant services:

- `apps/hwd/src/dirt_hwd/app.py` wires hardware background services.
- `apps/hwd/src/dirt_hwd/services/humidifier.py` owns the current Govee H7142 humidifier loop and dispatch. It reads VPD, RH, fan duty, grow stage, and lights state. It records H7142 actuator metrics and structured logs.
- `apps/hwd/src/dirt_hwd/services/humidifier_pi.py` is a pure PI controller for humidifier intensity. It should inform the new pure controller design.
- `apps/hwd/src/dirt_hwd/services/humidifier_dispatch.py` maps a continuous humidifier output to H7142 levels. Reuse this dispatch boundary.
- `apps/hwd/src/dirt_hwd/services/fan_controller.py` owns the current supervisory fan trim. Its top-level authority should be replaced, but its fan-node client usage and observability fields are useful references.
- `apps/hwd/src/dirt_hwd/services/kasa_schedule.py` reconciles scheduled Kasa plugs such as lights and older heater plugs. After cutover it should remain a lights scheduler only. The dehumidifier plug should be modeled as a DB-known Kasa actuator but controlled by climate policy, not by a time schedule.
- `apps/hwd/src/dirt_hwd/services/thermoforge.py` currently owns schedule-driven ThermoForge heater reconciliation. The climate controller should reuse its BLE protocol/client pieces but retire the schedule-derived target loop as heater authority.
- `apps/shared/src/dirt_shared/services/grow_state.py` owns `STAGE_TARGETS` and lights context. Its current comments define `temperature_f` and `vpd_kpa` as primary targets and `humidity_pct` as an envelope.
- `apps/shared/src/dirt_shared/config.py` owns environment-backed config slices such as `HumidifierConfig`, `FanTrimConfig`, and heater settings.
- `apps/shared/src/dirt_shared/services/readings.py` provides latest readings and writes actuator readings.
- `apps/shared/src/dirt_shared/observability.py` owns log stream retention.

Current main-tent stage policy as of this plan:

- Main grow flower start date is 2026-05-03.
- Lights schedule is 09:00 to 21:00 America/Denver.
- `flower_early` targets in `STAGE_TARGETS` are currently `temperature_f=(68, 80)`, `humidity_pct=(40, 60)`, and `vpd_kpa=(1.0, 1.3)`.

Terms used in this plan:

- VPD: vapor pressure deficit in kPa. Higher VPD means drier air from the plant's perspective; lower VPD means wetter air.
- RH: relative humidity percentage. RH is constrained by disease/condensation risk but is not the main control target.
- Fan floor: minimum fan duty reserved for filtration, air exchange, and mixing. It is not considered active cooling demand.
- Elevated fan demand: fan duty above floor requested for cooling or drying.
- Split-range control: one signed demand is allocated to different actuators depending on direction, for example humidifier for too-dry VPD error and dehumidifier/fan for too-wet VPD error.
- Staged heater dispatch: mapping a continuous internal heat demand to discrete ThermoForge states: off, then levels 1 through 10. Level 0 appears in decoded status when the unit is off; active heating commands should use levels 1 through 10.
- Anti-windup: logic that prevents PI integrators from accumulating impossible demand while actuators are saturated, disabled, or clipped by higher-priority constraints.
- Bumpless transfer: switching between lights-on/lights-off policies or replacing the previous controller authority without a sudden jump caused by stale integral state.


## Plan of Work

Milestone 1: confirm and seed the dehumidifier actuator.

Once the user has provisioned the Kasa plug, identify its device ID, IP/provider UID, and tent scope. Add or update DB seed/migration rows so the dehumidifier is a first-class actuator under `homebox/main`, with a capability such as `capability_id='power'`, `metric_name='dehumidifier_on'`, and an unambiguous device ID such as `kasa-dehumidifier-main`. This is not a scheduled actuator; the climate controller will command it.

If the Kasa provider code currently assumes `schedule.kind IN ('lights', 'heater')`, do not overload that scheduler for dehumidification. Add a small direct Kasa power command boundary for climate-controlled plugs, or extract the existing plug resolution/write behavior into a reusable internal helper whose name reflects the shared Kasa power operation. Do not keep a fake `schedule.kind='dehumidifier'` merely to reuse scheduled code.

Milestone 2: define climate policy explicitly.

Add a pure module, probably `apps/hwd/src/dirt_hwd/services/climate_policy.py`, with dataclasses or Pydantic models as appropriate. Internal compute-only types can be dataclasses. If policy is persisted as JSON or exposed over an API later, use Pydantic DTOs per `docs/rules/boundary-contracts.md`.

The policy should include:

- stage and phase, where phase is `lights_on` or `lights_off`;
- VPD target band by stage and phase;
- temperature target band by stage and phase;
- hard minimum temperature, initially 70°F;
- RH maximum by stage and phase;
- fan floor and fan maximum;
- heater supported levels, initially off plus ThermoForge levels 1 through 10;
- actuator stale-sensor limits;
- deadbands and minimum on/off durations for Kasa dehumidifier cycling.

Initial policy should be conservative and explicit. Suggested starting values:

- veg lights-on: VPD 0.9-1.1 kPa, temp 75-80°F, RH max 70%;
- veg lights-off: VPD 0.7-0.9 kPa, temp 70-74°F, RH max 75%;
- flower early lights-on: VPD 1.1-1.3 kPa, temp 76-78°F, RH max 65% unless the user overrides to 80%;
- flower early lights-off: VPD 0.9-1.1 kPa, temp 70-72°F, RH max 75-80%;
- flower late lights-on: VPD 1.2-1.5 kPa, temp 74-78°F, RH max 55-60%;
- flower late lights-off: VPD 1.1-1.3 kPa, temp 70-72°F, RH max 60%.

These are starting controller policy values, not hidden constants. Implement them in `Settings` or a policy module so they are easy to inspect and tune. If the user confirms flower RH max should be exactly 80%, represent it directly as an envelope value even if VPD policy normally keeps actual RH lower.

Milestone 3: implement pure climate demand and allocation.

Add `apps/hwd/src/dirt_hwd/services/climate_controller.py` or split pure logic into `climate_math.py` plus service wiring. The pure function should take `ClimateInput`, `ClimatePolicy`, and `ClimateState`, and return `ClimateDecision`.

Suggested internal shape:

- `ClimateInput`: timestamp, temperature, RH, VPD, reading ages, lights state, stage, current actuator states.
- `ClimatePolicy`: bands, constraints, fan floor, actuator limits, ThermoForge supported levels, deadbands, minimum cycle times.
- `ClimateState`: PI integrators, last actuator changes, dehumidifier cycle state, heater level hold state, mode/phase for bumpless transfer.
- `ClimateDecision`: requested fan duty, humidifier intensity/level, dehumidifier power, heater target, reason codes, constraint flags, updated state.

The algorithm should run in this priority order:

1. Sensor failsafe. If temperature/RH/VPD is missing or stale, turn off humidifier and dehumidifier, hold fan at a safe floor or current value, and allow heater only if fresh temperature is available and below hard minimum.
2. Hard low-temperature guard. If temperature is below 70°F, heat. Keep fan at floor. Do not command elevated fan cooling. If RH/VPD is unsafe at the same time, dehumidifier may run and elevated fan may be allowed only as a drying safety action.
3. Hard RH guard. If RH is above max, force humidifier off and request drying from dehumidifier first, then elevated fan if temperature margin allows. If temperature is near the floor, prefer dehumidifier plus heater over fan purge.
4. VPD split-range control. If VPD is above target band, the air is too dry: humidifier demand rises and elevated fan demand falls toward floor if temperature allows. If VPD is below target band, the air is too wet: dehumidifier and/or elevated fan demand rises, with heater assist only when temperature is below target or close to the floor.
5. Temperature trim. If temperature is above target band, fan can rise above floor for cooling. If temperature is below target band, heater can rise while fan remains at floor unless drying safety overrides.
6. Conflict resolution. Never run humidifier and dehumidifier simultaneously. Allow heater with fan floor. Avoid heater plus elevated fan cooling. Allow heater plus elevated fan drying only for high-RH/low-VPD safety and log that reason explicitly.

Use anti-windup/external-reset logic. If the allocator clips humidifier output because RH is at max, the humidifier integrator must track delivered output. If dehumidifier minimum-off time prevents a requested on command, the drying integrator must not continue winding up as though the command were delivered. If fan is capped by low-temperature safety, the cooling/drying fan contribution should be tracked to the capped output.

Heater dispatch must not pretend the ThermoForge is continuous. The temperature controller may compute a continuous internal heat demand in percent, but dispatch should quantize it to off or levels 1 through 10. Start with a simple monotonic bucket mapping from `heat_demand_pct` to levels, then add level-boundary hysteresis and a minimum level hold time so normal noise does not chatter between adjacent heat levels. A hard low-temperature guard may override the hold timer to step up faster; over-temperature or stale-sensor safety may command off immediately. The PI integrator should track delivered heat output after quantization so it does not wind up while the dispatch layer holds a lower level or keeps the heater off.

Milestone 4: add actuator command boundaries.

Create small explicit actuator interfaces so the climate service does not contain provider details:

- fan actuator: reads current duty and sets duty through the existing ESP32 fan node API;
- humidifier actuator: uses existing Govee/H7142 dispatch and quantization;
- dehumidifier actuator: sets a DB-known Kasa plug on/off and records `dehumidifier_on`;
- heater actuator: commands existing heater authority without duplicating BLE/Kasa protocol code. For ThermoForge, it must accept explicit staged targets: off or level 1 through 10. For a plain Kasa heater plug, it may only support off/on and should expose that lower-resolution capability to the allocator.

Add a pure heater dispatch helper, for example `apps/hwd/src/dirt_hwd/services/heater_dispatch.py`, if no existing ThermoForge dispatch module fits. It should convert continuous heat demand to staged ThermoForge targets and enforce hysteresis/hold timers independently from BLE transport. Tests should cover off, low/mid/high level selection, boundary hysteresis, minimum hold behavior, hard low-temperature step-up, and immediate safety-off.

Do not add generic actuator registries unless duplication becomes real during implementation. A direct `ClimateActuators` composition object with four explicit fields is enough.

Milestone 4b: remove schedule-driven heater ownership.

Before dispatch cutover, create the migration and service changes that make heater devices climate-controlled instead of schedule-controlled. Keep the heater `device` and `capability` rows. Remove or disable schedule rows whose only purpose is climate heat, such as `main-thermoforge-night` and any Kasa heater schedule that should no longer run independently. Do not remove light schedules.

Update `ScheduledKasaActuatorService` default schedule kinds so it only owns non-climate scheduled loads, currently lights. If a breeding heat pad still needs schedule-only behavior outside the climate controller scope, record that as an explicit exception in this plan; otherwise migrate it to the climate controller or disable its schedule too.

Refactor ThermoForge code so BLE connection, status read, `set_power()`, and `set_level()` remain usable by the climate heater actuator, but `ScheduledThermoForgeService` is no longer wired as a background service once `ClimateControllerService` dispatches heater commands. Do not leave a durable wrapper that computes heater targets from a schedule.

Milestone 5: direct authority cutover with guarded live validation.

Stop wiring `FanTrimLoopService`, `HumidifierLoopService`, and `ScheduledThermoForgeService` as independent climate authorities. Wire `ClimateControllerService` in dispatch mode as the only loop allowed to command fan, humidifier, dehumidifier, and heater climate targets. Keep scheduled Kasa light control running for light schedules only.

Direct cutover is preferred over compatibility wrappers. If rollback is needed during live rollout, use git/service rollback and re-enable the old services in `app.py`; do not leave permanent dual-authority code paths.

During cutover, preserve the hardware-specific event streams where useful, but make `climate_controller` the top-level decision stream. For example, a climate tick logs why the fan target changed; the fan actuator may still log the actual fan state change.

Before restarting `dirt-hwd`, run the focused controller tests and verify current sensor freshness. After restart, watch `var/logs/climate_controller/YYYY-MM-DD.jsonl`, `var/logs/humidifier/YYYY-MM-DD.jsonl`, `var/logs/fan_controller/YYYY-MM-DD.jsonl`, and `var/logs/heater/YYYY-MM-DD.jsonl` for the first 10-15 minutes. Confirm there is exactly one climate authority emitting command decisions, no simultaneous humidifier/dehumidifier command, and VPD begins moving toward the active band. If the new controller behaves unexpectedly, stop `dirt-hwd`, restore the previous app wiring, restart, and record the rollback in this plan.

Milestone 6: retire obsolete code and docs.

After live behavior is stable, delete or demote obsolete top-level logic:

- remove or stop using `FanTrimLoopService` authority code if it has no remaining caller;
- keep `humidifier_dispatch.py` and provider-specific H7142 code;
- remove humidifier PI controller paths that are replaced by climate PI, unless a pure helper remains genuinely reused;
- remove scheduled heater target derivation and any obsolete `schedule.kind='heater'` rows that are no longer real scheduling contracts;
- update `docs/observability.md`, `wiki/hardware/humidifier-control.md`, and any epic docs that still describe the old separate loops as authoritative.

Move agent-owned tests to the new controller contract. Do not edit human-owned invariants under `apps/tests/invariants/`; fix code to satisfy them.


## Concrete Steps

Start every implementation session from the repo root:

    cd /home/akcom/code/dirt

Read required docs:

    sed -n '1,220p' docs/commands.md
    sed -n '1,220p' docs/database.md
    sed -n '1,220p' docs/observability.md
    sed -n '1,160p' docs/grow-state.md
    sed -n '1,220p' docs/rules/simple-clean-architecture.md
    sed -n '1,220p' docs/rules/boundary-contracts.md

Inspect current actuator rows after the dehumidifier Kasa plug is provisioned:

    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt

Inside `psql`, confirm table shapes before writing SQL:

    \d site
    \d tent
    \d zone
    \d device
    \d capability
    \d sensorreading
    \d schedule

Use focused queries to verify the main tent and new plug:

    SELECT st.site_id, t.tent_id, z.zone_id, d.device_id, d.name, d.controller, d.provider_uid_kind, d.provider_uid, d.ip, d.enabled
    FROM device d
    JOIN site st ON st.id = d.site_id
    JOIN tent t ON t.id = d.tent_id
    LEFT JOIN zone z ON z.id = d.zone_id
    WHERE st.site_id = 'homebox'
    ORDER BY t.tent_id, d.device_id;

When adding migrations:

    atlas migrate diff seed_main_dehumidifier --env local
    atlas migrate hash --env local
    atlas migrate apply --env local --dry-run

If `atlas migrate lint` is available locally, run it. If the installed Atlas CLI reports lint is Pro-only, record that in this plan and rely on dry-run plus tests.

Run focused Python tests while developing pure controller code:

    uv run pytest apps/hwd/tests/test_climate_policy.py apps/hwd/tests/test_climate_controller.py -q
    uv run ruff check apps/hwd/src/dirt_hwd/services/climate_policy.py apps/hwd/src/dirt_hwd/services/climate_controller.py apps/hwd/tests/test_climate_policy.py apps/hwd/tests/test_climate_controller.py

Run broader validation before live wiring:

    uv run pytest apps/hwd/tests -q
    uv run pytest apps/shared/tests -q
    uv run pytest apps/tests/invariants -q
    uv run ruff check

Before applying local DB migrations to the live database, take a backup:

    mkdir -p var/db-backups
    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD pg_dump -h 127.0.0.1 -U dirt -d dirt > var/db-backups/dirt-$(date +%Y%m%d-%H%M%S)-pre-climate-controller.sql

Apply local migrations only after dry-run and review:

    atlas migrate apply --env local

Restart `dirt-hwd` only during the live rollout milestone:

    systemctl --user restart dirt-hwd
    systemctl --user status dirt-hwd --no-pager
    journalctl --user -u dirt-hwd -n 100 --no-pager

Inspect climate logs:

    tail -n 20 var/logs/climate_controller/$(date +%F).jsonl | jq .


## Validation and Acceptance

Pure controller tests must cover at least these cases:

- VPD too high, RH below max, temp in band: humidifier demand increases; dehumidifier is off; fan remains at floor or decreases toward floor.
- VPD too low, temp safely above floor: dehumidifier turns on and fan may rise above floor; humidifier is off.
- RH above max regardless of VPD target: humidifier is forced off and drying is requested.
- Temperature below 70°F: heater is requested; fan stays at floor unless RH/VPD safety requires elevated drying.
- Heater plus fan floor is allowed and not logged as a conflict.
- Heater plus elevated fan cooling is suppressed.
- Heater plus elevated fan drying is allowed only under high-RH/low-VPD safety and logs an explicit reason.
- Missing or stale VPD/RH: humidifier and dehumidifier are off; fan and heater follow failsafe rules.
- Dehumidifier minimum on/off time prevents rapid cycling.
- Phase transition from lights-on to lights-off is bumpless: integrators do not cause a large immediate actuator jump.
- Allocator clipping feeds back into integrator state so impossible demand does not wind up.

Dispatch-mode acceptance:

- `ClimateControllerService` is the only app-wired climate authority for fan, humidifier, dehumidifier, and heater climate targets.
- `FanTrimLoopService` no longer runs as an independent service.
- `HumidifierLoopService` no longer runs as an independent control authority.
- `ScheduledThermoForgeService` no longer runs as an independent heater authority.
- Scheduled Kasa actuator control still owns lights, but no climate heater or dehumidifier command depends on a schedule row.
- When VPD is above the lights-on target band and RH is below max, the humidifier command increases and the dehumidifier remains off.
- When VPD is below the target band or RH is above max, the humidifier is off and dehumidifier/fan drying is requested according to temperature constraints.
- When temperature falls below 70°F, heater demand appears and fan remains at floor unless drying safety overrides.
- Baseline fan floor is preserved across heating.
- Actuator readings update in `sensorreading` for dehumidifier and existing actuators.
- Logs explain every command change with reason codes that are sufficient to reconstruct the control decision.

Human-observable live checks:

- In the web UI or SQL, `temperature_f`, `humidity_pct`, and `vpd_kpa` should move toward the active policy band after controller actions.
- `var/logs/climate_controller/YYYY-MM-DD.jsonl` should show no simultaneous humidifier and dehumidifier command.
- During lights-off, temperature should settle near the night target without falling below 70°F.
- During lights-on, VPD should remain inside or close to the active flower band unless an actuator saturates.
- Heater logs and readings should show supported ThermoForge levels only: off/effective level 0 when not running, or levels 1 through 10 while running.
- During the first live 10-15 minutes after cutover, the operator should see exactly one climate decision stream and should not see old fan/humidifier/heater schedule loops issuing independent corrective commands.


## Idempotence and Recovery

Reading docs, running tests, and running dry-run migrations are safe to repeat.

Migrations must be idempotent or reviewed for idempotence before live apply. Seed migrations should use stable natural identifiers such as `site_id='homebox'`, `tent_id='main'`, `device_id='kasa-dehumidifier-main'`, and `capability_id='power'`. Do not create duplicate devices or capabilities if the migration is applied once and then inspected.

Before applying local migrations, take a `pg_dump` backup under `var/db-backups/`. If a migration is wrong before apply, edit the migration and run `atlas migrate hash --env local`. If a migration is wrong after apply, create a forward corrective migration; do not hand-edit the live schema.

Dispatch-mode rollback during live rollout should be explicit:

1. Restore `app.py` service wiring to the previous authoritative loops.
2. Restart `dirt-hwd`.
3. Verify logs show the old services active and `climate_controller` no longer dispatching.
4. Record the rollback reason and evidence in this plan.

Do not run destructive git commands such as `git reset --hard` or `git checkout --` unless the user explicitly asks.


## Artifacts and Notes

Historical fan regression artifact:

- Script: `debug/fan_temp_regression.py`.
- Result used by this plan: in steady lights-on/heater-off history, a +10 percentage point fan increase predicts roughly -0.4°F to -0.5°F over 5-30 minutes.
- Interpretation: fan is a modest cooling actuator above its filtration floor.

External references used while authoring this plan:

- Multivariable greenhouse temperature/humidity control, split-range humidity control, day/night schemes, PI, anti-windup, and bumpless transfer: https://www.sciencedirect.com/science/article/pii/S094735802400027X.
- Anti-windup for saturated actuators, including clamping, back-calculation, and tracking mode for complex actuator scenarios: https://www.mathworks.com/help/simulink/slref/anti-windup-control-using-a-pid-controller.html.
- Constrained model predictive greenhouse control as a later possible direction after actuator identification: https://www.sciencedirect.com/science/article/pii/S2214317323000525.
- MPC as a common greenhouse climate-control research approach: https://arxiv.org/abs/2303.06110.
- Greenhouse humidity, transpiration, condensation, and disease-risk context: https://www.greenhouse-management.com/greenhouse_management/greenhouse_ventilation_cooling/greenhouse_humidity_control.htm.
- Day/night temperature differential and DIP context: https://www.greenhouse-management.com/greenhouse_management/managing_temperature_greenhouse_crops/temperature_drop_dip_greenhouse_crops.htm.


## Interfaces and Dependencies

End-state app interfaces:

- `apps/hwd/src/dirt_hwd/services/climate_policy.py`: pure policy construction and phase-specific target selection.
- `apps/hwd/src/dirt_hwd/services/climate_controller.py`: pure controller/allocation logic plus, if kept in one file, the service loop that dispatches decisions.
- `ClimateControllerService`: background service wired from `apps/hwd/src/dirt_hwd/app.py`.
- `ClimateInput`, `ClimatePolicy`, `ClimateState`, and `ClimateDecision`: internal value objects for testable control logic.
- `climate_controller` observability stream with 30-day retention in `apps/shared/src/dirt_shared/observability.py`.
- `dehumidifier_on` metric persisted to `sensorreading`.
- A DB-known Kasa device for the dehumidifier, expected natural ID `kasa-dehumidifier-main` unless the provisioned plug identity suggests a clearer name.

Actuator dependencies:

- Fan: existing fan controller ESP32 HTTP API via `dirt_shared.services.fan_node.FanNodeClient`.
- Humidifier: existing Govee H7142 client/dispatch code from `apps/hwd/src/dirt_hwd/services/humidifier.py` and `humidifier_dispatch.py`.
- Dehumidifier: Kasa plug local control, using existing Kasa dependency already present for lights/heaters.
- Heater: existing Kasa heater plug and/or ThermoForge BLE client code, depending on current deployed hardware. Heater target selection must come from `ClimateControllerService`, not from `schedule.kind='heater'`.
- ThermoForge heater: discrete levels `0..10` at the protocol/status layer. Climate dispatch should command off or levels `1..10`; decoded level `0` means effective off.

Configuration dependencies:

- Fan floor and max percent.
- Hard minimum temperature, initially 70°F.
- Per-stage, per-phase VPD bands.
- Per-stage, per-phase temperature bands.
- Per-stage, per-phase RH max envelope.
- Sensor stale thresholds.
- Dehumidifier minimum on/off durations.
- Heater level hysteresis and minimum level hold duration.
- PI gains and integrator clamps for VPD and temperature terms.

Database dependencies:

- `site`, `tent`, `zone`, `device`, `capability`, and `sensorreading` tables.
- Atlas migrations under `migrations/`.
- No app-start DDL.

Test dependencies:

- New app-owned tests under `apps/hwd/tests/`.
- Existing app tests under `apps/hwd/tests/`.
- Shared tests under `apps/shared/tests/`.
- Human-owned invariants under `apps/tests/invariants/`, which must not be edited.


## Revision Notes

- 2026-05-21 / Codex: Initial ExecPlan created after confirming fan has a modest cooling effect and after choosing constrained split-range PI supervisor over extending separate humidifier and fan loops.
