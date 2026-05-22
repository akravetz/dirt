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
- [ ] Confirm the dehumidifier Kasa plug identity after the user provisions it.
- [ ] Implement and validate the DB-known dehumidifier actuator.
- [ ] Implement pure climate policy/allocation code with focused tests.
- [ ] Wire a shadow climate controller beside existing loops and compare logs.
- [ ] Cut over to the new climate controller as the sole climate actuator authority.
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

- Observation: Published greenhouse control work treats this as a coupled multivariable temperature/humidity problem and uses PI, split-range control, decoupling, anti-windup, and day/night scheme transfer.
  Evidence: ScienceDirect open-access article "A practical solution for multivariable control of temperature and humidity in greenhouses" says nighttime control uses heating and dehumidification, daytime control uses ventilation, dehumidification, and humidification, and the design uses PI, anti-windup, bumpless transfer, and split-range humidity control. Source: https://www.sciencedirect.com/science/article/pii/S094735802400027X.

- Observation: Actuator saturation and allocator clipping are expected, not edge cases.
  Evidence: MathWorks' anti-windup documentation describes integrator windup under actuator saturation and recommends back-calculation, clamping, or tracking mode when the effective actuator output differs from the raw PID output. Source: https://www.mathworks.com/help/simulink/slref/anti-windup-control-using-a-pid-controller.html.

- Observation: Day/night temperature policy is normal in greenhouse control, but aggressive drops are not required for this tent.
  Evidence: Greenhouse temperature references describe day/night differential and DIP techniques; this plan uses only a modest lights-off target drop with a hard 70°F minimum, not an aggressive pre-dawn DIP. Source: https://www.greenhouse-management.com/greenhouse_management/managing_temperature_greenhouse_crops/temperature_drop_dip_greenhouse_crops.htm.


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

- Decision: Implement a constrained split-range PI supervisor before considering full MPC.
  Rationale: Model predictive control is common in greenhouse literature, but this tent does not yet have identified dehumidifier dynamics. A split-range PI supervisor is inspectable, testable, and consistent with the existing codebase. Historical actuator data can later support MPC if needed.
  Date/Author: 2026-05-21 / Codex

- Decision: Use a shadow-mode milestone before authority cutover.
  Rationale: The current loops are live climate controls. Shadow mode lets us compare proposed actuator commands against existing behavior without touching the tent.
  Date/Author: 2026-05-21 / Codex


## Outcomes & Retrospective

Not started. At each milestone, update this section with what was implemented, what tests/logs proved it, and whether the implementation still matches the purpose above.


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
- `apps/hwd/src/dirt_hwd/services/kasa_schedule.py` reconciles scheduled Kasa plugs such as lights and heater plugs. The dehumidifier plug should be modeled as a DB-known Kasa actuator but controlled by climate policy, not by a time schedule.
- `apps/hwd/src/dirt_hwd/services/thermoforge.py` owns ThermoForge heater reconciliation. If present in the working tree, the new controller should either command it through a small explicit interface or route heater target decisions to its existing reconciliation path.
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
- Anti-windup: logic that prevents PI integrators from accumulating impossible demand while actuators are saturated, disabled, or clipped by higher-priority constraints.
- Bumpless transfer: switching between lights-on/lights-off policies or shadow/live authority without a sudden jump caused by stale integral state.


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
- actuator stale-sensor limits;
- deadbands and minimum on/off durations for Kasa dehumidifier cycling.

Initial policy should be conservative and explicit. Suggested starting values:

- veg lights-on: VPD 0.9-1.1 kPa, temp 75-80°F, RH max 70%;
- veg lights-off: VPD 0.7-0.9 kPa, temp 70-74°F, RH max 75%;
- flower early lights-on: VPD 1.1-1.3 kPa, temp 76-78°F, RH max 65% unless the user overrides to 80%;
- flower early lights-off: VPD 0.9-1.1 kPa, temp 70-72°F, RH max 75-80%;
- flower late lights-on: VPD 1.2-1.5 kPa, temp 74-78°F, RH max 55-60%;
- flower late lights-off: VPD 1.0-1.2 kPa, temp 70-72°F, RH max 65%.

These are starting controller policy values, not hidden constants. Implement them in `Settings` or a policy module so they are easy to inspect and tune. If the user confirms flower RH max should be exactly 80%, represent it directly as an envelope value even if VPD policy normally keeps actual RH lower.

Milestone 3: implement pure climate demand and allocation.

Add `apps/hwd/src/dirt_hwd/services/climate_controller.py` or split pure logic into `climate_math.py` plus service wiring. The pure function should take `ClimateInput`, `ClimatePolicy`, and `ClimateState`, and return `ClimateDecision`.

Suggested internal shape:

- `ClimateInput`: timestamp, temperature, RH, VPD, reading ages, lights state, stage, current actuator states.
- `ClimatePolicy`: bands, constraints, fan floor, actuator limits, deadbands, minimum cycle times.
- `ClimateState`: PI integrators, last actuator changes, dehumidifier cycle state, mode/phase for bumpless transfer.
- `ClimateDecision`: requested fan duty, humidifier intensity/level, dehumidifier power, heater target, reason codes, constraint flags, updated state.

The algorithm should run in this priority order:

1. Sensor failsafe. If temperature/RH/VPD is missing or stale, turn off humidifier and dehumidifier, hold fan at a safe floor or current value, and allow heater only if fresh temperature is available and below hard minimum.
2. Hard low-temperature guard. If temperature is below 70°F, heat. Keep fan at floor. Do not command elevated fan cooling. If RH/VPD is unsafe at the same time, dehumidifier may run and elevated fan may be allowed only as a drying safety action.
3. Hard RH guard. If RH is above max, force humidifier off and request drying from dehumidifier first, then elevated fan if temperature margin allows. If temperature is near the floor, prefer dehumidifier plus heater over fan purge.
4. VPD split-range control. If VPD is above target band, the air is too dry: humidifier demand rises and elevated fan demand falls toward floor if temperature allows. If VPD is below target band, the air is too wet: dehumidifier and/or elevated fan demand rises, with heater assist only when temperature is below target or close to the floor.
5. Temperature trim. If temperature is above target band, fan can rise above floor for cooling. If temperature is below target band, heater can rise while fan remains at floor unless drying safety overrides.
6. Conflict resolution. Never run humidifier and dehumidifier simultaneously. Allow heater with fan floor. Avoid heater plus elevated fan cooling. Allow heater plus elevated fan drying only for high-RH/low-VPD safety and log that reason explicitly.

Use anti-windup/external-reset logic. If the allocator clips humidifier output because RH is at max, the humidifier integrator must track delivered output. If dehumidifier minimum-off time prevents a requested on command, the drying integrator must not continue winding up as though the command were delivered. If fan is capped by low-temperature safety, the cooling/drying fan contribution should be tracked to the capped output.

Milestone 4: add actuator command boundaries.

Create small explicit actuator interfaces so the climate service does not contain provider details:

- fan actuator: reads current duty and sets duty through the existing ESP32 fan node API;
- humidifier actuator: uses existing Govee/H7142 dispatch and quantization;
- dehumidifier actuator: sets a DB-known Kasa plug on/off and records `dehumidifier_on`;
- heater actuator: commands existing heater authority, either Kasa heater plug or ThermoForge, without duplicating BLE/Kasa protocol code.

Do not add generic actuator registries unless duplication becomes real during implementation. A direct `ClimateActuators` composition object with four explicit fields is enough.

Milestone 5: shadow mode.

Wire `ClimateControllerService` into `dirt-hwd` in shadow mode. In shadow mode it reads sensors and current actuator states, computes decisions, records a `climate_controller` `tick` event, but does not dispatch actuator changes.

Keep current `HumidifierLoopService` and `FanTrimLoopService` live during this milestone. Shadow logs must include:

- stage, lights state, phase;
- temp/RH/VPD readings and ages;
- active policy bands and hard constraints;
- current actuator states;
- proposed actuator commands;
- delivered commands as `null` or unchanged in shadow;
- demand terms for VPD and temperature;
- reason codes and constraint flags.

Add a debug analyzer under `debug/climate-controller/analyze.py` or extend existing analysis scripts to compare proposed commands to observed actuator behavior and recent sensor trends. This analyzer should be a debug tool, not app code.

Milestone 6: authority cutover.

Stop wiring `FanTrimLoopService` and `HumidifierLoopService` as independent authorities. Wire `ClimateControllerService` in dispatch mode as the only loop allowed to command fan, humidifier, dehumidifier, and heater climate targets.

Direct cutover is preferred over compatibility wrappers. If rollback is needed during live rollout, use git/service rollback and re-enable the old services in `app.py`; do not leave permanent dual-authority code paths.

During cutover, preserve the hardware-specific event streams where useful, but make `climate_controller` the top-level decision stream. For example, a climate tick logs why the fan target changed; the fan actuator may still log the actual fan state change.

Milestone 7: retire obsolete code and docs.

After live behavior is stable, delete or demote obsolete top-level logic:

- remove or stop using `FanTrimLoopService` authority code if it has no remaining caller;
- keep `humidifier_dispatch.py` and provider-specific H7142 code;
- remove humidifier PI controller paths that are replaced by climate PI, unless a pure helper remains genuinely reused;
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

Shadow-mode acceptance:

- `dirt-hwd` runs with current authoritative loops still active.
- `var/logs/climate_controller/YYYY-MM-DD.jsonl` receives one tick per poll interval.
- Shadow ticks include policy bands, hard constraints, current actuator states, proposed commands, reasons, and sensor ages.
- No fan, humidifier, dehumidifier, or heater command is dispatched by the shadow service.

Dispatch-mode acceptance:

- `ClimateControllerService` is the only app-wired climate authority for fan, humidifier, dehumidifier, and heater climate targets.
- `FanTrimLoopService` no longer runs as an independent service.
- `HumidifierLoopService` no longer runs as an independent control authority.
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


## Idempotence and Recovery

Reading docs, running tests, running dry-run migrations, and running shadow mode are safe to repeat.

Migrations must be idempotent or reviewed for idempotence before live apply. Seed migrations should use stable natural identifiers such as `site_id='homebox'`, `tent_id='main'`, `device_id='kasa-dehumidifier-main'`, and `capability_id='power'`. Do not create duplicate devices or capabilities if the migration is applied once and then inspected.

Before applying local migrations, take a `pg_dump` backup under `var/db-backups/`. If a migration is wrong before apply, edit the migration and run `atlas migrate hash --env local`. If a migration is wrong after apply, create a forward corrective migration; do not hand-edit the live schema.

Shadow-mode rollback is simple: remove or disable the shadow service wiring and restart `dirt-hwd`. Since shadow mode does not dispatch commands, no actuator recovery is needed.

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
- Heater: existing Kasa heater plug and/or ThermoForge service path, depending on current deployed hardware.

Configuration dependencies:

- Fan floor and max percent.
- Hard minimum temperature, initially 70°F.
- Per-stage, per-phase VPD bands.
- Per-stage, per-phase temperature bands.
- Per-stage, per-phase RH max envelope.
- Sensor stale thresholds.
- Dehumidifier minimum on/off durations.
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
