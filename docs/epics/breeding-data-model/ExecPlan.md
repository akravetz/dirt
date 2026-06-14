# Data Model Cleanup and Breeding Records

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, Dirt can track a real breeding program while also cleaning up the broader data-model habit of adding parallel text identifiers to Dirt-owned tables. Every table uses integer `id` as its canonical identity across local relationships, sync payloads, configuration references, and hosted projections. Breeding records add only the extra keys that are real domain artifacts, such as `plant.key`: the unique human-readable plant identifier printed on tags and used in notes/photos.

Each plant has a required strain and cultivar through its plant line, optional seed-lot or clone provenance, durable lifecycle timestamps, current and historical tent position, daily notes, and breeding events such as pollen collection or sex observation. The hosted UI can answer "which plants are currently in this tent and where are they?" directly from plant location history instead of inferring that from `growrun`.

This matters because breeding records must survive tent moves, culling, flowering runs, future clone/mother workflows, and parent selection. `growrun` currently owns plant identity, strain, germination date, and flower date in ways that are no longer truthful. The target architecture makes the individual plant the durable record, makes `plant_location_history` the occupancy model for tents and grid positions, and removes grow-run-centered compatibility shims rather than preserving stale A-D assumptions.

The work is complete when a developer can query current plants in a tent with `plant_location_history.end_at IS NULL`, see plant tag keys such as `SBBS-R1-001` without confusing those keys for database identity, record free-text notes and breeding events per plant, record internal crosses and resulting seed lots, move plants between tents without changing identity, and run the hosted dashboard against generated API contracts that no longer expose `grow_run_id` as plant identity scope.


## Progress

- [x] (2026-06-14T00:00Z) Drafted the data-model-first ExecPlan from the user's breeding-program requirements and the repo's current `growrun`/`plant` model.
- [x] (2026-06-14T00:00Z) Revised the plan into a broader data-model cleanup plan: integer `id` is canonical Dirt identity, parallel text `*_id` columns are not allowed for human convenience, and plant tag values use `key`.
- [x] (2026-06-14T02:33Z) Milestone 1 complete: inspected local source rows and active local control-plane dev projection, and finalized explicit plant key mapping for all current plants.
- [x] (2026-06-14T02:54Z) Milestone 2 complete: added local SQLModel breeding tables and cut `Plant` over to durable integer identity plus required `key`, line/provenance FKs, generated provenance booleans, lifecycle timestamps, and breeding selection fields.
- [x] (2026-06-14T03:42Z) Milestone 3 complete: backed up the live local database, applied migration `20260614024621_breeding_data_model.sql`, and ran acceptance SQL.
- [x] Implement local SQLModel tables, constraints, generated columns, and Atlas migration.
- [x] (2026-06-14T03:58Z) Milestone 4 complete: local shared/voice services and tests now use integer `Plant.id`, displayed `Plant.key`, and current occupancy from `plant_location_history.end_at IS NULL`.
- [x] (2026-06-14T04:18Z) Milestone 5 complete: gateway catalog DTOs, hosted cloud projection tables, and control-plane sync/API internals now use source integer plant identity, plant keys, line/seed-lot/location projections, and no grow-run plant scope.
- [x] (2026-06-14T04:20Z) Milestone 6 complete: hosted browser plant list/detail contracts, generated frontend schema, and dashboard/detail UI now use source integer plant identity, plant keys, line identity, current grid positions, lifecycle timestamps, and no moisture target or grow-run plant fields.
- [x] Cut over services, gateway/cloud sync, hosted browser API, and generated frontend contracts.
- [x] (2026-06-14T04:36Z) Milestone 7 complete: retired source-owned `growrun` code/schema, removed `snapshot.growrun_id`, added the final local Atlas migration, deleted dead plant sticker UI, updated current docs, and validated.
- [x] (2026-06-14T04:36Z) Validate locally and record implementation evidence.


## Surprises & Discoveries

- Observation: The current source-of-truth plant model is still grow-run scoped.
  Evidence: `apps/shared/src/dirt_shared/models/plant.py` enforces `UniqueConstraint("growrun_id", "plant_id")`; `apps/shared/src/dirt_shared/models/grow_run.py` stores `germination_date`, `flower_start_date`, `strain`, `plant_count`, and `is_current`.

- Observation: Hosted cloud plant projection repeats the grow-run scope.
  Evidence: `apps/control-plane/src/dirt_control/models/cloud.py` defines `CloudPlant` with unique key `(site_id, tent_id, grow_run_id, plant_id)` and `CloudPlantMetricStream` includes `grow_run_id`.

- Observation: Several existing Dirt tables use integer `id` plus text `*_id` as a parallel identity.
  Evidence: `site.site_id`, `tent.tent_id`, `device.device_id`, and `growrun.grow_run_id` follow this pattern. This plan must not copy that pattern into new breeding tables unless the text key is owned by a real external, hardware, vendor, protocol, file, or domain workflow.

- Observation: Plant-breeding standards and tools separate germplasm identity, seed or accession provenance, crosses/pedigree, individual plants, and observations.
  Evidence: BrAPI, Breedbase, MCPD, and MIAPPE all model these as separate concepts rather than overloading one "plant" row. Relevant references: `https://brapi.org/`, `https://plant-breeding-api.readthedocs.io/`, `https://solgenomics.github.io/sgn/`, `https://www.genesys-pgr.org/descriptorlists/0cd31350-234b-4ebf-80bc-fc65f14f7541`, and `https://www.miappe.org/`.

- Observation: The local source database currently has 9 plant rows across two current grow runs.
  Evidence: `psql` on `dirt` found main plants `a`-`d` in grow run `main-2026-03-15` and breeding plants `r1`-`r5` in grow run `breeding-track-a-2026-04-28`; both grow runs are current and their `plant_count` values match actual plant rows.

- Observation: The active local control-plane dev database is `dirt_cloud_dev_7ff9482e8f`, and it mirrors the same grow-run-scoped plant identities.
  Evidence: `var/dev/control-plane/state.json` points at `dirt_cloud_dev_7ff9482e8f`; `cloud_plant` has 9 rows keyed by `site_id`, `tent_id`, `grow_run_id`, and `plant_id`; `cloud_plant_metric_stream` has 4 rows for main plant `a`.

- Observation: Local source snapshots are entirely grow-run scoped to the main tent today.
  Evidence: `snapshot` has 14,642 rows, all with `growrun_id` set; grouped inspection found only `main/main-2026-03-15`, from `2026-03-23 13:05:43.89886-06` through `2026-06-13 20:32:06.77961-06`.

- Observation: Local plant metric stream ownership is already through `plant_metric_stream`, not a plant column.
  Evidence: `plant.moisture_capability_id` does not exist; `plant_metric_stream` has 12 local rows: four streams each for plant row ids 1, 3, and 4, and none for row ids 2 or 5-9. The active cloud dev projection currently has only the four streams for main plant `a`.

- Observation: This installed Atlas canary gates every clean desired-state extension bootstrap path behind `atlas login`.
  Evidence: `composite_schema`, an Atlas `docker "postgres"` dev block, and loader-emitted `CREATE EXTENSION IF NOT EXISTS btree_gist` each failed with `requires 'atlas login'` or `extensions are available to logged-in users only`. The migration itself dry-runs because it creates `btree_gist` before location exclusion constraints. A synced diff check passed only when Atlas was pointed at an externally preinitialized disposable Postgres dev URL with `btree_gist` already installed.

- Observation: `growrun` cannot be dropped by the Milestone 3 migration while current desired SQLModel metadata still contains `GrowRun` and `Snapshot.growrun_id`.
  Evidence: `apps/shared/src/dirt_shared/models/snapshot.py` still defines `growrun_id` with a FK to `growrun.id`, and `apps/shared/src/dirt_shared/models/__init__.py` still imports `GrowRun`.

- Observation: Running shared and voice pytest suites concurrently can race on shared Postgres test-template setup.
  Evidence: A worker-reported parallel run hit `driver: bad connection`; sequential `uv run pytest apps/shared/tests -q` and `uv run pytest apps/voice/tests -q` both passed.


