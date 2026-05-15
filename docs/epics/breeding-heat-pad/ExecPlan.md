# Breeding Tent Heat Pad Schedule

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

The breeding tent gets too cold during the dark period. A seedling heat pad is plugged into a new TP-Link Kasa plug currently reachable at `192.168.1.202`. After this change, Dirt will run that heat pad from its own explicit local-time schedule, without relying on a Kasa app schedule or a one-off script.

The initial visible behavior is that the breeding heat pad turns on at `00:00` and turns off at `06:00` local time, matching the current dark window for the breeding tent. The heat pad schedule is deliberately independent from the breeding light schedule. That keeps the control surface easy to understand and makes future changes obvious: if the pad should pre-warm 30 minutes before lights-off or shut off 30 minutes before lights-on, edit the heat pad schedule directly.

This should reuse Dirt's existing scoped hardware architecture: `site` / `tent` / `zone` / `device` / `capability` rows, Kasa MAC verification, and database-owned `schedule` rows. The architecture may expand slightly to support scheduled non-light Kasa actuators, but the heat pad must not masquerade as a light just to fit the current `LightsLoopService`.


## Progress

- [x] (2026-05-15) Read `.agents/PLANS.md`, `docs/commands.md`, `docs/database.md`, `docs/observability.md`, and `docs/rules/boundary-contracts.md`.
- [x] (2026-05-15) Inspected existing Kasa lights architecture in `apps/hwd/src/dirt_hwd/services/lights.py`, `apps/hwd/src/dirt_hwd/services/kasa_inventory.py`, `apps/shared/src/dirt_shared/models/schedule.py`, and the multi-Kasa lights epic.
- [x] (2026-05-15) Confirmed multi-tenant lights support is already present for scoped Kasa light schedules.
- [x] (2026-05-15) Wrote this implementation plan.
- [x] (2026-05-15) Revised the plan to follow the repo-wide clean architecture preference: direct replacement, no durable compatibility wrapper, and removal of the misleading light-specific service name.
- [x] (2026-05-15) Revised the plan to use an explicit heat pad schedule instead of source/inverse schedule composition.
- [ ] Discover the new Kasa plug at `192.168.1.202` and record its stable MAC/provider identity.
- [ ] Add local DB seed/migration rows for the breeding heat pad device, capability, and direct schedule.
- [ ] Replace the light-specific Kasa loop with a canonical scheduled Kasa actuator loop that owns both lights and heat pads.
- [ ] Add observability, tests, and operator validation for the heat pad schedule.
- [ ] Restart `dirt-hwd` and verify the real plug reconciles safely.


## Surprises & Discoveries

- Observation: Multi-tenant Kasa lights are already mostly implemented.
  Evidence: `LightsLoopService._load_targets()` queries all enabled `Schedule.kind == "lights"` rows joined to scoped Kasa `Device` rows, and existing migration `migrations/20260509040000_authoritative_kasa_lights.sql` seeds `main`, `breeding`, and `clones` Kasa light schedules.

- Observation: Kasa control already has the safety property needed for this heat pad.
  Evidence: `apps/hwd/src/dirt_hwd/services/kasa_inventory.py` treats the database as the owner of device identity, tries the stored IP only as a fast path, and verifies the observed MAC before returning a controllable device.

- Observation: The current schedule shape already fits the heat pad when the pad owns its own schedule.
  Evidence: `Schedule` has `kind`, `starts_local`, `ends_local`, `timezone`, `enabled`, and optional device/capability ownership. A `kind='heat_pad'` row with `starts_local='00:00'` and `ends_local='06:00'` is enough for the initial behavior.


## Decision Log

- Decision: Represent the heat pad as its own scoped Kasa actuator, not as another light.
  Rationale: The hardware is a heat source with different safety expectations, logs, UI labels, and future control policy. Reusing Kasa discovery and schedule reconciliation is clean; pretending it is a light is not.
  Date/Author: 2026-05-15 / Codex

- Decision: Use the Kasa plug's MAC as the canonical identity and treat `192.168.1.202` as only a connection hint.
  Rationale: This matches the existing lights architecture and prevents Dirt from controlling the wrong plug after DHCP changes or Kasa alias changes.
  Date/Author: 2026-05-15 / Codex

