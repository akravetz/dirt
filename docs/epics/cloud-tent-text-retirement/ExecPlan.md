# Cloud scoped text bridge retirement

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, the hosted cloud path will no longer carry the old source-owned text scope identities through storage, gateway payloads, browser responses, generated contracts, or service logic. The local scoped identity cleanup already made local `Tent.id`, `Zone.id`, and `Schedule.id` the source row identities and exposed those values to the hosted control plane as `source_tent_id`, `source_zone_id`, and `source_schedule_id`. The remaining cloud text fields named `tent_id`, `zone_id`, and `schedule_id` are compatibility bridges from the older hosted schema. They duplicate source IDs, appear in several cloud projection tables, and force browser services and gateway contracts to keep translating between integer source identity and old strings such as `"main"`, `"canopy"`, or `"main-lights-photoperiod"`.

The user-visible goal is not a new screen. The goal is operational: future hosted control-plane work should read and write source identities without hidden fallback maps, legacy response fields, or storage columns that can drift from the source identity. A human can observe success by running the test suites, regenerating the hosted contract, inspecting generated OpenAPI/TypeScript schemas, and confirming that no active cloud/gateway/browser code refers to legacy text `tent_id`, `zone_id`, or `schedule_id` fields except historical migrations and deliberately out-of-scope local integer foreign keys with those names.

This plan deliberately does not retire cloud `site_id`. Hosted gateway auth, credentials, configuration, audit filtering, browser site responses, and idempotency keys still use `site_id` as the hosted site/tenant scope. Retiring that field would be a separate auth and tenancy migration.

This plan also retires the command-contract artifact that made every command look tent-targeted. Command queue fields should describe lifecycle and ownership: who requested the command, where it is queued, when it expires, and what status it has. The actual work belongs in the typed payload. A separate optional command target belongs only on hardware-addressed commands such as PTZ camera movement. Breeding commands should not invent a tent target. Breeding payloads keep `source_tent_id` only when the action itself places or moves plants into a tent.

This rollout must be deployable in isolated pieces. Dirt has a local gateway process and a hosted control-plane process that are not always deployed at the exact same moment. `apps/shared/src/dirt_shared/cloud_contract.py` uses `extra="forbid"` for owned protocols, so simply deleting a field from a contract will break any old producer that still sends it. The safe path is an expand/tolerate/cut-over/contract sequence: add source storage first, make legacy fields optional and deprecated, change consumers to ignore them, stop producers from sending them, wait for stale payloads to drain, then delete the fields and drop database columns last.


## Progress

- [x] (2026-06-19) Created this ExecPlan after auditing legacy cloud text tent references and reviewing `.agents/PLANS.md`, `docs/rules/simple-clean-architecture.md`, `docs/rules/boundary-contracts.md`, `docs/rules/data-modeling.md`, `docs/database.md`, and current gateway/browser/control-plane code.
- [x] (2026-06-19) Broadened scope to include legacy text `zone_id` and `schedule_id`, explicitly left hosted cloud `site_id` out of scope, and added the `metric_freshness` stale scope-name cleanup.
- [x] (2026-06-19) Locked command-contract direction: keep one command queue, remove required tent targeting, add an optional hardware target for PTZ-style commands, and keep breeding tent references only inside breeding payloads that actually need them.
- [x] (2026-06-20) Refreshed plan references after the browser UI refactor audit: added the `/live` PTZ command and breeding pending-command UI touchpoints, included `apps/hwd/src` in the inventory grep, and refreshed current artifact line references.
- [x] (2026-06-20) Milestone 1: add compatibility characterization tests and migration inventory queries for every legacy scoped text path.
- [x] (2026-06-20) Milestone 2: expand cloud storage so every table that currently needs text `tent_id`, `zone_id`, or `schedule_id` also has enough source identity to read without it, especially `cloud_asset`.
- [x] (2026-06-20) Milestone 3: make gateway/shared/browser contracts tolerant by marking legacy text fields optional and deprecated while keeping `extra="forbid"`.
- [x] (2026-06-20) Milestone 4: change consumers and storage reads to use source identity only, while producers still write both source and legacy storage fields.
- [ ] Milestone 5: stop gateway/control-plane producers from emitting legacy scoped text fields after tolerant consumers are deployed.
- [ ] Milestone 6: remove legacy scoped text fields from Pydantic contracts and generated browser contracts after old payloads have drained.
- [ ] Milestone 7: drop legacy cloud scoped text storage columns, indexes, constraints, helper functions, and tests that only protect the bridge.
- [ ] Milestone 8: run final validation, update docs, and record deployment evidence.


## Surprises & Discoveries

- Observation: The old text scope fields are not only a command bridge.
  Evidence: `apps/control-plane/src/dirt_control/models/cloud.py` still defines text `tent_id` on `CloudTent`, `CloudZone`, `CloudDevice`, `CloudCapability`, `CloudSchedule`, `CloudPlantLocation`, `CloudLatestMetric`, `CloudMetricRollup`, `CloudAsset`, and `CloudCommand`.

- Observation: Legacy zone and schedule fields are active contract/storage bridges.
  Evidence: `apps/shared/src/dirt_shared/cloud_contract.py` still defines `CatalogZone.legacy_zone_id`, `CatalogSchedule.legacy_schedule_id`, and `AssetCompleteRequest.zone_id`; `apps/control-plane/src/dirt_control/models/cloud.py` still defines text `zone_id` on `CloudZone`, `CloudDevice`, `CloudSchedule`, `CloudLatestMetric`, and `CloudAsset`, plus text `schedule_id` on `CloudSchedule`.

- Observation: The browser app is already mostly clean.
  Evidence: handwritten code under `web-ui/src/` uses hosted `/api/tents/{source_tent_id}/...` paths and source tent IDs. Remaining browser-visible legacy text references are generated types and one test fixture using `legacy_target_tent_id`.