## Decision Log

- Decision: Retire `growrun` as a plant identity, strain, and lifecycle owner.
  Rationale: Plant identity must survive tent moves and future flowering tents. A grow run is an operational cohort concept, but Dirt's current `growrun` table has become the canonical owner of plant facts that belong to individual plants or plant lines.
  Date/Author: 2026-06-14 / User + Codex

- Decision: Use integer `id` as Dirt's canonical identity, including Dirt-owned sync and configuration boundaries.
  Rationale: Parallel text `*_id` columns make the data model harder to reason about when Dirt owns both sides. Readability alone is not a reason to create a second identity.
  Date/Author: 2026-06-14 / User + Codex

- Decision: Replace the old A-D scoped plant text identity with `plant.key`, not `plant.plant_id`.
  Rationale: Values such as `SBBS-R1-001` are real breeding tags that people will write on labels, notes, and photos, but they are not the database identity. The database identity remains `plant.id`.
  Date/Author: 2026-06-14 / User + Codex

- Decision: Add storage and source comments for `plant.key`.
  Rationale: `key` is intentionally generic because it is the plant's domain key, but the semantics are not obvious from the name alone. PostgreSQL column comments and SQLModel/SQLAlchemy source comments should explain that it is the unique human-readable plant identifier printed on tags and used in notes/photos.
  Date/Author: 2026-06-14 / User + Codex

- Decision: Represent purchased seed lines and internally bred lines with the same `plant_line` table.
  Rationale: Both purchased and internally bred material still has strain and cultivar identity. Purchased lines can leave `project_code` and `generation_label` null or partially known without requiring a separate model.
  Date/Author: 2026-06-14 / User + Codex

- Decision: Require both `strain` and `cultivar` on `plant_line`.
  Rationale: The user wants those fields to be explicit for purchased seeds and internal lines. Unknown parents do not excuse missing strain/cultivar labels in Dirt's working record.
  Date/Author: 2026-06-14 / User + Codex

- Decision: Include clone provenance now, but keep it simple.
  Rationale: Cannabis breeding commonly uses clones, mothers, and reversed plants. The schema should not assume every plant germinated from seed, but v1 does not need a separate mother/clone subsystem.
  Date/Author: 2026-06-14 / Codex

- Decision: Store core lifecycle state directly on `plant`, not only as events.
  Rationale: `germinated_at`, `veg_started_at`, `flower_started_at`, `culled_at`, `culled_reason`, `harvested_at`, and `selected_for_breeding_at` are first-class plant state queried by UI and services. Requiring every caller to find the latest event of each type would create avoidable complexity.
  Date/Author: 2026-06-14 / Codex

- Decision: Use `plant_event` for irregular breeding actions and observations.
  Rationale: Event rows are a good fit for facts such as pollen collected, sex observed, reversed, clone taken, and transplant notes. They avoid widening `plant` for every future breeding action.
  Date/Author: 2026-06-14 / User + Codex

- Decision: Use `plant_location_history` with `grid_position` as free text and current occupancy derived from `end_at IS NULL`.
  Rationale: The grid system is not finalized, but the UI needs current tent occupancy now. A text `grid_position` supports values like `A1` or `D5`; partial unique indexes and exclusion constraints keep current and overlapping locations coherent.
  Date/Author: 2026-06-14 / User + Codex

- Decision: Do not link plant location history to `zone`.
  Rationale: Current `zone` usage is for devices, schedules, snapshots, commands, and readings. Plants exist in tents and have grid/tray positions; no app behavior needs a plant-zone relationship.
  Date/Author: 2026-06-14 / User + Codex

- Decision: Model seed production canonically as `seed_lot` rows, not only as plant events.
  Rationale: A produced seed lot is durable source material for future plants. A `seeds_produced` event can still be recorded as a note-like event, but the seed lot is the queryable artifact used by propagation.
  Date/Author: 2026-06-14 / Codex

- Decision: Do not model breeding business state as string enum/check-list columns.
  Rationale: At the database/application boundary those values are still string contracts. Concrete facts, generated columns, lookup tables, and constraints make drift harder and keep the model closer to the domain.
  Date/Author: 2026-06-14 / User + Codex


## Outcomes & Retrospective

Milestone 1 validation completed on 2026-06-14T02:33Z. Commands run:

- `rg -n "growrun|grow_run_id|GrowRun|germination_date|flower_start_date|plant_count|is_current" apps web-ui contracts migrations docs -g '*'`
- `rg -n "class Plant|CloudPlant|CatalogPlant|PlantMetricStream|plant_location|plant_note|plant_event" apps web-ui contracts -g '*'`
- `psql` schema inspection for local `growrun` and `plant`
- `psql` row inspection for local `growrun`, `plant`, `plant_metric_stream`, and `snapshot`
- `psql` row inspection for active local control-plane dev `cloud_plant` and `cloud_plant_metric_stream`

Explicit migration key mapping:

| Plant row id | Tent | Old plant text id | New `plant.key` |
|---:|---|---|---|
| 1 | main | `a` | `SBBS-R1-001` |
| 2 | main | `b` | `SBBS-R1-002` |
| 3 | main | `c` | `SBBS-R1-003` |
| 4 | main | `d` | `SBBS-R1-004` |
| 5 | breeding | `r1` | `SBBS-R1-005` |
| 6 | breeding | `r2` | `SBBS-R1-006` |
| 7 | breeding | `r3` | `SBBS-R1-007` |
| 8 | breeding | `r4` | `SBBS-R1-008` |
| 9 | breeding | `r5` | `SBBS-R1-009` |

No implementation migration has been generated yet. Later migration work must preserve these integer row ids and preserve `plant_metric_stream.plant_id` ownership.

Milestone 2 implementation completed on 2026-06-14T02:54Z. Changed files:

- `apps/shared/src/dirt_shared/models/plant.py`
- `apps/shared/src/dirt_shared/models/__init__.py`

Validation evidence:

- `uv run --package dirt-shared python scripts/atlas-load-sqlmodel.py postgresql` passed and emitted the new target DDL, including `plant_line`, `cross_event`, `seed_lot`, updated `plant`, `plant_location_history`, `plant_note`, `plant_event`, `COMMENT ON COLUMN plant.key`, generated columns, partial current-location indexes, and location exclusion constraints.
- `uv run ruff check apps/shared/src/dirt_shared/models/plant.py apps/shared/src/dirt_shared/models/__init__.py` passed.
- `git diff --check` passed.
- `uv run pytest apps/shared/tests -q` produced 186 passed and 12 failed. The failures are expected at this milestone because Milestone 4 has not yet cut shared services and tests from removed `Plant.plant_id`, `Plant.growrun_id`, and `Plant.display_order` to `Plant.key`, `plant_location_history`, and integer `plant.id`.

Cleanup note: the implementation simplify pass removed extra FK indexes that were not in the target DDL so the model stays close to the ExecPlan schema.

Milestone 3 migration review reached the pre-apply gate on 2026-06-14T03:31Z. Changed files:

- `migrations/20260614024621_breeding_data_model.sql`
- `migrations/atlas.sum`

Migration summary:

- Creates `btree_gist`, `plant_line`, `cross_event`, `seed_lot`, `plant_location_history`, `plant_note`, and `plant_event`.
- Backfills one purchased SBBS R1 plant line and seed lot for the current Sirius Black x BS01 material. The migration records unknown vendor as `Unknown vendor` because no vendor exists in current grow-run rows.
- Maps existing plant row ids 1-9 to `SBBS-R1-001` through `SBBS-R1-009`, preserving integer `plant.id` and `plant_metric_stream.plant_id` ownership.
- Creates current location rows with main positions `A1`-`D1` and breeding positions `A1`-`E1`.
- Backfills `germinated_at` and `flower_started_at` from existing current grow-run dates.
- Removes obsolete local `plant` grow-run scope, display, sticker/status/purple, and moisture target columns.
- Leaves `growrun` and `snapshot.growrun_id` for later retirement because current desired source still depends on them.

