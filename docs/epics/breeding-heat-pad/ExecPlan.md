# Breeding Tent Heat Pad Schedule

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

The breeding tent gets too cold during the dark period. A seedling heat pad is plugged into a new TP-Link Kasa plug currently reachable at `192.168.1.202`. After this change, Dirt will turn that heat pad on when the breeding tent lights turn off, and turn it off when the breeding tent lights turn on, without relying on a Kasa app schedule or a one-off script.

The visible behavior is that the breeding heat pad follows the inverse of the breeding light schedule. With the current breeding light schedule of `06:00` to `00:00` local time, the heat pad should be on from `00:00` to `06:00`. If the breeding light schedule changes later, the pad should follow that new lights-off window rather than requiring a second duplicated schedule edit.

This should reuse Dirt's existing scoped hardware architecture: `site` / `tent` / `zone` / `device` / `capability` rows, Kasa MAC verification, and database-owned `schedule` rows. The architecture may expand slightly to support scheduled non-light Kasa actuators, but the heat pad must not masquerade as a light just to fit the current `LightsLoopService`.


## Progress

- [x] (2026-05-15) Read `.agents/PLANS.md`, `docs/commands.md`, `docs/database.md`, `docs/observability.md`, and `docs/rules/boundary-contracts.md`.
- [x] (2026-05-15) Inspected existing Kasa lights architecture in `apps/hwd/src/dirt_hwd/services/lights.py`, `apps/hwd/src/dirt_hwd/services/kasa_inventory.py`, `apps/shared/src/dirt_shared/models/schedule.py`, and the multi-Kasa lights epic.
- [x] (2026-05-15) Confirmed multi-tenant lights support is already present for scoped Kasa light schedules.
- [x] (2026-05-15) Wrote this implementation plan.
- [ ] Discover the new Kasa plug at `192.168.1.202` and record its stable MAC/provider identity.
- [ ] Add local DB seed/migration rows for the breeding heat pad device, capability, and derived schedule.
- [ ] Extract or add a generic scheduled Kasa actuator loop while preserving existing light behavior.
- [ ] Add observability, tests, and operator validation for the heat pad schedule.
- [ ] Restart `dirt-hwd` and verify the real plug reconciles safely.


## Surprises & Discoveries

- Observation: Multi-tenant Kasa lights are already mostly implemented.
  Evidence: `LightsLoopService._load_targets()` queries all enabled `Schedule.kind == "lights"` rows joined to scoped Kasa `Device` rows, and existing migration `migrations/20260509040000_authoritative_kasa_lights.sql` seeds `main`, `breeding`, and `clones` Kasa light schedules.

- Observation: Kasa control already has the safety property needed for this heat pad.
  Evidence: `apps/hwd/src/dirt_hwd/services/kasa_inventory.py` treats the database as the owner of device identity, tries the stored IP only as a fast path, and verifies the observed MAC before returning a controllable device.

- Observation: The current schedule shape can represent a direct heat pad window, but not a clean relationship to the breeding light schedule.
  Evidence: `Schedule` has `starts_local` and `ends_local`, but no source schedule reference. A direct heat pad schedule of `00:00` to `06:00` would work today, but it would drift if `breeding-lights-photoperiod` changes.


## Decision Log

- Decision: Represent the heat pad as its own scoped Kasa actuator, not as another light.
  Rationale: The hardware is a heat source with different safety expectations, logs, UI labels, and future control policy. Reusing Kasa discovery and schedule reconciliation is clean; pretending it is a light is not.
  Date/Author: 2026-05-15 / Codex

- Decision: Use the Kasa plug's MAC as the canonical identity and treat `192.168.1.202` as only a connection hint.
  Rationale: This matches the existing lights architecture and prevents Dirt from controlling the wrong plug after DHCP changes or Kasa alias changes.
  Date/Author: 2026-05-15 / Codex

- Decision: Add a generic scheduled Kasa power actuator path, then keep `LightsLoopService` as either a thin wrapper or a compatibility name over that generic path.
  Rationale: Lights and heat pads share the same mechanics: load scoped schedules, resolve a known Kasa plug, derive desired on/off state, reconcile, update device freshness, and log transitions. The difference is schedule kind, capability id, stream name, and whether a schedule is direct or derived from another schedule.
  Date/Author: 2026-05-15 / Codex

- Decision: Make the heat pad schedule derive from `breeding-lights-photoperiod` with inverse semantics.
  Rationale: The user wants "as soon as we turn the lights off." A source relationship keeps that intent true when the breeding light window changes, instead of duplicating `00:00` and `06:00` in a second row.
  Date/Author: 2026-05-15 / Codex


