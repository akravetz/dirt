# Plant Identity Model Cleanup and Breeding Run Seed

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.

## Purpose / Big Picture

After this change, Dirt can represent plants from more than the original four-plant main tent. The database and API will use one stable plant identifier per grow run, support arbitrary labels such as `r1` through `r5`, preserve a human-friendly name, sort plants explicitly, and allow plants to have no sticker color. The user can then record the current breeding Track A pollen run as five real plants in the breeding tent without forcing those plants through the old A-D shape.

This matters because the breeding tent is now a first-class operating space. Track A exists only to produce pollen from selected SBxBS01 regular plants; its plants are labeled `R1`-style, not `A`-style, and only five plants remain. The current model has `plant.code` constrained to one lowercase letter and `plant.sticker_color` required with four values. That model is no longer truthful.

The work is complete when `/api/plants?tent_id=breeding` returns the five Track A plants ordered by `display_order`, each with `plant_id`, `name`, nullable `sticker_color`, status, purple flag, and moisture fields; `/api/plants/r1?tent_id=breeding` can retrieve a breeding plant by id; the main tent still returns A-D correctly; and the generated frontend/backend contracts no longer expose the A-D-only `PlantCode` enum.


## Progress

- [x] (2026-05-24T03:16:08Z) Created this ExecPlan from the user's decisions: remove useless `code`, remove duplicative `label`, use `plant_id` plus `name`, add `display_order`, expand and nullable-ize sticker color, seed five Track A plants, and defer multi-tent wiki refactor.
- [x] (2026-05-24T04:48:10Z) Implement schema/model migration for plant identity and Track A run seed.
- [x] (2026-05-24T05:09:31Z) Update backend services, API contracts, generated clients, frontend, and tests.
  - [x] (2026-05-24T04:56:15Z) Milestone 2 backend services and local API updated to `plant_id`, display ordering, scoped detail/moisture queries, nullable sticker colors, and no DB `label`.
  - [x] (2026-05-24T04:56:15Z) Milestone 3 webapp OpenAPI and generated Python/TypeScript clients updated to remove `PlantCode`, expose `plant_id`, remove plant detail `label`, and make plant sticker color required-nullable with `brown`.
  - [x] (2026-05-24T05:02:21Z) Milestone 4 frontend consumers updated to use `plant_id`, handle nullable sticker colors, include `brown`, and remove plant detail label rendering.
  - [x] (2026-05-24T05:09:31Z) Milestone 5 tests updated to assert the canonical `plant_id` contract, nullable sticker colors, seeded Track A breeding plants, and no plant `code`/`label` payload fields.
- [x] (2026-05-24T05:14:09Z) Validate with focused backend, contract, frontend, invariant, migration, SQL, and API-smoke commands.


## Surprises & Discoveries

- Observation: The live database has the `breeding` tent and devices, but no breeding `growrun` or breeding `plant` rows.
  Evidence: `SELECT ... FROM growrun` returned only `main-2026-03-15`; `tent` contains `main`, `breeding`, and `clones`.

- Observation: `Plant.sticker_color` is a required Postgres enum with only `yellow`, `orange`, `pink`, and `blue`, while the breeding tent has five plants and sticker colors must be nullable.
  Evidence: `apps/shared/src/dirt_shared/models/enums.py` defines `PlantSticker`; `apps/shared/src/dirt_shared/models/plant.py` makes `sticker_color` non-null.

- Observation: `code` is a boundary field, not just a database field.
  Evidence: `contracts/webapp-v1.yaml`, `contracts/python/src/dirt_contracts/webapp_v1/models.py`, `web-ui/src/api-client/generated/schema.ts`, `apps/web/src/dirt_web/api/plants.py`, `web-ui/src/ui/PlantsStrip.tsx`, and several tests reference `code` or `PlantCode`.

- Observation: Atlas lint is not available in this local community CLI configuration.
  Evidence: `atlas migrate lint --env local --latest 1` reported that the command requires Atlas Pro; `atlas migrate apply --env local --dry-run` was used for migration review instead.

