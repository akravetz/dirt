# Plant Sex Tests

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, Dirt can track external plant sex tests such as Farmer Freeman EZ-XY kits as first-class breeding records. An operator can select plants in the hosted Breeding Logbook, record that samples were collected for a batch, type the vendor test code printed on each kit, optionally mark when the samples were sent, and later enter explicit received-back results that update both the sex-test record and the plant's current sex.

This matters because the current plant model can store current plant sex, but it cannot explain how that sex was determined or track pending lab tests. The immediate workflow is manual entry of Farmer Freeman test codes and results, but the model should stay vendor-neutral enough for later retests, inconclusive results, or another lab. A plant usually has one sex test, but the storage model is one-to-many so inconclusive or corrected tests do not force data loss.

The work is complete when a developer can create a pending sex test for each selected plant, see those test codes inline on the plant list and plant detail, filter/search plants by sex-test state or code, enter bulk results with an explicit `result_received_at` supplied by the UI, and observe conclusive results set `plant.sex_key` through the existing command-backed gateway flow.


## Progress

- [x] (2026-07-01T00:00Z) Reviewed the current plant, breeding-logbook, gateway command, cloud projection, and frontend plant workflow shape.
- [x] (2026-07-01T00:00Z) Locked product and model decisions with the operator: one-to-many sex tests, one open pending test per plant, timestamp fields, explicit UI-supplied result receipt time, inline plant read arrays, no standalone list endpoint in v1, and command-backed writes.
- [x] (2026-07-01T00:00Z) Drafted this ExecPlan.
- [x] (2026-07-01T18:06:15-06:00) Implement local sex-test source storage.
- [x] (2026-07-01T18:21:37-06:00) Add shared gateway/catalog contracts and cloud projection storage.
- [ ] Add sex-test command contracts and command execution.
- [ ] Add hosted browser read/write API routes and generated frontend contract.
- [ ] Add hosted UI sampling, pending-results, filtering, and detail history workflows.
- [ ] Validate end-to-end with tests and browser verification.


## Surprises & Discoveries

- Observation: Hosted breeding writes are already command-backed, not direct browser writes.
  Evidence: `apps/control-plane/src/dirt_control/api/browser/breeding_logbook.py` exposes write routes such as `POST /api/breeding-logbook/plants:bulk-sex`, and `apps/control-plane/src/dirt_control/services/breeding_logbook.py` enqueues typed breeding commands instead of mutating source plant rows directly.

- Observation: The gateway command executor already owns local breeding mutations and plant sex events.
  Evidence: `apps/gateway/src/dirt_gateway/breeding_commands.py` handles `BreedingBulkSexPayload` by updating `Plant.sex_key` and inserting `PlantEvent(is_sex_observation=True, metadata_json={"sex_key": ...})`.

- Observation: The hosted plant list/detail contracts are already screen-shaped and plant-list focused.
  Evidence: `apps/control-plane/src/dirt_control/api/browser_schemas/breeding_logbook.py` defines `BreedingLogbookPlantRowResponse` and `BreedingLogbookPlantDetailResponse`; `web-ui/src/features/plants/plantsQueries.ts` maps those rows into `PlantRow`.

- Observation: The frontend already has the selection, bulk panel, pending-command, optimistic-patch, and delayed-projection refresh machinery needed for this feature.
  Evidence: `web-ui/src/features/plants/PlantsWorkspace.tsx` manages selected plants and bulk panels; `web-ui/src/features/plants/plantsMutations.ts` tracks `PlantsPendingCommand` objects and applies pending plant patches.

- Observation: The current plant sex lookup is broad enough for manual observations, but lab sex-test results should initially accept conclusive male/female results plus an inconclusive state.
  Evidence: `dirt_shared.cloud_contract.PlantSexKey` includes `unknown`, `male`, `female`, `herm`, and `reversed`. The user's sex-test result workflow is specifically to punch in male, female, or inconclusive results from Farmer Freeman.

