# Breeding Logbook UI Integration

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, Dirt has a production-shaped Breeding Logbook surface in the hosted React UI instead of the temporary dashboard prototype selector. An operator can review plants in a dense table or board, select and move plants by pointer drag, open a plant detail journal, and exercise Add seeds / Add plants flows against deterministic mock data while the backend API contract is being designed. The mock data lives in one clearly named file so the frontend can be built at high fidelity without preserving throwaway prototype code or duplicating API contracts.

The plan also adds the missing durable breeding facts that the UI depends on: current plant sex and seed-lot sex type. `plant` currently has no canonical current sex field, and `seed_lot` currently has no queryable regular/feminized distinction. This plan adds lookup tables and foreign keys for those fields, then projects them through the gateway/cloud/browser contract when the real API is wired.

The work is complete when the recent `Plant Workbench` and `Generation Notebook` prototypes are removed, the Breeding Logbook route renders from TanStack Query hooks backed by `web-ui/src/features/breeding-logbook/breedingLogbook.mockData.ts`, the DB schema stores plant sex and seed-lot sex type, the proposed browser API shape is documented and tested at the DTO level, and local screenshots of the implemented app are compared against the standalone HTML prototype through an LLM-assisted, human-reviewed rubric loop.


## Progress

- [x] (2026-06-18) Read `docs/commands.md`, frontend reference packs, UI refinement skill guidance, `.agents/PLANS.md`, and the Breeding Logbook handoff README.
- [x] (2026-06-18) Inspected `debug/plant_mgmt.zip`, `debug/design_handoff_breeding_logbook/Breeding Logbook.dc.html`, the standalone screenshots, current `web-ui`, current hosted plant APIs, and existing breeding data-model ExecPlans.
- [x] (2026-06-18) Confirmed the current data model has no canonical current plant sex field and no canonical seed-lot sex type field.
- [x] (2026-06-18) Resolved product decisions with the operator: replace the dashboard prototype selector, keep frontend queries mock-backed first, include DB migration and API audit, model plant sex and seed-lot sex type as lookup tables with plain `key` primary keys and semantic branching columns, implement pointer drag-and-drop, and use an LLM-assisted screenshot review loop.
- [x] (2026-06-18) Drafted this ExecPlan.
- [ ] Implement Milestone 1: remove recent frontend prototype selector/code and add the production-shaped Breeding Logbook feature shell with mock-backed TanStack Query.
- [ ] Implement Milestone 2: add plant sex and seed-lot sex type lookup tables, fields, migrations, seeds, and local/cloud projection contracts.
- [ ] Implement Milestone 3: complete the mock-backed Breeding Logbook views and pointer drag-and-drop behavior.
- [ ] Implement Milestone 4: audit and propose ergonomic real browser API endpoints and DTOs, backed by tests and generated contract expectations.
- [ ] Implement Milestone 5: run local browser verification and the LLM/human screenshot review cycle.


## Surprises & Discoveries

- Observation: The Breeding Logbook bundle is already expanded under `debug/design_handoff_breeding_logbook/`, and the zip contains the standalone HTML, source HTML, README, and eight reference screenshots.
  Evidence: `unzip -l debug/plant_mgmt.zip` lists `design_handoff_breeding_logbook/Breeding Logbook (standalone).html`, `Breeding Logbook.dc.html`, `README.md`, and `screenshots/01-plants-table.png` through `08-dark-theme.png`.

- Observation: `web-ui/src/routes/index.tsx` is already dirty with a temporary prototype selector and static `Plant Workbench` / `Generation Notebook` prototypes.
  Evidence: `git diff -- web-ui/src/routes/index.tsx web-ui/src/prototypes/plantManagementPrototype.mockData.ts` shows imports from `@/prototypes/plantManagementPrototype.mockData`, a `View` selector, and prototype components embedded in the dashboard route.

- Observation: The active hosted browser plant API is read-heavy and already returns plant summaries, detail, and mapped telemetry history, but plant detail still returns empty notes/events arrays.
  Evidence: `apps/control-plane/src/dirt_control/api/browser.py` defines `GET /api/tents/{tent_id}/plants`, `GET /api/tents/{tent_id}/plants/{plant_id}`, and `GET /api/tents/{tent_id}/plants/{plant_id}/metrics/history`; `_plant_detail_response()` sets `notes=[]` and `events=[]`.

- Observation: Local `plant` has no canonical current sex field.
  Evidence: `apps/shared/src/dirt_shared/models/plant.py` defines `PlantEvent.is_sex_observation` but `Plant` has no `sex` or `sex_key` column. Existing sex details would have to live in event metadata if used today.

