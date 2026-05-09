# Multi Kasa Lights With Authoritative Device Identity

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.

## Purpose / Big Picture

Dirt currently controls one Kasa EP10 plug for the main grow lights. The user now has three identical Kasa EP10 plugs on the LAN: the existing main tent light plug, a clone light plug, and a breeding tent light plug. After this change, Dirt will know those plugs as canonical database devices, verify their stable hardware identity before controlling them, and run independent light schedules for each tent or light zone.

The visible outcome is simple: the main flower tent can run 12 hours on and 12 hours off, while clone and breeding lights can run 18 hours on and 6 hours off. The local web UI and the hosted public web UI will show each selected tent's active light schedule in local time, so a human can confirm the intended photoperiod without reading `.env`, logs, or database rows.

The safety outcome matters as much as the display outcome. Network discovery is allowed to find Kasa plugs, but discovery must not decide which plug to control. The local database is the desired inventory. A Kasa plug is controllable only when the observed device identity matches the canonical DB identity for that device.


## Progress

- [x] (2026-05-09T03:37:47Z) Investigated current local schedule, device, Kasa, and cloud sync models.
- [x] (2026-05-09T03:37:47Z) Confirmed current LAN Kasa EP10 discoveries: `lights` at `192.168.1.181` with MAC `6C:4C:BC:45:37:F6`, `clone-light` at `192.168.1.220` with MAC `10:5A:95:8B:E8:B7`, and renamed `breeding-tent-light` formerly discovered at `192.168.1.180` with MAC `10:5A:95:8B:E6:76`.
- [x] (2026-05-09T03:37:47Z) Wrote this implementation plan.
- [ ] Add local schema and seed migration for authoritative Kasa device identity.
- [ ] Refactor the local lights controller to reconcile all enabled DB-known Kasa light schedules.
- [ ] Add local schedule read/update APIs and generated contracts.
- [ ] Add typed schedule projection to gateway sync and hosted control-plane storage/API.
- [ ] Update local and hosted web UI schedule displays.
- [ ] Validate with tests, dry-run gateway sync, local UI, hosted UI, and controlled plug reconciliation.


## Surprises & Discoveries

- Observation: The local data model is closer to multi-light support than the running service is.
  Evidence: `schedule` already has `site_id`, `tent_id`, nullable `device_id`, nullable `capability_id`, `kind`, `starts_local`, `ends_local`, `timezone`, and `enabled`; `apps/hwd/src/dirt_hwd/services/lights.py` still accepts one `kasa_lights_host` from `LightsConfig` and always calls `GrowStateService.lights_state(site_id="homebox", tent_id="main")`.

- Observation: Hosted sync currently has catalog tables for site, tent, zone, device, and capability, but not schedules.
  Evidence: `apps/gateway/src/dirt_gateway/local.py:GatewayLocalServiceBundle.collect_catalog()` returns `site`, `tents`, `zones`, `devices`, and `capabilities`; `apps/control-plane/src/dirt_control/models/cloud.py` has `CloudSite`, `CloudTent`, `CloudZone`, `CloudDevice`, and `CloudCapability`, but no `CloudSchedule`.

- Observation: Clone lights are not represented by a current tent in the live database.
  Evidence: live `tent` rows are `homebox/main` and `homebox/breeding`. The plan must either add a `clones` tent or attach clone lights as a zone/device under an existing tent.

- Observation: The existing local web UI already has selected-tent cloud queries on the hosted path, which is a good display anchor.
  Evidence: `web-ui/src/routes/index.tsx` hosted mode loads `/api/sites`, `/api/tents`, `/api/tents/{tent_id}/state`, `/api/tents/{tent_id}/metrics/current`, `/api/tents/{tent_id}/devices`, and latest assets.


## Decision Log

- Decision: Make `device` the canonical owner of Kasa identity, and treat Kasa discovery as observation only.
  Rationale: Three identical EP10 plugs can appear on the network, aliases can change, and DHCP can move IP addresses. The app must not control a plug unless the observed stable identity matches the DB identity for that canonical device.
  Date/Author: 2026-05-09 / Codex