## Outcomes & Retrospective

Not yet implemented. At completion, record whether the generic scheduled Kasa actuator path replaced the existing lights loop internally, whether the derived schedule columns were sufficient, and whether the real plug followed the breeding light schedule during a live reconciliation.


## Context and Orientation

Repository root is `/home/akcom/code/dirt`.

Read these docs before implementation:

- `docs/commands.md` before running tests, service commands, or development commands.
- `docs/database.md` before editing `apps/shared/src/dirt_shared/models/` or running Atlas migrations.
- `docs/references/atlas/INDEX.md` before running `atlas migrate diff`, `atlas migrate apply`, or `atlas migrate lint`.
- `docs/observability.md` before adding or changing `log_event()` streams.
- `docs/rules/boundary-contracts.md` before changing API, gateway, hosted sync, command, or persisted JSON payload shapes.
- `docs/references/tanstack-router-v1/INDEX.md`, `docs/references/tailwind-v4/INDEX.md`, and `docs/references/modern-idiomatic-typescript/INDEX.md` before editing `web-ui/src/**`.

Important existing pieces:

- `apps/shared/src/dirt_shared/models/device.py` defines `Device` and `Capability`. `Device.provider_uid_kind='mac'` plus `Device.provider_uid='<MAC>'` is already the stable Kasa identity pattern.
- `apps/shared/src/dirt_shared/models/schedule.py` defines `Schedule`. Schedules are scoped to a site and tent, may target a device and capability, and currently carry `kind`, `starts_local`, `ends_local`, `timezone`, and `enabled`.
- `apps/hwd/src/dirt_hwd/services/kasa_inventory.py` verifies DB-known Kasa devices by MAC before control.
- `apps/hwd/src/dirt_hwd/services/lights.py` is the current DB-backed Kasa schedule reconciler for `kind='lights'`.
- `apps/hwd/src/dirt_hwd/app.py` wires `LightsLoopService` into `dirt-hwd`.
- `apps/shared/src/dirt_shared/services/light_schedules.py` and the gateway/control-plane schedule contracts currently focus on light schedules. Do not expand these to raw dictionaries; use Pydantic DTOs at boundaries if the heat-pad schedule is exposed over API or sync.
- The current breeding light schedule is seeded as `schedule_id='breeding-lights-photoperiod'`, tent `homebox/breeding`, kind `lights`, starts `06:00`, ends `00:00`, timezone `America/Denver`.

Terms:

- A direct schedule stores its own local on/off window in `starts_local` and `ends_local`.
- A derived schedule computes its active window from another schedule. For this feature, the heat pad schedule is the inverse of the breeding lights schedule: active when the source lights schedule is inactive.
- A scheduled Kasa actuator is any DB-known Kasa plug whose power state is reconciled from a scoped schedule. Lights are one kind; the heat pad is another.


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

Milestone 2: Add schedule-source support for derived schedules.

Expand `Schedule` only as much as needed to express "this schedule is the inverse of another scoped schedule." Add nullable columns to `apps/shared/src/dirt_shared/models/schedule.py` and an Atlas migration:

- `source_schedule_id: str | None`, scoped to the same site/tent as the child schedule.
- `source_relation: str | None`, with initial owned values `inverse` and possibly `same` if useful for future reuse.

Keep `starts_local` and `ends_local` for direct schedules. For a derived schedule, the source schedule is authoritative; computed start/end values should be produced by the service layer. The heat pad row should be:

- `schedule_id='breeding-heat-pad-lights-off'`
- `kind='heat_pad'`
- `device_id` pointing at `kasa-heat-pad-breeding`
- `capability_id` pointing at `heat_pad_power`
- `source_schedule_id='breeding-lights-photoperiod'`
- `source_relation='inverse'`
- `timezone='America/Denver'`
- `enabled=true`

Add tests that prove a derived schedule returns an active window of `00:00` to `06:00` when the source lights schedule is `06:00` to `00:00`.

Milestone 3: Seed the heat pad device and capability.

Create an Atlas migration after the MAC discovery step. The migration should upsert:

- A breeding tent zone for the heat pad if the chosen zone does not already exist.
- The canonical Kasa heat pad `device` row.
- One actuator `capability` row with `capability_id='heat_pad_power'`, `kind='actuator'`, `metric_name='heat_pad_on'`, `unit='bool'`, and `source='kasa'` if this matches existing capability conventions.
- The derived heat pad `schedule` row described above.