- Observation: The refactored browser UI has two handwritten command-contract areas that must move with the generated command schemas.
  Evidence: `web-ui/src/routes/live.tsx` builds PTZ `CommandCreateRequest` values with flat `source_tent_id`, `device_id`, and `capability_id`; `web-ui/src/features/breeding-logbook/breedingLogbookMutations.ts` stores generated `CommandResponse` values for pending command convergence; `web-ui/src/features/breeding-logbook/breedingLogbookQueries.test.ts` contains the only handwritten `legacy_target_tent_id` fixture.

- Observation: `CloudAsset` is the main storage gap.
  Evidence: `AssetSignUploadRequest` and `AssetCompleteRequest` already include `source_tent_id`, and `AssetCompleteRequest` includes `source_zone_id`, but `CloudAsset` stores text `tent_id` and `zone_id` and does not yet store source scope IDs. Browser asset lookup still joins through `CloudTent.tent_id`.

- Observation: `CloudContractModel` makes field deletion intentionally strict.
  Evidence: `apps/shared/src/dirt_shared/cloud_contract.py` defines `model_config = ConfigDict(extra="forbid")`. Once a field is deleted from a DTO, payloads that still contain that field fail validation instead of being ignored.

- Observation: Command execution likely does not need the legacy field anymore.
  Evidence: `apps/gateway/src/dirt_gateway/commands.py` derives local command scope from `item.source_tent_id` for PTZ commands and from typed breeding command payloads for breeding commands; it does not need `item.tent_id` to execute.

- Observation: The fake `breeding-logbook` tent is a symptom of the old command contract, not a domain concept.
  Evidence: `apps/control-plane/src/dirt_control/services/browser_commands.py` defines `BREEDING_SITE_WIDE_TENT_ID = "breeding-logbook"` because `CloudCommand.tent_id` and `ClaimedCommand.tent_id` are required. Site-wide breeding commands such as seed lot creation, bulk sex, bulk cull, and plant notes enqueue with that fake value even though the gateway ignores tent scope for those actions.

- Observation: `site_id` is still a hosted site/tenant scope, not just a legacy local text identity.
  Evidence: `DIRT_CLOUD_SITE_ID`, gateway credentials, `GatewayPrincipal.allowed_site_id`, browser site responses, audit filters, and cloud idempotency keys still use cloud `site_id`.

- Observation: One local observability path still uses stale scope naming.
  Evidence: `apps/shared/src/dirt_shared/services/readings.py` emits `source_tent_id` in capability freshness scope metadata, while `apps/hwd/src/dirt_hwd/services/metric_freshness.py` still reads and logs `tent_id`.

- Observation: The Milestone 1 characterization tests required the first slice of DTO tolerance to be executable.
  Evidence: `CatalogTent`, `CatalogZone`, `CatalogSchedule`, `CapturePolicyResponse`, and `ClaimedCommand` now accept missing legacy bridge fields while `CloudContractModel` still uses `extra="forbid"`; no producers, consumers, storage models, or generated browser contracts were cut over in this milestone.

- Observation: New cloud asset rows also needed source scope writes, not just source columns and backfills.
  Evidence: Milestone 2 updates `/api/gateway/v1/assets/complete` to persist `CloudAsset.source_tent_id` and `CloudAsset.source_zone_id` from `AssetCompleteRequest` while retaining legacy `tent_id` and `zone_id` writes.

- Observation: Pydantic runtime deprecation warnings are too noisy for compatibility reads.
  Evidence: Milestone 3 uses `json_schema_extra={"deprecated": True}` for transition fields so OpenAPI and generated TypeScript communicate deprecation without emitting `DeprecationWarning` when old compatibility fields are read.

- Observation: Active consumers can use source identity while legacy fields remain in compatibility responses and storage writes.
  Evidence: Milestone 4 switches browser asset reads, device-liveness audit joins, gateway command execution scope, and metric freshness observability to source identity; legacy command `tent_id` and breeding-logbook storage strings remain only as compatibility production for Milestone 5.


## Decision Log

- Decision: Use an expand/tolerate/cut-over/contract rollout instead of deleting fields in one change.
  Rationale: This matches the direction of common API and database migration guidance. Google AIP-180 treats removing or renaming existing fields as backward-incompatible. Prisma's expand/contract description recommends adding the new structure, migrating data, switching clients, and only then removing the old structure. PostgreSQL supports staged validation patterns such as `CHECK (...) NOT VALID` followed by `VALIDATE CONSTRAINT`, which are useful when tightening existing tables.
  Date/Author: 2026-06-19 / Codex

- Decision: Keep `extra="forbid"` on Dirt-owned contracts during the transition.
  Rationale: `extra="forbid"` catches stale and misspelled owned-protocol fields. The transition should keep old field names explicitly in the DTOs while they are tolerated, not relax the whole contract to ignore arbitrary fields.
  Date/Author: 2026-06-19 / Codex

- Decision: Make legacy fields optional and deprecated before stopping producers.
  Rationale: Optional/deprecated fields let new consumers accept both old and new payloads. Deleting a field before producers stop sending it would break validation. Marking the field deprecated also makes the transitional state visible in generated OpenAPI and TypeScript output where FastAPI/Pydantic emits the JSON Schema annotation.
  Date/Author: 2026-06-19 / Codex

- Decision: Separate producer direction from consumer direction in the deploy plan.
  Rationale: Some payloads are gateway-to-control-plane requests, while command claim and capture policy payloads are control-plane-to-gateway responses. For gateway request fields, the hosted control plane must tolerate missing legacy fields before the gateway stops sending them. For hosted response fields, the local gateway must tolerate missing legacy fields before the control plane stops sending them.
  Date/Author: 2026-06-19 / Codex

- Decision: Retire legacy text `zone_id` and `schedule_id` bridges in this plan along with legacy text `tent_id`.
  Rationale: The local scoped identity cleanup retired `Zone.zone_id` and `Schedule.schedule_id` for the same reason it retired `Tent.tent_id`: these values are source-owned parallel identities. Keeping them after `tent_id` is gone would leave the same drift risk and bridge code under different names.
  Date/Author: 2026-06-19 / Codex