- Observation: Local Atlas diff still needs the existing `btree_gist` disposable-dev workaround when SQLModel desired-state loading reaches plant-location exclusion constraints.
  Evidence: `atlas migrate diff plant_sex_tests_verify --env local --format '{{ sql . "  " }}'` failed before this migration with `pq: data type bigint has no default operator class for access method "gist"` on `plant_location_history`; the same sync check passed against disposable PostgreSQL 17 on port 55434 after `CREATE EXTENSION IF NOT EXISTS btree_gist;`.


## Decision Log

- Decision: Add a first-class `plant_sex_test` source table instead of adding sex-test fields to `plant`.
  Rationale: A sex test is an evidence record with its own vendor code, sample dates, result state, and notes. Plants usually have one test, but inconclusive, lost, duplicated, or corrected tests are real enough that one-to-many is the truthful model.
  Date/Author: 2026-07-01 / Operator + Codex

- Decision: Store `plant_sex_test.plant_id` as an integer FK to `plant.id`.
  Rationale: Dirt-owned object relationships use integer `id` as canonical identity. Browser and command payloads may use human-facing `plant.key`, but local storage should not add a parallel Dirt-owned text identifier.
  Date/Author: 2026-07-01 / Codex

- Decision: Store the vendor test code as a real external key on the sex-test row.
  Rationale: Farmer Freeman kit codes are created outside Dirt, typed from physical labels/results, and must remain searchable/auditable. The correct name is a vendor-owned field such as `vendor_test_code`, not a new plant identity.
  Date/Author: 2026-07-01 / Operator + Codex

- Decision: Use `vendor_name text` and optional `assay_name text` in v1, not vendor lookup tables.
  Rationale: The current workflow only needs to record "Farmer Freeman" and "EZ-XY". A lookup table is not justified until vendors need metadata, configured defaults, aliases, ordering, or reporting semantics.
  Date/Author: 2026-07-01 / Codex

- Decision: Use timestamp columns for collection, sent, and result-received facts.
  Rationale: The rest of the breeding lifecycle model uses timestamps, and the operator prefers timestamps because extra precision does not hurt. The UI can still present date-focused controls.
  Date/Author: 2026-07-01 / Operator

- Decision: Do not default `result_received_at` in the backend.
  Rationale: Results may be entered after reception. `result_received_at` is a domain event time, so the UI must supply it explicitly. Backend defaults remain acceptable for system bookkeeping fields such as `created_at` and `updated_at`.
  Date/Author: 2026-07-01 / Operator

- Decision: Enforce one pending/open sex test per plant with a partial unique index.
  Rationale: The strictness catches accidental duplicate sampling entry and matches the expected starting workflow. Multiple historical tests and retests after an inconclusive or resulted test remain possible. The constraint can be relaxed later if simultaneous duplicate samples become intentional.
  Date/Author: 2026-07-01 / Operator + Codex

- Decision: Keep existing `plants:bulk-sex` as manual/current-sex entry and do not have it update sex-test rows.
  Rationale: Manual or visual sexing is a different evidence source from lab results. A lab-result workflow can update `plant.sex_key`, but generic bulk sexing should not pretend a lab test was received.
  Date/Author: 2026-07-01 / Codex

- Decision: Inline sex-test arrays on plant list and detail responses; do not add a standalone list endpoint in v1.
  Rationale: The expected scale is small, and the user workflows start from plant selection, plant detail, and pending tests visible on the plant list. A list endpoint can be added later if result imports, pagination, or reporting need it.
  Date/Author: 2026-07-01 / Operator + Codex

- Decision: Use command-backed browser mutations for sex-test writes.
  Rationale: The local home database remains the source of truth for breeding records. The hosted browser should enqueue typed commands, the gateway should apply them locally, and gateway catalog sync should project the resulting state back to hosted read models.
  Date/Author: 2026-07-01 / Codex

- Decision: Bulk result entry takes one explicit `result_received_at` for the submitted batch.
  Rationale: The likely workflow is "these results came back on this date" followed by entering male/female/inconclusive per test. If later workflows need per-row received dates, the contract can add an explicit row-level command.
  Date/Author: 2026-07-01 / Operator + Codex


