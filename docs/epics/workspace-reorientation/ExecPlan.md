# Tents, Plants, and Seeds Workspace Reorientation

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, the hosted Dirt web UI is organized around the three real operator workspaces: `Tents`, `Plants`, and `Seeds`. The current dashboard becomes the `Tents` workspace because it is already centered on physical tent state: metrics, schedules, devices, assets, plants currently in the tent, and gateway status. The current Breeding Logbook is split into a canonical `Plants` workspace and a canonical `Seeds` workspace. Operators can deep link directly to list, create, detail, and edit flows such as `/plants`, `/plants/new`, `/plants/$plantKey`, `/plants/$plantKey/edit`, `/seeds`, `/seeds/new`, `/seeds/$seedLotId`, and `/seeds/$seedLotId/edit`.

This matters because the app should match how work is actually done. Tent work is environment and controller intent. Plant work is living plant operations, defaulting to active plants with an archive filter. Seed work is seed-lot inventory. The old top-level `Live` and `Wiki` routes are unused in the web UI and should be deleted rather than preserved as dead surfaces.

The work is complete when the top navigation is exactly `Tents`, `Plants`, and `Seeds`; `/` lands on the Tents workspace; `/live`, `/wiki`, and `/breeding-logbook` are gone from the web UI; plant and seed-lot list/create/detail/edit pages are routable; seed-lot detail and edit are backed by explicit browser API DTOs and command-backed mutations where writes cross to the local source of truth; and local browser verification shows the three workspaces functioning through the real dev auth flow.


## Progress

- [x] (2026-06-21) Read `docs/commands.md`, `.agents/PLANS.md`, `docs/rules/simple-clean-architecture.md`, `docs/rules/frontend-server-state.md`, `docs/rules/boundary-contracts.md`, and relevant TanStack Router/Query/TypeScript reference indexes.
- [x] (2026-06-21) Inspected the current `web-ui/src/routes/` tree, top bar, dashboard route, live route, wiki route, breeding-logbook feature, generated hosted schema references, control-plane breeding-logbook API, shared cloud command contract, and gateway breeding command executor.
- [x] (2026-06-21) Confirmed the operator decisions: delete Live/Wiki from the web UI only; top nav becomes Tents/Plants/Seeds; `/` lands on Tents; Tents means physical tents; Plants defaults active with an archive filter; Seeds means seed lots; adding a seed lot is seed inventory work; germination/clone creation is plant work; plants originate from seed lots or clones; seed-lot detail/edit pages are required for consistency.
- [x] (2026-06-21) Drafted this ExecPlan.
- [x] (2026-06-21 18:37 MDT) Milestone 1 complete: deleted unused `/live` and `/wiki` web UI routes, removed `Live`/`Wiki` top-nav tabs, removed unused wiki localStorage helpers, and regenerated `web-ui/src/routeTree.gen.ts` through the Vite/TanStack Router toolchain.
- [x] (2026-06-21 18:55 MDT) Milestone 2 complete: established the canonical workspace route files, moved the dashboard implementation to `/tents`, redirected `/` to `/tents`, added temporary routable Plants/Seeds/detail/edit placeholders, removed `/breeding-logbook`, and regenerated `web-ui/src/routeTree.gen.ts`.
- [x] (2026-06-21 19:09 MDT) Milestone 3 complete: extracted the hosted dashboard into `web-ui/src/features/tents/TentsWorkspace.tsx`, made `/tents` choose a default physical tent, rendered `/tents/$sourceTentId` from the route param, and changed tent selection to typed route navigation.
- [x] (2026-06-21 19:36 MDT) Milestone 4 complete: split the Breeding Logbook frontend into canonical Plants routes, moved plant UI/query/mutation/type code to `web-ui/src/features/plants`, made `/plants` list state URL-backed, added routable plant create/detail/edit flows, linked Tents plant cards to `/plants/$plantKey`, and removed the old tent-scoped plant detail route.
- [ ] Milestone 5: add seed-lot detail/edit API and command contracts.
- [ ] Milestone 6: split seed-lot list/create/detail/edit into routable Seeds pages.
- [ ] Milestone 7: validate with focused tests, generated contracts, local browser screenshots, and dead-code checks.