- Decision: Do not retire hosted cloud `site_id` in this plan.
  Rationale: Cloud `site_id` currently scopes gateway credentials, auth checks, configuration, audit filters, idempotency keys, and browser site responses. Removing it is not just a projection cleanup; it is an auth and tenancy migration. Keep `source_site_id` for source identity while leaving cloud `site_id` as the hosted scope for this plan.
  Date/Author: 2026-06-19 / Codex

- Decision: Historical migrations are not part of the active-code grep target.
  Rationale: old migration files document how existing databases reached their current state. The acceptance check should allow `cloud/migrations/*.sql` to mention old columns while active source, current generated contracts, and new migrations no longer use legacy source-owned text scope fields.
  Date/Author: 2026-06-19 / Codex

- Decision: Keep one command queue, but separate command lifecycle, optional hardware target, and typed action payload.
  Rationale: The queue lifecycle is generic, but target shape is not. PTZ commands address a physical camera capability, so they should carry an explicit target. Breeding commands are domain actions; some payloads place or move plants into a tent, while others operate on seed lots or plant keys and have no tent target. Requiring top-level `tent_id` made non-tent commands invent `breeding-logbook` and made the contract look camera-specific. The final contract should remove required top-level tent scope, remove `legacy_target_tent_id`, and represent PTZ targeting as an optional target object while breeding keeps real domain identifiers inside typed payloads.
  Date/Author: 2026-06-19 / Codex

- Decision: Split the Milestone 2 cloud migration into transactional add/backfill SQL and a separate non-transactional concurrent-index migration.
  Rationale: Atlas generated concurrent indexes with `-- atlas:txmode none`. Keeping long backfills in that same file would make partial failure recovery worse. The source-column add/backfill migration can stay transactional, while only the concurrent indexes need non-transactional execution.
  Date/Author: 2026-06-20 / Codex


## Outcomes & Retrospective

- Milestone 1 added shared DTO compatibility tests for legacy scoped text fields and transitional command target shapes, plus non-destructive SQL inventory queries in `docs/epics/cloud-tent-text-retirement/milestone-1-inventory.sql`. Validation passed: `uv run pytest apps/shared/tests/test_cloud_contract.py apps/shared/tests/test_cloud_assets.py apps/shared/tests/test_camera_publisher.py -q` (`34 passed`), `uv run pytest apps/gateway/tests/test_sync.py -q` (`38 passed`), `uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q` (`59 passed`), `uv run ruff check apps/shared/src/dirt_shared apps/gateway/src/dirt_gateway apps/control-plane/src/dirt_control apps/shared/tests apps/gateway/tests apps/control-plane/tests`, and `git diff --check`.
- Milestone 2 added `CloudAsset.source_tent_id` and `CloudAsset.source_zone_id`, backfilled source scope for cloud projection tables that already had source columns, added source-scope indexes for later read cutover, and updated asset completion storage to write both source and legacy scope. Validation passed: `uv run atlas migrate hash --dir file://cloud/migrations`, `uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q` (`61 passed`), `uv run pytest apps/shared/tests/test_cloud_contract.py apps/shared/tests/test_cloud_assets.py apps/shared/tests/test_camera_publisher.py -q` (`34 passed`), `uv run pytest apps/gateway/tests/test_sync.py -q` (`38 passed`), `uv run ruff check apps/shared/src/dirt_shared apps/gateway/src/dirt_gateway apps/control-plane/src/dirt_control apps/shared/tests apps/gateway/tests apps/control-plane/tests`, and `git diff --check`.
- Milestone 3 made shared cloud contracts and browser command schemas tolerate old flat PTZ command shapes and new `target`-shaped PTZ commands while keeping `CloudContractModel.extra="forbid"`. Hosted browser OpenAPI and TypeScript contracts were regenerated with optional/deprecated transition fields. Validation passed: `scripts/gen-hosted-contract`, `uv run pytest apps/shared/tests/test_cloud_contract.py apps/shared/tests/test_cloud_assets.py apps/shared/tests/test_camera_publisher.py -q` (`35 passed`), `uv run pytest apps/gateway/tests/test_sync.py -q` (`38 passed`), `uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q` (`63 passed`), `uv run ruff check apps/shared/src/dirt_shared apps/gateway/src/dirt_gateway apps/control-plane/src/dirt_control apps/shared/tests apps/gateway/tests apps/control-plane/tests`, `pnpm --dir web-ui typecheck`, `pnpm --dir web-ui lint`, `pnpm --dir web-ui test` (`3 files, 12 tests passed`), and `git diff --check`.
- Milestone 4 changed active source/hosted consumers to use source identity for reads and execution decisions while producers still write compatibility fields. Browser latest assets now query `CloudAsset.source_tent_id`; device-liveness audit joins metrics to devices by `source_tent_id` and logs `source_tent_id`; gateway command execution uses PTZ `target` with flat-field compatibility and uses breeding `source_tent_id` only from typed payloads; metric freshness reads and logs `source_tent_id`. Validation passed: `uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q` (`63 passed`), `uv run pytest apps/gateway/tests/test_sync.py -q` (`39 passed`), `cd apps/hwd && uv run pytest -q` (`325 passed`), `uv run pytest apps/shared/tests/test_cloud_contract.py apps/shared/tests/test_cloud_assets.py apps/shared/tests/test_camera_publisher.py -q` (`35 passed`), `uv run ruff check apps/shared/src/dirt_shared apps/gateway/src/dirt_gateway apps/control-plane/src/dirt_control apps/hwd/src/dirt_hwd apps/shared/tests apps/gateway/tests apps/control-plane/tests apps/hwd/tests`, and `git diff --check`.


## Context and Orientation

The local scoped identity cleanup is recorded in `docs/epics/scoped-identity-cleanup/ExecPlan.md`. It retired local text identities such as `tent.tent_id`, `zone.zone_id`, and `schedule.schedule_id`, and moved gateway/cloud/browser boundaries to source integer IDs. The source identities in the hosted cloud are `source_tent_id`, `source_zone_id`, and `source_schedule_id`; they are the integer primary keys of local source rows as reported by the gateway.