## Outcomes & Retrospective

- Milestone 1 added local source storage for plant sex tests. `apps/shared/src/dirt_shared/models/plant.py` now defines `PlantSexTest`, `apps/shared/src/dirt_shared/models/__init__.py` exports it, and local migration `migrations/20260701235933_plant_sex_tests.sql` creates `plant_sex_test` with the required foreign keys, vendor-code uniqueness, one-open-pending-test partial unique index, timestamp ordering check, result-state check, and nonblank checks.
- Milestone 1 validation passed: `uv run --package dirt-shared python scripts/atlas-load-sqlmodel.py postgresql`, `atlas migrate hash --env local`, `set -a; source .env; set +a; atlas migrate apply --env local --dry-run`, `uv run pytest apps/shared/tests/test_plant_sex_test_models.py -q` (`14 passed`), `uv run ruff check` and `uv run ruff format --check` on touched Python files, `git diff --check` on milestone files, and the disposable-Postgres `atlas migrate diff plant_sex_tests_verify --env local --dev-url ... --format '{{ sql . "  " }}'` sync check.
- No live/local migration apply was run for Milestone 1.
- Milestone 2 added `CatalogPlantSexTest`, required `CatalogRequest.sex_tests`, `CatalogResponse.sex_tests`, gateway catalog collection for scoped local `PlantSexTest` rows, hosted `CloudPlantSexTest` storage, and idempotent gateway catalog upsert/count handling. Cloud migration `cloud/migrations/20260702001559_plant_sex_tests.sql` creates `cloud_plant_sex_test` with source-test and vendor-code uniqueness plus plant/result query indexes.
- Milestone 2 validation passed: `atlas migrate hash --env cloud`, `atlas migrate diff plant_sex_tests_verify --env cloud --format '{{ sql . "  " }}'`, `uv run pytest apps/shared/tests/test_cloud_contract.py -q` (`29 passed`), `uv run pytest apps/gateway/tests/test_sync.py apps/gateway/tests/test_cloud_client.py apps/gateway/tests/test_gateway_boundary_guardrails.py -q` (`54 passed`), `uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q` (`65 passed`), `uv run ruff check` on touched Python files, and `git diff --check` on milestone files.
- No live/cloud migration apply was run for Milestone 2.


## Context and Orientation

Dirt stores canonical home grow state in local PostgreSQL through SQLModel models under `apps/shared/src/dirt_shared/models/`. The gateway service in `apps/gateway/` projects local state into shared Pydantic contracts from `apps/shared/src/dirt_shared/cloud_contract.py`, delivers those projections to the hosted control plane, claims hosted commands, and applies breeding commands locally in `apps/gateway/src/dirt_gateway/breeding_commands.py`.

The hosted control plane in `apps/control-plane/` stores projected rows in cloud tables under `apps/control-plane/src/dirt_control/models/cloud.py`. Gateway catalog upsert happens in `apps/control-plane/src/dirt_control/api/gateway.py`. Browser-facing Breeding Logbook routes live in `apps/control-plane/src/dirt_control/api/browser/breeding_logbook.py`, with response/request DTOs in `apps/control-plane/src/dirt_control/api/browser_schemas/breeding_logbook.py` and orchestration in `apps/control-plane/src/dirt_control/services/breeding_logbook.py`.

The React UI for plants lives in `web-ui/src/features/plants/`. `plantsQueries.ts` maps generated hosted API responses into local view types from `plantsTypes.ts`. `plantsMutations.ts` wraps command-backed browser writes and tracks pending commands so the UI can show optimistic or syncing state while the gateway applies the command and the hosted projection catches up. `PlantsWorkspace.tsx` owns the list/detail surfaces, selection state, bulk panels, filtering, and user workflows.

Relevant existing concepts:

- `plant.id`: local integer database identity for Dirt-owned relationships.
- `plant.key`: human-readable plant tag such as `SBBS-R1-001`, used in browser and command payloads because it is what the operator sees and types.
- `plant.sex_key`: current plant sex lookup key, already projected to hosted plant rows.
- `PlantEvent.is_sex_observation`: timeline event kind currently used by bulk sex updates.
- `CatalogRequest`: shared gateway-to-control-plane read projection contract.
- `CommandType`: shared cloud command type literal set used by browser write routes, command claim responses, and gateway local execution.