- Decision: Replace `LightsLoopService` with a canonical scheduled Kasa actuator service.
  Rationale: Lights and heat pads share the same mechanics: load scoped schedules, resolve a known Kasa plug, derive desired on/off state, reconcile, update device freshness, and log transitions. Once the loop owns more than lights, `LightsLoopService` is a misleading abstraction. The clean implementation is to introduce a service named for the actual responsibility, wire that service directly in `apps/hwd/src/dirt_hwd/app.py`, update owned tests and imports, and delete the light-specific class rather than preserving a wrapper or alias.
  Date/Author: 2026-05-15 / User/Codex

- Decision: Give the heat pad its own direct schedule instead of deriving it from the breeding light schedule.
  Rationale: Direct schedules are easier to understand, inspect, and edit. The heat pad may eventually need offsets from the light window, such as pre-warming 30 minutes before lights-off or shutting off 30 minutes before lights-on. Encoding those choices as explicit `starts_local` and `ends_local` values keeps the pad decoupled from lights and avoids clever schedule-composition logic.
  Date/Author: 2026-05-15 / User/Codex


## Outcomes & Retrospective

Not yet implemented. At completion, record whether `ScheduledKasaActuatorService` fully replaced `LightsLoopService`, whether the direct heat pad schedule was sufficient, and whether the real plug followed the configured heat pad schedule during a live reconciliation.


## Context and Orientation

Repository root is `/home/akcom/code/dirt`.

Read these docs before implementation:

- `docs/commands.md` before running tests, service commands, or development commands.
- `docs/database.md` before editing `apps/shared/src/dirt_shared/models/` or running Atlas migrations.
- `docs/references/atlas/INDEX.md` before running `atlas migrate diff`, `atlas migrate apply`, or `atlas migrate lint`.
- `docs/observability.md` before adding or changing `log_event()` streams.
- `docs/rules/simple-clean-architecture.md` before revising this plan's architecture or deciding whether to preserve a compatibility path.
- `docs/rules/boundary-contracts.md` before changing API, gateway, hosted sync, command, or persisted JSON payload shapes.
- `docs/references/tanstack-router-v1/INDEX.md`, `docs/references/tailwind-v4/INDEX.md`, and `docs/references/modern-idiomatic-typescript/INDEX.md` before editing `web-ui/src/**`.

Important existing pieces:

- `apps/shared/src/dirt_shared/models/device.py` defines `Device` and `Capability`. `Device.provider_uid_kind='mac'` plus `Device.provider_uid='<MAC>'` is already the stable Kasa identity pattern.
- `apps/shared/src/dirt_shared/models/schedule.py` defines `Schedule`. Schedules are scoped to a site and tent, may target a device and capability, and currently carry `kind`, `starts_local`, `ends_local`, `timezone`, and `enabled`.
- `apps/hwd/src/dirt_hwd/services/kasa_inventory.py` verifies DB-known Kasa devices by MAC before control.
- `apps/hwd/src/dirt_hwd/services/lights.py` is the current DB-backed Kasa schedule reconciler for `kind='lights'`. This plan replaces that light-specific service with a generic scheduled Kasa actuator service and removes the old class.
- `apps/hwd/src/dirt_hwd/app.py` currently wires `LightsLoopService` into `dirt-hwd`; it should wire the new scheduled Kasa actuator service directly after this plan is implemented.
- `apps/shared/src/dirt_shared/services/light_schedules.py` and the gateway/control-plane schedule contracts currently focus on light schedules. Do not expand these to raw dictionaries; use Pydantic DTOs at boundaries if the heat-pad schedule is exposed over API or sync.
- The current breeding light schedule is seeded as `schedule_id='breeding-lights-photoperiod'`, tent `homebox/breeding`, kind `lights`, starts `06:00`, ends `00:00`, timezone `America/Denver`.
- The initial heat pad schedule should be `schedule_id='breeding-heat-pad-night'`, tent `homebox/breeding`, kind `heat_pad`, starts `00:00`, ends `06:00`, timezone `America/Denver`.

Terms:

- A direct schedule stores its own local on/off window in `starts_local` and `ends_local`.
- A scheduled Kasa actuator is any DB-known Kasa plug whose power state is reconciled from its own scoped schedule. Lights are one kind; the heat pad is another.


## Plan of Work

Milestone 1: Discover and record the heat pad plug identity.

Use `python-kasa` through a small throwaway script under `debug/` or an existing inspection pattern to connect to `192.168.1.202`, authenticate with `KASA_USERNAME` / `KASA_PASSWORD`, call `update()`, and record the observed MAC, alias, model, firmware, hardware version, and RSSI. Do not log credentials.

The result should be a Kasa identity tuple suitable for a canonical `device` row:

- `site_id='homebox'`
- `tent_id='breeding'`
- `zone_id='root-zone'` or `zone_id='heat'`; choose one and keep it consistent in the migration and UI labels
- `device_id='kasa-heat-pad-breeding'`
- `name='Kasa breeding heat pad'`
- `kind='actuator'`
- `controller='kasa'`
- `ip='192.168.1.202'`
- `provider_uid_kind='mac'`
- `provider_uid='<discovered MAC>'`

Milestone 2: Define the direct heat pad schedule model.

Do not add schedule-source, inverse, offset, or composition fields. The existing `Schedule` model already has the fields needed for a direct heat pad schedule:

- `schedule_id='breeding-heat-pad-night'`
- `kind='heat_pad'`
- `device_id` pointing at `kasa-heat-pad-breeding`
- `capability_id` pointing at `heat_pad_power`
- `starts_local='00:00'`
- `ends_local='06:00'`
- `timezone='America/Denver'`
- `enabled=true`

Add tests that prove a direct `00:00` to `06:00` heat pad schedule is on during that window and off outside it. The same time-window helper should continue to handle midnight-crossing schedules such as `21:00` to `09:00` for future heat pad tuning.

Milestone 3: Seed the heat pad device and capability.

Create an Atlas migration after the MAC discovery step. The migration should upsert:

- A breeding tent zone for the heat pad if the chosen zone does not already exist.
- The canonical Kasa heat pad `device` row.
- One actuator `capability` row with `capability_id='heat_pad_power'`, `kind='actuator'`, `metric_name='heat_pad_on'`, `unit='bool'`, and `source='kasa'` if this matches existing capability conventions.
- The direct heat pad `schedule` row described above.

Do not store the Kasa username/password or any token in the DB.

Milestone 4: Replace light-specific reconciliation with canonical Kasa schedule reconciliation.

Create the canonical scheduled Kasa implementation and delete the light-specific service. The durable module should be named for the responsibility rather than the first actuator kind it supported, for example:

- `apps/hwd/src/dirt_hwd/services/kasa_schedule.py`
- `ScheduledKasaTarget`
- `ScheduledKasaActuatorService`
- `ScheduleTargetLoader` or a DB loader that can select allowed schedule kinds

Move the reusable behavior out of `apps/hwd/src/dirt_hwd/services/lights.py` into the new module, then remove `LightsLoopService` and update all owned callers/tests/imports in the same implementation. Do not leave a durable `LightsLoopService` wrapper, alias, or compatibility class. A temporary wrapper is acceptable only as an in-progress implementation step and must be gone before the ExecPlan is marked complete.

The canonical service should:

- Load enabled schedules for configured kinds such as `lights` and `heat_pad`.
- Join through `Site`, `Tent`, `Zone`, `Device`, and `Capability`.
- Require `Device.enabled is true`, `Device.controller == 'kasa'`, `provider_uid_kind == 'mac'`, and non-null `provider_uid`.
- Resolve schedules only from their own `starts_local` / `ends_local`.
- Compute desired state with the existing `derive_lights_from_times()` helper or a renamed generic time-window helper. Preserve midnight-crossing behavior.
- Connect through `KasaInventory.connect_verified()` and never control unverified plugs.
- Cache connected plug objects by `device_id`, disconnect removed/inactive devices, and refresh `Device.last_seen`, IP, firmware, and Kasa metadata after successful polls.
- Emit one transition log event only when the plug state changes.

Wire one app-level scheduled Kasa actuator service in `apps/hwd/src/dirt_hwd/app.py` to handle both `lights` and `heat_pad`. Preserve the existing runtime behavior for light schedules by moving those tests to the new service and asserting the same outcomes, not by preserving the old class name.

Milestone 5: Add heat-pad observability.

Register a new `heat_pad` stream in `apps/shared/src/dirt_shared/observability.py` with 30-day retention. Log:

- `state_change` with `site_id`, `tent_id`, `zone_id`, `device_id`, `capability_id`, `schedule_id`, `new_state`, `reason`, `minutes_until_off`, and `minutes_until_on`.
- `error` with scope fields and a compact exception summary.

Use reasons such as `scheduled_on` and `scheduled_off`. Do not encode light-specific reasons in the heat pad stream; the pad is following its own schedule.

Milestone 6: API/UI projection if needed for operator visibility.

At minimum, the operator should be able to confirm the heat pad schedule and current desired state without reading raw SQL. Prefer adding a generic scheduled actuator read model rather than overloading light-only endpoints.