## Surprises & Discoveries

- Observation: The current route tree is small enough for a direct cutover.
  Evidence: `web-ui/src/routes/` contains `index.tsx`, `live.tsx`, `wiki.tsx`, `breeding-logbook.tsx`, `login.tsx`, `__root.tsx`, and `tents.$sourceTentId.plants.$plantId.tsx`.

- Observation: The hosted wiki route is only a placeholder, but wiki-specific localStorage helpers remain.
  Evidence: `web-ui/src/routes/wiki.tsx` renders "Wiki unavailable" and makes no network calls; `web-ui/src/shared/storage.ts` still exports `readRecentWikiFiles`, `pushRecentWikiFile`, `readExpandedWikiFolders`, and `writeExpandedWikiFolders`.

- Observation: The Live route contains the only web UI PTZ controls, but deleting the web route does not imply deleting backend PTZ command support.
  Evidence: `web-ui/src/routes/live.tsx` owns `/live`; PTZ command DTOs and gateway command execution also support other clients and should remain unless a separate backend cleanup proves they are dead.

- Observation: The current Breeding Logbook frontend is one large route-local state machine instead of routable pages.
  Evidence: `web-ui/src/features/breeding-logbook/BreedingLogbookPage.tsx` stores `view: "plants" | "add-seeds" | "add-plants" | "detail"` in React state and switches between surfaces inside one component.

- Observation: Plant list, plant detail, add seed lot, germinate, clone, bulk plant edits, cull, and notes already have browser API/query/mutation wiring. Seed-lot detail and seed-lot update do not.
  Evidence: `apps/control-plane/src/dirt_control/api/browser/breeding_logbook.py` exposes `GET /api/breeding-logbook/seed-lots` and `POST /api/breeding-logbook/seed-lots`, but no `GET /api/breeding-logbook/seed-lots/{seed_lot_id}` and no seed-lot update command route.

- Observation: Seed-lot inventory editing should not pretend to edit every piece of lineage identity.
  Evidence: local `SeedLot` owns `sex_type_key`, `is_purchased`, `vendor_name`, `acquired_at`, `produced_by_cross_event_id`, `seed_count`, and `notes`; line identity lives on `PlantLine`, and cross parent identity lives through `CrossEvent`.

- Observation: The frontend dead-code invariant requires the existing breeding-logbook feature to stay reachable after deleting the stale `/breeding-logbook` route.
  Evidence: the first Milestone 2 commit attempt failed `apps/tests/invariants/test_typescript_dead_code.py::test_no_unused_files_exports_or_deps`; `pnpm knip` reported `src/features/breeding-logbook/BreedingLogbookPage.tsx` and its exported hooks/types as unused until the leaf `/plants` route temporarily rendered `BreedingLogbookPage`.

- Observation: Direct plant edit routes need their own form-draft hydration.
  Evidence: the first Milestone 4 implementation populated the plant facts draft only from the inline Edit click path; direct `/plants/$plantKey/edit` could render an empty draft until the route was corrected to initialize the draft from the fetched plant once per plant edit session.


## Decision Log

- Decision: Delete Live and Wiki only from the web UI.
  Rationale: The operator does not use the browser Live View or Wiki surfaces. The repository `wiki/`, daily report/wiki workflows, gateway wiki projection, and backend PTZ/gateway contracts may still serve non-web-UI workflows and are out of scope for this cleanup.
  Date/Author: 2026-06-21 / Operator

- Decision: The top-level app navigation is exactly `Tents`, `Plants`, and `Seeds`.
  Rationale: These are the operator's actual workspaces. Keeping `Dashboard`, `Live`, `Wiki`, or `Breeding Logbook` in top navigation preserves stale product structure.
  Date/Author: 2026-06-21 / Operator

- Decision: `/` lands on the Tents workspace.
  Rationale: The current dashboard is already the physical tent workspace. A separate home page would add a non-workspace landing layer that the operator did not ask for.
  Date/Author: 2026-06-21 / Operator

- Decision: Tents are physical tents, not grow cycles.
  Rationale: The future control workflow is "set this physical tent to veg or flower controller intent," which changes light cycle and VPD/default control bands. Grow-cycle intelligence is not the product goal; operator control is.
  Date/Author: 2026-06-21 / Operator