The hosted control-plane storage model is in `apps/control-plane/src/dirt_control/models/cloud.py`. The relevant current tables are:

- `CloudTent`: has `source_tent_id` and legacy text `tent_id`.
- `CloudZone`: has `source_tent_id`, `source_zone_id`, and legacy text `tent_id` / `zone_id`.
- `CloudDevice`: has `source_tent_id`, `source_zone_id`, and legacy text `tent_id` / `zone_id`.
- `CloudCapability`: has `source_tent_id` and legacy text `tent_id`.
- `CloudSchedule`: has `source_tent_id`, `source_zone_id`, `source_schedule_id`, and legacy text `tent_id` / `zone_id` / `schedule_id`.
- `CloudPlantLocation`: has `source_tent_id` and legacy text `tent_id`.
- `CloudLatestMetric`: has `source_tent_id`, `source_zone_id`, and legacy text `tent_id` / `zone_id`.
- `CloudMetricRollup`: has `source_tent_id` and legacy text `tent_id`.
- `CloudAsset`: has legacy text `tent_id` / `zone_id` and needs source identity added.
- `CloudCommand`: has `source_tent_id` and legacy text `tent_id`.

`CloudSite.site_id` remains in scope as the hosted site/tenant string for this plan. `source_site_id` may continue to be stored and projected as source identity, but replacing cloud `site_id` is deferred.

The shared gateway protocol is in `apps/shared/src/dirt_shared/cloud_contract.py`. Current legacy scoped text fields include:

- `CatalogTent.legacy_tent_id`, a gateway-to-control-plane catalog request field.
- `CatalogZone.legacy_zone_id`, a gateway-to-control-plane catalog request field.
- `CatalogSchedule.legacy_schedule_id`, a gateway-to-control-plane catalog request field.
- `AssetSignUploadRequest.tent_id`, `AssetCompleteRequest.tent_id`, `AssetCompleteRequest.zone_id`, and `AssetFailureRequest.tent_id`, gateway-to-control-plane asset request fields.
- `CapturePolicyResponse.tent_id`, a control-plane-to-gateway response field.
- `ClaimedCommand.tent_id`, inherited by `CommandResultResponse`, a control-plane-to-gateway command response field.

The command contract should be read as lifecycle plus action, not as "a tent command". The current shape forces every claimed command to carry a text tent:

    class ClaimedCommand(CloudContractModel):
        command_id: str
        site_id: str
        tent_id: str
        source_tent_id: int | None
        device_id: str | None
        capability_id: str | None
        command_type: CommandType
        payload: PtzCommandPayload | BreedingCommandPayload

The final shape should keep lifecycle fields at top level and move physical addressing into an optional target. PTZ commands get a target; breeding commands normally do not.

    class PtzCommandTarget(CloudContractModel):
        kind: Literal["ptz"]
        source_tent_id: int | None = None
        device_id: Literal["obsbot-main"]
        capability_id: Literal["ptz_move"]

    CommandTarget: TypeAlias = PtzCommandTarget

    class ClaimedCommand(CloudContractModel):
        command_id: str
        site_id: str
        command_type: CommandType
        target: CommandTarget | None
        payload: PtzCommandPayload | BreedingCommandPayload

A breeding payload that places plants still carries a real tent because the action needs it:

    class BreedingBulkMovePayload(CloudContractModel):
        plant_keys: list[str]
        source_tent_id: int
        grid_position: None

A breeding payload that has no tent should not carry one:

    class BreedingBulkSexPayload(CloudContractModel):
        plant_keys: list[str]
        sex_key: PlantSexKey

The local gateway producer is `apps/gateway/src/dirt_gateway/local.py`. It currently sends `legacy_tent_id=str(tent.tent_pk)`, `legacy_zone_id=str(zone.id)`, and `legacy_schedule_id=str(schedule.id)` in catalog payloads, and `tent_id=str(tent.tent_pk)` / `zone_id=str(zone_pk)` in local snapshot asset payloads. Camera upload policy helpers in `apps/shared/src/dirt_shared/services/camera_publisher.py` still pass text `tent_id` through capture policy responses.

The hosted gateway receiver is `apps/control-plane/src/dirt_control/api/gateway.py`. It currently builds `legacy_tent_ids` and `legacy_zone_ids`, writes legacy `tent_id`, `zone_id`, and `schedule_id` into cloud projection tables, resolves legacy text values with `_legacy_tent_id_from_projection()` and `_legacy_zone_id_from_projection()`, and stores assets by text `tent_id`.

Browser-facing services now live under `apps/control-plane/src/dirt_control/services/`. Legacy text scope reads and command bridges remain in:

- `browser_assets.py`, which looks up `CloudAsset` rows through `CloudAsset.tent_id == tent.tent_id`.
- `browser_health.py`, which joins `CloudLatestMetric` to `CloudDevice` through text `tent_id` and logs it in audit metadata.
- `browser_commands.py`, which maps `source_tent_id` to legacy text, exposes `legacy_target_tent_id`, and stores the fake `breeding-logbook` tent for site-wide breeding commands.
- `browser_tents.py`, where `tent_display_name()` falls back to `CloudPlantLocation.tent_id` for old rows.

The browser OpenAPI/TypeScript contract is generated by `scripts/gen-hosted-contract`, which writes `contracts/hosted-browser-v1.json` and `web-ui/src/api-client/generated/hosted-schema.ts`. Do not hand-edit generated files.

After the browser UI refactor, handwritten browser command usage is concentrated in two areas. `web-ui/src/routes/live.tsx` is the PTZ command producer for the live camera screen and currently submits flat command target fields from generated `CommandCreateRequest`. `web-ui/src/features/breeding-logbook/breedingLogbookMutations.ts` and `web-ui/src/features/breeding-logbook/breedingLogbookQueries.test.ts` consume generated `CommandResponse` for pending command tracking; they should continue to use command lifecycle/status fields and should not depend on legacy tent targeting.


## Plan of Work