Before implementing this plan, read these docs in addition to this file:

- `docs/commands.md`
- `docs/database.md`
- `docs/rules/simple-clean-architecture.md`
- `docs/rules/data-modeling.md`
- `docs/rules/boundary-contracts.md`
- `docs/rules/frontend-server-state.md`
- `docs/references/atlas/INDEX.md` before generating or applying migrations
- `docs/references/tanstack-query-v5/INDEX.md` before changing frontend query/mutation code
- `docs/references/tanstack-router-v1/INDEX.md` before changing route files
- `docs/references/tailwind-v4/INDEX.md` before changing Tailwind classes or styles
- `docs/references/modern-idiomatic-typescript/INDEX.md` before authoring TypeScript/TSX


## Plan of Work

Milestone 1 adds local source storage. In `apps/shared/src/dirt_shared/models/plant.py`, add a `PlantSexTest` SQLModel table with:

- `id bigint primary key`
- `plant_id bigint not null references plant(id) on delete restrict`
- `vendor_name text not null`
- `assay_name text null`
- `vendor_test_code text not null`
- `sample_collected_at timestamptz not null`
- `sample_sent_at timestamptz null`
- `result_received_at timestamptz null`
- `result_sex_key text null references plant_lku_sex(key) on delete restrict`
- `is_inconclusive boolean not null default false`
- `notes text null`
- `created_at timestamptz not null default now()`
- `updated_at timestamptz not null default now()`

The table must include nonblank checks for `vendor_name`, `assay_name`, `vendor_test_code`, and `notes`; a unique constraint on `(vendor_name, vendor_test_code)`; an index on `(plant_id, sample_collected_at desc)`; and a partial unique index that allows only one open pending test per plant where `result_received_at IS NULL`. Add timestamp ordering checks so `sample_sent_at` is not before `sample_collected_at` and `result_received_at` is not before the collected/sent timestamps. Add a result-state check that pending tests have no result sex and are not inconclusive, while received tests have exactly one of `result_sex_key` or `is_inconclusive = true`.

Generate a local Atlas migration under `migrations/` from the SQLModel change. Do not hand-write DDL unless Atlas cannot express a required constraint and the migration is reviewed. Do not apply the migration to live/local without the backup step from `docs/database.md`.

Milestone 2 adds shared boundary contracts and cloud projection storage. In `apps/shared/src/dirt_shared/cloud_contract.py`, add `CatalogPlantSexTest` and include `sex_tests: list[CatalogPlantSexTest]` on `CatalogRequest` plus a `sex_tests: int` count on `CatalogResponse`. The catalog DTO should use source identities:

- `source_sex_test_id: int`
- `source_plant_id: int`
- `vendor_name: str`
- `assay_name: str | None = Field(...)`
- `vendor_test_code: str`
- `sample_collected_at: datetime`
- `sample_sent_at: datetime | None = Field(...)`
- `result_received_at: datetime | None = Field(...)`
- `result_sex_key: PlantSexKey | None = Field(...)`
- `is_inconclusive: bool`
- `notes: str | None = Field(...)`

In `apps/control-plane/src/dirt_control/models/cloud.py`, add `CloudPlantSexTest` with hosted `site_id`, `source_sex_test_id`, `source_plant_id`, sex-test fields, sync timestamps, a unique constraint on `(site_id, source_sex_test_id)`, a unique constraint on `(site_id, vendor_name, vendor_test_code)`, and useful indexes for plant and pending-result queries. Add a cloud Atlas migration under `cloud/migrations/`.

In `apps/gateway/src/dirt_gateway/local.py`, collect local `PlantSexTest` rows into `CatalogPlantSexTest` rows. In `apps/control-plane/src/dirt_control/api/gateway.py`, upsert `body.sex_tests` into `CloudPlantSexTest` and include the count in `CatalogResponse`. Update shared, gateway, and control-plane tests that pin catalog contract completeness.