- Decision: Plant workspace defaults to active plants with an archive filter.
  Rationale: Active plants are the routine operational view. Culled/harvested plants should remain accessible without competing with daily plant work.
  Date/Author: 2026-06-21 / Operator

- Decision: Seeds workspace means seed lots.
  Rationale: The first-class seed object in the current data model and operator workflow is a seed lot. Germinating seeds creates plants and therefore belongs in `/plants/new`, not `/seeds/new`.
  Date/Author: 2026-06-21 / Operator

- Decision: Seed-lot edit initially covers seed-lot-owned inventory facts, not full lineage rewrites.
  Rationale: `SeedLot` owns inventory facts such as seed count, sex type, notes, and purchased acquisition/vendor facts. Prefix, generation, strain, cultivar, and source-name are `PlantLine` facts, and cross parents are `CrossEvent` facts. Editing those through a seed-lot page would cross ownership boundaries unless a later plan deliberately introduces line/cross editing.
  Date/Author: 2026-06-21 / Codex

- Decision: Remove the old `/breeding-logbook` web route instead of keeping it as a compatibility shell.
  Rationale: This is source-owned browser UI and the operator requested a direct reorientation. Keeping `/breeding-logbook` as a hidden wrapper would preserve stale language and make future route ownership harder to inspect.
  Date/Author: 2026-06-21 / Codex


## Outcomes & Retrospective

Milestone 1 removed the dead hosted Live and Wiki browser surfaces without touching backend PTZ/wiki projection code or repository wiki content. Validation passed with `pnpm --dir web-ui typecheck`, `pnpm --dir web-ui lint`, `git diff --check`, and the focused dead-code search `rg -n "HostedLive|WikiPage|readRecentWiki|pushRecentWiki|ExpandedWiki|/live|/wiki" web-ui/src`, which returned no matches.

Milestone 2 established the top-level workspace chrome with exactly `Tents`, `Plants`, and `Seeds`. `/` now redirects to `/tents`, `/breeding-logbook` is no longer a web route, `/login` is the only route without shared chrome, and canonical Plants/Seeds/Tents route files exist for later milestones to fill in. The leaf `/plants` route temporarily renders the existing `BreedingLogbookPage` so live plant functionality and dead-code invariants remain intact until Milestone 4 replaces it with canonical Plants pages. Validation passed with `pnpm --dir web-ui exec vite build`, `pnpm --dir web-ui typecheck`, `pnpm --dir web-ui lint`, `pnpm --dir web-ui test`, `pnpm --dir web-ui knip --no-progress`, `uv run pytest apps/tests/invariants/test_typescript_dead_code.py -q`, `git diff --check`, and the required stale-route search; the remaining `Wiki` matches are the retained projected-wiki labels in `web-ui/src/routes/tents.$sourceTentId.plants.$plantId.tsx`.

Milestone 3 made physical tent identity URL-owned while preserving existing tent data panels, refresh behavior, and the old tent-scoped plant detail child route. `/tents` now loads sites/tents and replaces to the first active/default physical tent, while `/tents/$sourceTentId` drives tent state, current metrics, presentation, history, plants, devices, light schedules, assets, and sync status from the route param. Validation passed with `pnpm --dir web-ui exec vite build`, `pnpm --dir web-ui typecheck`, `pnpm --dir web-ui lint`, `pnpm --dir web-ui test`, `pnpm --dir web-ui knip --no-progress`, `uv run pytest apps/tests/invariants/test_typescript_dead_code.py -q`, `git diff --check`, and the stale-reference search for `Dashboard`, state-only selected tent variables, and removed routes.