Add or extend a shared service, for example `apps/shared/src/dirt_shared/services/schedules.py`, that lists schedules by tent and optional kind. It should return each schedule's own local window and current state. Then expose one local FastAPI endpoint under `apps/web/src/dirt_web/api/scope.py` or a new schedule module:

- `GET /api/tents/{tent_id}/schedules`
- Optional query `kind=lights` or `kind=heat_pad`

If this endpoint crosses to the hosted control plane, update `apps/shared/src/dirt_shared/cloud_contract.py`, `apps/gateway/src/dirt_gateway/local.py`, `apps/control-plane/src/dirt_control/api/gateway.py`, and `apps/control-plane/src/dirt_control/api/browser.py` with typed Pydantic DTOs. Do not add handwritten hosted frontend interfaces; regenerate hosted contracts if the web UI consumes hosted schedule data.

UI work is optional for first live control if logs and API are sufficient, but the clean end state is a compact breeding tent schedule/status row showing:

- Lights `06:00-00:00`, currently on/off.
- Heat pad `00:00-06:00`, currently on/off.
- Next transition.

Milestone 7: Tests and live rollout.

Add focused tests:

- Unit tests for direct schedule resolution, including midnight crossing.
- HWD service tests with fake Kasa plugs proving the heat pad turns on during its configured schedule and turns off outside that schedule.
- Regression tests proving existing light schedules still reconcile and refresh `Device.last_seen`.
- DB/service tests proving the heat pad target loader ignores unverified Kasa devices, disabled devices, disabled schedules, schedules without usable local times, and non-Kasa controllers.
- API/gateway tests only if API or hosted projection is expanded.

After tests pass, apply the local migration, restart `dirt-hwd`, and verify logs and device state. Because this controls a heat source, the first live run should be observed manually: confirm the pad is physically plugged into the intended Kasa device, placed safely, and not trapped under material that cannot dissipate heat.


## Concrete Steps

Start from the repo root:

    cd /home/akcom/code/dirt

Inspect the current rows before changing schema or data:

    set -a; source .env; set +a
    PGPASSWORD="$DIRT_PG_PASSWORD" psql -h 127.0.0.1 -U dirt -d dirt

Useful read-only SQL:

    SELECT t.tent_id, z.zone_id, d.device_id, d.ip, d.provider_uid_kind, d.provider_uid
    FROM device d
    JOIN tent t ON t.id = d.tent_id
    LEFT JOIN zone z ON z.id = d.zone_id
    WHERE d.controller = 'kasa'
    ORDER BY t.tent_id, d.device_id;

    SELECT t.tent_id, s.schedule_id, s.kind, s.starts_local, s.ends_local, s.timezone, s.enabled
    FROM schedule s
    JOIN tent t ON t.id = s.tent_id
    WHERE t.tent_id = 'breeding'
    ORDER BY s.kind, s.schedule_id;

Discover the plug in a throwaway debug script or equivalent `uv run --package dirt-hwd ...` command. Record only non-secret device facts in this plan under `Artifacts and Notes`.

After editing SQLModel classes:

    atlas migrate diff breeding_heat_pad_schedule --env local

Review and manually adjust the generated migration if Atlas cannot express the intended seed rows cleanly. Then run focused tests:

    uv run pytest apps/hwd/tests/test_kasa_schedule.py -q
    uv run pytest apps/shared/tests -q
    uv run pytest apps/tests/invariants/ -q

Before committing:

    scripts/agent-fix
    uv run pytest -q

Live apply and service restart require operator awareness because they affect a heat source:

    pg_dump dirt > var/db-backups/dirt-$(date +%F-%H%M%S)-pre-heat-pad.sql
    atlas migrate apply --env local
    systemctl --user restart dirt-hwd
    journalctl --user -u dirt-hwd -n 100 --no-pager


## Validation and Acceptance

The feature is accepted when all of these are true:

- The local DB has a canonical enabled Kasa device for the breeding heat pad with a verified MAC, not just IP `192.168.1.202`.
- The heat pad schedule is enabled with `starts_local='00:00'`, `ends_local='06:00'`, and `timezone='America/Denver'`.
- A fake-service test proves that during the heat pad window the plug receives `turn_on()`, and outside the heat pad window it receives `turn_off()`.
- Existing Kasa light behavior is covered by tests against `ScheduledKasaActuatorService`; no test imports `LightsLoopService` after completion.
- `apps/hwd/src/dirt_hwd/app.py` wires the canonical scheduled Kasa actuator service directly; no durable `LightsLoopService` wrapper, alias, or compatibility class remains.
- `var/logs/heat_pad/YYYY-MM-DD.jsonl` records a `state_change` when the pad changes state, with breeding tent scope and the heat pad schedule id.
- A live `dirt-hwd` run connects only after MAC verification and updates the heat pad device `last_seen`.
- Manual observation confirms the physical heat pad follows its configured schedule.