Milestone 1 establishes a precise inventory and safety net. Add tests that prove old and new payload shapes can coexist during the compatibility period. The tests should cover both directions of the gateway contract: gateway-to-control-plane request DTOs and control-plane-to-gateway response DTOs. Also add or document SQL inventory queries for cloud rows where source IDs are missing while legacy text `tent_id`, `zone_id`, or `schedule_id` values are present.

Milestone 2 expands storage. Add source identity columns to tables that cannot yet be read without text scope fields. At minimum, add `CloudAsset.source_tent_id` and `CloudAsset.source_zone_id`; then backfill them from existing rows by joining `cloud_asset.site_id` / `cloud_asset.tent_id` / `cloud_asset.zone_id` to `cloud_tent` and `cloud_zone`. Review current source columns on `CloudZone`, `CloudDevice`, `CloudSchedule`, `CloudLatestMetric`, `CloudMetricRollup`, and `CloudCommand`; add backfills, source-based unique constraints, and indexes where needed before changing reads. Do not drop any text column in this milestone.

Milestone 3 makes contracts tolerant. In `apps/shared/src/dirt_shared/cloud_contract.py`, make legacy tent, zone, and schedule fields optional with defaults and mark them deprecated. Keep `extra="forbid"`. Add the optional command target shape while still accepting the old flat command fields during the compatibility period. `ClaimedCommand` should validate old PTZ payloads that carry top-level `source_tent_id` / `device_id` / `capability_id`, new PTZ payloads that carry `target`, and breeding payloads with no command target. In browser schemas, make `legacy_target_tent_id` optional or remove it only if no generated/browser client needs it yet; prefer optional/deprecated first to preserve generated-contract compatibility during this milestone. Treat `web-ui/src/routes/live.tsx` as the browser PTZ producer that must compile against the transitional `CommandCreateRequest`, and treat the breeding logbook pending-command code as a `CommandResponse` consumer that should not read the target fields for behavior.

Milestone 4 changes consumers. Update control-plane and gateway code so reads and decisions use source IDs, never legacy text `tent_id`, `zone_id`, or `schedule_id`. Browser assets should query `CloudAsset.source_tent_id` and use source zone identity when zone scope matters. Browser health should join devices and metrics by source tent identity plus device identity. Command execution should not read `ClaimedCommand.tent_id`. For PTZ commands, the gateway should read hardware scope from the optional command target. For breeding commands, the gateway should read tent scope only from typed breeding payloads that actually include `source_tent_id`; seed-lot, bulk-sex, bulk-cull, and note commands should have no tent scope. Browser command responses should not compute a legacy target from source tent identity for application logic. Replace `metric_freshness`'s stale local `tent_id` observability field with `source_tent_id`. During this milestone, producers may still write both old and new storage fields.

Milestone 5 stops legacy production. Once Milestone 3 has been deployed everywhere that consumes the payloads, remove production of legacy text fields. The local gateway should stop sending `CatalogTent.legacy_tent_id`, `CatalogZone.legacy_zone_id`, `CatalogSchedule.legacy_schedule_id`, asset request `tent_id`, and asset request `zone_id`. The hosted control plane should stop returning command/capture-policy text `tent_id` fields after the local gateway can tolerate their absence. PTZ commands should serialize an explicit target. Breeding commands should serialize `target=None` and should stop writing or returning the fake `BREEDING_SITE_WIDE_TENT_ID` / `breeding-logbook` value. Keep the optional DTO fields for one full compatibility window so old queued outbox rows and old deployments do not fail validation.

Milestone 6 deletes contract fields. After the compatibility window, remove the optional legacy fields from Pydantic DTOs and browser schemas. Command DTOs should no longer expose top-level text `tent_id`, `legacy_target_tent_id`, or old flat PTZ target fields as generic command metadata. Regenerate hosted contracts and update generated frontend tests/fixtures. Update `web-ui/src/routes/live.tsx` to send the final PTZ `target` shape and update breeding logbook command fixtures to omit `legacy_target_tent_id`. Before deleting, verify that local cloud outbox payloads and command result payloads do not contain old legacy field names that a future `model_validate()` call would reject.

Milestone 7 contracts storage. Remove legacy text scope fields from active SQLModel models, helper functions, source queries, audit metadata, and active constraints. Generate a cloud Atlas migration that drops source-owned text `tent_id`, `zone_id`, and `schedule_id` columns and constraints only after all source-based constraints and non-null checks are in place. If Atlas generates a lock-heavy migration, hand-edit it according to `docs/database.md` and `docs/references/atlas/INDEX.md`: prefer staged checks, concurrent indexes where supported, and narrow `atlas:nolint` comments only when the risk is understood.

Milestone 8 validates and records the end state. Run backend, invariant, contract, and frontend checks. Record grep evidence showing active source has no legacy scoped text bridges except allowed local integer FK names, cloud `site_id`, and historical migrations. Update this ExecPlan and any affected docs.


## Concrete Steps

Start from the repository root:

    cd /home/akcom/code/dirt

Read required docs before implementing:

    sed -n '1,220p' docs/commands.md
    sed -n '1,220p' docs/database.md
    sed -n '1,220p' docs/rules/boundary-contracts.md
    sed -n '1,220p' docs/rules/data-modeling.md
    sed -n '1,220p' docs/rules/simple-clean-architecture.md
    sed -n '1,220p' docs/references/atlas/INDEX.md

Milestone 1 inventory commands:

    rg -n "legacy_(tent|zone|schedule)_id|legacy_target_tent_id|BREEDING_SITE_WIDE_TENT_ID|breeding-logbook|Temporary cloud.*(tent|scope)|_legacy_(tent|zone)_id|_asset_storage_tent_id|tent_display_name|CloudAsset\\.(tent_id|zone_id)|CloudLatestMetric\\.(tent_id|zone_id)|CloudCommand\\.tent_id|CloudSchedule\\.(tent_id|zone_id|schedule_id)" apps/control-plane/src apps/shared/src apps/gateway/src apps/hwd/src web-ui/src --glob '!api-client/generated/**'

    rg -n "\\b(tent_id|zone_id|schedule_id)\\b" apps/control-plane/src/dirt_control/models/cloud.py apps/shared/src/dirt_shared/cloud_contract.py apps/control-plane/src/dirt_control/api/gateway.py apps/control-plane/src/dirt_control/services apps/gateway/src/dirt_gateway apps/shared/src/dirt_shared/services/camera_publisher.py apps/hwd/src/dirt_hwd/services/metric_freshness.py web-ui/src --glob '!api-client/generated/**'