- Observation: Running the focused shared and web pytest commands concurrently races on the session-scoped Postgres template database.
  Evidence: A parallel rerun produced `relation "growrun" does not exist` and `template database "dirt_test_template_7ff9482e8f" does not exist`; sequential reruns of the same commands passed.

- Observation: The TypeScript dead-code invariant caught exported sticker constants after the UI moved to exported helper functions.
  Evidence: `uv run pytest apps/tests/invariants/ -q` initially failed with unused exports `STICKER_FILL` and `STICKER_STROKE`; making those constants internal fixed the invariant without editing `apps/tests/invariants/`.


## Decision Log

- Decision: Use `plant.plant_id` as the canonical stable plant identifier within a grow run.
  Rationale: `plant_id` already has the right uniqueness constraint, `(growrun_id, plant_id)`, and can truthfully represent `a`, `d`, `r1`, `r5`, or later labels without schema churn.
  Date/Author: 2026-05-23 / user and Codex.

- Decision: Remove `plant.code` rather than relaxing it.
  Rationale: `code` duplicates identity, was constrained to the original A-D grow, and creates two possible answers to "which plant is this?" Keeping it would preserve stale architecture.
  Date/Author: 2026-05-23 / user and Codex.

- Decision: Remove `plant.label`.
  Rationale: The existing `label` values duplicate structured status or narrative wiki notes. The durable plant fields should be `plant_id`, `name`, `status`, `purple`, sticker metadata, moisture targets, and sort order.
  Date/Author: 2026-05-23 / user and Codex.

- Decision: Add `plant.display_order` and use it for list ordering.
  Rationale: Text ordering of ids fails for ids such as `r10`; explicit order is inspectable and independent of identity.
  Date/Author: 2026-05-23 / user.

- Decision: Keep sticker color as an enum-backed concept for now, expand the enum, and make the column nullable.
  Rationale: The user explicitly chose enum expansion plus nullable over converting to free-form text. The implementation should add the fifth known color once confirmed from the physical labels or existing data source.
  Date/Author: 2026-05-23 / user.

- Decision: Punt multi-tent wiki refactoring.
  Rationale: The current wiki plant detail path assumes `wiki/plants/plant-a.md` style pages. Supporting breeding-plant pages across tents is a larger information-architecture project and is not needed to record Track A in the database.
  Date/Author: 2026-05-23 / user.


## Outcomes & Retrospective