- Decision: Add first-class stable identity fields to the local `device` table instead of introducing a separate `device_identity` table for this milestone.
  Rationale: The current `device` table already owns `controller`, `ip`, `firmware_version`, `last_seen`, and `metadata`; each Kasa plug needs one stable identity, the MAC address. A separate identity table is more flexible but adds unnecessary join and migration surface now. If future devices need multiple identities, add `device_identity` in a later migration and backfill from these fields.
  Date/Author: 2026-05-09 / Codex

- Decision: Use `device.provider_uid_kind='mac'` and `device.provider_uid='<normalized MAC>'` for Kasa EP10 identity.
  Rationale: The Kasa local discovery output exposes MAC for these devices, and MAC survives alias and IP changes. Keep the field names provider-neutral because Govee, ESP32, OBSBOT, and future integrations may use cloud IDs, hostnames, serials, or USB IDs.
  Date/Author: 2026-05-09 / Codex

- Decision: Add a real `clones` tent unless implementation discovery proves clone lights are physically and operationally part of the breeding tent.
  Rationale: Independent photoperiods are easiest to reason about when each growth area has its own tent scope. If clone lights share the breeding tent environment but need a separate photoperiod, schedules can still target a specific light device under the same tent, but the UI phrase "per tent" becomes less accurate.
  Date/Author: 2026-05-09 / Codex

- Decision: Sync schedules to cloud as explicit data, not as derived grow state.
  Rationale: Hosted UI needs schedule visibility for tents that may not have a current grow and for device-specific schedules. The gateway already syncs catalog-shaped data; schedules are another catalog-like boundary and should have typed DTOs.
  Date/Author: 2026-05-09 / Codex


## Outcomes & Retrospective

Not yet implemented. At completion, record whether first-class `device.provider_uid*` fields were sufficient, whether a `clones` tent was created, and whether hosted schedule sync was added to the catalog endpoint or as a separate gateway endpoint.


## Context and Orientation

Repository root is `/home/akcom/code/dirt`.

Read these docs before implementation:

- `docs/commands.md` before running dev, test, lint, web UI, gateway, or deploy commands.
- `docs/database.md` before editing SQLModel models, migrations, or Atlas schema.
- `docs/rules/boundary-contracts.md` before changing local APIs, hosted gateway payloads, command payloads, outbox JSON, or generated contracts.
- `docs/hosted-control-plane.md` before operating gateway sync or deploying hosted control-plane changes.
- `docs/references/tanstack-router-v1/INDEX.md`, `docs/references/tailwind-v4/INDEX.md`, and `docs/references/modern-idiomatic-typescript/INDEX.md` before authoring or refactoring `web-ui/src/**`.
- `docs/references/atlas/INDEX.md` before running `atlas migrate diff/apply/lint`.

Important existing files and concepts:

- Local DB identity lives in `apps/shared/src/dirt_shared/models/device.py`. `Device` has stable public `device_id`, human name, `kind`, `controller`, `enabled`, JSON metadata, `last_seen`, `ip`, `firmware_version`, and timestamps.
- Capabilities live in the same model module as `Capability`. Kasa light devices should have an actuator capability with `capability_id='lights_power'`.
- Local schedules live in `apps/shared/src/dirt_shared/models/schedule.py`. `Schedule` rows are scoped by DB foreign keys to site and tent, may target a device/capability, and include `kind`, `starts_local`, `ends_local`, `timezone`, and `enabled`.
- Current grow and current tent photoperiod logic is in `apps/shared/src/dirt_shared/services/grow_state.py`. `GrowStateService.current_light_schedule()` returns one enabled `kind='lights'` schedule for a site/tent and falls back to `05:00-23:00`.
- Current Kasa light control is in `apps/hwd/src/dirt_hwd/services/lights.py`. It uses `python-kasa` `Discover.discover_single(host, credentials=creds)`, one env-configured host, and one default device id `kasa-lights-main`.
- `apps/hwd/src/dirt_hwd/app.py` wires one `LightsLoopService` into the production background service list.
- Local web grow endpoints are in `apps/web/src/dirt_web/api/grow.py` and scoped tent endpoints are in `apps/web/src/dirt_web/api/scope.py`.
- The OpenAPI contract is `contracts/webapp-v1.yaml`, with generated Python models in `contracts/python/src/dirt_contracts/webapp_v1/models.py` and TypeScript clients consumed by `web-ui`.
- Gateway local projection is `apps/gateway/src/dirt_gateway/local.py`. It currently collects catalog, latest metrics, rollups, and latest snapshot assets.
- Hosted gateway write API DTOs are currently in `apps/control-plane/src/dirt_control/api/gateway.py`.
- Hosted browser read APIs are in `apps/control-plane/src/dirt_control/api/browser.py`.
- Hosted cloud SQLModel tables are in `apps/control-plane/src/dirt_control/models/cloud.py`; cloud migrations live under `cloud/migrations/`.
- Hosted web UI route is `web-ui/src/routes/index.tsx`. It has separate hosted and local dashboard code paths in one route file.