Validation evidence:

- `uv run --package dirt-shared python scripts/atlas-load-sqlmodel.py postgresql` passed.
- `atlas migrate hash --env local` passed and updated `migrations/atlas.sum`.
- `atlas migrate apply --env local --dry-run` passed.
- `atlas migrate apply --url "docker://postgres/17/dev?search_path=public" --dir "file://migrations"` applied all 45 local migrations to an ephemeral Postgres dev database successfully.
- `git diff --check` passed.
- `atlas migrate diff breeding_data_model_check --env local` fails in the default repo config because the desired dev DB lacks `btree_gist` before evaluating SQLModel exclusion constraints.
- The same diff check passed with an externally preinitialized disposable dev URL: `atlas migrate diff breeding_data_model_check --env local --dev-url "postgres://postgres:dev@127.0.0.1:55433/dev?sslmode=disable&search_path=public"` after `CREATE EXTENSION IF NOT EXISTS btree_gist;` in that disposable database.

Pre-apply gate: before mutating the live local `dirt` database, take the compressed custom-format backup from `docs/database.md`, run `atlas migrate apply --env local`, and then run the acceptance SQL in this ExecPlan.

Milestone 3 live local apply completed on 2026-06-14T03:42Z after user confirmation. Backup:

- `var/db-backups/dirt-2026-06-13-213926-pre-breeding-data-model.dump`

Apply and acceptance evidence:

- `atlas migrate apply --env local` applied `20260614024621_breeding_data_model.sql` successfully.
- `atlas migrate status --env local` reports current version `20260614024621`, 45 executed files, and 0 pending files.
- Plant acceptance SQL returned 9 plants with keys `SBBS-R1-001` through `SBBS-R1-009`, one `plant_line`, one `seed_lot`, expected germination timestamps, and expected flower timestamps.
- Current location acceptance SQL returned 9 current `plant_location_history` rows: main `A1`-`D1` and breeding `A1`-`E1`.
- `btree_gist` is installed, `plant.key` has the required SQL column comment, both plant-location exclusion constraints exist, and `plant_metric_stream` still has 12 rows across 3 plants.
- `moisture_target_low` and `moisture_target_high` no longer exist in local information schema.
- `plant_location_history` has no `zone_id` or `position` column.
- `growrun.grow_run_id` and `snapshot.growrun_id` still exist and are intentionally deferred to later grow-run retirement milestones.
- The generic `cloud_outbox.event_type` column still exists; this is not the new `plant_event` kind model and is not a plant business-state enum.
- `uv run pytest apps/shared/tests -q` still reports 186 passed and 12 failed because Milestone 4 has not yet cut shared services/tests from removed `Plant.plant_id`, `Plant.growrun_id`, and `Plant.display_order`.

Milestone 4 completed on 2026-06-14T03:58Z. Changed files:

- `apps/shared/src/dirt_shared/services/readings.py`
- `apps/shared/src/dirt_shared/services/daily_sensors.py`
- `apps/shared/src/dirt_shared/services/grow_state.py`
- `apps/shared/tests/test_daily_sensors.py`
- `apps/shared/tests/test_grow_state.py`
- `apps/shared/tests/test_scoped_identity_models.py`
- `apps/voice/src/dirt_voice/tools/sensors.py`
- `apps/voice/tests/test_sensor_tools.py`

Outcome:

- Plant moisture capability/read queries use current `PlantLocationHistory.end_at IS NULL`, return/display `Plant.key`, and order by `PlantLocationHistory.grid_position` then `Plant.key`.
- Daily sensor snapshots and voice current-status soil moisture maps are keyed by plant tag keys such as `SBBS-R1-001`.
- `GrowStateService` now derives stage, week, plant count, and current payload from current plant lifecycle timestamps and current tent occupancy while keeping legacy grow-run accessors only until grow-run retirement.
- Agent-owned local tests now use `Plant.key` and `PlantLocationHistory` instead of removed `Plant.plant_id`, `Plant.growrun_id`, and `Plant.display_order`.

Validation evidence:

- `uv run pytest apps/shared/tests -q` passed with 198 tests.
- `uv run pytest apps/voice/tests -q` passed with 2 tests.
- `uv run ruff check` on touched local-service/test files passed.
- `git diff --check` passed.

Known gap:

- Snapshot `growrun_id` write paths in daily report and camera publisher remain intentionally deferred with the remaining `growrun` table/model retirement.

Milestone 5 completed on 2026-06-14T04:18Z. Changed files:

- `apps/shared/src/dirt_shared/cloud_contract.py`
- `apps/shared/tests/test_cloud_contract.py`
- `apps/gateway/src/dirt_gateway/local.py`
- `apps/gateway/tests/test_sync.py`
- `apps/control-plane/src/dirt_control/models/cloud.py`
- `apps/control-plane/src/dirt_control/models/__init__.py`
- `apps/control-plane/src/dirt_control/api/gateway.py`
- `apps/control-plane/src/dirt_control/api/browser.py`
- `apps/control-plane/tests/test_api.py`
- `cloud/migrations/20260614040640_breeding_cloud_projection.sql`
- `cloud/migrations/atlas.sum`

Outcome:

- Gateway-to-cloud catalog DTOs now project plant lines, seed lots, current plant locations, plants keyed by source integer `Plant.id`, and plant metric streams keyed by source integer plant id plus device/capability/metric.
- Hosted cloud mirror tables now use `source_plant_id` for Dirt-owned plant identity, carry `key` as the plant tag, and mirror line, seed-lot, and current location data needed by the browser.
- Hosted control-plane gateway upsert logic no longer depends on `grow_run_id` for plant or plant metric stream identity.
- The cloud migration drops and recreates the old grow-run-scoped hosted projection tables because old cloud projection rows cannot be truthfully backfilled into the new local integer plant IDs without a source catalog refresh.
- Browser API internals were minimally updated to read the new cloud projection while route shape and frontend contract regeneration remain in Milestone 6.

Validation evidence:

- `uv run pytest apps/shared/tests/test_cloud_contract.py -q` passed with 14 tests.
- `uv run pytest apps/gateway/tests -q` passed with 31 tests.
- `uv run pytest apps/control-plane/tests -q` passed with 53 tests.
- `uv run ruff check` on touched Milestone 5 files passed.
- `atlas migrate apply --url "docker://postgres/17/dev?search_path=public" --dir "file://cloud/migrations"` applied the cloud migration series to an ephemeral PostgreSQL 17 database successfully.
- `atlas migrate diff breeding_cloud_projection_check --env cloud` reported the migration directory synced with desired state.
- `git diff --check` passed.

Milestone 6 completed on 2026-06-14T04:20Z. Changed files:

- `apps/control-plane/src/dirt_control/api/browser.py`
- `apps/control-plane/tests/test_api.py`
- `contracts/hosted-browser-v1.json`
- `web-ui/src/api-client/generated/hosted-schema.ts`
- `web-ui/src/routes/index.tsx`
- `web-ui/src/routes/tents.$tentId.plants.$plantId.tsx`

Outcome:

- Hosted browser plant list/detail responses now return current plants through `CloudPlantLocation.end_at IS NULL`, include integer source plant `id`, `key`, line identity, `grid_position`, current location, lifecycle timestamps, and omit old `grow_run_id` and moisture target fields.
- The hosted OpenAPI browser contract and generated TypeScript schema were regenerated with `scripts/gen-hosted-contract`.
- The dashboard plant cards link by plant `key`, show current grid position and line identity, and no longer render moisture target text.
- The plant detail page shows line identity, current location, lifecycle timestamps, telemetry, projected wiki content, and note/event panels. Note/event arrays are currently empty because Milestone 5 did not add cloud note/event projection tables or gateway sync.

Validation evidence:

- `uv run pytest apps/control-plane/tests/test_api.py -q` passed with 42 tests.
- `uv run pytest apps/control-plane/tests -q` passed with 53 tests.
- `scripts/gen-hosted-contract` passed.
- `uv run ruff check apps/control-plane/src/dirt_control/api/browser.py apps/control-plane/tests/test_api.py` passed.
- `pnpm --dir web-ui typecheck` passed.
- `pnpm --dir web-ui lint` passed.
- `pnpm --dir web-ui test` passed with 2 files and 3 tests.
- `git diff --check` passed.

Milestone 7 completed on 2026-06-14T04:36Z. Changed files:

- `apps/shared/src/dirt_shared/models/grow_run.py`
- `apps/shared/src/dirt_shared/models/snapshot.py`
- `apps/shared/src/dirt_shared/models/__init__.py`
- `apps/shared/src/dirt_shared/models/enums.py`
- `apps/shared/src/dirt_shared/services/{scope,grow_state,camera_publisher,daily_report,daily_synthesis}.py`
- `apps/shared/src/dirt_shared/config.py`
- `apps/shared/tests/{test_capture,test_daily_report,test_grow_state}.py`
- `migrations/20260614042851_retire_growrun.sql`
- `migrations/atlas.sum`
- `web-ui/src/ui/PlantSticker.tsx`
- `web-ui/src/styles.css`
- `docs/database.md`
- `docs/grow-state.md`
- `docs/wiki/{conventions,data-architecture,workflows/daily-update}.md`
- `wiki/AGENTS.md`

Outcome:

- Removed the source-owned `GrowRun` SQLModel and all current source imports of `dirt_shared.models.grow_run`.
- Removed `Snapshot.growrun_id` from SQLModel and stopped camera publisher and daily-report snapshot write paths from looking up or writing grow-run scope.
- Removed unused grow-stage/plant-status/plant-sticker enum exports from source; `plant_status` and `plant_sticker` were already dropped by `20260614024621_breeding_data_model.sql`, and no local `grow_stage` type exists in the migration series.
- Added local migration `20260614042851_retire_growrun.sql`, which drops `snapshot.growrun_id` and `growrun`. The migration was generated with a disposable Postgres dev DB preinitialized with `btree_gist` because default Atlas desired-state loading still cannot create the exclusion-constraint operator classes before loading SQLModel DDL.
- Moved remaining grow-state tests to plant lifecycle/current-location context and removed grow-run compatibility assertions.
- Deleted unused `web-ui/src/ui/PlantSticker.tsx` and the now-unused sticker CSS tokens after invariants flagged dead UI code.
- Updated current database, grow-state, wiki workflow, and wiki routing docs so they no longer describe grow-run-scoped plant identity.

Validation evidence:

- `uv run --package dirt-shared python scripts/atlas-load-sqlmodel.py postgresql` passed and emitted desired DDL without `growrun` or `snapshot.growrun_id`.
- `atlas migrate diff retire_growrun --env local` failed in the default repo config with the known `btree_gist` desired-state loader issue.
- `atlas migrate diff retire_growrun --env local --dev-url "postgres://postgres:dev@127.0.0.1:55433/dev?sslmode=disable&search_path=public"` passed after creating `btree_gist` in a disposable Postgres 17 container.
- `atlas migrate hash --env local` passed.
- `atlas migrate apply --env local --dry-run` passed and reported one pending migration, `20260614042851`, with two SQL statements. This did not apply the migration to the live local `dirt` database.
- `atlas migrate apply --url "docker://postgres/17/dev?search_path=public" --dir "file://migrations"` applied all 46 local migrations to an ephemeral PostgreSQL 17 database successfully.
- `uv run pytest apps/shared/tests -q` passed with 199 tests.
- `uv run pytest apps/gateway/tests -q` passed with 31 tests.
- `uv run pytest apps/control-plane/tests -q` passed with 53 tests.
- `uv run pytest apps/camera-agent/tests -q` passed with 7 tests.
- `uv run pytest apps/tests/invariants/ -q` passed with 41 tests; invariants were not edited.
- `pnpm --dir web-ui typecheck` passed.
- `pnpm --dir web-ui lint` passed.
- `pnpm --dir web-ui test` passed with 2 files and 3 tests.
- `make fix` passed; it reformatted two Python files and found no lint errors after fixes.
- `git diff --check` passed.
- Main-agent re-verification passed after review feedback: SQLModel DDL generation, live dry-run of pending migration, disposable PostgreSQL full migration replay, shared/gateway/control-plane/camera-agent tests, invariants, web-ui typecheck/lint/test, `make fix`, and `git diff --check` all passed. The only active-source grep hits for retired plant fields are negative API assertions and unrelated PTZ preset sticker metadata.

Known gap:

Milestone 7 live local apply completed on 2026-06-14 after user confirmation. Backup:

- `var/db-backups/dirt-2026-06-13-230155-pre-retire-growrun.dump`

Apply and acceptance evidence:

- `atlas migrate apply --env local` applied `20260614042851_retire_growrun.sql` successfully.
- `atlas migrate status --env local` reports current version `20260614042851`, 46 executed files, and 0 pending files.
- Acceptance SQL found no `growrun_id` or `grow_run_id` columns in the live local database.
- `to_regclass('public.growrun')` returned null, confirming the `growrun` table is absent.
- Plant acceptance SQL still returns 9 plants with keys `SBBS-R1-001` through `SBBS-R1-009`, expected line identity, and expected lifecycle timestamps.
- Current location acceptance SQL still returns 9 current `plant_location_history` rows: breeding `A1`-`E1` and main `A1`-`D1`.


## Context and Orientation

Dirt uses SQLModel table classes under `apps/shared/src/dirt_shared/models/` for local PostgreSQL state, Atlas migrations under `migrations/`, and a hosted control-plane projection under `apps/control-plane/src/dirt_control/models/cloud.py`. Browser-facing hosted API response types are generated from FastAPI OpenAPI into `web-ui/src/api-client/generated/hosted-schema.ts`; do not hand-write hosted response interfaces in `web-ui/src/api-client/cloud.ts`.

The relevant implemented source files are:

- `apps/shared/src/dirt_shared/models/plant.py`: durable local plant, line, provenance, location, note, event, cross, seed-lot, and metric-stream tables.
- `apps/shared/src/dirt_shared/models/snapshot.py`: scoped snapshot metadata without grow-run ownership.
- `apps/shared/src/dirt_shared/services/grow_state.py`: plant/tent lifecycle context and stage-derived environmental targets based on current plant locations and lifecycle timestamps.
- `apps/shared/src/dirt_shared/cloud_contract.py`: gateway-to-control-plane catalog DTOs with integer source identities and plant tag keys.
- `apps/gateway/src/dirt_gateway/local.py` and `apps/gateway/src/dirt_gateway/sync.py`: local-to-cloud projection and outbox code.
- `apps/control-plane/src/dirt_control/models/cloud.py`: hosted mirror tables for plant lines, seed lots, plants, current locations, and metric streams.
- `apps/control-plane/src/dirt_control/api/browser.py`: hosted browser API responses consumed by the React dashboard.
- `web-ui/src/routes/index.tsx` and `web-ui/src/routes/tents.$tentId.plants.$plantId.tsx`: browser plant listing/detail surfaces using generated hosted types.

Use these repository rules while implementing:

- Read `docs/database.md` before editing SQLModel classes or Atlas migrations.
- Read `docs/rules/data-modeling.md` before adding or preserving persisted identifiers.
- Read `docs/rules/simple-clean-architecture.md` before making compatibility decisions.
- Read `docs/rules/boundary-contracts.md` before changing gateway, control-plane, outbox, or generated browser payloads.
- Read `docs/references/atlas/INDEX.md` before running Atlas commands or editing migration files.
- Read `docs/references/tanstack-router-v1/INDEX.md`, `docs/references/tailwind-v4/INDEX.md`, and `docs/references/modern-idiomatic-typescript/INDEX.md` before editing relevant web-ui route or TypeScript files.


## Proposed Data Model