- Milestone 1 implemented the persistence cutover in SQLModel and a pending Atlas migration. `Plant.code`, `Plant.label`, and `ck_plant_code_lowercase_letter` are removed from the model; `Plant.display_order` is non-null with server default `0`; `Plant.sticker_color` is nullable; and `PlantSticker` includes `brown`.
- Migration `20260524044500_plant_identity_cleanup.sql` adds the `brown` enum value, adds/backfills `display_order`, drops `code` and `label`, makes `sticker_color` nullable, seeds `breeding-track-a-2026-04-28`, and seeds Track A plants R1-R5 with sticker colors pink, yellow, brown, blue, and orange.
- Validation passed: `atlas migrate apply --env local --dry-run`; `uv run --package dirt-shared python -c "from dirt_shared.models.plant import Plant; from dirt_shared.models.enums import PlantSticker; assert hasattr(Plant, 'display_order'); assert not hasattr(Plant, 'code'); assert not hasattr(Plant, 'label'); assert PlantSticker.BROWN.value == 'brown'; print('ok')"`.
- Milestone 2 updated `PlantsService`, local plant API handlers, daily sensor plant moisture lookup, and voice sensor tool lookup from `code` to `plant_id`. Lists now order by `display_order, plant_id`; detail and moisture endpoints accept `site_id`/`tent_id` and validate plant ids against scoped current grow rows.
- Milestone 2 validation passed: `uv run --package dirt-shared python -c "... PlantSummary ..."`; `uv run --package dirt-web python -c "import dirt_web.api.plants; print('ok')"`; `uv run --package dirt-voice python -c "from dirt_voice.tools.sensors import build_sensor_tools ..."`; `uv run ruff check` and `uv run ruff format --check` on the touched backend files; `uv run pytest apps/shared/tests/test_daily_sensors.py -q`; `git diff --check` on the touched backend files.
- Milestone 3 updated `contracts/webapp-v1.yaml`, regenerated `contracts/python/src/dirt_contracts/webapp_v1/models.py`, and regenerated `web-ui/src/api-client/generated/schema.ts`.
- Milestone 3 validation passed: `uv run --package dirt-web python -c "from dirt_contracts.webapp_v1.models import Plant, PlantDetail, PlantMoistureHistory; ..."`; `uv run --package dirt-web python -c "import dirt_web.api.plants; print('ok')"`; `pnpm --dir web-ui exec biome check --write src/api-client/generated/schema.ts`. `rg` confirms no remaining `PlantCode` in contract/generated artifacts; remaining `label` matches are PTZ preset fields, not plant payloads.
- Milestone 4 updated dashboard plant selection, plant cards, plant detail, wiki/live sticker narrowing, and shared plant UI types to use arbitrary string `plant_id` and nullable sticker helpers. Validation passed: `pnpm --dir web-ui typecheck`; `pnpm --dir web-ui lint`; `pnpm --dir web-ui test` (Vitest exited 0 with no matching `src/**/*.{test,spec}.{ts,tsx}` files).
- Milestone 5 updated agent-owned shared, web API, and frontend e2e tests to use `plant_id` instead of `code`/`PlantCode`, remove plant `label` expectations, assert nullable `sticker_color`, and cover breeding Track A through API boundary behavior rather than duplicating seed SQL.
- Milestone 5 validation passed: `uv run pytest apps/shared/tests/test_scoped_identity_models.py -q`; `uv run pytest apps/web/tests/test_plants_list_endpoint.py apps/web/tests/test_plants_detail_endpoint.py apps/web/tests/test_plants_moisture_endpoint.py -q`; `uv run ruff check` and `uv run ruff format --check` on touched Python tests; `pnpm --dir web-ui typecheck`; `pnpm --dir web-ui lint`; `pnpm --dir web-ui test` (no matching unit test files under `src`). Playwright e2e specs were not run because the worktree dev server was not running at `http://localhost:5171`.
- Milestone 6 created backup `var/db-backups/dirt-2026-05-23-231143-pre-plant-identity-cleanup.sql`, applied migration `20260524044500_plant_identity_cleanup.sql` locally with `atlas migrate apply --env local`, and confirmed SQL acceptance. Current grow runs are `main-2026-03-15` and `breeding-track-a-2026-04-28`; breeding plants are `r1` through `r5` ordered 1-5 with sticker colors pink, yellow, brown, blue, orange; plant columns include `display_order`, `plant_id`, `name`, and nullable `sticker_color`, with `code` and `label` absent.
- Milestone 6 validation passed: `uv run pytest apps/shared/tests/test_scoped_identity_models.py -q`; `uv run pytest apps/web/tests/test_plants_list_endpoint.py apps/web/tests/test_plants_detail_endpoint.py apps/web/tests/test_plants_moisture_endpoint.py -q`; `uv run pytest apps/tests/invariants/ -q` (`112 passed`); `pnpm --dir web-ui typecheck`; `pnpm --dir web-ui lint`; `pnpm --dir web-ui test` (no matching unit test files under `src`); local ASGI API smoke against the migrated database for `/api/plants?tent_id=main`, `/api/plants?tent_id=breeding`, `/api/plants/r1?tent_id=breeding`, and `/api/plants/a/moisture?range=24h&tent_id=main`; `git diff --check`.
- Direct cutover outcome: source-owned code no longer uses `Plant.code`, `Plant.label`, `PlantCode`, or `get_plant_by_code`; the only remaining `label` fields in plant-adjacent searches belong to PTZ/wiki/UI generic labels, not the removed plant DB field.


## Context and Orientation

The current scoped grow model lives in the PostgreSQL database and SQLModel table classes under `apps/shared/src/dirt_shared/models/`. The relevant table models are:

- `apps/shared/src/dirt_shared/models/grow_run.py`: `GrowRun`, one current grow cycle per tent.
- `apps/shared/src/dirt_shared/models/plant.py`: `Plant`, one row per plant in a grow run.
- `apps/shared/src/dirt_shared/models/enums.py`: `PlantSticker` and `PlantStatus`, shared Python/Postgres enum definitions.

The database already has scoped `site`, `tent`, `zone`, `device`, `capability`, and `schedule` rows from prior multi-tent migrations. Seed-data migrations use idempotent `INSERT ... ON CONFLICT DO UPDATE` patterns. Examples are `migrations/20260507220940_breeding_env_node.sql`, `migrations/20260509040000_authoritative_kasa_lights.sql`, and `migrations/20260512161000_seed_breeding_camera.sql`.

The current `plant` table has these fields that this plan changes:

- `plant_id`: text, non-null, unique per `growrun_id`. This remains and becomes the canonical route/key identifier.
- `code`: text, non-null, constrained by `ck_plant_code_lowercase_letter` to one lowercase letter. This is removed.
- `name`: text, non-null. This remains as the human display name.
- `sticker_color`: `plant_sticker`, non-null. This becomes nullable and the enum gains the fifth sticker color.
- `label`: nullable text. This is removed.

The local web API exposes plant data from `apps/web/src/dirt_web/api/plants.py`. It currently maps `PlantSummary.code` to a generated contract enum `PlantCode` and parses `/api/plants/{code}` through that enum. The contract source is `contracts/webapp-v1.yaml`; generated Python models live in `contracts/python/src/dirt_contracts/webapp_v1/models.py`; generated TypeScript schemas live in `web-ui/src/api-client/generated/schema.ts`. Do not hand-edit generated files if the repo provides a generation script; find the contract generation command with `rg "webapp-v1|openapi|schema.ts|gen" scripts contracts web-ui`.

The shared service that queries plants is `apps/shared/src/dirt_shared/services/plants.py`. It currently orders by `Plant.code` and has methods named `get_plant_by_code`. Those methods should be renamed to plant-id terminology and order by `Plant.display_order`, then `Plant.plant_id` as a deterministic fallback.

The frontend consumes `plant.code` in components such as `web-ui/src/ui/PlantsStrip.tsx`, `web-ui/src/ui/PlantDetail.tsx`, and routes under `web-ui/src/routes/`. After this change it should consume `plant.plant_id`. Existing display copy can use `plant.name`.

The wiki integration is deliberately not generalized in this plan. `PlantDetailService` may still look up `wiki/plants/plant-{plant_id}.md`. For breeding plants without wiki pages, the API should return an empty timeline/note and a fallback path, or the detail route can return basic DB fields only if that is already how the service behaves for missing pages. Do not create a broader multi-tent wiki architecture in this change.

The current breeding Track A dates come from the wiki, not the database:

- Started around `2026-04-28`.
- Seven seeds sprouted and were potted on `2026-05-05`.
- Five plants were ultimately kept.
- The run is an SBxBS01 regular pollen-production run.


## Plan of Work

Milestone 1 changes the persistence model. Edit `apps/shared/src/dirt_shared/models/plant.py` to remove the `code` and `label` columns, add `display_order` as a non-null integer with a default, and make `sticker_color` nullable. Edit `apps/shared/src/dirt_shared/models/enums.py` to add the fifth sticker color. The implementation must first confirm the exact fifth enum value from the user or a durable source; do not guess from photos. Generate or hand-author an Atlas migration that:

- Alters the Postgres `plant_sticker` enum to include the fifth value.
- Adds `plant.display_order` with a safe default for existing rows.
- Backfills main plants: A=1, B=2, C=3, D=4.
- Drops `ck_plant_code_lowercase_letter`.
- Drops `plant.code`.
- Drops `plant.label`.
- Makes `plant.sticker_color` nullable.
- Seeds a current breeding `growrun` under `homebox/breeding`.
- Seeds five breeding `plant` rows with `plant_id` values `r1` through `r5`, names `Track A R1` through `Track A R5`, `display_order` 1 through 5, `status='secondary'`, `purple=false`, and nullable sticker colors matching known physical stickers or null if unknown.