Do not store the Kasa username/password or any token in the DB.

Milestone 4: Extract generic Kasa schedule reconciliation.

Refactor `apps/hwd/src/dirt_hwd/services/lights.py` toward a shared implementation, for example:

- `apps/hwd/src/dirt_hwd/services/kasa_schedule.py`
- `ScheduledKasaTarget`
- `ScheduledKasaActuatorService`
- `ScheduleTargetLoader` or a DB loader that can select allowed schedule kinds

The generic service should:

- Load enabled schedules for configured kinds such as `lights` and `heat_pad`.
- Join through `Site`, `Tent`, `Zone`, `Device`, and `Capability`.
- Require `Device.enabled is true`, `Device.controller == 'kasa'`, `provider_uid_kind == 'mac'`, and non-null `provider_uid`.
- Resolve direct schedules from `starts_local` / `ends_local`.
- Resolve derived schedules by loading the source schedule in the same site/tent and applying `source_relation`.
- Compute desired state with the existing `derive_lights_from_times()` helper or a renamed generic time-window helper. Preserve midnight-crossing behavior.
- Connect through `KasaInventory.connect_verified()` and never control unverified plugs.
- Cache connected plug objects by `device_id`, disconnect removed/inactive devices, and refresh `Device.last_seen`, IP, firmware, and Kasa metadata after successful polls.
- Emit one transition log event only when the plug state changes.

Keep existing light behavior compatible. `LightsLoopService` may remain as a wrapper that configures the generic service for `kind='lights'` and stream `lights`, or it may be replaced by one app-wired service that handles both `lights` and `heat_pad`. If using one service, name it clearly in `apps/hwd/src/dirt_hwd/app.py` so the composition root still reads as hardware services, not miscellaneous loops.

Milestone 5: Add heat-pad observability.

Register a new `heat_pad` stream in `apps/shared/src/dirt_shared/observability.py` with 30-day retention. Log:

- `state_change` with `site_id`, `tent_id`, `zone_id`, `device_id`, `capability_id`, `schedule_id`, `source_schedule_id`, `new_state`, `reason`, `minutes_until_off`, and `minutes_until_on`.
- `error` with scope fields and a compact exception summary.
- Optional `source_schedule_unresolved` if a derived schedule is enabled but its source cannot be loaded.

For direct schedules, use reasons such as `scheduled_on` and `scheduled_off`. For the heat pad, use explicit reasons such as `source_lights_off` and `source_lights_on` so log readers can distinguish the inverse relationship from a direct time window.

Milestone 6: API/UI projection if needed for operator visibility.

At minimum, the operator should be able to confirm the heat pad schedule and current desired state without reading raw SQL. Prefer adding a generic scheduled actuator read model rather than overloading light-only endpoints.

Add or extend a shared service, for example `apps/shared/src/dirt_shared/services/schedules.py`, that lists schedules by tent and optional kind. It should return computed windows for derived schedules and include source schedule fields. Then expose one local FastAPI endpoint under `apps/web/src/dirt_web/api/scope.py` or a new schedule module:

- `GET /api/tents/{tent_id}/schedules`
- Optional query `kind=lights` or `kind=heat_pad`

If this endpoint crosses to the hosted control plane, update `apps/shared/src/dirt_shared/cloud_contract.py`, `apps/gateway/src/dirt_gateway/local.py`, `apps/control-plane/src/dirt_control/api/gateway.py`, and `apps/control-plane/src/dirt_control/api/browser.py` with typed Pydantic DTOs. Do not add handwritten hosted frontend interfaces; regenerate hosted contracts if the web UI consumes hosted schedule data.

UI work is optional for first live control if logs and API are sufficient, but the clean end state is a compact breeding tent schedule/status row showing:

- Lights `06:00-00:00`, currently on/off.
- Heat pad derived from lights, `00:00-06:00`, currently on/off.
- Next transition.

Milestone 7: Tests and live rollout.

Add focused tests:

- Unit tests for direct and inverse derived schedule resolution, including midnight crossing.
- HWD service tests with fake Kasa plugs proving the heat pad turns on when the source lights schedule is off and turns off when source lights are on.
- Regression tests proving existing light schedules still reconcile and refresh `Device.last_seen`.
- DB/service tests proving the heat pad target loader ignores unverified Kasa devices, disabled devices, disabled schedules, missing source schedules, and non-Kasa controllers.
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