Milestone 3 adds sex-test command contracts and local execution. In `apps/shared/src/dirt_shared/cloud_contract.py`, add these command types:

- `breeding_sex_tests_bulk_create`
- `breeding_sex_test_update`
- `breeding_sex_tests_bulk_result`

Add Pydantic payload models:

- `BreedingBulkCreateSexTestsPayload`: `vendor_name`, `assay_name`, `sample_collected_at`, `sample_sent_at`, and `tests`, where each test has `plant_key`, `vendor_test_code`, and optional `notes`.
- `BreedingUpdateSexTestPayload`: complete editable state for one sex test, including `sex_test_source_id`; this is for correcting metadata or a result after entry.
- `BreedingBulkResultSexTestsPayload`: required `result_received_at` and result rows, each with `sex_test_source_id` and exactly one of a conclusive `result_sex_key` or `is_inconclusive = true`.

For v1, browser result rows should accept conclusive `male` or `female` results plus inconclusive. Manual `plants:bulk-sex` remains the path for `herm`, `reversed`, or other observation-based sex states.

In `apps/gateway/src/dirt_gateway/breeding_commands.py`, teach `BreedingCommandExecutor.execute()` to handle the three new payloads. Bulk create should require plant keys, reject duplicate plant keys in the batch, rely on the database partial unique constraint for one pending test per plant, and produce useful command errors for unknown plants or duplicate vendor test codes. Bulk result should require explicit `result_received_at`, update each test, update `Plant.sex_key` only for conclusive results, and add `PlantEvent(is_sex_observation=True)` for every received sex-test result with metadata including `source: "sex_test"`, `sex_test_id`, `vendor_name`, `vendor_test_code`, `result_sex_key` or `is_inconclusive`.

Milestone 4 adds hosted browser schemas, routes, and service read mapping. In `apps/control-plane/src/dirt_control/api/browser_schemas/breeding_logbook.py`, add `BreedingLogbookSexTestResponse` and include `sex_tests: list[BreedingLogbookSexTestResponse]` on `BreedingLogbookPlantRowResponse`. This array is inline on both list and detail through the existing `plant` field in detail. Sort tests with pending/open tests first, then newest collected/result dates.

Add request DTOs for the three browser write routes. The browser request DTOs should include `idempotency_key` and should validate nonblank vendor names, test codes, and notes. Add routes in `apps/control-plane/src/dirt_control/api/browser/breeding_logbook.py`:

- `POST /api/breeding-logbook/sex-tests:bulk-create`
- `POST /api/breeding-logbook/sex-tests/{sex_test_id}:update`
- `POST /api/breeding-logbook/sex-tests:bulk-result`

In `apps/control-plane/src/dirt_control/services/breeding_logbook.py`, read `CloudPlantSexTest` rows for plant lists and details, attach them to plant row responses, validate referenced plant keys/test IDs before enqueueing commands, and enqueue the new shared payloads with the new command types. Do not add a standalone list-sex-tests route in v1.

Run `scripts/gen-hosted-contract` after the FastAPI OpenAPI schema changes. Do not add handwritten hosted response interfaces in `web-ui/src/api-client/cloud.ts`.

Milestone 5 adds frontend query types and mutations. In `web-ui/src/features/plants/plantsTypes.ts`, add a `PlantSexTest` type with camel-cased equivalents of the browser response fields, and include `sexTests: readonly PlantSexTest[]` on `PlantRow`. In `plantsQueries.ts`, map generated hosted sex-test rows into the view model. Include vendor test code and status in `plantSearchText()` so searching a Farmer Freeman code finds the plant.

In `plantsMutations.ts`, add mutation inputs and API functions for bulk-create, update, and bulk-result sex-test commands. Extend `PendingOperation`, `PlantsPendingCommand`, projection detection, and optimistic patches enough to show a pending sex-test code immediately after sample creation and to show conclusive sex updates after result submission. Follow `docs/rules/frontend-server-state.md`: command acceptance is not projection convergence, so pending state must remain visible until the synced plant read model reflects the sex tests/results.

