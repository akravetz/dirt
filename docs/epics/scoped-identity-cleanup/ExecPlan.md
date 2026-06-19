# Scoped identity cleanup

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, Dirt's local scoped data model uses one truthful identity for each Dirt-owned object. The local database already relates sites, tents, zones, schedules, devices, snapshots, commands, plants, and irrigation records through integer primary keys and foreign keys. Several older object tables also carry parallel text `*_id` fields that are not external identifiers: `site.site_id`, `tent.tent_id`, `zone.zone_id`, and `schedule.schedule_id`. Those text fields have become a second identity system used by firmware payloads, service parameters, gateway sync, hosted browser routes, object keys, and tests.

The desired end state is simpler: local Dirt-owned relationships use integer `id` values; user-visible names use `name`; semantic behavior uses explicit fields such as `tent.role` or schedule `kind`; firmware ingest routes by `device_id`; and cloud/browser boundaries use source integer IDs where they need to refer to local rows. This plan intentionally does not decide or change `device.device_id` or `capability.capability_id`; those are more protocol-like and require separate analysis.

The work is complete when the local database no longer has text identity columns for sites, tents, zones, or schedules; firmware ingest no longer requires `site_id`, `tent_id`, or `zone_id`; gateway/cloud/browser contracts no longer expose those fields as object identity; and tests plus generated contracts prove the updated boundaries.


## Progress

- [x] (2026-06-19) Audited the six local string `*_id` candidates against `docs/rules/data-modeling.md`: `site_id`, `tent_id`, `zone_id`, `schedule_id`, `device_id`, and `capability_id`.
- [x] (2026-06-19) Locked the decision to retire `Site.site_id`; Dirt is currently a single-site installation and local relationships already use `site.id`.
- [x] (2026-06-19) Locked the decision to retire `Zone.zone_id`; zones are internal topology and existing relationships already use `zone.id`.
- [x] (2026-06-19) Locked the decision to retire `Tent.tent_id`; use `Tent.id`, `Tent.name`, and explicit semantics such as `Tent.role`.
- [x] (2026-06-19) Locked the decision to update firmware ingest so `device_id` is the routing identity and firmware stops sending `site_id`, `tent_id`, and `zone_id`.
- [x] (2026-06-19) Locked the decision to retire `Schedule.schedule_id`; schedules should be found by their real owner fields and referenced by `Schedule.id`.
- [x] (2026-06-19) Milestone 1: added characterization tests for current ingest, local services, gateway sync, browser contracts, camera capture, daily report, and schedule behavior before migration.
- [x] (2026-06-19) Milestone 2: updated local service APIs to stop accepting or returning `site_id`, `tent_id`, `zone_id`, and `schedule_id` text identities where no boundary requires them.
- [x] (2026-06-19) Milestone 3: updated firmware ingest and HWD ingest to route by `device_id` only, deriving tent and zone from the device row.
- [x] (2026-06-19) Milestone 4: updated gateway/cloud contracts and hosted control-plane projections to use source integer IDs instead of retired text identities.
- [x] (2026-06-19) Milestone 5: updated browser API, generated hosted contracts, and frontend consumers for numeric tent/source identifiers and explicit display fields.
- [x] (2026-06-19) Milestone 6: updated camera-agent, daily report, PTZ/camera capture, asset object key/idempotency construction, and observability payloads.
- [x] (2026-06-19) Milestone 7: created Atlas migrations and code cutover that remove retired text columns and replace cloud/source columns as needed; destructive local migration has not been applied to the live local database pending operator confirmation.
- [x] (2026-06-19) Milestone 8: validated locally, regenerated contracts, updated documentation, and recorded final evidence.


## Surprises & Discoveries

- Observation: The local database has exactly one site.
  Evidence: `SELECT count(*) FROM site;` returned `1`; the row is `id=1, site_id='homebox', name='Homebox', location='Denver, MT', timezone='America/Denver'`.

- Observation: `site_id`, `tent_id`, and `zone_id` text fields are not needed for local relationships.
  Evidence: local dependent tables store integer FKs: `tent.site_id`, `zone.site_id`, `zone.tent_id`, `device.site_id`, `device.tent_id`, `device.zone_id`, `schedule.site_id`, `schedule.tent_id`, `snapshot.site_id`, `snapshot.tent_id`, `snapshot.zone_id`, `command.site_id`, `command.tent_id`, `command.zone_id`, and `plant_location_history.site_id` / `tent_id`.