Known local Kasa EP10 observations from 2026-05-09 discovery:

- Main tent: alias `lights`, IP `192.168.1.181`, MAC `6C:4C:BC:45:37:F6`, EP10 hardware `1.0 (US)`, firmware `1.1.1 Build 250908 Rel.112508`.
- Clone lights: alias `clone-light`, IP `192.168.1.220`, MAC `10:5A:95:8B:E8:B7`, same EP10 hardware/firmware.
- Breeding tent lights: alias renamed by user to `breeding-tent-light`, last observed IP `192.168.1.180`, MAC `10:5A:95:8B:E6:76`, same EP10 hardware/firmware.


## Plan of Work

Milestone 1: Local device identity schema and seed data.

Add provider-neutral stable identity fields to `Device` in `apps/shared/src/dirt_shared/models/device.py`:

- `provider_uid_kind: str | None`, for example `mac`.
- `provider_uid: str | None`, for example normalized uppercase colon-separated MAC.

Add indexes and a partial uniqueness constraint when both fields are present. The uniqueness should prevent two enabled or canonical device rows from claiming the same Kasa MAC. If Atlas cannot express the partial unique index cleanly through SQLModel metadata, add the index manually in the migration file after `atlas migrate diff` and document the manual edit in the migration comment.

Backfill and seed canonical rows through an Atlas local migration:

- Update `kasa-lights-main` with `controller='kasa'`, `kind='actuator'`, `zone_id='lights'`, `ip='192.168.1.181'`, `provider_uid_kind='mac'`, `provider_uid='6C:4C:BC:45:37:F6'`, and metadata containing observed alias/model/hardware/firmware.
- Insert `kasa-lights-clones` for clone lights with IP `192.168.1.220` and MAC `10:5A:95:8B:E8:B7`. If a `clones` tent is added, attach it there. If not, attach it to the chosen existing tent/zone and record that decision.
- Insert or update `kasa-lights-breeding` for breeding tent lights with IP `192.168.1.180` and MAC `10:5A:95:8B:E6:76`, attached to `homebox/breeding` and a lights zone.
- Insert `lights_power` actuator capabilities for the two new Kasa light devices.

Also seed schedule rows:

- Main stays `main-lights-photoperiod`, `09:00` to `21:00`, device `kasa-lights-main`, capability `lights_power`.
- Clone lights get an 18/6 lights schedule, for example `clones-lights-photoperiod`, with exact local times chosen during implementation. Prefer `06:00` to `00:00` unless the user chooses otherwise before implementation.
- Breeding tent lights get an 18/6 schedule, for example `breeding-lights-photoperiod`, with the same default `06:00` to `00:00` unless changed.

Milestone 2: Kasa inventory and identity verification service.

Create a small Kasa adapter module, for example `apps/hwd/src/dirt_hwd/services/kasa_inventory.py`, that wraps `python-kasa` and exposes typed internal results:

- `discover_known_devices(expected: list[KasaExpectedDevice]) -> dict[str, KasaResolvedDevice]`.
- `resolve_device(expected) -> KasaResolvedDevice | None`.
- `connect_verified(expected) -> Device | None`.

This adapter should:

- Try `device.ip` first as a fast path.
- After connecting, call `update()` and read the observed MAC, alias, model, hardware, firmware, and RSSI if exposed by `python-kasa`.
- Compare observed MAC to `device.provider_uid`; if mismatched, disconnect and refuse to control.
- If the fast path fails or mismatches, run Kasa discovery and search for the expected MAC.
- If discovery finds the expected MAC at a new IP, return that IP so the caller can update `device.ip`.
- Never control an EP10 whose MAC is not in the DB expected set.

Keep credential handling in `Settings` and do not log usernames or passwords. Logs may include device ids, aliases, IPs, MACs, and mismatch errors.

Milestone 3: Multi-device lights reconciliation.

Refactor `apps/hwd/src/dirt_hwd/services/lights.py` so the service no longer owns a single host. It should query enabled Kasa light schedules from the DB each tick, or cache them with periodic refresh. A schedule is controllable when:

- `Schedule.kind == 'lights'`
- `Schedule.enabled is true`
- `Schedule.starts_local` and `Schedule.ends_local` are not null
- `Schedule.device_id` references an enabled `Device`
- `Device.controller == 'kasa'`
- `Device.provider_uid_kind == 'mac'`
- `Device.provider_uid` is present
- `Schedule.capability_id`, if present, references `lights_power` or an enabled actuator capability for that device

For each schedule, compute current desired state from `starts_local`, `ends_local`, and `timezone`. Reuse or extract `GrowStateService._derive_lights_from_times()` into a public pure helper if needed; do not duplicate time-window edge cases. The service should reconcile each plug independently and log events to the `lights` stream with the actual schedule/device scope:

- `site_id`
- `tent_id`
- `zone_id`
- `device_id`
- `capability_id`
- `schedule_id`
- `new_state`
- `reason`
- `minutes_until_off`
- `minutes_until_on`

Update `apps/hwd/src/dirt_hwd/app.py` wiring and `apps/shared/src/dirt_shared/config.py`. Keep `KASA_USERNAME`, `KASA_PASSWORD`, and `LIGHTS_POLL_INTERVAL`. Retire `KASA_LIGHTS_HOST` from production control after the DB-backed service is working; leave an `.env.example` note if a compatibility fallback is kept for one release.

Milestone 4: Local schedule APIs and contracts.

Add typed DTOs for light schedules to `contracts/webapp-v1.yaml`:

- `LightSchedule` with `site_id`, `tent_id`, nullable `zone_id`, `device_id`, `capability_id`, `schedule_id`, `kind`, `enabled`, `timezone`, `starts_local`, `ends_local`, computed `duration_hours`, computed `is_on`, and transition minutes.
- `LightSchedulesResponse` with `schedules: LightSchedule[]`.
- `LightScheduleUpdateRequest` for local editing if write UI is in scope. Include `starts_local`, `ends_local`, `timezone`, and `enabled`. Do not allow changing `device_id` through the same endpoint.

Add local FastAPI routes under `apps/web/src/dirt_web/api/scope.py` or a new `apps/web/src/dirt_web/api/schedules.py`:

- `GET /api/tents/{tent_id}/lights/schedules`
- Optional `PATCH /api/tents/{tent_id}/lights/schedules/{schedule_id}` for editing local schedules.

The GET endpoint should work even when a tent has no current grow. It should read schedule rows directly instead of calling `GrowStateService.get_grow_current_payload()`.

Regenerate Python and TypeScript contracts using the repository's existing contract generation command. If no single command exists, inspect `pyproject.toml`, `contracts/`, and existing generated files, then document the exact command in this plan before running it.

Milestone 5: Gateway schedule sync and hosted API.

Add explicit schedule sync to the hosted control plane. Preferred design:

- Extend gateway catalog payload with `schedules: list[CatalogSchedule]`.
- Add a `CatalogSchedule` Pydantic DTO in `apps/control-plane/src/dirt_control/api/gateway.py`.
- Add a `CloudSchedule` SQLModel in `apps/control-plane/src/dirt_control/models/cloud.py`.
- Add a cloud Atlas migration under `cloud/migrations/` for `cloud_schedule`.
- Upsert schedules in the existing `PUT /api/gateway/v1/catalog` transaction.
- Add hosted browser route `GET /api/tents/{tent_id}/lights/schedules`.

`CloudSchedule` should store:

- `schedule_key` primary key, for example `{site_id}:{tent_id}:{schedule_id}`.
- `site_id`
- `tent_id`
- nullable `zone_id`
- nullable `device_id`
- nullable `capability_id`
- `schedule_id`
- `kind`
- `starts_local`
- `ends_local`
- `timezone`
- `is_enabled`
- `synced_at`
- `created_at`
- `updated_at`

If the catalog payload becomes too broad, use a separate gateway endpoint `PUT /api/gateway/v1/schedules`, but default to catalog extension because schedules are inventory/configuration state and should sync alongside devices and capabilities.

Update gateway tests in `apps/gateway/tests/test_sync.py` and control-plane tests to prove schedules are produced locally, accepted by cloud, stored, and returned to browser clients.

Milestone 6: Web UI display.

Update `web-ui/src/routes/index.tsx` in both local and hosted dashboard paths:

- Local mode should call the generated local API for the current or selected tent's light schedules.
- Hosted mode should call the hosted `/api/tents/{tent_id}/lights/schedules` route through `cloudGet`.
- Display the active light schedule in local time near existing tent/grow status, not buried in the devices table. A compact panel or row is enough:
  - label from device/schedule, for example "Main lights" or "Breeding tent light"
  - local on/off window, for example `09:00-21:00`
  - photoperiod, for example `12/12` or `18/6`
  - current state and next transition, for example `On, off in 4h 12m`
  - timezone abbreviation or full timezone if it differs from the user's browser timezone

Follow frontend repository rules before editing:

- Read `docs/references/tanstack-router-v1/INDEX.md` before changing routes.
- Read `docs/references/tailwind-v4/INDEX.md` before changing Tailwind classes.
- Read `docs/references/modern-idiomatic-typescript/INDEX.md` before TypeScript authoring.
- Use generated API client types for local API responses.
- Avoid fetching outside existing API-client/cloud helper patterns.
- Keep the UI operational and compact; do not add a marketing-style section.

Milestone 7: Optional local schedule editing UI.

If the user wants schedule edits from the browser in the same feature, add a small schedule editor after the display is working. Use time inputs or segmented presets for `12/12` and `18/6`; keep explicit `starts_local` and `ends_local` visible. Writes should hit the local API only. Hosted should remain read-only unless a separate command pathway for schedule changes is designed and reviewed.

Do not add hosted schedule write commands in this plan. Hosted commands currently target PTZ only and are intentionally narrow.


## Concrete Steps

Start with a clean understanding of the working tree. There may be unrelated local changes; do not revert them.

    cd /home/akcom/code/dirt
    git status --short --branch

Read required docs:

    sed -n '1,220p' docs/commands.md
    sed -n '1,220p' docs/database.md
    sed -n '1,220p' docs/rules/boundary-contracts.md
    sed -n '1,220p' docs/hosted-control-plane.md
    sed -n '1,220p' docs/references/atlas/INDEX.md

Inspect current schema and rows:

    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c '\d device' -c '\d schedule'
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "SELECT site.site_id,tent.tent_id,device.device_id,device.name,device.controller,device.ip,device.metadata FROM device JOIN site ON site.id=device.site_id LEFT JOIN tent ON tent.id=device.tent_id ORDER BY tent.tent_id NULLS FIRST, device.device_id;"
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "SELECT sch.schedule_id, sch.kind, sch.enabled, sch.timezone, sch.starts_local, sch.ends_local, site.site_id, tent.tent_id, dev.device_id FROM schedule sch JOIN site ON site.id=sch.site_id JOIN tent ON tent.id=sch.tent_id LEFT JOIN device dev ON dev.id=sch.device_id ORDER BY tent.tent_id, sch.schedule_id;"