Milestone 6 adds frontend UI workflows. In `PlantsWorkspace.tsx`, add a sex-test bulk panel reachable from the selected-plant action area. The sample-entry panel should default vendor to `Farmer Freeman`, assay to `EZ-XY`, sample collection timestamp to the current local datetime, sent timestamp to blank or user-provided, and render one row per selected plant with an input for `vendorTestCode`. A one-off add path can use the same panel with one selected/current plant.

On the plant list/table, add a compact Sex Test column or inline cell content showing the latest pending/resulted vendor test code and status. Add filters for untested, pending, resulted, and inconclusive plants. Keep text dense and utilitarian; this is an operational data-entry workflow, not a landing page.

Add a pending-results view or panel derived from the inline plant list data. It should show pending tests with plant key/name/location, vendor test code, and result controls for Female, Male, and Inconclusive. The form must require an explicit result received timestamp before submission. The UI may prefill the control with today's local datetime, but the submitted request must carry the explicit value.

On plant detail, show a sex-test history section with add/edit/result actions. The detail journal may also display synced sex-test result events through existing `PlantEvent` projection; do not invent a second timeline source unless product behavior needs it.

Milestone 7 validates and simplifies. Run focused backend, frontend, invariant, and browser checks. Use the existing simplify cleanup bias after implementation: remove dead helper code, prefer existing plant bulk/pending-command patterns, and do not leave adapters around old shapes because sex tests are new source-owned functionality.


## Concrete Steps

Start from the repository root:

    cd /home/akcom/code/dirt

Read required references for the files being touched:

    sed -n '1,260p' docs/commands.md
    sed -n '1,260p' docs/database.md
    sed -n '1,260p' docs/rules/simple-clean-architecture.md
    sed -n '1,260p' docs/rules/data-modeling.md
    sed -n '1,260p' docs/rules/boundary-contracts.md
    sed -n '1,260p' docs/rules/frontend-server-state.md
    sed -n '1,220p' docs/references/atlas/INDEX.md
    sed -n '1,220p' docs/references/tanstack-query-v5/INDEX.md
    sed -n '1,220p' docs/references/tanstack-router-v1/INDEX.md
    sed -n '1,220p' docs/references/tailwind-v4/INDEX.md
    sed -n '1,220p' docs/references/modern-idiomatic-typescript/INDEX.md

Inspect the current files before editing:

    rg -n "class Plant|PlantLkuSex|PlantEvent|BreedingBulkSexPayload|CatalogRequest|CommandType" apps/shared/src/dirt_shared
    rg -n "BreedingCommandExecutor|_bulk_sex|_bulk_update_facts" apps/gateway/src/dirt_gateway/breeding_commands.py
    rg -n "BreedingLogbookPlantRowResponse|bulk_sex_plants_command|list_plants" apps/control-plane/src/dirt_control
    rg -n "PlantRow|BulkPanel|PendingOperation|bulkSex" web-ui/src/features/plants

After SQLModel edits, generate and review migrations:

    uv run --package dirt-shared python scripts/atlas-load-sqlmodel.py postgresql
    atlas migrate diff plant_sex_tests --env local
    atlas migrate diff plant_sex_tests --env cloud
    atlas migrate hash --env local
    atlas migrate hash --env cloud
    atlas migrate apply --env local --dry-run

Before applying any local live migration, create a compressed backup as described in `docs/database.md`:

    set -a; source .env; set +a
    mkdir -p var/db-backups
    PGPASSWORD=$DIRT_PG_PASSWORD pg_dump \
      -h 127.0.0.1 -U dirt -d dirt \
      -Fc --compress=zstd:level=6 \
      -f var/db-backups/dirt-$(date +%F-%H%M%S)-pre-plant-sex-tests.dump

Then apply only when intentionally mutating the local database:

    atlas migrate apply --env local

Regenerate the hosted frontend contract after browser API schema changes:

    DIRT_CLOUD_ASSET_STORE=local scripts/gen-hosted-contract