The SQL below is the target shape. Implementation should migrate existing tables with `ALTER TABLE` where practical, but these `CREATE TABLE` statements define the final model and constraints.

Use `timestamptz` for timestamps. Application code must write UTC-aware datetimes; PostgreSQL stores the moment in time and renders it in the session timezone.

Some target FKs form a real cycle: plants can come from seed lots, produced seed lots can come from crosses, and crosses reference parent plants. The migration may create tables first and add those FKs with `ALTER TABLE` after all referenced tables exist. The final constraints must still match the target model below.

### `plant_line`

`plant_line` represents the genetic/market identity of a line of plants. It covers purchased seed lines and internal breeding lines. Purchased lines usually have `project_code IS NULL` and may have `generation_label IS NULL`; internal lines can use values such as `SBBS` and `R1`.

```sql
CREATE TABLE plant_line (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    project_code text NULL,
    generation_label text NULL,
    strain text NOT NULL,
    cultivar text NOT NULL,
    description text NULL,
    source_name text NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT uq_plant_line_identity UNIQUE NULLS NOT DISTINCT (
        project_code,
        generation_label,
        strain,
        cultivar
    ),
    CONSTRAINT ck_plant_line_project_code_not_blank CHECK (
        project_code IS NULL OR btrim(project_code) <> ''
    ),
    CONSTRAINT ck_plant_line_generation_label_not_blank CHECK (
        generation_label IS NULL OR btrim(generation_label) <> ''
    ),
    CONSTRAINT ck_plant_line_strain_not_blank CHECK (btrim(strain) <> ''),
    CONSTRAINT ck_plant_line_cultivar_not_blank CHECK (btrim(cultivar) <> ''),
    CONSTRAINT ck_plant_line_description_not_blank CHECK (
        description IS NULL OR btrim(description) <> ''
    ),
    CONSTRAINT ck_plant_line_source_name_not_blank CHECK (
        source_name IS NULL OR btrim(source_name) <> ''
    )
);
```

Constraints to implement:

- Primary key on `id`.
- Unique identity across `project_code`, `generation_label`, `strain`, and `cultivar` with `NULLS NOT DISTINCT` so duplicate external lines cannot be inserted by leaving nullable fields null.
- Required non-empty `strain` and `cultivar`.
- Nullable text fields must be either null or non-blank.

### `cross_event`

`cross_event` records an intentional breeding cross between two known Dirt plants. It is only for crosses where the parent plants are in Dirt. Purchased seed-line parent labels stay on `plant_line` notes/description until the actual parents exist as plants.

```sql
CREATE TABLE cross_event (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    resulting_line_id bigint NOT NULL,
    seed_parent_plant_id bigint NOT NULL,
    pollen_parent_plant_id bigint NOT NULL,
    pollinated_at timestamptz NOT NULL,
    pollen_parent_is_reversed boolean NULL,
    notes text NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT fk_cross_event_resulting_line
        FOREIGN KEY (resulting_line_id) REFERENCES plant_line(id) ON DELETE RESTRICT,
    CONSTRAINT fk_cross_event_seed_parent
        FOREIGN KEY (seed_parent_plant_id) REFERENCES plant(id) ON DELETE RESTRICT,
    CONSTRAINT fk_cross_event_pollen_parent
        FOREIGN KEY (pollen_parent_plant_id) REFERENCES plant(id) ON DELETE RESTRICT,
    CONSTRAINT ck_cross_event_distinct_parents CHECK (
        seed_parent_plant_id <> pollen_parent_plant_id
    ),
    CONSTRAINT ck_cross_event_notes_not_blank CHECK (
        notes IS NULL OR btrim(notes) <> ''
    )
);
```

Constraints to implement:

- Primary key on `id`.
- Required FK to the resulting `plant_line`.
- Required FKs to seed parent and pollen parent `plant` rows.
- Parents must be two different plant rows.
- `pollen_parent_is_reversed` is a nullable fact: `true` means reversed female pollen, `false` means regular male pollen, and `NULL` means not recorded.

### `seed_lot`

`seed_lot` represents acquired or produced seed material. It is the canonical source record for seed-grown plants.

```sql
CREATE TABLE seed_lot (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    line_id bigint NOT NULL,
    is_purchased boolean NOT NULL DEFAULT false,
    vendor_name text NULL,
    acquired_at timestamptz NULL,
    produced_by_cross_event_id bigint NULL,
    is_produced boolean GENERATED ALWAYS AS (produced_by_cross_event_id IS NOT NULL) STORED,
    seed_count integer NULL,
    notes text NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT fk_seed_lot_line
        FOREIGN KEY (line_id) REFERENCES plant_line(id) ON DELETE RESTRICT,
    CONSTRAINT fk_seed_lot_cross_event
        FOREIGN KEY (produced_by_cross_event_id) REFERENCES cross_event(id) ON DELETE RESTRICT,
    CONSTRAINT ck_seed_lot_not_purchased_and_produced CHECK (
        NOT (is_purchased AND produced_by_cross_event_id IS NOT NULL)
    ),
    CONSTRAINT ck_seed_lot_vendor_for_purchased CHECK (
        NOT is_purchased OR (vendor_name IS NOT NULL AND btrim(vendor_name) <> '')
    ),
    CONSTRAINT ck_seed_lot_vendor_only_when_purchased CHECK (
        is_purchased OR vendor_name IS NULL
    ),
    CONSTRAINT ck_seed_lot_seed_count_positive CHECK (
        seed_count IS NULL OR seed_count >= 0
    ),
    CONSTRAINT ck_seed_lot_notes_not_blank CHECK (
        notes IS NULL OR btrim(notes) <> ''
    )
);
```

Constraints to implement:

- Primary key on `id`.
- Required FK to `plant_line`.
- `is_purchased` is a stored fact.
- `is_produced` is generated from `produced_by_cross_event_id IS NOT NULL`.
- A seed lot cannot be both purchased and produced.
- Purchased seed lots must have a non-blank vendor and no internal cross.
- Produced seed lots reference a `cross_event`.
- Unknown source is represented as `is_purchased = false` and `produced_by_cross_event_id IS NULL`.
- `seed_count` cannot be negative.

### `plant`

`plant` is the durable individual plant record. A clone gets its own integer `id` and its own `key` even when genetically identical to its source plant.

```sql
CREATE TABLE plant (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    key text NOT NULL,
    line_id bigint NOT NULL,
    source_seed_lot_id bigint NULL,
    clone_source_plant_id bigint NULL,
    is_seed_grown boolean GENERATED ALWAYS AS (source_seed_lot_id IS NOT NULL) STORED,
    is_clone boolean GENERATED ALWAYS AS (clone_source_plant_id IS NOT NULL) STORED,
    name text NOT NULL,
    germinated_at timestamptz NULL,
    rooted_at timestamptz NULL,
    veg_started_at timestamptz NULL,
    flower_started_at timestamptz NULL,
    culled_at timestamptz NULL,
    culled_reason text NULL,
    harvested_at timestamptz NULL,
    selected_for_breeding_at timestamptz NULL,
    selected_for_breeding_reason text NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT uq_plant_key UNIQUE (key),
    CONSTRAINT fk_plant_line
        FOREIGN KEY (line_id) REFERENCES plant_line(id) ON DELETE RESTRICT,
    CONSTRAINT fk_plant_source_seed_lot
        FOREIGN KEY (source_seed_lot_id) REFERENCES seed_lot(id) ON DELETE RESTRICT,
    CONSTRAINT fk_plant_clone_source
        FOREIGN KEY (clone_source_plant_id) REFERENCES plant(id) ON DELETE RESTRICT,
    CONSTRAINT ck_plant_key_not_blank CHECK (btrim(key) <> ''),
    CONSTRAINT ck_plant_name_not_blank CHECK (btrim(name) <> ''),
    CONSTRAINT ck_plant_seed_or_clone_not_both CHECK (
        source_seed_lot_id IS NULL OR clone_source_plant_id IS NULL
    ),
    CONSTRAINT ck_plant_not_self_clone CHECK (
        clone_source_plant_id IS NULL OR clone_source_plant_id <> id
    ),
    CONSTRAINT ck_plant_seed_not_rooted_as_clone CHECK (
        source_seed_lot_id IS NULL OR rooted_at IS NULL
    ),
    CONSTRAINT ck_plant_clone_not_germinated CHECK (
        clone_source_plant_id IS NULL OR germinated_at IS NULL
    ),
    CONSTRAINT ck_plant_culled_reason_required CHECK (
        (culled_at IS NULL AND culled_reason IS NULL)
        OR (culled_at IS NOT NULL AND culled_reason IS NOT NULL AND btrim(culled_reason) <> '')
    ),
    CONSTRAINT ck_plant_culled_or_harvested_not_both CHECK (
        culled_at IS NULL OR harvested_at IS NULL
    ),
    CONSTRAINT ck_plant_selection_reason_not_blank CHECK (
        selected_for_breeding_reason IS NULL OR btrim(selected_for_breeding_reason) <> ''
    )
);

COMMENT ON COLUMN plant.key IS
    'Unique human-readable plant identifier printed on tags and used in notes/photos, e.g. SBBS-R1-001.';
```