- Observation: Local `seed_lot` has no canonical regular/feminized field.
  Evidence: `apps/shared/src/dirt_shared/models/plant.py` defines `SeedLot` with `is_purchased`, `vendor_name`, `produced_by_cross_event_id`, `seed_count`, and `notes`, but no seed sex/type column. Current migrations mention regular/feminized only in descriptions and notes.

- Observation: There is an untracked migration, `migrations/20260614213709_correct_seed_lot_sources.sql`, that corrects Plants A-D to feminized material and moves only `SBBS-R1-006` / R2 to regular material.
  Evidence: The migration updates seed lot 1 as feminized source material, creates a regular BS01 line/seed lot if missing, and updates only `WHERE key = 'SBBS-R1-006'`.

- Observation: MSW is intentionally removed from active frontend code, so the mock-backed Breeding Logbook should not reintroduce a service-worker API layer.
  Evidence: `docs/epics/hosted-website-control-plane/GeneratedApiMigrationExecPlan.md` records MSW removal and says deterministic hosted data should use a real test seam or direct fixtures, not mock API route handlers.

- Observation: `docs/rules/data-modeling.md` was refined during planning to distinguish object tables from lookup tables.
  Evidence: The operator clarified that object tables should use integer `id`, while lookup tables represent controlled strings with structured metadata and should use plain `key` as their primary key. The rule now documents `plant.sex_key REFERENCES plant_lku_sex(key)` and `seed_lot.sex_type_key REFERENCES seed_lot_lku_sex_type(key)`.

- Observation: Human/LLM visual review should be run as a structured rubric loop rather than a one-off "looks close" judgment.
  Evidence: Braintrust describes human-in-the-loop evaluation as reviewer scoring against a defined rubric and using feedback to calibrate future evaluation; Phoenix documents aligning LLM evals to human annotations by iterating evaluator prompts against human ground truth; iRULER studies iterative rubric refinement for LLM evaluation; Anthropic's Constitutional AI work is an adjacent critique/revision loop pattern. Sources: `https://www.braintrust.dev/articles/human-in-the-loop-evals-for-llm-apps`, `https://arize.com/docs/phoenix/cookbook/human-in-the-loop-workflows-annotations/aligning-llm-evals-with-human-annotations-typescript`, `https://arxiv.org/html/2602.12779v1`, and `https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback`.


## Decision Log

- Decision: Replace the current dashboard prototype selector and remove the recent prototype code.
  Rationale: The `Plant Workbench` and `Generation Notebook` selector was exploratory. Breeding Logbook is now the selected product direction and should supersede that code directly.
  Date/Author: 2026-06-18 / Operator

- Decision: Build the first Breeding Logbook UI as a production-shaped mock-backed feature using TanStack Query.
  Rationale: The goal is high-fidelity frontend integration and API-shape audit before wiring real backend writes. React Query already owns async data in `web-ui`, and using query hooks keeps the future cutover to real API calls local and inspectable.
  Date/Author: 2026-06-18 / Operator + Codex

- Decision: Keep all frontend mock data in `web-ui/src/features/breeding-logbook/breedingLogbook.mockData.ts`.
  Rationale: The mock data should be obvious, centralized, and easy to delete or compare against the future generated API contract. Query functions may live near the feature but must import their data from this one file.
  Date/Author: 2026-06-18 / Operator

- Decision: Do not implement real hosted write paths in this plan.
  Rationale: Backend mutation architecture for local source-of-truth changes is not in scope. Mock-backed UI interactions may mutate React Query cache or route-local feature state to exercise behavior, but they must not pretend to be durable writes.
  Date/Author: 2026-06-18 / Operator

- Decision: Add durable plant sex and seed-lot sex type to the database as part of this plan.
  Rationale: The UI needs current sex and seed-lot regular/feminized facts. Encoding these only in notes, descriptions, or event metadata is not queryable or truthful enough.
  Date/Author: 2026-06-18 / Operator

- Decision: Model plant sex as a lookup table named `plant_lku_sex` with plain string primary key values `unknown`, `male`, `female`, `herm`, and `reversed`.
  Rationale: Plant sex is a controlled string set with display and semantic metadata, not an object table. `plant.sex_key` should reference `plant_lku_sex.key`; application branching should use semantic lookup columns instead of matching key strings.
  Date/Author: 2026-06-18 / Operator

- Decision: Model seed-lot sex type as a lookup table named `seed_lot_lku_sex_type` with plain string primary key values `unknown`, `feminized`, and `regular`.
  Rationale: All seed lots are assumed photoperiod for this pass; regular/feminized is the needed queryable distinction. The lookup can carry semantic columns such as `is_feminized` and `is_regular` so code does not branch on sentinel strings. Additional seed traits such as auto/photoperiod are out of scope unless future requirements need them.
  Date/Author: 2026-06-18 / Operator