- Observation: Current tent rows are small and fully Dirt-owned.
  Evidence: live rows are `id=1/main/Main Tent/flower`, `id=2/breeding/Breeding Tent/breeding`, and `id=3/clones/Clone Tent/clone`.

- Observation: Current zone rows are internal topology labels scoped to tents.
  Evidence: live rows include `main/canopy`, `main/reservoir`, `main/plant-a` through `main/plant-d`, `main/lights`, `breeding/canopy`, `breeding/lights`, `breeding/heat`, and `clones/lights`.

- Observation: Current schedules already have integer dependents.
  Evidence: live schedule rows are `main-lights-photoperiod`, `breeding-lights-photoperiod`, `clones-lights-photoperiod`, and `breeding-drip-pump-irrigation`; `irrigation_schedule_item.schedule_id` and `irrigation_run.schedule_id` are bigint FKs to `schedule.id`.

- Observation: Firmware and camera-agent currently use text scope fields as payload/config convenience, not because the database needs them.
  Evidence: firmware ingest payloads include `site_id`, `tent_id`, and `zone_id`; camera-agent config requires `DIRT_SITE_ID` and `DIRT_TENT_ID`; HWD can instead resolve placement from the `Device` row when given `device_id`.


## Decision Log

- Decision: Retire `Site.site_id` entirely.
  Rationale: Dirt is a single-site installation today. Local rows already relate through `site.id`, and a text `homebox` identity is scaffolding from a future multi-site design. If hosted/gateway code needs source partitioning, it should use gateway/installation identity or local source integer IDs, not a second local site identity column.
  Date/Author: 2026-06-19 / Operator and Codex

- Decision: Retire `Zone.zone_id` entirely.
  Rationale: Zones are internal topology. Devices and snapshots already store `zone.id` as an FK. Firmware can route by `device_id`; PTZ and daily report should use camera views/presets instead of treating zone strings as identity.
  Date/Author: 2026-06-19 / Operator and Codex

- Decision: Retire `Tent.tent_id` entirely.
  Rationale: Tents are Dirt-owned objects with integer identity, display names, and semantic roles. Text values such as `main`, `breeding`, and `clones` are operator-readable aliases, not external identities. Local code should use `Tent.id`, display `Tent.name`, and branch on explicit facts such as `Tent.role` or plant lifecycle fields.
  Date/Author: 2026-06-19 / Operator and Codex

- Decision: Firmware ingest should route by `device_id`, not site/tent/zone text scope.
  Rationale: Firmware should only identify the reporting device. Placement is database configuration on the `Device` row. Moving a device to another tent or zone should not require reflashing firmware. HWD ingest should look up `Device` by `device_id`, derive `device.tent_id` and `device.zone_id`, resolve enabled capabilities for the device, update `device.last_seen`, and insert capability-owned `SensorReading` rows.
  Date/Author: 2026-06-19 / Operator and Codex

- Decision: Retire `Schedule.schedule_id` entirely.
  Rationale: Schedule strings such as `main-lights-photoperiod` are readable seed/upsert handles, not domain-owned identifiers. Schedules should be referenced by `Schedule.id`; queried by real owner fields such as `tent_id`, `kind`, `device_id`, and `capability_id`; and displayed through composed labels from kind, tent name, and device name.
  Date/Author: 2026-06-19 / Operator and Codex

- Decision: `Device.device_id` and `Capability.capability_id` are explicitly out of scope.
  Rationale: These values are more complicated and may be real protocol/interface identities. Firmware, sensor contracts, actuator command routing, camera-agent config, vendor/provider metadata, and metric ownership all depend on them. They require separate discussion and a separate ExecPlan or later milestone.
  Date/Author: 2026-06-19 / Operator and Codex


## Outcomes & Retrospective