Milestone 2 updates shared services and local API code. In `apps/shared/src/dirt_shared/services/plants.py`, rename dataclass fields and methods from `code` to `plant_id`, remove `label`, make `sticker_color` optional, and order by `display_order`. In `apps/web/src/dirt_web/api/plants.py`, replace the `PlantCode` enum parsing with string plant-id validation against current-grow database rows. Keep route paths as `/api/plants/{plant_id}`; FastAPI path variable names should change to `plant_id`, but the URL path can remain stable.

Milestone 3 updates the webapp contract and generated clients. In `contracts/webapp-v1.yaml`, remove `PlantCode`, add `plant_id: string` to `Plant`, `PlantDetail`, and `PlantMoistureHistory`, remove `label` from `PlantDetail`, and make `sticker_color` a required nullable field where plant payloads include it. Expand `PlantStickerColor` with the fifth color. Regenerate `contracts/python/src/dirt_contracts/webapp_v1/models.py` and `web-ui/src/api-client/generated/schema.ts` with the repository's generator commands. If no generator exists for one output, update the checked-in generated artifact in the same commit and record the command search in `Artifacts and Notes`.

Milestone 4 updates frontend consumers. Replace `code` references for plant identity with `plant_id` and remove label rendering paths that only display the old DB `label`. Components that render sticker swatches must handle `null`. Any object maps keyed by code should be keyed by `plant_id`. Follow `docs/references/modern-idiomatic-typescript/INDEX.md`: use inferred generated types, avoid `any`, avoid TypeScript enums, and prefer narrow helper functions for nullable sticker colors.

Milestone 5 updates tests. Backend tests under `apps/shared/tests` and `apps/web/tests` should assert arbitrary plant ids and nullable sticker color behavior. Frontend tests under `web-ui/tests` should expect `plant_id`. Human-owned invariant tests under `apps/tests/invariants/` must not be edited; fix source code to satisfy them. Update any fixture comments that still claim sticker colors are limited to four colors.

Milestone 6 validates end-to-end behavior and records evidence in this ExecPlan. Apply the migration locally only after reviewing the SQL. Query the DB for the breeding run and plants. Run focused pytest suites, invariants, web-ui typecheck/lint/tests, and a smoke API request against `dirt-web` if the service is running or can be safely started.


## Concrete Steps

Start by confirming the exact fifth sticker color value:

    cd /home/akcom/code/dirt
    rg -n "sticker|R1|R2|R3|R4|R5|Track A" wiki docs debug

If the value is not documented, ask the user for the exact lowercase color name before writing the enum migration.

Inspect current DB state:

    cd /home/akcom/code/dirt
    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "SELECT * FROM tent ORDER BY id;"
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "SELECT g.grow_run_id, t.tent_id, g.germination_date, g.flower_start_date, g.plant_count, g.is_current FROM growrun g JOIN tent t ON t.id=g.tent_id ORDER BY t.tent_id, g.grow_run_id;"
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "SELECT p.plant_id, p.name, p.display_order FROM plant p JOIN tent t ON t.id=p.tent_id WHERE t.tent_id IN ('main','breeding') ORDER BY t.tent_id, p.display_order, p.plant_id;"

The last query will fail before the migration because `display_order` does not exist; that failure is expected during planning and should pass after migration.

Edit SQLModel files:

    apps/shared/src/dirt_shared/models/enums.py
    apps/shared/src/dirt_shared/models/plant.py

Generate or create the migration. Preferred schema workflow is Atlas:

    cd /home/akcom/code/dirt
    atlas migrate diff plant_identity_cleanup --env local

If Atlas cannot represent the data seed or enum alteration cleanly, hand-edit the generated migration or create a migration file following existing seed migrations, then run:

    atlas migrate hash --env local
    atlas migrate apply --env local --dry-run

Update service and API files:

    apps/shared/src/dirt_shared/services/plants.py
    apps/web/src/dirt_web/api/plants.py
    apps/shared/src/dirt_shared/services/daily_sensors.py
    apps/voice/src/dirt_voice/tools/sensors.py