Constraints to implement:

- Primary key on `id`.
- Globally unique `key`, no grow-run scope. This is the physical/domain plant tag, not the database identity.
- `plant.key` must have both the SQL column comment shown above and a SQLModel/SQLAlchemy source comment with the same meaning.
- Required FK to `plant_line`.
- Optional FK to `seed_lot` for seed-grown plants.
- Optional self-FK to clone source plant for clones.
- `is_seed_grown` and `is_clone` are generated from provenance FKs.
- Unknown propagation is represented as both provenance FKs null.
- A plant cannot be both seed-grown and clone-propagated.
- Culling requires a non-blank reason.
- A plant cannot be both culled and harvested.
- `selected_for_breeding_at` means approved parent used or planned for breeding, not merely "keep for now".

### `plant_location_history`

`plant_location_history` tracks current and past tent occupancy. `grid_position` is free text for v1 and can hold grid coordinates such as `A1`, `B1`, or `D5`.

```sql
CREATE TABLE plant_location_history (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    plant_id bigint NOT NULL,
    site_id bigint NOT NULL,
    tent_id bigint NOT NULL,
    grid_position text NOT NULL,
    start_at timestamptz NOT NULL,
    end_at timestamptz NULL,
    is_current boolean GENERATED ALWAYS AS (end_at IS NULL) STORED,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT fk_plant_location_plant
        FOREIGN KEY (plant_id) REFERENCES plant(id) ON DELETE RESTRICT,
    CONSTRAINT fk_plant_location_site
        FOREIGN KEY (site_id) REFERENCES site(id) ON DELETE RESTRICT,
    CONSTRAINT fk_plant_location_tent
        FOREIGN KEY (tent_id) REFERENCES tent(id) ON DELETE RESTRICT,
    CONSTRAINT ck_plant_location_grid_position_not_blank CHECK (btrim(grid_position) <> ''),
    CONSTRAINT ck_plant_location_time_order CHECK (
        end_at IS NULL OR end_at > start_at
    )
);

CREATE UNIQUE INDEX ux_plant_location_current_per_plant
    ON plant_location_history (plant_id)
    WHERE end_at IS NULL;

CREATE UNIQUE INDEX ux_plant_location_current_grid_position_per_tent
    ON plant_location_history (tent_id, grid_position)
    WHERE end_at IS NULL;

CREATE INDEX ix_plant_location_current_tent
    ON plant_location_history (tent_id, grid_position, plant_id)
    WHERE end_at IS NULL;

CREATE INDEX ix_plant_location_plant_start
    ON plant_location_history (plant_id, start_at DESC);

ALTER TABLE plant_location_history
    ADD CONSTRAINT ex_plant_location_no_overlap_per_plant
    EXCLUDE USING gist (
        plant_id WITH =,
        tstzrange(start_at, COALESCE(end_at, 'infinity'::timestamptz), '[)') WITH &&
    );

ALTER TABLE plant_location_history
    ADD CONSTRAINT ex_plant_location_no_overlap_per_tent_grid_position
    EXCLUDE USING gist (
        tent_id WITH =,
        grid_position WITH =,
        tstzrange(start_at, COALESCE(end_at, 'infinity'::timestamptz), '[)') WITH &&
    );
```

Constraints to implement:

- Primary key on `id`.
- Required FK to `plant`, `site`, and `tent`. There is no plant `zone_id`.
- `grid_position` must be non-blank text.
- `end_at` must be after `start_at` when present.
- Generated `is_current` field equals `end_at IS NULL`; application code should treat `end_at` as the source of truth.
- A plant can have only one current location.
- A tent position can have only one current plant.
- Exclusion constraints prevent overlapping historical locations for the same plant and overlapping historical occupancy for the same tent position. The migration must enable `btree_gist` if it is not already enabled.

### `plant_note`

`plant_note` stores free-text daily notes and observations. This is intentionally separate from structured trait scoring; add structured observations later only when the workflow requires it.

```sql
CREATE TABLE plant_note (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    plant_id bigint NOT NULL,
    observed_at timestamptz NOT NULL,
    body text NOT NULL,
    created_by text NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT fk_plant_note_plant
        FOREIGN KEY (plant_id) REFERENCES plant(id) ON DELETE RESTRICT,
    CONSTRAINT ck_plant_note_body_not_blank CHECK (btrim(body) <> ''),
    CONSTRAINT ck_plant_note_created_by_not_blank CHECK (
        created_by IS NULL OR btrim(created_by) <> ''
    )
);

CREATE INDEX ix_plant_note_plant_observed_at
    ON plant_note (plant_id, observed_at DESC);
```

Constraints to implement:

- Primary key on `id`.
- Required FK to `plant`.
- Required non-blank `body`.
- Indexed by plant and observation time for plant detail timelines.

### `plant_event`

`plant_event` stores irregular breeding actions or observations. Lifecycle fields on `plant` remain canonical for cull, harvest, veg start, and flower start.

```sql
CREATE TABLE plant_event (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    plant_id bigint NOT NULL,
    is_pollen_collection boolean NOT NULL DEFAULT false,
    is_seed_production boolean NOT NULL DEFAULT false,
    is_clone_taken boolean NOT NULL DEFAULT false,
    is_sex_observation boolean NOT NULL DEFAULT false,
    is_reversal boolean NOT NULL DEFAULT false,
    is_transplant boolean NOT NULL DEFAULT false,
    is_selection_for_breeding boolean NOT NULL DEFAULT false,
    occurred_at timestamptz NOT NULL,
    reason text NULL,
    notes text NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT fk_plant_event_plant
        FOREIGN KEY (plant_id) REFERENCES plant(id) ON DELETE RESTRICT,
    CONSTRAINT ck_plant_event_one_kind CHECK (
        (CASE WHEN is_pollen_collection THEN 1 ELSE 0 END) +
        (CASE WHEN is_seed_production THEN 1 ELSE 0 END) +
        (CASE WHEN is_clone_taken THEN 1 ELSE 0 END) +
        (CASE WHEN is_sex_observation THEN 1 ELSE 0 END) +
        (CASE WHEN is_reversal THEN 1 ELSE 0 END) +
        (CASE WHEN is_transplant THEN 1 ELSE 0 END) +
        (CASE WHEN is_selection_for_breeding THEN 1 ELSE 0 END) = 1
    ),
    CONSTRAINT ck_plant_event_reason_not_blank CHECK (
        reason IS NULL OR btrim(reason) <> ''
    ),
    CONSTRAINT ck_plant_event_notes_not_blank CHECK (
        notes IS NULL OR btrim(notes) <> ''
    ),
    CONSTRAINT ck_plant_event_metadata_object CHECK (
        jsonb_typeof(metadata) = 'object'
    )
);

CREATE INDEX ix_plant_event_plant_occurred_at
    ON plant_event (plant_id, occurred_at DESC);
```