- Milestone 1 added focused agent-owned characterization tests for HWD ingest scope behavior, local command targeting, gateway catalog scoped boundary fields, hosted browser schedule/assets routes, and camera capture metadata. Existing tests already covered local metric/history/grow-state/light-schedule lookups, breeding command execution, daily report photo scoping, camera-agent upload payloads, and capture-policy responses, so the new tests fill boundary gaps instead of snapshotting broad seed data. Validation passed with `uv run pytest apps/shared/tests apps/hwd/tests apps/gateway/tests apps/control-plane/tests -q` (`640 passed` on 2026-06-19). Frontend checks were not run because no `web-ui/`, generated contract, or frontend files changed.
- Milestone 2 moved local shared services toward integer primary-key scope and explicit default-site/default-tent helpers. Firmware and gateway boundary shapes were preserved through clearly named temporary `*_from_text_scope` adapters so Milestones 3 and 4 can remove those contracts deliberately. Validation passed with `uv run pytest apps/shared/tests apps/hwd/tests apps/gateway/tests apps/control-plane/tests -q` (`640 passed` on 2026-06-19) and `git diff --check`. During verification, parallel app-suite runs collided on PostgreSQL test templates; rerunning sequentially and then rerunning the exact combined command passed cleanly.
- Milestone 3 cut HWD firmware ingest over to required `device_id` payloads with `extra="forbid"` so stale `site_id`, `tent_id`, and `zone_id` fields fail validation. `ReadingsService` now loads enabled devices by `device_id`, derives placement from the `Device` row, updates heartbeat/diagnostics on the enabled device, and inserts only enabled capability-owned readings. Firmware ingest clients and edited firmware call sites no longer emit site/tent/zone fields. Validation passed with focused ingest/readings tests (`52 passed`) and `uv run pytest apps/shared/tests apps/hwd/tests apps/gateway/tests apps/control-plane/tests -q` (`642 passed` on 2026-06-19). `uv run ruff check` on touched Python files and `git diff --check` passed. Firmware build checks for fan, plant, reservoir, and RS485 substrate projects were attempted but stop on missing gitignored `secrets.h` files; `firmware/` itself is not a single PlatformIO project for `pio test -e native`.
- Milestone 4 moved gateway-owned catalog, latest metric, and rollup DTOs to source integer IDs for local row identity (`source_site_id`, `source_tent_id`, `source_zone_id`, `source_schedule_id`). Hosted receivers now upsert by source identity while retaining explicitly named legacy bridge values for browser compatibility until Milestones 5 and 7. Cloud projection models gained additive nullable source-id columns plus the additive cloud migration `cloud/migrations/20260619033538_scoped_identity_source_projection.sql`. Validation passed with focused gateway/contract/control-plane tests after a transient PostgreSQL teardown retry, `uv run pytest apps/shared/tests apps/hwd/tests apps/gateway/tests apps/control-plane/tests -q` (`643 passed` on 2026-06-19), `uv run ruff check` on touched Python files, `git diff --check`, and `atlas migrate hash --dir file://cloud/migrations`. `atlas migrate lint --env cloud --latest 1` could not run because this Atlas install gates `migrate lint` behind Atlas Pro login; `atlas migrate hash --dry-run` is not supported by this installed CLI.
- Milestone 5 moved hosted browser tent routes and frontend route/query keys from string tent aliases to numeric `source_tent_id` / `sourceTentId`, regenerated `contracts/hosted-browser-v1.json` and `web-ui/src/api-client/generated/hosted-schema.ts`, and updated Breeding Logbook browser DTOs to expose `current_tent_id`, `current_tent_name`, and `grid_position` instead of `location_key` / `location_label`. The old substring-based `_stage_for_tent_id()` helper is gone; frontend board/drop behavior now uses one explicit role-to-drop-stage helper so plant lifecycle `stage_key` remains a plant fact. Temporary command/storage compatibility remains explicitly named as legacy tent-id bridging. Validation passed with `scripts/gen-hosted-contract`, `pnpm --dir web-ui typecheck`, `pnpm --dir web-ui lint`, `pnpm --dir web-ui test` (`3 passed`, `12 tests`), focused control-plane tests (`58 passed`), `uv run ruff check` on touched control-plane files, and `git diff --check`. The broad backend command `uv run pytest apps/shared/tests apps/hwd/tests apps/gateway/tests apps/control-plane/tests -q` reported `643 passed` plus the recurring PostgreSQL teardown `InsufficientPrivilegeError`; rerunning the affected test `apps/shared/tests/test_grow_state.py::test_lights_off_before_schedule` passed in isolation.
- Milestone 6 moved camera-agent startup/config to camera device identity (`DIRT_CAMERA_DEVICE_ID`) instead of `DIRT_SITE_ID` / `DIRT_TENT_ID`; hosted capture policy now enriches uploads with source placement derived from synced camera rows. Daily report sensor/photo configuration now uses source tent IDs, daily photos record camera `view_id` rather than preset-to-zone text mappings, and hosted extra photos fetch `/api/tents/{source_tent_id}/assets/latest`. New camera asset object keys and idempotency keys are camera-device/source keyed instead of text site/tent paths; cloud completion can still derive legacy storage placement from source tent or device identity while historical object keys remain opaque. Camera/daily observability docs now describe device/source placement fields. Validation passed with focused camera-agent/shared/control-plane tests (`120 passed`), `uv run ruff check` on touched Python files, and `git diff --check`. The broader backend command including camera-agent tests reported `651 passed` plus the recurring PostgreSQL teardown `InsufficientPrivilegeError`; rerunning the affected HWD ingest test passed in isolation.
- Milestone 7 removed the retired local SQLModel text identity fields from `Site`, `Tent`, `Zone`, and `Schedule`, and cut local services/tests over to integer source IDs, default-scope helpers, names, and roles. The local migration `migrations/20260619045533_scoped_identity_cleanup.sql` drops the old uniqueness constraints and planned columns `site.site_id`, `tent.tent_id`, `zone.zone_id`, and `schedule.schedule_id` with narrow `-- atlas:nolint DS103` annotations. The cloud migration `cloud/migrations/20260619045602_scoped_identity_command_source_tent.sql` adds nullable `cloud_command.source_tent_id` so command bridge payloads can carry source tent identity; remaining cloud string fields are explicitly temporary wire/storage bridges while source IDs are canonical local identity. No live/local `atlas migrate apply` was run because the destructive migration requires operator confirmation; pytest applied migrations only to ephemeral test databases. Validation passed with `uv run pytest apps/shared/tests apps/hwd/tests apps/gateway/tests apps/control-plane/tests apps/camera-agent/tests -q` (`651 passed`), `uv run ruff check` on touched Python files, `git diff --check`, `atlas migrate hash --dir file://migrations`, `atlas migrate hash --dir file://cloud/migrations`, and `atlas migrate diff --env cloud --format '{{ sql . "  " }}'` reporting the cloud migration directory synced. Local `atlas migrate diff scoped_identity_cleanup --env local` remains blocked by the existing desired-schema `btree_gist`/GIST bigint operator-class issue; Atlas local lint remains blocked by v0.38 Pro login gating.
- Milestone 8 completed the final documentation and validation pass. Documentation now describes the post-cleanup source model in `docs/database.md`, updates camera-agent/daily-report operational guidance in `docs/commands.md`, updates camera/capture observability scope fields in `docs/observability.md`, and removes stale site/tent/zone payload examples from the affected firmware/wiki docs and related ExecPlans. Hosted contracts were regenerated with `scripts/gen-hosted-contract`. Final validation on 2026-06-19 passed `scripts/gen-hosted-contract`, `pnpm --dir web-ui typecheck`, `pnpm --dir web-ui lint`, `pnpm --dir web-ui test` (`3 files`, `12 tests`), `uv run pytest apps/tests/invariants -q` (`41 passed`), `uv run ruff check` on touched Python files, `git diff --check`, `atlas migrate hash --dir file://migrations`, `atlas migrate hash --dir file://cloud/migrations`, and `atlas migrate diff --env cloud --format '{{ sql . "  " }}'` reporting the cloud migration directory synced. The broad backend suite `uv run pytest apps/shared/tests apps/hwd/tests apps/gateway/tests apps/control-plane/tests apps/camera-agent/tests -q` reached `651 passed` and then hit the recurring PostgreSQL teardown `InsufficientPrivilegeError`; rerunning the affected test `apps/hwd/tests/test_ingest_api.py::test_ingest_updates_device_on_second_post -q` passed. `atlas migrate lint --env local --latest 1` and `atlas migrate lint --env cloud --latest 1` remain blocked by Atlas v0.38 Pro login gating; local `atlas migrate diff scoped_identity_cleanup --env local` remains blocked by the existing `btree_gist`/GIST bigint operator-class replay issue. Firmware builds for `fan`, `reservoir`, `plant-a`, and `plant-a-substrate` all stop on missing ignored `secrets.h` headers, which matches the expected local secret-file requirement.