Update contract source and regenerate outputs:

    contracts/webapp-v1.yaml
    contracts/python/src/dirt_contracts/webapp_v1/models.py
    web-ui/src/api-client/generated/schema.ts

Find the exact generation command before modifying generated files:

    rg -n "webapp-v1|openapi-typescript|datamodel|contracts/python|generated/schema" scripts contracts pyproject.toml web-ui/package.json

Update frontend files that consume plant identity and sticker colors:

    web-ui/src/ui/PlantsStrip.tsx
    web-ui/src/ui/PlantDetail.tsx
    web-ui/src/ui/WikiSidebar.tsx
    web-ui/src/routes/live.tsx
    web-ui/src/routes/wiki.tsx
    web-ui/src/ui/plant-types.ts

Run focused validation:

    uv run pytest apps/shared/tests/test_scoped_identity_models.py -q
    uv run pytest apps/web/tests/test_plants_list_endpoint.py apps/web/tests/test_plants_detail_endpoint.py apps/web/tests/test_plants_moisture_endpoint.py -q
    uv run pytest apps/tests/invariants/ -q
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test

Before committing later, run:

    scripts/agent-fix


## Validation and Acceptance

Database acceptance:

- `growrun` has one current run for `homebox/main` and one current run for `homebox/breeding`.
- The breeding run has `grow_run_id='breeding-track-a-2026-04-28'`, `purpose='pollen'`, `germination_date='2026-04-28'`, `plant_count=5`, and `is_current=true`.
- `plant` has five rows for the breeding run, with `plant_id` `r1` through `r5`, `display_order` 1 through 5, and no use of the removed `code` or `label` columns.
- `plant.sticker_color` accepts null and the expanded fifth sticker enum value.

Run these SQL checks after applying locally:

    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "SELECT t.tent_id, g.grow_run_id, g.purpose, g.germination_date, g.flower_start_date, g.plant_count, g.is_current FROM growrun g JOIN tent t ON t.id=g.tent_id WHERE t.tent_id IN ('main','breeding') ORDER BY t.tent_id;"
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "SELECT t.tent_id, p.plant_id, p.name, p.display_order, p.sticker_color, p.status, p.purple FROM plant p JOIN tent t ON t.id=p.tent_id WHERE t.tent_id IN ('main','breeding') ORDER BY t.tent_id, p.display_order, p.plant_id;"
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -c "SELECT column_name FROM information_schema.columns WHERE table_name='plant' AND column_name IN ('code','label','display_order','plant_id','name','sticker_color') ORDER BY column_name;"

Expected: `code` and `label` are absent; `display_order`, `plant_id`, `name`, and nullable `sticker_color` are present.

API acceptance:

- `GET /api/plants?tent_id=main` returns main plants with ids `a` through `d`, no `code`, no `label`, and nullable `sticker_color` keys.
- `GET /api/plants?tent_id=breeding` returns five plants ordered `r1` through `r5`.
- `GET /api/plants/r1?tent_id=breeding` returns the database-backed detail envelope even if no breeding wiki page exists. If missing wiki data currently makes this endpoint unsuitable, record that as an accepted gap and ensure list endpoints work; do not start the multi-tent wiki refactor in this plan.
- `GET /api/plants/a/moisture?range=24h` still works for the main tent.

Frontend acceptance:

- The dashboard plant strip renders using `plant_id` for keys and routes.
- Plants with `sticker_color: null` render without a broken swatch or runtime error.
- TypeScript no longer references a generated `PlantCode` enum.

Test acceptance:

- Focused shared and web tests pass.
- `uv run pytest apps/tests/invariants/ -q` passes.
- `pnpm --dir web-ui typecheck`, `pnpm --dir web-ui lint`, and `pnpm --dir web-ui test` pass.


## Idempotence and Recovery

The migration should be idempotent where it seeds data: use `ON CONFLICT ON CONSTRAINT uq_growrun_tent_grow_run_id DO UPDATE` for `growrun` and `ON CONFLICT ON CONSTRAINT uq_plant_growrun_plant_id DO UPDATE` for plants. Re-running the migration against a database that already has the seed rows should update the intended fields, not duplicate rows.