Milestone 4 replaced the temporary Breeding Logbook-mounted Plants route with canonical Plants pages. `/plants` now renders active plants by default and keeps layout, grouping, and visibility in URL search state; `/plants/new` owns germination and cloning; `/plants/$plantKey` and `/plants/$plantKey/edit` are deep-linkable and preserve command-backed pending/projection UX for germination, cloning, plant fact updates, culling, moving, sexing, and notes. Tent plant cards now link to `/plants/$plantKey`, and the old `/tents/$sourceTentId/plants/$plantId` route file is deleted. `/seeds/new` temporarily mounts the seed-lot creation form from the Plants workspace as a bridge until Milestone 6 implements full Seeds pages. Validation passed with `pnpm --dir web-ui exec vite build`, `pnpm --dir web-ui typecheck`, `pnpm --dir web-ui lint`, `pnpm --dir web-ui test`, `pnpm --dir web-ui knip --no-progress`, `uv run pytest apps/tests/invariants/test_typescript_dead_code.py -q`, focused stale-route searches, and `git diff --check`; remaining `Breeding Logbook` and `/api/breeding-logbook` matches are generated/backend browser API contract names.


## Context and Orientation

Dirt's hosted web UI lives under `web-ui/`. It uses React, TanStack Router v1 file routes in `web-ui/src/routes/`, TanStack Query v5, Tailwind v4 classes, and generated hosted API types from `web-ui/src/api-client/generated/hosted-schema.ts`. The generated schema is produced by `scripts/gen-hosted-contract` from FastAPI routes in `apps/control-plane`.

The current browser route structure is:

    web-ui/src/routes/index.tsx                         # /
    web-ui/src/routes/live.tsx                          # /live
    web-ui/src/routes/wiki.tsx                          # /wiki
    web-ui/src/routes/breeding-logbook.tsx              # /breeding-logbook
    web-ui/src/routes/tents.$sourceTentId.plants.$plantId.tsx
    web-ui/src/routes/login.tsx
    web-ui/src/routes/__root.tsx

`web-ui/src/ui/TopBar.tsx` currently labels the primary tabs as `Dashboard`, `Live`, and `Wiki`. `web-ui/src/routes/__root.tsx` hides shared chrome on `/login` and `/breeding-logbook`; after this plan, only `/login` should own a full viewport without the workspace top bar unless a later route has a concrete reason.

`web-ui/src/routes/index.tsx` is the current hosted dashboard. It fetches sites, tents, tent state, current metrics, metric presentation, plant summaries, history, devices, light schedules, latest assets, and sync status. This page is the starting point for the `Tents` workspace.

`web-ui/src/features/breeding-logbook/` is the current plant/seed surface. It already has query and mutation modules:

    web-ui/src/features/breeding-logbook/breedingLogbookQueries.ts
    web-ui/src/features/breeding-logbook/breedingLogbookMutations.ts
    web-ui/src/features/breeding-logbook/breedingLogbookTypes.ts
    web-ui/src/features/breeding-logbook/BreedingLogbookPage.tsx

The browser API backing those files is in:

    apps/control-plane/src/dirt_control/api/browser/breeding_logbook.py
    apps/control-plane/src/dirt_control/api/browser_schemas/breeding_logbook.py
    apps/control-plane/src/dirt_control/services/breeding_logbook.py

The existing command-backed plant and seed-lot create mutations use the shared cloud command contract in:

    apps/shared/src/dirt_shared/cloud_contract.py
    apps/gateway/src/dirt_gateway/breeding_commands.py
    apps/gateway/src/dirt_gateway/commands.py

The current local source tables for plant and seed-lot facts are in `apps/shared/src/dirt_shared/models/plant.py`. Seed lots are synced to cloud `CloudSeedLot` rows in `apps/control-plane/src/dirt_control/models/cloud.py` through `apps/gateway/src/dirt_gateway/local.py` and `apps/control-plane/src/dirt_control/api/gateway.py`.

Before implementation, read these docs:

    sed -n '1,240p' docs/commands.md
    sed -n '1,260p' docs/rules/simple-clean-architecture.md
    sed -n '1,260p' docs/rules/boundary-contracts.md
    sed -n '1,220p' docs/rules/frontend-server-state.md
    sed -n '1,220p' docs/references/tanstack-router-v1/INDEX.md
    sed -n '1,220p' docs/references/tanstack-query-v5/INDEX.md
    sed -n '1,220p' docs/references/modern-idiomatic-typescript/INDEX.md

If implementation changes Tailwind class-heavy layouts, also read:

    sed -n '1,220p' docs/references/tailwind-v4/INDEX.md