- Decision: Seed current data so Plants A-D are feminized seed-lot material and R1-R5 are regular seed-lot material with male plant sex.
  Rationale: The operator explicitly wants current source records corrected as part of the migration. Existing untracked correction work only handles R2; this plan broadens the correction to all Track A R1-R5 plants.
  Date/Author: 2026-06-18 / Operator

- Decision: Treat `breeding` as a tent/location, not a lifecycle stage.
  Rationale: Lifecycle should remain derived from plant timestamps and durable facts; tents and locations are represented through `plant_location_history`.
  Date/Author: 2026-06-18 / Operator

- Decision: Implement real pointer/mouse drag-and-drop for the board in the mock-backed UI.
  Rationale: The board interaction is central to the prototype. Keyboard-accessible DnD is not required for v1, while the bulk Move control remains the non-drag path.
  Date/Author: 2026-06-18 / Operator

- Decision: Use an LLM-assisted screenshot comparison loop with human review for visual acceptance.
  Rationale: Pixel-perfect automation is likely brittle for this high-fidelity port. A structured rubric plus human corrections can encode operator preferences over successive reviews and catch visual issues that simple screenshot diffing misses.
  Date/Author: 2026-06-18 / Operator + Codex


## Outcomes & Retrospective

No implementation milestones have been completed yet. Fill this section after each milestone with changed files, validation commands, screenshots, API audit artifacts, and any tradeoffs accepted during the human review loop.


## Context and Orientation

The target repository is Dirt: Python services under `apps/`, hosted control-plane API under `apps/control-plane`, generated browser API schema under `web-ui/src/api-client/generated/hosted-schema.ts`, and React/TanStack Router frontend under `web-ui/`. The frontend uses React 19, TanStack Router v1, TanStack Query, Tailwind v4 tokens in `web-ui/src/styles.css`, and a generated OpenAPI client in `web-ui/src/api-client/hosted.ts`.

The design reference lives in `debug/design_handoff_breeding_logbook/`:

- `README.md` describes the high-fidelity Breeding Logbook design, expected behavior, data shape, and design tokens.
- `Breeding Logbook.dc.html` is the source-of-truth prototype markup and script. The script defines state transitions for list/table, board, selection, bulk sex/move/cull, add seed lot, germinate plants, clone plants, note logging, and detail event rendering.
- `Breeding Logbook (standalone).html` is the offline browser app used as the visual comparison reference.
- `screenshots/01-plants-table.png` through `08-dark-theme.png` are reference states for visual acceptance.

Current frontend state:

- `web-ui/src/routes/index.tsx` is the hosted dashboard route. It currently contains real hosted dashboard queries plus an uncommitted temporary `View` selector that switches to static `Plant Workbench` and `Generation Notebook` prototypes.
- `web-ui/src/prototypes/plantManagementPrototype.mockData.ts` is the uncommitted static data source for those prototypes. This plan removes it and replaces it with feature-owned Breeding Logbook mock data.
- `web-ui/src/routes/tents.$tentId.plants.$plantId.tsx` is the existing hosted plant detail route. It can be reused as API orientation but should not block the mock-backed Breeding Logbook detail view.
- `web-ui/src/ui/Gauge.tsx`, `Sparkline.tsx`, `RangeSwitch.tsx`, `HoverTimestamp.tsx`, and `TopBar.tsx` are existing UI primitives. Reuse them when they match the design; add Breeding Logbook-specific primitives under the feature directory when reuse would contort general components.

Current backend state:

- Local durable breeding records live in `apps/shared/src/dirt_shared/models/plant.py`: `PlantLine`, `CrossEvent`, `SeedLot`, `Plant`, `PlantLocationHistory`, `PlantNote`, `PlantEvent`, and `PlantMetricStream`.
- `Plant` has lifecycle timestamps, provenance FKs, and selection/cull facts, but no current sex field.
- `SeedLot` has purchased/produced facts and notes, but no regular/feminized field.
- Gateway catalog DTOs live in `apps/shared/src/dirt_shared/cloud_contract.py`. The gateway collects local projections in `apps/gateway/src/dirt_gateway/local.py`, and cloud upserts live in `apps/control-plane/src/dirt_control/api/gateway.py`.
- Hosted browser DTOs and routes live in `apps/control-plane/src/dirt_control/api/browser.py`, then `scripts/gen-hosted-contract` regenerates `contracts/hosted-browser-v1.json` and `web-ui/src/api-client/generated/hosted-schema.ts`.

Required docs before implementation:

- `docs/commands.md` before running commands.
- `docs/database.md`, `docs/rules/data-modeling.md`, and `docs/references/atlas/INDEX.md` before schema/migration work.
- `docs/rules/boundary-contracts.md` before changing browser/gateway DTOs.
- `docs/rules/simple-clean-architecture.md` before choosing abstractions or compatibility.
- `docs/references/tanstack-router-v1/INDEX.md`, `docs/references/modern-idiomatic-typescript/INDEX.md`, and `docs/references/tailwind-v4/INDEX.md` before frontend work.


## Plan of Work

Milestone 1 removes the temporary prototypes and creates the production-shaped Breeding Logbook frontend shell.

Remove `web-ui/src/prototypes/plantManagementPrototype.mockData.ts` and all imports/components in `web-ui/src/routes/index.tsx` that support `Plant Workbench`, `Generation Notebook`, and the `View` selector. The dashboard route should return to the real hosted dashboard only.

Add a new route for the Breeding Logbook under `web-ui/src/routes/`, using TanStack Router file-based routing. The recommended route is `web-ui/src/routes/breeding-logbook.tsx` with `createFileRoute("/breeding-logbook")`. Because the standalone prototype owns its own sticky top bar and visual shell, update `web-ui/src/routes/__root.tsx` and `web-ui/src/ui/TopBar.tsx` deliberately: either include a top-level nav entry that navigates to `/breeding-logbook` and let the route render inside the global app chrome, or suppress global chrome for this route and rely on the Breeding Logbook top bar for parity. The implementation should choose the option that makes the LLM/human screenshot comparison to the standalone app meaningful. If suppressing global chrome, record that decision in this plan and add a route-level way back to the dashboard only if the operator asks for it; do not add extra chrome that breaks the reference comparison by default.

Create the feature directory:

    web-ui/src/features/breeding-logbook/

Use production-ish names:

- `BreedingLogbookPage.tsx` for the route component.
- `breedingLogbook.mockData.ts` as the only mock-data source.
- `breedingLogbookQueries.ts` for query functions/hooks that currently return mock data.
- `breedingLogbookTypes.ts` for frontend DTO-like types that mirror the proposed browser API.
- Small component files such as `BreedingLogbookTopBar.tsx`, `PlantListTable.tsx`, `PlantBoard.tsx`, `BulkActionToolbar.tsx`, `SeedLotForm.tsx`, `AddPlantsForm.tsx`, and `PlantJournalDetail.tsx` only when this improves readability. Avoid broad component abstraction until the UI composition proves the split.

All `useQuery` calls for the Breeding Logbook must go through query functions in `breedingLogbookQueries.ts`. Those query functions must return deterministic mock objects imported from `breedingLogbook.mockData.ts`. Do not use MSW, URL fixture parameters, or raw generated API response interfaces in the mock-backed phase.

Milestone 2 adds durable plant sex and seed-lot sex type.

Edit `apps/shared/src/dirt_shared/models/plant.py` to add two lookup tables and two FKs:

- `PlantLkuSex`: table name `plant_lku_sex`, primary key `key text`, required fields `display_name text not null`, `display_order int not null`, and semantic boolean columns for branching such as `is_male`, `is_female`, `is_intersex`, and `is_reversed`.
- `SeedLotLkuSexType`: table name `seed_lot_lku_sex_type`, primary key `key text`, required fields `display_name text not null`, `display_order int not null`, and semantic boolean columns for branching such as `is_feminized` and `is_regular`.
- `Plant.sex_key text not null default 'unknown' references plant_lku_sex(key)`.
- `SeedLot.sex_type_key text not null default 'unknown' references seed_lot_lku_sex_type(key)`.

The lookup keys are:

- Plant sex: `unknown`, `male`, `female`, `herm`, `reversed`.
- Seed-lot sex type: `unknown`, `feminized`, `regular`.

Add source comments and migration comments explaining that these are lookup tables: controlled string values with display and semantic metadata. Avoid stuttered lookup PK names such as `plant_sex_key`; the lookup table PK is plain `key`, and referencing object tables carry the context in columns like `plant.sex_key`.

Generate a local Atlas migration. The migration must:

1. Create and seed `plant_lku_sex` and `seed_lot_lku_sex_type`.
2. Add `plant.sex_key` and `seed_lot.sex_type_key` with safe defaults.
3. Set Plants A-D (`SBBS-R1-001` through `SBBS-R1-004`) to seed lot sex type `feminized`.
4. Ensure Track A R1-R5 (`SBBS-R1-005` through `SBBS-R1-009`) are tied to a regular seed lot and set that seed lot's sex type to `regular`.
5. Set plant sex for all five Track A plants to `male`.
6. Leave other plants as `unknown` unless a more specific source fact already exists and is explicitly migrated.