## Context and Orientation

The local SQLModel tables live under `apps/shared/src/dirt_shared/models/`. The relevant post-cleanup models are:

- `apps/shared/src/dirt_shared/models/site.py`: `Site.id` plus display/config fields.
- `apps/shared/src/dirt_shared/models/tent.py`: `Tent.id`, `Tent.site_id`, `Tent.name`, `Tent.role`, default/active flags.
- `apps/shared/src/dirt_shared/models/zone.py`: `Zone.id`, `Zone.site_id`, `Zone.tent_id`, `Zone.name`, `Zone.zone_type`.
- `apps/shared/src/dirt_shared/models/schedule.py`: `Schedule.id`, integer owner FKs, `kind`, and local timing fields.
- `apps/shared/src/dirt_shared/models/device.py`: `Device.device_id` and `Capability.capability_id`, which are out of scope for this plan.

The hosted control-plane cloud projection lives in `apps/control-plane/src/dirt_control/models/cloud.py`. It now uses cloud-local IDs plus source integer ID columns where a local row identity is needed; remaining text fields are explicitly named legacy wire/storage bridges or display labels.

The gateway contract lives in `apps/shared/src/dirt_shared/cloud_contract.py`. The local gateway collector is `apps/gateway/src/dirt_gateway/local.py`; the hosted gateway receiver is `apps/control-plane/src/dirt_control/api/gateway.py`.