If implementation changes SQL schema or migrations, read `docs/database.md` and the Atlas reference pack first. This plan is written to avoid new database schema where possible; seed-lot detail/edit can be built from existing `SeedLot`, `PlantLine`, and `CrossEvent` facts.


## Plan of Work

Milestone 1 deletes unused web UI surfaces. Remove `web-ui/src/routes/live.tsx` and `web-ui/src/routes/wiki.tsx`. Remove `Live` and `Wiki` tabs from `web-ui/src/ui/TopBar.tsx`. Remove wiki-specific localStorage helpers from `web-ui/src/shared/storage.ts` if no remaining web UI imports use them. Search with `rg -n "wiki|Wiki|live|HostedLive|readRecentWiki|ExpandedWiki|/live|/wiki" web-ui/src` and delete dead frontend code that is reachable only from those web routes. Do not delete backend PTZ command code, backend wiki projection code, the repository `wiki/` directory, or daily report code in this milestone.

Milestone 2 establishes the new route IA and top-level chrome. Add or rename TanStack file routes so the canonical web routes are:

    /
    /tents
    /tents/$sourceTentId
    /plants
    /plants/new
    /plants/$plantKey
    /plants/$plantKey/edit
    /seeds
    /seeds/new
    /seeds/$seedLotId
    /seeds/$seedLotId/edit
    /login

The root `/` route should redirect or immediately navigate to `/tents`. Prefer a route-level redirect if that works cleanly with the current TanStack Router setup. The top bar should mark a tab active by route prefix, so `/plants/$plantKey/edit` still highlights `Plants`. Use typed TanStack Router `Link` or `navigate({ to, params, search })`; do not build route URLs with string interpolation.

Milestone 3 moves the dashboard into the Tents workspace. Extract the current dashboard implementation from `web-ui/src/routes/index.tsx` into a named feature component such as `web-ui/src/features/tents/TentsWorkspace.tsx`. `web-ui/src/routes/tents.tsx` should render the workspace shell or choose the default tent, and `web-ui/src/routes/tents.$sourceTentId.tsx` should render a specific physical tent. Preserve the existing tent data queries, metrics, history, assets, devices, light schedules, and sync status. Rename user-visible copy from `Dashboard` to `Tents` or tent-specific labels, and rename stale constants like `DASHBOARD_ROUTE` when they move.

Tent identity should be in the URL. If a site has multiple tents, the tent selector should navigate to `/tents/$sourceTentId` rather than only changing component state. `/tents` may show a loading/default-selection state while sites/tents load, then navigate to the first or operator-default tent. The plan does not implement editable tent controller profiles yet; do not add fake "veg/flower mode" controls that cannot persist. Keep the component structure ready for a future physical-tent intent panel by making the selected tent the central route param.

Milestone 4 splits Plants out of the current Breeding Logbook. Move plant-oriented frontend code from `web-ui/src/features/breeding-logbook/` into a canonical plant workspace module, for example `web-ui/src/features/plants/`. The `/plants` route should render the existing filterable/groupable plant list, default to active plants, and expose archived/culled/harvested plants through URL search state. Use TanStack Router `validateSearch` for list state such as layout, group-by, and archive visibility rather than keeping the whole workspace mode in component state.

Move "add plants" into `/plants/new`. This page owns germination and cloning because plants must originate from seed lots or clones. The existing `useGerminatePlantsMutation` and `useClonePlantsMutation` are command-backed mutations; preserve their pending command UX and projection refresh behavior per `docs/rules/frontend-server-state.md`.

Move the plant detail surface to `/plants/$plantKey`. Move the existing edit/update facts behavior to either inline edit affordances on detail plus a routable `/plants/$plantKey/edit` state, or a dedicated edit page that shares the detail loader and submits `useUpdatePlantFactsMutation`. The route should fetch `GET /api/breeding-logbook/plants/{plant_key}` and plant history through generated hosted types. Delete the older tent-scoped plant detail route once dashboard links and detail behavior use `/plants/$plantKey`, unless implementation discovers that it owns a still-required behavior not present in the breeding-logbook plant detail response. If such a behavior exists, move it into the canonical plant detail route rather than keeping two plant-detail routes.