Expected log shape:

    {"stream":"heat_pad","event":"state_change","site_id":"homebox","tent_id":"breeding","device_id":"kasa-heat-pad-breeding","capability_id":"heat_pad_power","schedule_id":"breeding-heat-pad-night","new_state":"on","reason":"scheduled_on",...}


## Idempotence and Recovery

The Kasa discovery step is read-only and safe to repeat.

The migration should use upserts for seed data so it is safe to apply once through Atlas and safe to inspect repeatedly. Do not run ad hoc DDL from app startup code.

If the plug cannot be verified by MAC, the service must log an error and skip control rather than falling back to IP-only control. Fix the DB identity or Kasa provisioning, then retry by restarting `dirt-hwd` or waiting for the next poll.

Rollback options:

- Disable only the heat pad schedule:

    UPDATE schedule
    SET enabled = false, updated_at = now()
    WHERE schedule_id = 'breeding-heat-pad-night';

- Then restart or wait for `dirt-hwd` to stop reconciling the target. Manually turn the Kasa plug off in the Kasa app if immediate physical shutoff is needed.

- To revert schema changes, restore from the pre-migration backup or write a normal Atlas down/forward migration according to `docs/database.md`; do not hand-edit production schema outside Atlas.


## Artifacts and Notes

Known user-provided fact:

- New Kasa plug fast-path IP: `192.168.1.202`.

Facts still to discover:

- Kasa alias.
- Stable MAC/provider UID.
- Model, hardware version, firmware version, and RSSI.

Existing breeding light schedule for context:

- `schedule_id='breeding-lights-photoperiod'`
- `kind='lights'`
- current seeded window: `06:00` to `00:00`

Initial heat pad schedule:

- `schedule_id='breeding-heat-pad-night'`
- `kind='heat_pad'`
- initial seeded window: `00:00` to `06:00`
- future tuning examples: `23:30` to `06:00` for pre-warm, or `00:00` to `05:30` for early shutoff


## Interfaces and Dependencies

End-state local DB interfaces:

- `device.device_id='kasa-heat-pad-breeding'`
- `device.controller='kasa'`
- `device.provider_uid_kind='mac'`
- `device.provider_uid='<discovered MAC>'`
- `capability.capability_id='heat_pad_power'`
- `schedule.schedule_id='breeding-heat-pad-night'`
- `schedule.kind='heat_pad'`
- `schedule.starts_local='00:00'`
- `schedule.ends_local='06:00'`
- `schedule.timezone='America/Denver'`

End-state Python interfaces:

- Existing `KasaInventory.connect_verified()` remains the only Kasa control entry point.
- `ScheduledKasaActuatorService` owns Kasa schedule reconciliation for `lights` and `heat_pad`.
- `apps/hwd/src/dirt_hwd/app.py` wires `ScheduledKasaActuatorService` directly.
- `LightsLoopService` is removed. No durable wrapper, alias, compatibility class, or light-specific scheduling service remains.
- A pure schedule resolver computes direct schedule windows and can be tested without hardware.

End-state observability:

- `heat_pad` stream registered in `apps/shared/src/dirt_shared/observability.py`.
- State transition and error events include scope and schedule fields.

External dependencies:

- Existing `python-kasa` dependency.
- Existing Kasa credentials from `KASA_USERNAME` and `KASA_PASSWORD`.
- The physical Kasa plug at `192.168.1.202`, verified by MAC before control.


## Revision Notes

- 2026-05-15: Initial plan written. The plan explicitly reuses the multi-tenant Kasa lights pattern and expands it into a generic scheduled Kasa actuator path for the breeding heat pad.
- 2026-05-15: Revised per user architecture preference. The plan now requires direct replacement of `LightsLoopService` with `ScheduledKasaActuatorService`; compatibility wrappers are not an end-state and must be removed before completion.
- 2026-05-15: Revised per user simplicity preference. The heat pad now owns a direct `00:00` to `06:00` schedule; source/inverse schedule composition is intentionally out of scope.