Review and manually adjust the generated migration if Atlas cannot express the intended derived-schedule comments or seed rows cleanly. Then run focused tests:

    uv run pytest apps/hwd/tests/test_lights_loop.py -q
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
- The heat pad schedule is enabled and derives from `breeding-lights-photoperiod` with inverse semantics.
- With breeding lights scheduled `06:00` to `00:00`, the computed heat pad window is `00:00` to `06:00`.
- A fake-service test proves that during the dark window the heat pad plug receives `turn_on()`, and during the light window it receives `turn_off()`.
- Existing Kasa light tests still pass unchanged or with only naming updates caused by the shared implementation.
- `var/logs/heat_pad/YYYY-MM-DD.jsonl` records a `state_change` when the pad changes state, with breeding tent scope and the source light schedule id.
- A live `dirt-hwd` run connects only after MAC verification and updates the heat pad device `last_seen`.
- Manual observation confirms the physical heat pad turns on only during lights-off and turns off when lights are on.

Expected log shape:

    {"stream":"heat_pad","event":"state_change","site_id":"homebox","tent_id":"breeding","device_id":"kasa-heat-pad-breeding","capability_id":"heat_pad_power","schedule_id":"breeding-heat-pad-lights-off","source_schedule_id":"breeding-lights-photoperiod","new_state":"on","reason":"source_lights_off",...}


## Idempotence and Recovery

The Kasa discovery step is read-only and safe to repeat.

The migration should use upserts for seed data so it is safe to apply once through Atlas and safe to inspect repeatedly. Do not run ad hoc DDL from app startup code.

If the plug cannot be verified by MAC, the service must log an error and skip control rather than falling back to IP-only control. Fix the DB identity or Kasa provisioning, then retry by restarting `dirt-hwd` or waiting for the next poll.

If the source light schedule cannot be loaded, the heat pad should fail off or skip control. Prefer skip-with-error over guessing a duplicated stale window; the source relationship is the safety contract.

Rollback options:

- Disable only the heat pad schedule:

    UPDATE schedule
    SET enabled = false, updated_at = now()
    WHERE schedule_id = 'breeding-heat-pad-lights-off';

- Then restart or wait for `dirt-hwd` to stop reconciling the target. Manually turn the Kasa plug off in the Kasa app if immediate physical shutoff is needed.

- To revert schema changes, restore from the pre-migration backup or write a normal Atlas down/forward migration according to `docs/database.md`; do not hand-edit production schema outside Atlas.


## Artifacts and Notes

Known user-provided fact:

- New Kasa plug fast-path IP: `192.168.1.202`.

Facts still to discover:

- Kasa alias.
- Stable MAC/provider UID.
- Model, hardware version, firmware version, and RSSI.

Existing breeding light source schedule:

- `schedule_id='breeding-lights-photoperiod'`
- `kind='lights'`
- current seeded window: `06:00` to `00:00`
- expected inverse heat pad window: `00:00` to `06:00`


## Interfaces and Dependencies

End-state local DB interfaces:

- `device.device_id='kasa-heat-pad-breeding'`
- `device.controller='kasa'`
- `device.provider_uid_kind='mac'`
- `device.provider_uid='<discovered MAC>'`
- `capability.capability_id='heat_pad_power'`
- `schedule.schedule_id='breeding-heat-pad-lights-off'`
- `schedule.kind='heat_pad'`
- `schedule.source_schedule_id='breeding-lights-photoperiod'`
- `schedule.source_relation='inverse'`

End-state Python interfaces:

- Existing `KasaInventory.connect_verified()` remains the only Kasa control entry point.
- A generic scheduled Kasa actuator service owns shared reconciliation behavior.
- `LightsLoopService` remains compatible for existing lights or is replaced in `apps/hwd/src/dirt_hwd/app.py` by a clearly named scheduled Kasa actuator service.
- A pure schedule resolver computes direct and inverse windows and can be tested without hardware.

End-state observability:

- `heat_pad` stream registered in `apps/shared/src/dirt_shared/observability.py`.
- State transition and error events include scope and schedule source fields.

External dependencies:

- Existing `python-kasa` dependency.
- Existing Kasa credentials from `KASA_USERNAME` and `KASA_PASSWORD`.
- The physical Kasa plug at `192.168.1.202`, verified by MAC before control.


## Revision Notes

- 2026-05-15: Initial plan written. The plan explicitly reuses the multi-tenant Kasa lights pattern and expands it into a generic scheduled Kasa actuator path for the breeding heat pad.