Confirm Kasa identity before writing seed migrations:

    set -a; source .env; set +a
    uv run --package dirt-hwd kasa --username "$KASA_USERNAME" --password "$KASA_PASSWORD" --target 192.168.1.255 --discovery-timeout 8 discover

Do not toggle devices during discovery. If a deliberate physical confirmation is needed, ask the user before toggling a plug.

Implement local schema:

    # edit apps/shared/src/dirt_shared/models/device.py
    # read docs/references/atlas/INDEX.md first
    atlas migrate diff authoritative_kasa_device_identity --env local

Review the generated migration. Add seed/upsert SQL for the Kasa devices, capabilities, zones/tents if needed, and schedules. Apply locally only after review and backup:

    mkdir -p var/db-backups
    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD pg_dump -h 127.0.0.1 -U dirt -d dirt > var/db-backups/dirt-$(date +%F-%H%M%S)-pre-multi-kasa-lights.sql
    atlas migrate apply --env local

Implement and test the Kasa adapter and lights service:

    uv run pytest apps/hwd/tests/test_lights_loop.py -q
    uv run pytest apps/shared/tests/test_grow_state.py -q

Implement local schedule API and contracts:

    # edit contracts/webapp-v1.yaml
    # run the repo's contract generation command after discovering it
    uv run pytest apps/web/tests/test_scope_endpoints.py apps/web/tests/test_grow_endpoint.py -q

Implement gateway schedule sync:

    uv run pytest apps/gateway/tests/test_sync.py apps/control-plane/tests -q
    systemctl --user stop dirt-gateway
    uv run --package dirt-gateway python -m dirt_gateway.main --once --dry-run

Implement UI display:

    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test
    pnpm --dir web-ui build

Run broader validation before commit:

    uv run pytest -q
    scripts/agent-fix
    git status --short


## Validation and Acceptance

Local database acceptance:

- `device` has three enabled Kasa light actuator rows with stable provider identity:
  - `kasa-lights-main`, MAC `6C:4C:BC:45:37:F6`
  - `kasa-lights-clones`, MAC `10:5A:95:8B:E8:B7`
  - `kasa-lights-breeding`, MAC `10:5A:95:8B:E6:76`
- Each Kasa light has a `lights_power` actuator capability.
- Each desired light controller has exactly one enabled `kind='lights'` schedule unless multiple schedules are explicitly designed for the same device.

Local service acceptance:

- Starting `dirt-hwd` logs that the lights loop loaded multiple DB-backed schedules.
- If a plug IP is correct, the loop verifies the MAC before sending `turn_on()` or `turn_off()`.
- If a plug IP changes, discovery finds the expected MAC, updates or reports the observed IP, and still controls only the matching canonical device.
- If an unknown EP10 appears, the loop logs it only as unknown and never controls it.
- If a DB-known device's observed MAC mismatches the expected MAC, the loop refuses to control that endpoint and emits a `lights` error event for that canonical device.

Local API acceptance:

- `GET /api/tents/main/lights/schedules` returns the main tent schedule with `09:00:00` and `21:00:00` local times and computed `12/12` equivalent duration.
- `GET /api/tents/breeding/lights/schedules` returns the breeding tent 18/6 schedule.
- If a `clones` tent is added, `GET /api/tents/clones/lights/schedules` returns the clone 18/6 schedule.
- These endpoints work for a tent that has no current `growrun`.

Cloud sync acceptance:

- `uv run --package dirt-gateway python -m dirt_gateway.main --once --dry-run` includes schedules in the payload summary without printing secrets.
- Cloud API tests prove `PUT /api/gateway/v1/catalog` persists schedules.
- Hosted browser route `GET /api/tents/{tent_id}/lights/schedules` returns synced schedule rows.
- Cloud migration applies through the supported deploy path, not app-start DDL.

UI acceptance:

- Local dashboard shows the selected tent's light schedule in local time.
- Hosted dashboard shows the selected tent's synced light schedule in local time.
- Main tent displays `09:00-21:00` and `12/12`.
- Clone and breeding light displays show their 18/6 schedule.
- UI handles no schedule, stale sync, and inactive device states without overlapping text or layout shifts.


## Idempotence and Recovery

Migrations must be safe to review and re-run through Atlas' normal tracking. Do not write app-start DDL.

Seed migrations should use deterministic public ids and conflict-safe upserts where possible. If a seed row already exists, update mutable fields such as `name`, `ip`, `metadata`, `provider_uid`, `starts_local`, `ends_local`, and `enabled` instead of inserting duplicates.

Kasa discovery and reconciliation are safe to repeat. Discovery is read-only. Reconciliation may toggle lights to the desired schedule state; before the first live run, verify schedule times so the service does not unexpectedly switch a light during a sensitive period.

If the new lights service misbehaves, recovery options are:

- Stop hardware service: `systemctl --user stop dirt-hwd`.
- Disable one schedule by setting `schedule.enabled=false` for that device.
- Disable one device by setting `device.enabled=false`.
- Temporarily restore the old single-plug service from git if this is still on a feature branch; do not `git reset --hard` over unrelated user changes.

For cloud sync, rollback should follow `docs/hosted-control-plane.md`. Since schedules are read-only hosted data in this plan, rollback is to stop sending schedules or ignore them in the hosted UI. Do not add hosted schedule write commands without a separate plan.


## Artifacts and Notes

Current local schedule query before implementation:

    schedule_id               kind    enabled  timezone        starts_local  ends_local  site_id  tent_id  device_id
    main-lights-photoperiod   lights  true     America/Denver  09:00:00      21:00:00    homebox  main     kasa-lights-main

Current live tents before implementation:

    homebox/main      Main Tent      role=flower    active=true
    homebox/breeding  Breeding Tent  role=breeding  active=true

Current Kasa discovery before implementation:

    lights                192.168.1.181  MAC 6C:4C:BC:45:37:F6  state off
    clone-light           192.168.1.220  MAC 10:5A:95:8B:E8:B7  state on
    breeding-tent-light   192.168.1.180  MAC 10:5A:95:8B:E6:76  state on


## Interfaces and Dependencies

Local database interfaces to add:

- `device.provider_uid_kind: text null`
- `device.provider_uid: text null`
- Unique/index support for stable provider identity.
- Seeded Kasa devices, capabilities, zones/tents as finalized, and schedules.

Local Python interfaces to add or update:

- `dirt_shared.models.Device` fields for provider identity.
- A schedule projection service or methods that list light schedules directly from `schedule` rows.
- `dirt_hwd.services.kasa_inventory` adapter for verified Kasa discovery/connect.
- `dirt_hwd.services.lights.LightsLoopService` DB-backed multi-device reconciliation.
- `dirt_shared.config.LightsConfig` no longer centered on one `kasa_lights_host`.

Local HTTP/API interfaces:

- `GET /api/tents/{tent_id}/lights/schedules`
- Optional `PATCH /api/tents/{tent_id}/lights/schedules/{schedule_id}` if local editing is included.
- Updated `contracts/webapp-v1.yaml` and regenerated Python/TypeScript clients.

Gateway and hosted interfaces:

- Gateway catalog payload includes `schedules`, or a new typed schedule endpoint exists.
- `CloudSchedule` model and cloud migration.
- Hosted `GET /api/tents/{tent_id}/lights/schedules`.
- Hosted web UI consumes the schedule endpoint in `web-ui/src/routes/index.tsx`.

External dependencies:

- Existing `python-kasa` dependency from `apps/hwd/pyproject.toml`.
- Existing Kasa credentials `KASA_USERNAME` and `KASA_PASSWORD`.
- LAN broadcast discovery on `192.168.1.0/24` for recovery from stale IPs.
- Existing gateway and hosted Railway deployment flow; no new cloud provider dependency.


## Revision Notes

- 2026-05-09 / Codex: Initial ExecPlan authored from current repository inspection and LAN Kasa discovery results.