Milestone 5 adds seed-lot detail and edit backend support. Add Pydantic browser response/request DTOs in `apps/control-plane/src/dirt_control/api/browser_schemas/breeding_logbook.py` for seed-lot detail and seed-lot inventory update. Add:

    GET /api/breeding-logbook/seed-lots/{seed_lot_id}
    POST /api/breeding-logbook/seed-lots/{seed_lot_id}:update

The detail response should include the existing summary fields plus seed-lot-owned detail fields and source context: line identity from `CloudPlantLine`, purchased vendor/acquisition fields when applicable, cross event/source labels when applicable, seed count, notes, and a count or compact list of plants created from the lot if the cloud projection can provide that cheaply. Keep the response model explicit; do not hand-roll `dict[str, Any]`.

The update route should enqueue a typed command because local data remains the source of truth. Add a shared cloud payload such as `BreedingUpdateSeedLotInventoryPayload` in `apps/shared/src/dirt_shared/cloud_contract.py` with required fields for the complete editable inventory state, including `seed_lot_source_id`, `sex_type_key`, `seed_count`, `notes`, and purchased-only fields such as `vendor_name` and `acquired_at` if they are editable. Add the command type to the `CommandType` literal, `BreedingCommandPayload`, claimed-command payload validation, gateway local command-type mapping, and `BreedingCommandExecutor`. The executor should load the local `SeedLot`, validate source-specific constraints against the existing row, update only seed-lot-owned fields, and return a concise result containing `source_seed_lot_id`.

Do not add compatibility aliases or raw JSON command payloads. Add focused tests in `apps/shared/tests/test_cloud_contract.py`, `apps/gateway/tests/test_sync.py`, `apps/control-plane/tests/test_api.py`, and `apps/control-plane/tests/test_control_plane_boundary_guardrails.py`. Regenerate the hosted OpenAPI/TypeScript client with `DIRT_CLOUD_ASSET_STORE=local scripts/gen-hosted-contract`.

Milestone 6 splits Seeds into routable pages. Move seed-lot query/mutation/type code into a canonical seed workspace module such as `web-ui/src/features/seeds/`. `/seeds` should render a real seed-lot list view, not only the add-seeds form. The list should support scan-friendly filtering/searching for inventory work, with URL search state for filters. The first-pass list can group or filter by source type and sex type if supported by existing data; avoid adding elaborate grouping that is not useful with current records.

Move the add seed lot form to `/seeds/new` and keep it focused on inventory creation. On successful command enqueue, show pending state and navigate or offer a route to `/seeds` after the command is accepted; because the projected seed-lot ID may not exist immediately, do not assume the create response can route to the new detail page unless the command result or projection provides the source ID.

Add `/seeds/$seedLotId` for seed-lot detail and `/seeds/$seedLotId/edit` for seed-lot inventory edit. The edit route should submit the command-backed update from Milestone 5 and use visible pending/convergence behavior rather than invalidation alone. The detail page should show source/lineage context read-only and make the editable inventory facts obvious.

Milestone 7 validates and cleans up. Remove stale `BreedingLogbook*` UI names where they are no longer truthful. It is acceptable for backend API paths to remain `/api/breeding-logbook/...` in this plan if renaming them would be pure churn; frontend features, routes, and visible labels should use `Plants` and `Seeds`. Search for dead route names, generated route imports, unused components, and stale tests. Let the TanStack Router Vite plugin regenerate `web-ui/src/routeTree.gen.ts` through a normal build/typecheck; do not hand-edit it.


## Concrete Steps

Start from the repository root:

    cd /home/akcom/code/dirt
    git status --short

Read required docs if they are not already in context:

    sed -n '1,240p' docs/commands.md
    sed -n '1,260p' docs/rules/simple-clean-architecture.md
    sed -n '1,260p' docs/rules/boundary-contracts.md
    sed -n '1,220p' docs/rules/frontend-server-state.md
    sed -n '1,220p' docs/references/tanstack-router-v1/INDEX.md
    sed -n '1,220p' docs/references/tanstack-query-v5/INDEX.md
    sed -n '1,220p' docs/references/modern-idiomatic-typescript/INDEX.md