Add focused tests in the relevant existing files:

    apps/shared/tests/test_cloud_contract.py
    apps/gateway/tests/test_sync.py
    apps/control-plane/tests/test_api.py
    apps/control-plane/tests/test_control_plane_boundary_guardrails.py
    apps/shared/tests/test_cloud_assets.py
    apps/shared/tests/test_camera_publisher.py

When browser command schemas change, inspect and update the handwritten generated-type consumers:

    web-ui/src/routes/live.tsx
    web-ui/src/features/breeding-logbook/breedingLogbookMutations.ts
    web-ui/src/features/breeding-logbook/breedingLogbookQueries.test.ts

Milestone 2 schema work:

    uv run atlas migrate diff cloud_asset_source_scope --env cloud
    uv run atlas migrate hash --dir file://cloud/migrations

Expected migration shape for assets is additive first. The exact SQL may vary, but the migration should resemble:

    ALTER TABLE "cloud_asset" ADD COLUMN "source_tent_id" bigint NULL, ADD COLUMN "source_zone_id" bigint NULL;
    UPDATE "cloud_asset" AS asset
    SET
      "source_tent_id" = tent."source_tent_id",
      "source_zone_id" = zone."source_zone_id"
    FROM "cloud_tent" AS tent
    LEFT JOIN "cloud_zone" AS zone
      ON zone."site_id" = asset."site_id"
     AND zone."tent_id" = asset."tent_id"
     AND zone."zone_id" = asset."zone_id"
    WHERE asset."site_id" = tent."site_id"
      AND asset."tent_id" = tent."tent_id"
      AND asset."source_tent_id" IS NULL;

After each source change, run focused checks before broad checks:

    uv run pytest apps/shared/tests/test_cloud_contract.py apps/shared/tests/test_cloud_assets.py apps/shared/tests/test_camera_publisher.py -q
    uv run pytest apps/gateway/tests/test_sync.py -q
    uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q
    uv run ruff check apps/shared/src/dirt_shared apps/gateway/src/dirt_gateway apps/control-plane/src/dirt_control apps/shared/tests apps/gateway/tests apps/control-plane/tests

When browser response schemas change, regenerate hosted contracts:

    scripts/gen-hosted-contract
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test

Run full validation at milestone boundaries:

    uv run pytest -q
    uv run pytest apps/tests/invariants -q
    git diff --check


## Validation and Acceptance

Milestone 1 is accepted when tests prove both old and new payload shapes are valid during compatibility:

- `CatalogTent` validates with and without `legacy_tent_id`.
- `CatalogZone` validates with and without `legacy_zone_id`.
- `CatalogSchedule` validates with and without `legacy_schedule_id`.
- Asset request DTOs validate with and without `tent_id`.
- Asset completion DTOs validate with and without `zone_id`.
- `CapturePolicyResponse` validates with and without `tent_id`.
- `ClaimedCommand` / `CommandResultResponse` validate with and without `tent_id`.
- `ClaimedCommand` validates a new PTZ command shape with an explicit `target`.
- `ClaimedCommand` validates a breeding command shape with `target=None`.
- Existing old-shape fixture payloads still pass until the deletion milestone.

Milestone 2 is accepted when cloud migrations add and backfill source storage without dropping legacy columns, and these checks pass against a migrated test database:

- All `cloud_asset` rows that represent tent-scoped snapshots have `source_tent_id`.
- All `cloud_asset` rows that represent zone-scoped snapshots have `source_zone_id`.
- Cloud projection tables with existing source scope columns are backfilled enough for source-based reads and constraints.
- Browser latest-assets behavior can be implemented against source identity.
- `atlas migrate hash --dir file://cloud/migrations` passes.

Milestone 3 is accepted when generated OpenAPI shows legacy fields as optional/deprecated or otherwise clearly transitional, and no old producer is broken by the DTO changes. The shared command contract accepts old flat PTZ target fields and the new optional target shape without relaxing `extra="forbid"`.

The browser command clients must also compile against the transitional generated schema. During this milestone, `/live` may still submit flat PTZ target fields if the browser `CommandCreateRequest` intentionally accepts both shapes; breeding logbook pending-command code must continue to use lifecycle/status fields rather than legacy target fields.

Milestone 4 is accepted when active consumers no longer read text scope identity for decisions:

- `browser_assets.py` queries by `CloudAsset.source_tent_id`.
- `browser_health.py` joins metrics/devices by source identity.
- `browser_commands.py` does not map source tent IDs to text target strings for command behavior.
- `apps/gateway/src/dirt_gateway/commands.py` does not read `item.tent_id`.
- `apps/gateway/src/dirt_gateway/commands.py` reads PTZ hardware scope from command `target` and breeding tent scope only from typed breeding payloads that include `source_tent_id`.
- `apps/hwd/src/dirt_hwd/services/metric_freshness.py` uses and logs `source_tent_id`, not stale `tent_id`, for source scope.

Milestone 5 is accepted when active producers stop emitting legacy fields while optional DTOs still tolerate them:

- `apps/gateway/src/dirt_gateway/local.py` does not produce `legacy_tent_id` or asset request `tent_id`.
- `apps/gateway/src/dirt_gateway/local.py` does not produce `legacy_zone_id`, `legacy_schedule_id`, or asset request `zone_id`.
- `apps/shared/src/dirt_shared/services/camera_publisher.py` does not produce capture-policy text `tent_id`.
- `apps/control-plane/src/dirt_control/api/gateway.py` does not include command/capture-policy text tent fields in responses unless the optional transition field is intentionally still present for a compatibility window.
- `apps/control-plane/src/dirt_control/services/browser_commands.py` no longer defines or writes `BREEDING_SITE_WIDE_TENT_ID` / `breeding-logbook`.
- PTZ command responses include the new target shape; breeding command responses have no command target unless a future breeding command truly addresses hardware.