Because `migrations/20260614213709_correct_seed_lot_sources.sql` is already present and untracked in this worktree, implementation must handle it deliberately. If it has not been applied anywhere, revise or supersede it in the same branch so the new migration corrects all R1-R5 plants, not only R2. If it has already been applied in the local DB, add a later migration that broadens the correction idempotently. Do not leave two migrations whose seed-lot intent conflicts.

Update cloud projection only after the local source model is correct:

- Extend `CatalogSeedLot` and `CatalogPlant` in `apps/shared/src/dirt_shared/cloud_contract.py` with `sex_type_key` and `sex_key`.
- Extend `CloudSeedLot` and `CloudPlant` in `apps/control-plane/src/dirt_control/models/cloud.py` with the same string fields. Cloud-side lookup tables are optional for the first projection; if added, mirror local keys and document why. If not added, enforce the allowed keys at the Pydantic boundary and keep cloud storage as projected string facts.
- Update `apps/gateway/src/dirt_gateway/local.py` to collect the new fields.
- Update `apps/control-plane/src/dirt_control/api/gateway.py` upserts.
- Update browser response models in `apps/control-plane/src/dirt_control/api/browser.py` where plant and seed-lot responses need these fields.
- Run `scripts/gen-hosted-contract` after browser response shape changes.

Milestone 3 builds the mock-backed Breeding Logbook views.

Port the behavior from `Breeding Logbook.dc.html` into React, but do not paste the prototype code. Use the existing Dirt design tokens from `web-ui/src/styles.css`: paper/ink colors, square corners, rule-gap grids, mono uppercase labels, Fraunces wordmark, magenta accents, and dark mode through `data-theme="dark"`.

The page-level state should follow the prototype:

- View/tab: `plants`, `add-seeds`, `add-plants`, and `detail`.
- List layout: `table` or `board`.
- Grouping: `stage` or `parents` for table only.
- Show culled toggle.
- Selected plant keys set.
- Bulk panel: `sex`, `move`, `cull`, or null.
- Add seed lot draft.
- Add plants mode: `germinate` or `clone`.
- Detail plant id and note composer text.

Query-backed data should include:

- Lookup data: plant sex values, seed-lot sex type values, tent/location options.
- Plant population with sex, lifecycle dates, current location/tent, line/provenance summary, last note/event summary, and telemetry summary.
- Seed lots with label, prefix, generation, parents/source, sex type, seed count when known.
- Plant detail with identity facts, lineage, event timeline, notes, and environment summary.
- Plant metric summaries/history for the detail environment panel.

Mock interactions may update local route state or React Query cache to preserve prototype behavior:

- Selecting plants shows bulk toolbar.
- Bulk sex changes mock plant sex in the cache.
- Bulk move changes mock plant location/tent in the cache and appends a mock move event.
- Bulk cull marks plants culled in the cache.
- Add seed lot prepends a mock seed lot.
- Sow plants and take clones append mock plant rows.
- Log note prepends a mock note event.

Keep these writes clearly mock-local. Name functions accordingly, for example `applyMockBulkMove`, so no implementer mistakes them for durable backend writes.

Implement pointer/mouse drag-and-drop for board chips without adding a heavy DnD dependency unless the implementation proves native pointer events are insufficient. Dragging a plant chip to a stage/location column should update the same mock cache path as bulk Move and add a mock move event. The board must still support selection plus the bulk Move toolbar as the non-drag path.

Milestone 4 audits and proposes the real API shape.

Create or update a document under `docs/epics/breeding-logbook-ui/`, recommended path `docs/epics/breeding-logbook-ui/api-audit.md`. This is part of the implementation deliverable, not a separate proposal. It must map every frontend query in `breedingLogbookQueries.ts` to a proposed browser API endpoint and response DTO.

The API shape should be ergonomic for the frontend and boundary-correct for the backend. Prefer endpoint responses that match whole screen needs over forcing the browser to reconstruct domain relationships with many tiny calls. Proposed read endpoints:

- `GET /api/breeding-logbook/bootstrap`
  Returns lookup rows, site/tent/location choices, and any global feature metadata needed before rendering.

- `GET /api/breeding-logbook/plants?include_culled=false&group_by=stage`
  Returns the list/table/board plant rows across relevant tents for the active site. Includes current location/tent, lifecycle-derived stage, sex, seed-lot/line summary, parent summary, last note/event summary, and telemetry count.

- `GET /api/breeding-logbook/seed-lots`
  Returns seed lots on file, including lots with no current plants. This fixes the current gateway behavior that only projects seed lots joined through current plants.