Firmware ingest goes through `apps/hwd/src/dirt_hwd/api/ingest.py` into `apps/shared/src/dirt_shared/services/readings.py`. Firmware sources include `firmware/fan_controller/`, `firmware/reservoir_node/`, `firmware/plant_node/`, and `firmware/rs485_substrate_node/`.

Hosted browser routes currently live in `apps/control-plane/src/dirt_control/api/browser.py`; a separate ExecPlan under `docs/epics/control-plane-browser-api-refactor/ExecPlan.md` will split that module. This identity cleanup should be coordinated with that work but is intentionally its own plan.


## Plan of Work

Milestone 1 establishes safety. Add focused characterization tests for the behaviors that currently rely on retired strings: HWD ingest with firmware payloads, current metric/history queries, grow state and light schedule lookups, command targeting, gateway catalog projection, hosted browser tent routes, breeding command enqueue/claim execution, camera-agent capture metadata, daily report photo scoping, and schedule/capture-policy response fields. Avoid tests that merely pin current seed values. Each test should protect a behavior or boundary that will still exist after the cleanup.

Milestone 2 updates local service APIs. Introduce small helpers that resolve the single default site by `Site.is_default` or fail clearly if none exists. Replace `site_id` and `tent_id` parameters in local internal services with integer IDs, default-site/default-tent helpers, or direct device/tent objects as appropriate. Remove string `zone_id` filters in favor of device placement or `zone.id` for internal callers. Keep changes scoped and do not touch `device_id` or `capability_id` semantics.

Milestone 3 updates firmware ingest. Change `IngestPayload` so `device_id` is required and `site_id`, `tent_id`, and `zone_id` are no longer accepted for new firmware payloads. In `ReadingsService`, look up the enabled `Device` by `device_id`, derive placement from `device.tent_id` and `device.zone_id`, resolve enabled `Capability` rows under that device, update diagnostics/last-seen, and insert readings. Update firmware payload builders to remove site/tent/zone fields. If any deployed board lacks `device_id`, document a short-lived fallback and remove it before this plan is complete.

Milestone 4 updates gateway and cloud contracts. Replace text site/tent/zone/schedule identity in catalog and metric projection DTOs with source integer IDs where row identity is needed, for example `source_tent_id`, `source_zone_id`, and `source_schedule_id`. Keep display names and semantic fields explicit. Hosted cloud tables should use cloud-local integer PKs and source integer identity columns for upserts. Do not introduce handwritten frontend types; regenerate generated contracts after FastAPI DTO changes.

Milestone 5 updates hosted browser and frontend contracts. Replace `/api/tents/{tent_id}/...` string-keyed behavior with numeric tent/source identity or a cleaner browser route shape chosen during implementation. Breeding Logbook rows and bootstrap should expose explicit tent fields such as `current_tent_id`, `current_tent_name`, and `grid_position`; they must not expose `location_key` / `location_label` as a disguised tent identity. Remove substring inference such as `_stage_for_tent_id()`. Plant lifecycle `stage_key` remains a plant fact, not a tent identity.