Milestone 6 is accepted when Pydantic DTOs and generated browser contracts no longer expose legacy scoped text fields:

- No `legacy_tent_id` or `legacy_target_tent_id` appears in active source or generated hosted contracts.
- No `legacy_zone_id` or `legacy_schedule_id` appears in active source or generated hosted contracts.
- No `tent_id: str` remains in cloud gateway DTOs where the value means old text source-owned identity.
- `ClaimedCommand` and browser `CommandResponse` do not expose `source_tent_id`, `device_id`, or `capability_id` as generic top-level command metadata for PTZ targeting; those values live under the optional target shape.
- `web-ui/src/routes/live.tsx` submits PTZ commands through the final target shape, and `web-ui/src/features/breeding-logbook/breedingLogbookQueries.test.ts` no longer carries a `legacy_target_tent_id` fixture.
- No `zone_id: str` or `schedule_id: str` remains in cloud gateway DTOs where the value means old text source-owned identity.
- `scripts/gen-hosted-contract` passes and generated frontend types compile.

Milestone 7 is accepted when cloud SQLModel storage no longer has old text scope columns for source-owned identity:

- `CloudAsset`, `CloudCommand`, `CloudLatestMetric`, and other cloud projection models no longer define text `tent_id` for source-owned tent identity.
- Cloud projection models no longer define text `zone_id` or `schedule_id` for source-owned zone/schedule identity.
- New source-based constraints replace old `site_id, tent_id, zone_id, schedule_id, ...` constraints where those text fields were source-owned bridges.
- `cloud/migrations/` contains the final drop migration and `atlas migrate hash --dir file://cloud/migrations` passes.

The final acceptance grep must allow local integer FK names and historical migrations, but not active legacy cloud text bridges. A useful final check is:

    rg -n "legacy_(tent|zone|schedule)_id|legacy_target_tent_id|BREEDING_SITE_WIDE_TENT_ID|breeding-logbook|Temporary cloud.*(tent|scope)|_legacy_(tent|zone)_id|_asset_storage_tent_id|tent_display_name|CloudAsset\\.(tent_id|zone_id)|CloudLatestMetric\\.(tent_id|zone_id)|CloudCommand\\.tent_id|CloudSchedule\\.(tent_id|zone_id|schedule_id)" apps/control-plane/src apps/shared/src apps/gateway/src apps/hwd/src web-ui/src --glob '!api-client/generated/**'

Expected result at completion:

    no matches


## Idempotence and Recovery

The expand milestones are safe to repeat. Adding nullable source columns, backfilling from deterministic joins, and changing consumers to prefer source identity can be rerun without data loss. Backfill SQL must be written with `WHERE source_* IS NULL` conditions so a retry does not overwrite already-correct source data.

Do not combine producer-stop, contract deletion, and column drop in one release. If a release needs rollback, the previous release must still understand the database and payloads it sees. The staged order is:

1. Add source storage and tolerant DTOs.
2. Deploy tolerant consumers in both directions.
3. Stop producers from sending legacy fields.
4. Wait for old outbox rows and old deployments to drain.
5. Delete contract fields.
6. Drop storage columns.

For gateway-to-control-plane requests, deploy the tolerant hosted control plane before deploying a gateway that stops sending legacy request fields. For control-plane-to-gateway responses, deploy the tolerant local gateway before deploying a hosted control plane that stops returning legacy response fields.

Before Milestone 6, inspect any persisted local outbox rows that may still contain old DTO JSON. If rows exist, either let them deliver before deleting fields or write a narrow migration/cleanup for that payload type. Do not make `CloudContractModel` globally ignore extras as a shortcut.

For cloud database migrations, do not run destructive `atlas migrate apply --env cloud` without the operator's explicit deploy instruction. Hosted deploys must use `scripts/deploy-control-plane`; do not run ad hoc Railway deploy commands.


## Artifacts and Notes

Initial active-source audit on 2026-06-19 found these important references. Current line references were refreshed on 2026-06-20:

    apps/shared/src/dirt_shared/cloud_contract.py:70: CatalogTent.legacy_tent_id
    apps/shared/src/dirt_shared/cloud_contract.py:79: CatalogZone.legacy_zone_id
    apps/shared/src/dirt_shared/cloud_contract.py:114: CatalogSchedule.legacy_schedule_id
    apps/shared/src/dirt_shared/cloud_contract.py:320: AssetSignUploadRequest.tent_id
    apps/shared/src/dirt_shared/cloud_contract.py:343: AssetCompleteRequest.zone_id
    apps/shared/src/dirt_shared/cloud_contract.py:358: AssetFailureRequest.tent_id
    apps/shared/src/dirt_shared/cloud_contract.py:372: CapturePolicyResponse.tent_id
    apps/shared/src/dirt_shared/cloud_contract.py:587: ClaimedCommand.tent_id
    apps/control-plane/src/dirt_control/api/browser_schemas/commands.py:16: CommandCreateRequest.source_tent_id
    apps/control-plane/src/dirt_control/api/browser_schemas/commands.py:28: CommandResponse.legacy_target_tent_id
    apps/control-plane/src/dirt_control/services/browser_commands.py:21: BREEDING_SITE_WIDE_TENT_ID
    apps/control-plane/src/dirt_control/services/browser_assets.py:33: CloudAsset.tent_id == tent.tent_id
    apps/control-plane/src/dirt_control/services/browser_commands.py:182: legacy_target_tent_id=command.tent_id
    apps/control-plane/src/dirt_control/api/gateway.py:157: legacy_tent_ids = {tent.source_tent_id: tent.legacy_tent_id for tent in body.tents}
    apps/control-plane/src/dirt_control/api/gateway.py:158: legacy_zone_ids = {zone.source_zone_id: zone.legacy_zone_id for zone in body.zones}
    apps/control-plane/src/dirt_control/api/gateway.py:315: "schedule_id": schedule.legacy_schedule_id
    apps/control-plane/src/dirt_control/api/gateway.py:1218: _asset_storage_tent_id(...)
    apps/hwd/src/dirt_hwd/services/metric_freshness.py:147: scope.get("tent_id")