Constraints to implement:

- Primary key on `id`.
- Required FK to `plant`.
- Event kind is represented by explicit boolean facts with an exactly-one constraint, not a string type column.
- Add partial indexes for individual event-kind booleans only when query volume requires them.
- `metadata` is reserved for opaque event details; if application logic begins depending on a structured metadata shape, define a Pydantic DTO at that boundary before writing/reading it.
- Indexed by plant timeline.


## GrowRun Retirement

`growrun` should be removed from source-owned plant identity and lifecycle flows in the same implementation series. Do not keep a long-term compatibility wrapper that rehydrates grow-run semantics from the new tables.

Target changes:

- Remove `Plant.growrun_id`, replace `UniqueConstraint("growrun_id", "plant_id")` with canonical integer `plant.id`, and rename the old text plant tag to `plant.key`.
- Move current `growrun.strain` to `plant_line.strain` and `plant_line.cultivar`.
- Move current `growrun.germination_date` and `growrun.flower_start_date` to plant-level `germinated_at` and `flower_started_at` timestamps for each existing plant.
- Replace `growrun.is_current` tent membership with `plant_location_history.end_at IS NULL`.
- Replace `growrun.plant_count` with count queries over current plant locations.
- Replace `GrowStateService` with a plant/tent context service that derives plant stage from plant lifecycle timestamps and derives tent context from current plants.
- Remove `growrun_id` from local cloud catalog DTOs, gateway outbox payloads, hosted `CloudPlant`, hosted `CloudPlantMetricStream`, browser responses, and generated frontend types. Dirt-owned sync should carry integer row identity and `key` only as a displayed/tagged domain key.
- Remove `moisture_target_low` and `moisture_target_high` from local `Plant`, hosted `CloudPlant`, gateway DTOs, browser API responses, generated frontend types, and plant UI. Delete the UI target display instead of replacing it with another target source.
- Remove `Snapshot.growrun_id` or stop writing it, then drop it once no query or projection depends on it. Snapshots should remain scoped by site/tent/view and can gain direct plant association later if plant-specific snapshot identity becomes necessary.
- Drop the `growrun` table only after source code, tests, cloud schema, and generated contracts no longer reference it.

The direct cutover is intentional. If a deploy-order bridge is required between gateway and hosted control-plane, keep it inside one milestone and remove it before the plan is complete.


## Plan of Work

Milestone 1 validates current data and finalizes key mapping. Inspect all existing `growrun`, `plant`, `plant_metric_stream`, `snapshot`, `cloud_plant`, and `cloud_plant_metric_stream` rows. Create a migration mapping for every existing plant. The expected main-tent tag mapping is old text `a -> SBBS-R1-001`, `b -> SBBS-R1-002`, `c -> SBBS-R1-003`, and `d -> SBBS-R1-004`, preserving integer row ids and moisture metric stream ownership. If existing breeding-tent rows such as `r1` through `r5` exist, add explicit `key` mappings for those rows before applying the migration; do not derive new keys implicitly.

Milestone 2 implements local SQLModel target tables. Add `PlantLine`, `SeedLot`, `CrossEvent`, `PlantLocationHistory`, `PlantNote`, and `PlantEvent` models under `apps/shared/src/dirt_shared/models/`. Modify `Plant` to match the target schema: canonical integer `id`, required `key`, plant-line/provenance FKs, lifecycle timestamps, breeding selection fields, and no `growrun_id`. Add a SQLModel/SQLAlchemy field comment explaining that `plant.key` is the unique human-readable plant identifier printed on tags and used in notes/photos. Update `apps/shared/src/dirt_shared/models/__init__.py`.

Milestone 3 creates and reviews the Atlas migration. The migration must create new tables, backfill one `plant_line` and `seed_lot` for current purchased `Sirius Black x BS01` material, rename the old text plant identifiers to `key` values using the explicit mapping, add `COMMENT ON COLUMN plant.key`, create current `plant_location_history` rows for each active plant, move grow-run dates to plant lifecycle timestamps, preserve `plant_metric_stream` relationships, remove `plant.growrun_id`, remove obsolete grow-run constraints, and eventually drop `growrun`. Use a compressed custom-format backup before local apply as described in `docs/database.md`.

Milestone 4 updates local services. Replace `GrowStateService` callers with a plant/tent context service. Update plant listing/detail/moisture services to query current plants through `plant_location_history`; order by `grid_position` and then `key`. Use integer `plant.id` for internal lookups and sync identity. Update daily reports, camera publisher, sensor summaries, and any voice tools that still use grow-run plant scope.

Milestone 5 updates gateway and hosted cloud projection. Extend `dirt_shared.cloud_contract` with DTOs for plant lines, seed lots, plant locations, plant notes if needed by the browser, and plant rows without `grow_run_id` or moisture target fields. Update gateway local projection and outbox validation before changing control-plane routes. Update `CloudPlant` uniqueness to the Dirt-owned integer source plant identity, carry `key` as a displayed/tagged domain key, add cloud mirror tables for line/location data needed by the browser, and remove `grow_run_id` from hosted plant metric stream identity.

Milestone 6 updates browser API and frontend. Regenerate the hosted OpenAPI client with `scripts/gen-hosted-contract` after FastAPI response models change. Update the tent plant list to query current location rows and show `grid_position`. Delete the plant-card moisture target text; the current app only displays the target and does not use it for control. Update plant detail to show line identity, lifecycle timestamps, current location, notes, and events. Keep the first UI pass workmanlike and data-dense; do not build a marketing or landing page.

Milestone 7 removes dead code and validates. Delete source-owned grow-run code, route fields, tests, and docs that only preserve the old model. Do not edit human-owned invariants. Run focused backend tests, control-plane tests, gateway tests, web-ui typecheck/lint/tests, invariants, and `make fix`. Record exact evidence in this ExecPlan.


## Concrete Steps

Read required docs:

    cd /home/akcom/code/dirt
    sed -n '1,240p' docs/database.md
    sed -n '1,220p' docs/rules/simple-clean-architecture.md
    sed -n '1,260p' docs/rules/boundary-contracts.md
    sed -n '1,220p' docs/references/atlas/INDEX.md

Inspect current schema and references:

    rg -n "growrun|grow_run_id|GrowRun|germination_date|flower_start_date|plant_count|is_current" apps web-ui contracts migrations docs -g '*'
    rg -n "class Plant|CloudPlant|CatalogPlant|PlantMetricStream|plant_location|plant_note|plant_event" apps web-ui contracts -g '*'

Inspect live local data before writing the migration:

    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "\d growrun"
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "\d plant"
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "SELECT t.tent_id, g.grow_run_id, g.strain, g.germination_date, g.flower_start_date, p.plant_id, p.name FROM plant p JOIN growrun g ON g.id = p.growrun_id JOIN tent t ON t.id = p.tent_id ORDER BY t.tent_id, p.plant_id;"

Create the local models and migration:

    atlas migrate diff breeding_data_model --env local
    atlas migrate hash --env local
    atlas migrate apply --env local --dry-run

Back up before applying locally:

    set -a; source .env; set +a
    mkdir -p var/db-backups
    PGPASSWORD=$DIRT_PG_PASSWORD pg_dump \
      -h 127.0.0.1 -U dirt -d dirt \
      -Fc --compress=zstd:level=6 \
      -f var/db-backups/dirt-$(date +%F-%H%M%S)-pre-breeding-data-model.dump

Apply locally only after reviewing the SQL:

    atlas migrate apply --env local

Regenerate hosted contracts after API changes:

    scripts/gen-hosted-contract

Run focused validation as implementation progresses:

    uv run pytest apps/shared/tests -q
    uv run pytest apps/gateway/tests -q
    uv run pytest apps/control-plane/tests -q
    uv run pytest apps/tests/invariants/ -q
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test

Before committing implementation work:

    make fix


## Validation and Acceptance

Database acceptance:

- `plant.id` is the canonical Dirt identity for relationships, sync, and configuration references.
- `plant.key` is globally unique and no longer scoped by `growrun_id`; it is the physical/domain plant tag, not the database identity.
- `plant.key` has a SQL column comment and a matching source-code field comment.
- Business state is not represented by string enum/check-list columns such as `source_type`, `propagation_type`, `event_type`, or `pollen_source_type`.
- Plant moisture target fields are removed from the plant model and hosted plant contracts because they are only display metadata today.
- `plant_line` has required non-blank `strain` and `cultivar`.
- Current purchased material is represented by `plant_line` plus `seed_lot`, even if parent plants are unknown.
- Current plants have explicit keys, lifecycle timestamps migrated from old grow-run dates where appropriate, and current `plant_location_history` rows.
- The query for current tent plants uses `plant_location_history.end_at IS NULL`.
- A plant cannot have two current locations.
- A tent position cannot have two current plants.
- Plant locations do not reference `zone_id`.
- Culling cannot be recorded without a non-blank `culled_reason`.
- `growrun` is absent from the final schema, or the only remaining references are explicitly documented external historical artifacts scheduled for deletion in the same plan.

Run acceptance SQL after local apply:

```sql
SELECT p.id, p.key, pl.strain, pl.cultivar, p.germinated_at, p.flower_started_at
FROM plant p
JOIN plant_line pl ON pl.id = p.line_id
ORDER BY p.key;

SELECT t.tent_id, l.grid_position, p.id, p.key, l.start_at
FROM plant_location_history l
JOIN plant p ON p.id = l.plant_id
JOIN tent t ON t.id = l.tent_id
WHERE l.end_at IS NULL
ORDER BY t.tent_id, l.grid_position, p.key;

SELECT table_name, column_name
FROM information_schema.columns
WHERE column_name IN ('growrun_id', 'grow_run_id')
ORDER BY table_name, column_name;

SELECT table_name, column_name
FROM information_schema.columns
WHERE column_name IN ('source_type', 'propagation_type', 'event_type', 'pollen_source_type')
ORDER BY table_name, column_name;

SELECT table_name, column_name
FROM information_schema.columns
WHERE column_name IN ('moisture_target_low', 'moisture_target_high')
ORDER BY table_name, column_name;

SELECT column_name
FROM information_schema.columns
WHERE table_name = 'plant_location_history'
  AND column_name IN ('zone_id', 'position');
```

Expected result: current plants list with integer ids and keys; current tent positions list without duplicates; `plant_location_history` uses `grid_position` and has no `zone_id` or `position`; no source-owned current tables expose `growrun_id`, `grow_run_id`, `source_type`, `propagation_type`, `event_type`, `pollen_source_type`, `moisture_target_low`, or `moisture_target_high`.

API and UI acceptance:

- Hosted browser API returns current tent plants from location history with integer `id`, `key`, line identity, current `grid_position`, lifecycle timestamps, and no `grow_run_id`.
- Plant detail can show notes and events for one globally identified plant.
- Moving a plant to another tent closes the old location row and opens a new row without changing `plant.id` or `plant.key`.
- Plant cards no longer render moisture target text.
- The frontend uses generated hosted types and contains no hand-written hosted plant response interfaces.

Test acceptance:

- Focused shared model/service tests pass.
- Gateway sync tests pass with typed DTO validation for the new plant catalog shape.
- Control-plane API tests pass with generated browser response models.
- `uv run pytest apps/tests/invariants/ -q` passes without editing human-owned invariant tests.
- `pnpm --dir web-ui typecheck`, `pnpm --dir web-ui lint`, and `pnpm --dir web-ui test` pass.
- `make fix` passes before commit.


## Idempotence and Recovery

Model and service edits are normal source changes and can be rerun safely. Atlas migration generation is not idempotent if repeated with different model state; inspect generated SQL, keep one migration file for this plan, and run `atlas migrate hash --env local` after manual edits.

Before applying DDL to the local live database, create the compressed custom-format backup shown above. Restore into a fresh database with `pg_restore` if rollback inspection is needed; do not casually restore over the live database. Hosted deployment must use `scripts/deploy-control-plane`; do not run ad hoc Railway DDL or app-start DDL.

If migration review finds unexpected existing plant rows, stop and update the explicit plant-id mapping in the migration rather than applying a derived rename. If a deploy-order issue requires temporary cloud compatibility, record it in `Decision Log`, keep it narrow, and remove it before marking this plan complete.


## Artifacts and Notes

Internet research sources used for the data-model split:

- BrAPI: `https://brapi.org/` and `https://plant-breeding-api.readthedocs.io/`
- Breedbase: `https://solgenomics.github.io/sgn/`
- FAO/Bioversity MCPD: `https://www.genesys-pgr.org/descriptorlists/0cd31350-234b-4ebf-80bc-fc65f14f7541`
- MIAPPE: `https://www.miappe.org/`
- Iowa State plant breeding notation: `https://iastate.pressbooks.pub/cropimprovement/chapter/pedigree-naming-systems-and-symbols/`

Current user decisions captured in this draft:

- Every table should use integer `id` as the canonical Dirt identity.
- Do not add text `*_id` columns merely for human convenience or Dirt-owned sync/config readability.
- Use `name`/`*_name` for human display text and `*_key` only for a real external, hardware, vendor, protocol, file, or domain-native key.
- Avoid string enum/check-list columns for business state; prefer concrete facts, generated columns, lookup tables, and constraints.
- Delete plant moisture targets and UI target display; do not replace them until a real watering workflow needs target configuration.
- Plant tag values such as `SBBS-R1-001` should be modeled as `plant.key`, not `plant.plant_id`.
- `plant.key` means the unique human-readable plant identifier printed on tags and used in notes/photos, for example `SBBS-R1-001`; code and SQL comments should state this.
- Do not maintain backwards compatibility shims for old plant identity.
- Plants may move between tents.
- Purchased seed lines use the same `plant_line` table, with nullable `project_code` and nullable `generation_label`.
- Both `strain` and `cultivar` are required on `plant_line`.
- Clones should get their own integer `plant.id` rows and their own `key` values.
- `selected_for_breeding` means approved parent used or planned for breeding.
- `plant_location_history.grid_position` is free text for v1.
- Culling requires both `culled_at` and `culled_reason`.


## Interfaces and Dependencies

Final local database interfaces:

- `plant_line`
- `seed_lot`
- `cross_event`
- `plant`
- `plant_location_history`
- `plant_note`
- `plant_event`
- Existing `plant_metric_stream`, updated only as needed to reference the global `plant` row without grow-run scope.

Final source modules:

- `apps/shared/src/dirt_shared/models/plant.py` owns `Plant`, `PlantMetricStream`, `PlantLine`, `SeedLot`, `CrossEvent`, `PlantLocationHistory`, `PlantNote`, and `PlantEvent`, unless implementation splits the new models into small files and re-exports them from `models/__init__.py`.
- `apps/shared/src/dirt_shared/services/grow_state.py` is removed or replaced by a plant/tent context service with no dependency on `growrun`.
- `apps/shared/src/dirt_shared/cloud_contract.py` exposes typed gateway DTOs with no `grow_run_id` in plant identity.
- `apps/control-plane/src/dirt_control/models/cloud.py` mirrors the new hosted plant identity and location projection.
- `web-ui/src/api-client/generated/hosted-schema.ts` is regenerated from FastAPI OpenAPI.

External dependencies:

- PostgreSQL 17.
- Atlas migrations.
- `btree_gist` PostgreSQL extension for location overlap exclusion constraints.
- Existing uv workspace and pnpm web-ui toolchain.


## Revision Notes

- 2026-06-14 / Codex: Initial draft with target SQL schemas, constraints, grow-run retirement path, migration strategy, and validation plan.
- 2026-06-14 / Codex: Added the data-modeling rule preference and revised the plan to remove duplicative text identifiers from `plant_line`, `cross_event`, and `seed_lot`; `plant.key` now represents the physical/domain plant tag while integer `plant.id` remains canonical identity.