- `GET /api/breeding-logbook/plants/{plant_key}`
  Returns the detail screen model: identity facts, lineage, current location, sex, lifecycle dates, notes, events, offspring/seed-lot summary, wiki projection if relevant, and environment summary.

- `GET /api/breeding-logbook/plants/{plant_key}/metrics/history?range=24h`
  Returns plant-scoped metric streams needed for the detail environment panel, using the existing mapped telemetry model.

Proposed future mutation endpoints should be documented but out of scope for implementation:

- `POST /api/breeding-logbook/seed-lots`
- `POST /api/breeding-logbook/plants:germinate`
- `POST /api/breeding-logbook/plants:clone`
- `PATCH /api/breeding-logbook/plants/{plant_key}/sex`
- `POST /api/breeding-logbook/plants:bulk-move`
- `POST /api/breeding-logbook/plants:bulk-cull`
- `POST /api/breeding-logbook/plants/{plant_key}/notes`

The audit must state that real hosted writes require a later command/sync design because the hosted control plane is not the local source of truth. Do not implement these mutation endpoints in this plan.

Milestone 5 validates visually with `agent-browser` and the LLM/human review loop.

Start the local hosted stack using the documented flow:

    make dev-up
    make dev-status

Open the Web URL from `make dev-status` with `agent-browser`, log in with `dev-admin` / `dev-password`, navigate to `/breeding-logbook`, and capture screenshots for the same states as the design bundle:

- Plants table.
- Plants board.
- Bulk actions open.
- Add seeds.
- Add plants germinate.
- Add plants clone.
- Plant detail.
- Dark theme.

Also open `debug/design_handoff_breeding_logbook/Breeding Logbook (standalone).html` through `agent-browser` with `--allow-file-access` if needed, or use the provided screenshots as the reference if local file access is awkward.

For each comparison, have the reviewing LLM produce a structured report:

- Reference screenshot path.
- App screenshot path.
- Overall judgment: `close_enough`, `needs_iteration`, or `blocked`.
- Rubric scores from 0 to 3 for layout geometry, spacing/density, typography, color/theme, component fidelity, interaction state, content/data fidelity, and responsive/text fit where applicable.
- Specific mismatches, ordered by visual impact.
- Suggested fix candidates.
- Explicit assumptions.

The operator must review each report. Record operator feedback in `docs/epics/breeding-logbook-ui/visual-review-notes.md` with timestamp, screenshot pair, accepted differences, rejected differences, and new preference guidance. Feed the accumulated guidance into the next screenshot review prompt. This creates a practical human/agent preference alignment loop: the LLM judges against a stable rubric, the human corrects it, and the corrections become future review context.

Do not mark visual acceptance complete until the operator agrees the screenshot set is close enough or explicitly accepts remaining differences.


## Concrete Steps

Start from the repository root:

    cd /home/akcom/code/dirt

Before implementation, inspect dirty files:

    git status --short
    git diff -- web-ui/src/routes/index.tsx web-ui/src/prototypes/plantManagementPrototype.mockData.ts
    git diff -- migrations/20260614213709_correct_seed_lot_sources.sql

Read required docs:

    sed -n '1,240p' docs/commands.md
    sed -n '1,260p' docs/database.md
    sed -n '1,240p' docs/rules/simple-clean-architecture.md
    sed -n '1,220p' docs/rules/data-modeling.md
    sed -n '1,220p' docs/rules/boundary-contracts.md
    sed -n '1,220p' docs/references/atlas/INDEX.md
    sed -n '1,220p' docs/references/tanstack-router-v1/INDEX.md
    sed -n '1,220p' docs/references/modern-idiomatic-typescript/INDEX.md
    sed -n '1,220p' docs/references/tailwind-v4/INDEX.md

Inspect the design source:

    sed -n '1,260p' debug/design_handoff_breeding_logbook/README.md
    sed -n '450,961p' 'debug/design_handoff_breeding_logbook/Breeding Logbook.dc.html'

Implement frontend cleanup and route:

    rg -n "PlantWorkbench|GenerationNotebook|PlantManagementPrototype|PLANT_MANAGEMENT_PROTOTYPE|prototypes" web-ui/src

Expected result after cleanup: no references to the old prototype selector or `web-ui/src/prototypes`.

Implement the DB model changes in:

    apps/shared/src/dirt_shared/models/plant.py
    apps/shared/src/dirt_shared/models/__init__.py

Generate and review local migration:

    atlas migrate diff plant_sex_seed_lot_type --env local
    atlas migrate hash --env local
    atlas migrate apply --env local --dry-run