Run focused tests as implementation progresses:

    uv run pytest apps/shared/tests/test_cloud_contract.py -q
    uv run pytest apps/gateway/tests/test_sync.py -q
    uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test
    uv run pytest apps/tests/invariants -q
    git diff --check

For browser verification, use the hosted local dev stack:

    make dev-up
    make dev-status
    agent-browser open <Web URL from make dev-status>

Log in with `dev-admin` / `dev-password`, open `/plants`, create a sex-test batch for selected plants, verify pending codes render in the list/detail, submit explicit received results, and verify the UI shows pending/syncing state until the projected plant rows include the new sex-test result and updated `sexKey`.


## Validation and Acceptance

Backend storage acceptance:

- `plant_sex_test` exists locally with integer `id`, integer `plant_id`, vendor/test-code fields, timestamp fields, result fields, and created/updated timestamps.
- The database rejects blank vendor/test codes, impossible timestamp ordering, pending rows with results, received rows with neither conclusive nor inconclusive results, duplicate `(vendor_name, vendor_test_code)`, and more than one open pending test per plant.
- The local Atlas migration and cloud Atlas migration both hash cleanly and dry-run successfully.

Gateway and cloud acceptance:

- `CatalogRequest` requires `sex_tests` and `CatalogResponse` reports a `sex_tests` count.
- The gateway local catalog collector projects `PlantSexTest` rows into `CatalogPlantSexTest`.
- The hosted gateway catalog route upserts `CloudPlantSexTest` rows idempotently.
- Shared contract tests reject omitted required nullable fields such as `assay_name`, `sample_sent_at`, `result_received_at`, `result_sex_key`, and `notes`.

Command acceptance:

- Bulk create creates one pending test row per plant and rejects unknown plants, duplicate plant keys in one request, duplicate vendor test codes, and a second pending test for the same plant.
- Bulk result requires an explicit `result_received_at`; conclusive results update both `plant_sex_test` and `plant.sex_key`; inconclusive results update only `plant_sex_test`; both create a sex-observation event with sex-test metadata.
- Existing `plants:bulk-sex` still updates plant sex without touching `plant_sex_test`.

Browser API acceptance:

- `GET /api/breeding-logbook/plants` includes `sex_tests` arrays inline on every plant row.
- `GET /api/breeding-logbook/plants/{plant_key}` includes the same sex-test history through `detail.plant.sex_tests`.
- The three sex-test write routes enqueue typed commands and return `CommandResponse`.
- Missing/invalid plant keys, sex test IDs, blank vendor codes, and missing result receipt timestamps produce 4xx responses before command enqueue.

Frontend acceptance:

- The plant list displays sex-test code/status and can search by vendor test code.
- The plant list can filter untested, pending, resulted, and inconclusive plants.
- Selecting multiple plants and opening the sex-test panel allows entry of one vendor test code per plant and submits one bulk-create command.
- Pending test codes remain visible after command acceptance even before the projection catches up.
- The pending-results panel requires the explicit received timestamp and allows Female, Male, or Inconclusive per pending test.
- Conclusive result submission updates the visible current sex optimistically/pending and reconciles with the projected server row.
- Plant detail shows sex-test history and supports one-off add/edit/result actions.

Recommended final validation commands:

    uv run pytest apps/shared/tests/test_cloud_contract.py -q
    uv run pytest apps/gateway/tests/test_sync.py apps/gateway/tests/test_gateway_boundary_guardrails.py -q
    uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q
    uv run pytest apps/tests/invariants -q
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test
    git diff --check

Before committing, run:

    make fix


## Idempotence and Recovery

The SQLModel edits, DTO edits, service edits, and frontend edits are source-owned and safe to repeat in a normal git worktree. `scripts/gen-hosted-contract` is safe to rerun after API schema changes and should be rerun whenever browser DTOs or routes change.

Atlas migration generation is repeatable only before the migration is committed. If Atlas generates a bad migration, inspect and fix the source SQLModel first, then regenerate or carefully patch the migration with an explanation in this plan. Do not apply app-start DDL or ad hoc SQL to bypass Atlas.