Milestone 6 updates camera, reports, assets, and observability. Camera-agent should not require `DIRT_SITE_ID` or `DIRT_TENT_ID`; it should identify the camera device and let the API derive placement. Daily report config should stop using tent text IDs and should instead use explicit source IDs, default tent selection, or named report sections based on the final service shape. PTZ and daily report should model camera views/presets directly instead of mapping view names through zone text identities. New asset object keys should not depend on retired text IDs; historical object keys can remain opaque.

Milestone 7 performs database migrations. Edit SQLModel models first, then generate Atlas migrations. Migrations should remove local `site.site_id`, `tent.tent_id`, `zone.zone_id`, and `schedule.schedule_id` after all code no longer needs them. They should also migrate cloud tables from text identities to source integer IDs if that is part of the implemented boundary shape. Review generated SQL carefully, especially uniqueness constraints and not-null changes.

Milestone 8 validates, documents, and records evidence. Update `docs/database.md`, any affected hosted/gateway docs, firmware notes, and the original browser API refactor ExecPlan if its assumptions change. Regenerate hosted contracts and frontend generated types. Run the full relevant backend, invariant, firmware, and frontend checks.


## Concrete Steps

Start every implementation session by reading required docs:

    cd /home/akcom/code/dirt
    sed -n '1,220p' docs/commands.md
    sed -n '1,260p' docs/rules/data-modeling.md
    sed -n '1,240p' docs/rules/simple-clean-architecture.md
    sed -n '1,260p' docs/rules/boundary-contracts.md
    sed -n '1,260p' docs/database.md
    sed -n '1,220p' docs/references/atlas/INDEX.md

If touching `web-ui/`, also read:

    sed -n '1,220p' docs/rules/frontend-server-state.md
    sed -n '1,220p' docs/references/tanstack-query-v5/INDEX.md
    sed -n '1,220p' docs/references/modern-idiomatic-typescript/INDEX.md

Inventory the current model and live data:

    rg -n "site_id|tent_id|zone_id|schedule_id" apps/shared/src/dirt_shared/models apps/control-plane/src/dirt_control/models
    set -a; source .env; set +a
    PGPASSWORD="$DIRT_PG_PASSWORD" psql -h 127.0.0.1 -U "$DIRT_PG_USER" -d "$DIRT_PG_DATABASE" -P pager=off \
      -c "SELECT id, site_id, name, location, timezone, is_default FROM site ORDER BY id;" \
      -c "SELECT id, tent_id, name, role, is_default, active FROM tent ORDER BY id;" \
      -c "SELECT z.id, z.zone_id, z.name, z.zone_type, z.tent_id FROM zone z ORDER BY z.id;" \
      -c "SELECT id, schedule_id, kind, tent_id, device_id, capability_id, starts_local, ends_local FROM schedule ORDER BY id;"

Run focused validation before edits:

    uv run pytest apps/shared/tests apps/hwd/tests apps/gateway/tests apps/control-plane/tests -q
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui test

Generate migrations only after SQLModel edits:

    atlas migrate diff scoped_identity_cleanup --env local

Regenerate hosted browser contracts after FastAPI DTO changes:

    scripts/gen-hosted-contract

Before committing:

    make fix
    git status --short
    git diff --check


## Validation and Acceptance

Acceptance requires all of the following:

- Local schema no longer contains `site.site_id`, `tent.tent_id`, `zone.zone_id`, or `schedule.schedule_id`.
- Local relationships still use integer FKs to `site.id`, `tent.id`, `zone.id`, and `schedule.id`.
- Firmware ingest accepts payloads with required `device_id` and no `site_id`, `tent_id`, or `zone_id`.
- HWD ingest still updates device freshness and writes capability-owned readings for fan controller, reservoir, and RS485 substrate devices.
- Gateway sync succeeds using source integer IDs or the chosen explicit boundary shape, with no retired text identity fields in owned DTOs.
- Hosted browser contracts and frontend code no longer expose retired fields as object identity.
- Breeding Logbook groups plants by explicit current tent identity/name and keeps lifecycle stage separate from tent identity.
- Camera-agent and daily report flows still capture/upload/render scoped photos without text tent/zone identity.
- `uv run pytest apps/shared/tests apps/hwd/tests apps/gateway/tests apps/control-plane/tests -q` passes.
- `uv run pytest apps/tests/invariants -q` passes unless an invariant milestone has explicit human approval for rule updates.
- `scripts/gen-hosted-contract` completes and generated diffs are intentional.
- `pnpm --dir web-ui typecheck`, `pnpm --dir web-ui lint`, and `pnpm --dir web-ui test` pass after frontend changes.
- Firmware builds/tests relevant to edited firmware pass, for example `cd firmware && pio test -e native` and targeted `pio run` environments.