Browser UI refactor audit on 2026-06-20 found these additional generated-contract touchpoints:

    web-ui/src/routes/live.tsx:19: HostedCommandCreate = hostedComponents["schemas"]["CommandCreateRequest"]
    web-ui/src/routes/live.tsx:120: commandMutation.mutate({ source_tent_id, device_id, capability_id, ... })
    web-ui/src/features/breeding-logbook/breedingLogbookMutations.ts:31: HostedCommand = hostedComponents["schemas"]["CommandResponse"]
    web-ui/src/features/breeding-logbook/breedingLogbookQueries.test.ts:562: legacy_target_tent_id fixture

External migration references used while drafting this plan:

- Google AIP-180 says removing or renaming existing API fields is backward-incompatible in the same major version: https://google.aip.dev/180
- Google AIP-203 notes that adding a new required field to an existing request message is backward-incompatible: https://google.aip.dev/203
- JSON Schema Draft 2020-12 includes a `deprecated` annotation whose value does not affect validation but signals future removal: https://www.learnjsonschema.com/2020-12/meta-data/deprecated/
- Prisma's expand/contract data guide describes adding the new structure, migrating data and clients, then removing the old structure: https://www.prisma.io/dataguide/types/relational/expand-and-contract-pattern
- PostgreSQL `ALTER TABLE` supports `ADD table_constraint NOT VALID` for staged validation of foreign-key and check constraints: https://www.postgresql.org/docs/current/sql-altertable.html


## Interfaces and Dependencies

The final active interfaces must use source identity:

- `apps/shared/src/dirt_shared/cloud_contract.py`
  - `CatalogTent` has `source_tent_id`, `name`, `role`, and `is_active`; it has no `legacy_tent_id`.
  - `CatalogZone` has `source_tent_id`, `source_zone_id`, `name`, `kind`, and `is_active`; it has no `legacy_zone_id`.
  - `CatalogSchedule` has source IDs, schedule times, owner device/capability fields, kind, timezone, and enabled state; it has no `legacy_schedule_id`.
  - `AssetSignUploadRequest`, `AssetCompleteRequest`, and `AssetFailureRequest` have source scope IDs where needed; they have no text `tent_id` or `zone_id`.
  - `CapturePolicyResponse` has `source_tent_id` and `tent_name`; it has no text `tent_id`.
  - `ClaimedCommand` and `CommandResultResponse` have lifecycle fields, `command_type`, typed `payload`, and `target: CommandTarget | None`; they have no text `tent_id`.
  - `PtzCommandTarget` carries PTZ hardware scope: optional `source_tent_id`, `device_id`, and `capability_id`.
  - Breeding command payloads carry domain identifiers. Only germinate, clone, and bulk move payloads carry `source_tent_id`; seed lot creation, bulk sex, bulk cull, and plant note payloads do not.

- `apps/control-plane/src/dirt_control/models/cloud.py`
  - Cloud projection rows use source IDs for local source tent, zone, and schedule identity.
  - `CloudAsset` has `source_tent_id` and `source_zone_id`.
  - `CloudCommand` has no required tent target. If PTZ target scope remains stored as flat nullable columns, those columns are treated as hardware target fields only; breeding commands do not duplicate payload `source_tent_id` into command metadata.
  - Active source-owned text `tent_id`, `zone_id`, and `schedule_id` columns are gone after the final migration.
  - `CloudSite.site_id`, `GatewayCredential.allowed_site_id`, and browser site response `site_id` remain unchanged in this plan.

- `apps/control-plane/src/dirt_control/api/gateway.py`
  - Gateway catalog, metric, rollup, asset, command, and capture-policy code reads source identity.
  - `_legacy_tent_id()`, `_legacy_zone_id()`, `_legacy_tent_id_from_projection()`, `_legacy_zone_id_from_projection()`, and `_asset_storage_tent_id()` are deleted or reduced only to non-legacy-scope responsibilities.

- `apps/control-plane/src/dirt_control/services/`
  - Browser services query by source identity and display tent names from `CloudTent.name`.
  - `CommandResponse` no longer includes `legacy_target_tent_id`; PTZ target information is exposed through the optional target shape, and breeding responses do not expose fake tent targets.

- `web-ui/src/api-client/generated/hosted-schema.ts`
  - Generated types no longer include `legacy_tent_id`, `legacy_zone_id`, `legacy_schedule_id`, `legacy_target_tent_id`, or cloud text fields for source-owned scope identity.

External services and tools:

- PostgreSQL 17 is the target production database family. Use Atlas cloud migrations under `cloud/migrations/`.
- Hosted deploys must use `scripts/deploy-control-plane`.
- Browser contract generation must use `scripts/gen-hosted-contract`.
- Python commands must use `uv run ...`.


## Revision Notes

- 2026-06-19: Initial plan created from the legacy text tent field audit and migration-path discussion. The plan deliberately uses a compatibility release between optional/deprecated fields and final deletion so each piece can be deployed independently without validation errors.
- 2026-06-19: Scope broadened after review to include legacy text `zone_id` and `schedule_id`; cloud `site_id` remains out of scope because it is tied to hosted auth/tenant scoping.
- 2026-06-19: Command-contract decision added: keep the shared command queue, remove required tent targeting, model PTZ as an optional hardware target, and remove the fake `breeding-logbook` tent from breeding commands.
- 2026-06-20: Refreshed plan after the browser UI refactor review. Added `/live` and breeding logbook generated-command consumers as explicit touchpoints, included `apps/hwd/src` in the first inventory grep, and updated the current audit line references.