Applying `atlas migrate apply --env local` mutates the local database. Before applying, create the compressed custom-format backup described in `docs/database.md`. If a local apply fails before commit, inspect Atlas output and PostgreSQL state before retrying. Restore into a fresh database for rollback investigation; do not casually restore over the live database.

Command execution should be transactional. The gateway sex-test command handlers must run inside the existing `AsyncSession(...), session.begin()` transaction so that a partial batch does not leave some plants/tests updated when another row fails validation.

If the frontend optimistic state diverges from the hosted projection, invalidate the affected plant list/detail queries through the existing `invalidatePlantsReads()` path and keep failed pending commands visible with the existing command error handling. Do not silently drop failed sex-test commands from the UI.

Existing dirty worktree changes in wiki files and `scripts/lint.py` predate this plan. Do not revert or modify them unless the operator explicitly asks.


## Artifacts and Notes

Milestone 1 evidence:

- Generated local migration: `migrations/20260701235933_plant_sex_tests.sql`.
- Focused storage tests: `apps/shared/tests/test_plant_sex_test_models.py`.

Milestone 2 evidence:

- Generated cloud migration: `cloud/migrations/20260702001559_plant_sex_tests.sql`.
- Focused contract/projection tests updated in `apps/shared/tests/test_cloud_contract.py`, `apps/gateway/tests/test_sync.py`, `apps/gateway/tests/test_cloud_client.py`, `apps/control-plane/tests/test_api.py`, and `apps/control-plane/tests/test_control_plane_boundary_guardrails.py`.

Initial planning evidence:

- `apps/shared/src/dirt_shared/models/plant.py` currently defines `Plant`, `PlantLkuSex`, and `PlantEvent`, but no sex-test table.
- `apps/shared/src/dirt_shared/cloud_contract.py` currently includes breeding plant command payloads and catalog plant DTOs, but no sex-test catalog or command DTOs.
- `apps/gateway/src/dirt_gateway/breeding_commands.py` currently handles bulk sex by updating `Plant.sex_key` and adding sex-observation events.
- `web-ui/src/features/plants/PlantsWorkspace.tsx` and `plantsMutations.ts` already provide the selection, bulk action, and pending-command patterns this feature should reuse.


## Interfaces and Dependencies

New local storage interface:

- `dirt_shared.models.PlantSexTest`
- PostgreSQL table `plant_sex_test`
- Migration under `migrations/`

New cloud storage interface:

- `dirt_control.models.CloudPlantSexTest`
- PostgreSQL table `cloud_plant_sex_test`
- Migration under `cloud/migrations/`

New shared gateway/catalog interfaces:

- `dirt_shared.cloud_contract.CatalogPlantSexTest`
- `CatalogRequest.sex_tests`
- `CatalogResponse.sex_tests`

New shared command interfaces:

- Command type `breeding_sex_tests_bulk_create`
- Command type `breeding_sex_test_update`
- Command type `breeding_sex_tests_bulk_result`
- `BreedingBulkCreateSexTestsPayload`
- `BreedingUpdateSexTestPayload`
- `BreedingBulkResultSexTestsPayload`

New hosted browser API interfaces:

- `BreedingLogbookSexTestResponse`
- `BreedingLogbookPlantRowResponse.sex_tests`
- `POST /api/breeding-logbook/sex-tests:bulk-create`
- `POST /api/breeding-logbook/sex-tests/{sex_test_id}:update`
- `POST /api/breeding-logbook/sex-tests:bulk-result`

New frontend interfaces:

- `PlantSexTest`
- `PlantRow.sexTests`
- sex-test bulk-create mutation
- sex-test update mutation
- sex-test bulk-result mutation
- plant list sex-test filters/search
- plant detail sex-test history

External dependency:

- No Farmer Freeman API integration is required. Farmer Freeman and EZ-XY are manual-entry values in v1. The only external value is the vendor-owned test code typed by the operator from the kit/result materials.


## Revision Notes

- 2026-07-01 / Codex: Initial ExecPlan drafted from operator-approved design decisions.