## Idempotence and Recovery

Source-only refactors are safe to repeat. Use focused tests and `git diff` to find the last passing boundary if the migration becomes confusing. Do not use `git reset --hard` unless explicitly requested.

Atlas migrations are not casual edits. If a generated migration is wrong, fix the SQLModel source and regenerate before applying. If a migration has already been applied locally, follow `docs/database.md` rollback guidance and use a backup or new forward migration; do not hand-edit applied migration history.

Contract generation is safe to repeat with `scripts/gen-hosted-contract`. Never patch `web-ui/src/api-client/generated/hosted-schema.ts` by hand.

Historical asset object keys may contain old text IDs. Treat them as opaque historical values unless a migration explicitly rewrites both metadata and stored objects. New code should not parse or derive identity from old object-key path segments.


## Artifacts and Notes

Pre-cleanup live local samples from 2026-06-19:

    site:
      id=1, site_id=homebox, name=Homebox, location="Denver, MT", timezone=America/Denver, is_default=true

    tents:
      id=1, tent_id=main, name="Main Tent", role=flower, devices=14, zones=9, current_plants=4
      id=2, tent_id=breeding, name="Breeding Tent", role=breeding, devices=5, zones=3, current_plants=1
      id=3, tent_id=clones, name="Clone Tent", role=clone, devices=1, zones=1, current_plants=0

    zones:
      main/canopy, main/reservoir, main/plant-a, main/plant-b, main/plant-c, main/plant-d, main/exhaust, main/lights, main/heat
      breeding/canopy, breeding/lights, breeding/heat
      clones/lights

    schedules:
      id=1, schedule_id=main-lights-photoperiod, kind=lights, tent=Main Tent, device=kasa-lights-main
      id=3, schedule_id=breeding-lights-photoperiod, kind=lights, tent=Breeding Tent, device=kasa-lights-breeding
      id=4, schedule_id=clones-lights-photoperiod, kind=lights, tent=Clone Tent, device=kasa-lights-clones
      id=11, schedule_id=breeding-drip-pump-irrigation, kind=irrigation, tent=Breeding Tent, device=shelly-breeding-drip-pump

Out-of-scope candidates for a later discussion:

    Device.device_id
    Capability.capability_id


## Interfaces and Dependencies

At the end of this plan, these interfaces should exist or be true:

- Local `Site` table has one canonical identity: `id`.
- Local `Tent` table has `id`, display `name`, semantic `role`, active/default fields, and no text `tent_id`.
- Local `Zone` table has `id`, display `name`, `zone_type`, FKs, and no text `zone_id`.
- Local `Schedule` table has `id`, owner FKs, `kind`, local timing fields, timezone/enabled fields, and no text `schedule_id`.
- HWD ingest request payloads require `device_id` and omit site/tent/zone text identity.
- Gateway/catalog DTOs use source integer IDs or explicit non-identity display fields for sites/tents/zones/schedules.
- Hosted/browser DTOs do not expose retired text fields as object identity.
- Camera capture metadata and daily report workflows do not require text tent/zone identity.
- `Device.device_id` and `Capability.capability_id` remain unchanged by this plan.

No new framework dependencies are expected.


## Revision Notes

- 2026-06-19: Initial ExecPlan created from operator/Codex data-modeling discussion. Locked decisions: retire text identities for site, tent, zone, and schedule; update firmware ingest to route by device; keep device and capability text IDs out of scope.
- 2026-06-19: Follow-up: add a first-class local Atlas diff helper, for example `scripts/atlas-local-diff`, that starts or reuses a disposable PostgreSQL 17 dev database, preinstalls `btree_gist`, and runs `atlas migrate diff <name> --env local --dev-url ...`. This should replace the ad hoc workaround needed because Atlas's default `docker://postgres/17/dev` desired-schema replay lacks the GiST operator classes required by `plant_location_history` exclusion constraints, while Atlas's cleaner extension bootstrap paths are gated by the installed CLI's login/Pro behavior.