Schema changes are not idempotent when applied manually. Do not run ad hoc `ALTER TABLE` statements outside Atlas. Review `atlas migrate apply --env local --dry-run` before applying. If a migration is generated but not applied and needs revision, edit the migration and run `atlas migrate hash --env local` before applying.

Before applying to the live local database, create a backup if the migration drops columns:

    set -a; source .env; set +a
    mkdir -p var/db-backups
    PGPASSWORD=$DIRT_PG_PASSWORD pg_dump -h 127.0.0.1 -U dirt -d dirt > var/db-backups/dirt-$(date +%F-%H%M%S)-pre-plant-identity-cleanup.sql

If tests fail after the migration, prefer fixing source code and tests to reintroducing compatibility aliases. If the database itself must be rolled back during development, restore from the backup or create a forward migration that reintroduces fields only if the user explicitly asks for rollback. Do not use destructive Git or database reset commands casually.


## Artifacts and Notes

Initial context gathered before authoring this plan:

- `docs/database.md` says `growrun` is the scoped grow-cycle source of truth and `plant` rows are scoped to a grow run.
- `docs/rules/simple-clean-architecture.md` says to replace misleading source-owned concepts directly and avoid compatibility wrappers.
- `docs/rules/boundary-contracts.md` says route payload changes require Pydantic DTO/contract updates rather than raw dictionaries.
- `docs/references/modern-idiomatic-typescript/INDEX.md` says frontend TypeScript changes should use generated types and avoid stale enum-heavy patterns in hand-written code.
- Live DB inspection showed only `main-2026-03-15` in `growrun`; the `breeding` tent exists but has no grow run.
- `rg` showed `code` and `sticker_color` usage across backend services, contracts, generated clients, frontend components, and tests.

Record migration filenames, generation commands, SQL dry-run excerpts, and final test outputs here as implementation proceeds.


## Interfaces and Dependencies

Database interfaces at completion:

- `plant.plant_id text not null`: canonical stable plant id within a grow run.
- `plant.name text not null`: human display name.
- `plant.display_order integer not null`: explicit per-grow display order.
- `plant.sticker_color plant_sticker null`: optional sticker color.
- `plant.code`: removed.
- `plant.label`: removed.
- `growrun` includes current breeding run `breeding-track-a-2026-04-28`.

Python model interfaces at completion:

- `dirt_shared.models.plant.Plant` has `plant_id`, `name`, `display_order`, optional `sticker_color`, `status`, `purple`, moisture targets, and optional `moisture_capability_id`.
- `dirt_shared.services.plants.PlantSummary` exposes `plant_id`, `name`, optional `sticker_color`, `status`, `purple`, moisture fields, and no `code` or `label`.
- `PlantsService.list_plants()` orders by `display_order`, then `plant_id`.
- `PlantsService.get_plant_by_id()` replaces `get_plant_by_code()`.

API and contract interfaces at completion:

- `/api/plants` response `Plant` objects contain `plant_id`, not `code`.
- `/api/plants/{plant_id}` accepts arbitrary plant ids for the current scoped grow run.
- `/api/plants/{plant_id}/moisture` accepts arbitrary plant ids.
- `PlantStickerColor` includes the fifth sticker color and plant payloads allow `sticker_color: null`.
- Generated Python and TypeScript contract artifacts match `contracts/webapp-v1.yaml`.

Frontend interfaces at completion:

- UI components use `plant.plant_id` for React keys, route params, API calls, and current selection state.
- Sticker swatch helpers accept `PlantStickerColor | null | undefined`.
- No hand-written frontend type narrows plant identity to `a | b | c | d`.

Operational dependencies:

- Atlas migration tooling and Postgres local database from `docs/database.md`.
- Existing command policy from `docs/commands.md`: use `uv run ...` for Python commands and `pnpm --dir web-ui ...` for frontend checks.
- No multi-tent wiki refactor is part of this plan.


## Revision Notes

- 2026-05-23 / Codex: Initial ExecPlan created from the plant identity cleanup discussion and current repository inspection.