Inspect current frontend route and dead-code references:

    rg --files web-ui/src/routes web-ui/src/features web-ui/src/ui web-ui/src/shared | sort
    rg -n "Dashboard|Live|Wiki|breeding-logbook|BreedingLogbook|/live|/wiki|/breeding-logbook" web-ui/src

Inspect current backend seed-lot API/command coverage before implementing Milestone 5:

    rg -n "seed-lots|SeedLot|BreedingCreateSeedLot|breeding_seed_lot" apps/control-plane/src apps/shared/src apps/gateway/src apps/control-plane/tests apps/shared/tests apps/gateway/tests

After backend contract changes, regenerate the hosted browser contract:

    DIRT_CLOUD_ASSET_STORE=local scripts/gen-hosted-contract

Run focused backend validation:

    uv run pytest apps/shared/tests/test_cloud_contract.py -q
    uv run pytest apps/gateway/tests/test_sync.py apps/gateway/tests/test_gateway_boundary_guardrails.py -q
    uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q

Run frontend validation:

    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test
    pnpm --dir web-ui build

Run repo-level architecture checks:

    uv run pytest apps/tests/invariants -q
    git diff --check

For local browser verification, use the supported hosted dev stack and the real local auth flow:

    make dev-up
    make dev-status
    agent-browser open <Web URL from make dev-status>

Log in with username `dev-admin` and password `dev-password`. Verify `/`, `/tents`, `/tents/1`, `/plants`, `/plants/new`, a real `/plants/$plantKey`, `/seeds`, `/seeds/new`, and a real `/seeds/$seedLotId`. Capture desktop and mobile screenshots in light and dark theme for the three workspace list/detail/create flows touched by the implementation.


## Validation and Acceptance

Acceptance is user-visible and contract-visible.

The browser UI is accepted when:

- The top navigation shows exactly `Tents`, `Plants`, and `Seeds`.
- `/` lands on the Tents workspace.
- `/live`, `/wiki`, and `/breeding-logbook` are not present in navigation and have no route files under `web-ui/src/routes/`.
- `/tents/$sourceTentId` deep links to a physical tent workspace, and changing tents updates the URL.
- `/plants` renders active plants by default and has an archive/culled/harvested filter.
- `/plants/new` owns germination and clone creation.
- `/plants/$plantKey` and `/plants/$plantKey/edit` are deep-linkable and can view/update existing plant facts through the existing command-backed flow.
- `/seeds` renders a seed-lot inventory list.
- `/seeds/new` creates seed lots.
- `/seeds/$seedLotId` and `/seeds/$seedLotId/edit` are deep-linkable and can view/update seed-lot inventory facts through the new command-backed flow.
- Direct user-facing labels no longer present the combined surface as `Breeding Logbook`.

Backend/browser contract acceptance for seed lots:

- `GET /api/breeding-logbook/seed-lots/{seed_lot_id}` returns a typed detail response and 404s for unknown seed lots.
- `POST /api/breeding-logbook/seed-lots/{seed_lot_id}:update` requires auth, validates the seed lot exists, enqueues a typed command, and returns `CommandResponse`.
- Gateway command claim validation rejects a seed-lot update command with the wrong payload shape.
- The gateway applies the seed-lot update idempotently to local `SeedLot` rows and reports the command result.

Dead-code acceptance:

- `rg -n "HostedLive|WikiPage|readRecentWiki|pushRecentWiki|ExpandedWiki|/live|/wiki|/breeding-logbook" web-ui/src` returns no live code references except historical comments that are intentionally kept, and those comments should generally be deleted.
- `pnpm --dir web-ui build` regenerates a route tree with no `/live`, `/wiki`, or `/breeding-logbook` routes.
- Invariant tests pass without modifying `apps/tests/invariants/`.


## Idempotence and Recovery

Deleting web route files and moving route components is safe to repeat as long as generated `web-ui/src/routeTree.gen.ts` is regenerated by the normal frontend toolchain. Do not hand-edit generated route tree entries.

The seed-lot update command should be idempotent at the hosted command layer through the existing `idempotency_key` path. Re-submitting the same command request with the same key should return or converge to the same command rather than applying duplicate local side effects.