If Atlas diff hits the known `btree_gist` dev-database issue from the breeding data-model plan, use the same externally initialized disposable dev database pattern recorded in `docs/epics/breeding-data-model/ExecPlan.md`; do not hand-apply DDL.

Run focused backend tests after model/contract changes:

    uv run pytest apps/shared/tests/test_cloud_contract.py -q
    uv run pytest apps/gateway/tests/test_sync.py apps/gateway/tests/test_gateway_boundary_guardrails.py -q
    uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q
    uv run pytest apps/tests/invariants -q

Regenerate hosted contract after browser API DTO changes:

    DIRT_CLOUD_ASSET_STORE=local scripts/gen-hosted-contract

Run frontend validation:

    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test
    pnpm --dir web-ui build

Run local browser validation:

    make dev-up
    make dev-status

Use the Web URL printed by `make dev-status`:

    agent-browser --session breeding-logbook set viewport 1360 940
    agent-browser --session breeding-logbook open <Web URL>
    agent-browser --session breeding-logbook fill "input[name='username']" dev-admin
    agent-browser --session breeding-logbook fill "input[name='password']" dev-password
    agent-browser --session breeding-logbook click "button[type='submit']"
    agent-browser --session breeding-logbook open <Web URL>/breeding-logbook
    agent-browser --session breeding-logbook screenshot debug/screenshots/breeding-logbook-plants-table.png

Adjust selectors based on `agent-browser snapshot -i -c`; do not guess brittle selectors if accessible roles are available.


## Validation and Acceptance

Backend acceptance:

- `plant_lku_sex` contains exactly the expected keys `unknown`, `male`, `female`, `herm`, and `reversed` with display names, stable display order, and semantic columns for branching.
- `seed_lot_lku_sex_type` contains exactly the expected keys `unknown`, `feminized`, and `regular` with display names, stable display order, and semantic columns for branching.
- `plant.sex_key` is required and references `plant_lku_sex(key)`.
- `seed_lot.sex_type_key` is required and references `seed_lot_lku_sex_type(key)`.
- Plants A-D are tied to feminized seed-lot material.
- Track A R1-R5 are tied to regular seed-lot material and have `plant.sex_key='male'`.
- Gateway and cloud projection DTOs carry the new fields without raw `dict[str, Any]` boundary payloads.
- Generated hosted browser schema reflects any browser DTO fields added by the API audit implementation.

Frontend acceptance:

- The dashboard no longer has the temporary `View` selector.
- `web-ui/src/prototypes/` is gone unless another unrelated user-owned file appears there during implementation; if so, stop and inspect before deleting.
- `/breeding-logbook` renders the Breeding Logbook, not a marketing page or placeholder.
- All Breeding Logbook queries use TanStack Query and currently resolve through mock query functions.
- All Breeding Logbook mock data lives in `web-ui/src/features/breeding-logbook/breedingLogbook.mockData.ts`.
- Plants table, board, bulk toolbar, Add seeds, Add plants germinate/clone, plant detail, note composer, and dark theme are implemented.
- Pointer drag on a board chip changes the mock plant location/stage grouping and records a mock move event.
- No MSW, service worker, or `cloud_fixture` behavior is reintroduced.
- No old `PlantWorkbench`, `GenerationNotebook`, or `PlantManagementPrototype` symbols remain.

Visual acceptance:

- `agent-browser` screenshots are captured for all eight reference states.
- Each screenshot pair has an LLM review report using the rubric in this plan.
- Operator feedback is recorded in `docs/epics/breeding-logbook-ui/visual-review-notes.md`.
- Feedback from one comparison is included as context in the next comparison.
- Final visual acceptance is operator-approved, not model-only.


## Idempotence and Recovery

Frontend cleanup is safe to repeat if guided by `rg` searches for the old prototype names. Do not delete unrelated dirty files without inspecting them.

Mock query implementation is safe to repeat because it is local to `web-ui/src/features/breeding-logbook/`. Keep mock data deterministic and avoid `Date.now()` in initial fixtures; if interaction handlers need generated IDs, wrap generation in a small helper and keep it mock-local.

Atlas migration generation is not idempotent if repeated blindly because it creates timestamped files. If a generated migration is wrong before it is applied, delete only the newly generated file you created and rerun `atlas migrate diff`, then `atlas migrate hash`. If a migration has been applied locally, add a follow-up migration rather than editing applied history.

The seed-lot correction work must account for `migrations/20260614213709_correct_seed_lot_sources.sql`. Before editing it, check whether the live local database has applied it with:

    atlas migrate status --env local

If unapplied, it can be revised or superseded before apply. If applied, do not edit it; create a new migration that safely corrects R1-R5.

Local browser sessions are safe to recreate:

    agent-browser --session breeding-logbook close

Then reopen with the local Web URL from `make dev-status`.

If `make dev-up` reports the dev database is missing or stale, follow `docs/commands.md`:

    make dev-refresh-db
    make dev-up

Do not run destructive database reset commands outside the documented dev lifecycle.


## Artifacts and Notes

Reference bundle:

- `debug/design_handoff_breeding_logbook/README.md`
- `debug/design_handoff_breeding_logbook/Breeding Logbook.dc.html`
- `debug/design_handoff_breeding_logbook/Breeding Logbook (standalone).html`
- `debug/design_handoff_breeding_logbook/screenshots/01-plants-table.png`
- `debug/design_handoff_breeding_logbook/screenshots/02-plants-board.png`
- `debug/design_handoff_breeding_logbook/screenshots/03-bulk-actions.png`
- `debug/design_handoff_breeding_logbook/screenshots/04-add-seeds.png`
- `debug/design_handoff_breeding_logbook/screenshots/05-add-plants-germinate.png`
- `debug/design_handoff_breeding_logbook/screenshots/06-add-plants-clone.png`
- `debug/design_handoff_breeding_logbook/screenshots/07-plant-detail.png`
- `debug/design_handoff_breeding_logbook/screenshots/08-dark-theme.png`

Human/LLM review-cycle references used to ground Milestone 5:

- Braintrust, human-in-the-loop evals: `https://www.braintrust.dev/articles/human-in-the-loop-evals-for-llm-apps`
- Arize Phoenix, aligning LLM evals with human feedback: `https://arize.com/docs/phoenix/cookbook/human-in-the-loop-workflows-annotations/aligning-llm-evals-with-human-annotations-typescript`
- iRULER rubric refinement: `https://arxiv.org/html/2602.12779v1`
- Anthropic Constitutional AI critique/revision pattern: `https://www.anthropic.com/research/constitutional-ai-harmlessness-from-ai-feedback`

Implementation should add:

- `docs/epics/breeding-logbook-ui/api-audit.md`
- `docs/epics/breeding-logbook-ui/visual-review-notes.md`
- Screenshot artifacts under `debug/screenshots/` or `var/dev/control-plane/screenshots/`, with paths recorded in `visual-review-notes.md`.


## Interfaces and Dependencies

Frontend interfaces:

- Route: `/breeding-logbook`, implemented with TanStack Router v1.
- Feature root: `web-ui/src/features/breeding-logbook/`.
- Mock data source: `web-ui/src/features/breeding-logbook/breedingLogbook.mockData.ts`.
- Query layer: TanStack Query hooks/functions in `breedingLogbookQueries.ts`, returning mock data until real API wiring lands.
- Styling: Tailwind v4 utilities backed by the existing Dirt CSS variables in `web-ui/src/styles.css`.
- Browser verification: `agent-browser`, not raw Playwright.

Local database interfaces:

- `plant_lku_sex(key, display_name, display_order, is_male, is_female, is_intersex, is_reversed)`.
- `seed_lot_lku_sex_type(key, display_name, display_order, is_feminized, is_regular)`.
- `plant.sex_key -> plant_lku_sex.key`.
- `seed_lot.sex_type_key -> seed_lot_lku_sex_type.key`.

Gateway/cloud interfaces:

- `CatalogPlant.sex_key`.
- `CatalogSeedLot.sex_type_key`.
- `CloudPlant.sex_key`.
- `CloudSeedLot.sex_type_key`.
- Browser plant/seed-lot DTO fields carrying sex display data or keys as determined by `api-audit.md`.

Proposed future browser API interfaces:

- `GET /api/breeding-logbook/bootstrap`
- `GET /api/breeding-logbook/plants`
- `GET /api/breeding-logbook/seed-lots`
- `GET /api/breeding-logbook/plants/{plant_key}`
- `GET /api/breeding-logbook/plants/{plant_key}/metrics/history`

Out-of-scope future mutation interfaces:

- `POST /api/breeding-logbook/seed-lots`
- `POST /api/breeding-logbook/plants:germinate`
- `POST /api/breeding-logbook/plants:clone`
- `PATCH /api/breeding-logbook/plants/{plant_key}/sex`
- `POST /api/breeding-logbook/plants:bulk-move`
- `POST /api/breeding-logbook/plants:bulk-cull`
- `POST /api/breeding-logbook/plants/{plant_key}/notes`


## Revision Notes

- 2026-06-18 / Codex: Initial plan drafted after reviewing the handoff prototype, current web UI, current plant data model, hosted browser APIs, existing breeding data-model plans, and operator clarifications.