If Milestone 5 reveals that a desired seed-lot edit field actually belongs to `PlantLine` or `CrossEvent`, stop and record the discovery in this plan. Do not widen the command to mutate line/cross ownership by accident. Either keep that field read-only in the seed detail UI or write a follow-up ExecPlan for line/cross editing.

If local browser verification is blocked because `make dev-up` reports the local dev database has not been restored, run:

    make dev-refresh-db
    make dev-up

If `scripts/gen-hosted-contract` fails because the default cloud asset store expects S3 settings, rerun with:

    DIRT_CLOUD_ASSET_STORE=local scripts/gen-hosted-contract

Do not run destructive git commands to recover from route moves. Use `git diff --name-status` and targeted edits. Never modify `apps/tests/invariants/`; treat invariant failures as feedback about the implementation.


## Artifacts and Notes

Initial planning evidence:

    rg --files web-ui/src | sort

showed current web routes:

    web-ui/src/routes/__root.tsx
    web-ui/src/routes/breeding-logbook.tsx
    web-ui/src/routes/index.tsx
    web-ui/src/routes/live.tsx
    web-ui/src/routes/login.tsx
    web-ui/src/routes/tents.$sourceTentId.plants.$plantId.tsx
    web-ui/src/routes/wiki.tsx

Initial backend inspection found no seed-lot detail/update routes:

    apps/control-plane/src/dirt_control/api/browser/breeding_logbook.py

currently includes `GET /breeding-logbook/seed-lots` and `POST /breeding-logbook/seed-lots`, but not a detail route or update route.

Record implementation screenshots, command outputs, route tree excerpts, and test summaries here as milestones complete.


## Interfaces and Dependencies

Final web routes:

    /
    /tents
    /tents/$sourceTentId
    /plants
    /plants/new
    /plants/$plantKey
    /plants/$plantKey/edit
    /seeds
    /seeds/new
    /seeds/$seedLotId
    /seeds/$seedLotId/edit
    /login

Removed web routes:

    /live
    /wiki
    /breeding-logbook
    /tents/$sourceTentId/plants/$plantId

The last route should be removed only after its plant-detail behavior is represented by `/plants/$plantKey`.

Frontend modules expected at the end may include:

    web-ui/src/features/tents/TentsWorkspace.tsx
    web-ui/src/features/plants/
    web-ui/src/features/seeds/
    web-ui/src/routes/tents.tsx
    web-ui/src/routes/tents.$sourceTentId.tsx
    web-ui/src/routes/plants.tsx
    web-ui/src/routes/plants.new.tsx
    web-ui/src/routes/plants.$plantKey.tsx
    web-ui/src/routes/plants.$plantKey.edit.tsx
    web-ui/src/routes/seeds.tsx
    web-ui/src/routes/seeds.new.tsx
    web-ui/src/routes/seeds.$seedLotId.tsx
    web-ui/src/routes/seeds.$seedLotId.edit.tsx

Exact file names should follow TanStack Router v1 file naming conventions and may be adjusted by the router plugin. The route string inside each `createFileRoute()` call should be maintained by the plugin after file moves.

Backend browser API additions:

    GET /api/breeding-logbook/seed-lots/{seed_lot_id}
    POST /api/breeding-logbook/seed-lots/{seed_lot_id}:update

Shared command contract additions:

    CommandType includes a seed-lot update command name
    BreedingUpdateSeedLotInventoryPayload or equivalent Pydantic DTO
    BreedingCommandPayload includes the new payload
    ClaimedCommand payload validation maps the new command type to the new payload

Gateway additions:

    apps/gateway/src/dirt_gateway/breeding_commands.py applies the seed-lot update
    apps/gateway/src/dirt_gateway/commands.py maps the cloud command type to a local command type string

Generated contract:

    contracts/hosted-browser-v1.json
    web-ui/src/api-client/generated/hosted-schema.ts

No new third-party frontend dependency is expected. No database migration is expected unless implementation discovers a missing persisted seed-lot fact that cannot be represented by existing `SeedLot`, `PlantLine`, or `CrossEvent` fields.


## Revision Notes

- 2026-06-21: Initial ExecPlan drafted from operator decisions and repository inspection.
