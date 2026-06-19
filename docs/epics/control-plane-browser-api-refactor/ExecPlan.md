# Control-plane browser API refactor

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, the hosted control-plane browser API is organized by feature instead of being concentrated in one transport-audience module. A developer or coding agent can add or debug a browser route by opening a focused router, schema, and service module instead of scanning `apps/control-plane/src/dirt_control/api/browser.py`, which is currently 3,593 lines and mixes request DTOs, response DTOs, FastAPI route handlers, SQLAlchemy query construction, command queueing, asset signing, metric presentation, plant projection, breeding logbook projection, admin operations, and formatting helpers.

This matters because the hosted control plane is now a real operator interface. The current structure makes small product fixes, such as the germination "Into tent" dropdown, trace through unrelated helper code and, before the scoped identity cleanup, hidden string heuristics like `_stage_for_tent_id()`. That investigation also exposed a deeper data-model smell: Dirt-owned objects such as tents carried an internal integer `id`, a parallel Dirt-owned text `tent_id`, and a human `name`. The scoped identity cleanup has since retired the local text `tent_id`; the browser refactor must preserve that simpler model instead of reintroducing text identity through route names, DTOs, or helper abstractions. The desired end state is similar in spirit to `dirt_hwd`: FastAPI route modules are HTTP boundary adapters; service/query modules own data access and application decisions; Pydantic schemas live in explicit contract modules; durable objects use one internal identity plus clear display fields; and architectural invariants prevent the browser API from regressing into another mega-module.

The work is complete when `apps/control-plane/src/dirt_control/api/browser.py` is retired or reduced to a thin compatibility-free aggregate, the browser API is split into feature routers with stable existing paths and OpenAPI output, direct DB/model access no longer lives in browser route modules, and invariant checks cover `dirt_control` with staged rules that preserve the new architecture.


## Progress

- [x] (2026-06-18) Created this ExecPlan after reviewing `browser.py`, the hwd FastAPI architecture, existing invariant tests, `.agents/PLANS.md`, and `docs/rules/simple-clean-architecture.md`.
- [ ] Milestone 1: take an inventory and add characterization tests that protect current browser route behavior before moving code.
- [ ] Milestone 2: split browser schemas out of `browser.py` without changing route behavior or generated OpenAPI shape.
- [ ] Milestone 3: split browser routes by feature while keeping existing paths and route response models stable.
- [ ] Milestone 4: extract data access and application decisions from browser route modules into focused control-plane services/query modules.
- [x] (2026-06-19) Milestone 5: removed the tent/location identity smell and made breeding logbook grouping explicitly tent-based as part of `docs/epics/scoped-identity-cleanup/ExecPlan.md`; future browser API refactor milestones must preserve that completed boundary.
- [ ] Milestone 6: add Stage 1 generic invariants for `dirt_control`.
- [ ] Milestone 7: add Stage 2 control-plane import-boundary invariants.
- [ ] Milestone 8: add Stage 3 browser-specific shape invariants and remove obsolete compatibility structure.
- [ ] Milestone 9: validate locally, regenerate hosted contracts, deploy if requested, and record final evidence.


## Surprises & Discoveries

- Observation: The scoped identity cleanup plan already retired browser tent paths keyed by ambiguous text `tent_id`.
  Evidence: `docs/epics/scoped-identity-cleanup/ExecPlan.md` Milestones 4-7 moved gateway/cloud/browser projections to source integer IDs, regenerated hosted contracts, and changed hosted tent routes to `/api/tents/{source_tent_id}/...`.

- Observation: The existing architecture invariants do not currently scan `dirt_control`.
  Evidence: `apps/tests/invariants/_helpers.py` defines `APPS = ("dirt_hwd", "dirt_shared", "dirt_voice")`; `dirt_control` lives under `apps/control-plane/src/dirt_control` and is absent from the invariant app list.

- Observation: The hwd app is protected by a route allowlist and import-boundary rules, not just convention.
  Evidence: `apps/tests/invariants/test_hwd_routes.py` allows only `/api/ingest/sensors`; `apps/tests/invariants/import_boundaries.invariant.ini` forbids `dirt_hwd.api` from importing `dirt_shared.db` or `dirt_shared.models`.

- Observation: Control-plane browser boundary guardrails exist, but they protect route response models and strict Pydantic DTO behavior rather than module architecture.
  Evidence: `apps/control-plane/tests/test_control_plane_boundary_guardrails.py` imports `dirt_control.api.browser` and asserts browser route response models, gateway route contracts, and selected DTO `extra="forbid"` behavior.

- Observation: `browser.py` contains route handlers and direct SQLAlchemy queries in the same module.
  Evidence: `apps/control-plane/src/dirt_control/api/browser.py` imports `select`, `and_`, `desc`, and `func` from SQLAlchemy near the top and contains dozens of `select(...)` calls throughout route handlers and private helpers.

- Observation: The germination dropdown bug surfaced a domain smell, not merely a UI filter.
  Evidence: Before the scoped identity cleanup, browser bootstrap computed `stage_key` for locations through `_stage_for_tent_id(tent_id)`, which inferred plant stage from substrings such as `"veg"`, `"clone"`, `"germ"`, and defaulted to `"flower"`.

- Observation: The Breeding Logbook board is really grouped by current tent, not by lifecycle stage.
  Evidence: Before the scoped identity cleanup, the UI's location options were produced from `CloudTent` rows, and plant row `location_key` / `location_label` were derived from `CloudPlantLocation.tent_id` and optional `grid_position`. The cleanup replaced those browser DTO fields with explicit tent/grid fields while keeping lifecycle stage separate.

- Observation: `location_key` and `location_label` were not intuitive browser contracts for the Breeding Logbook.
  Evidence: The old values were tent-derived. A reader could not tell from `location_key` whether the field was a tent id, grid slot, full location history row, or UI bucket. The cleanup replaced them with explicit fields such as current tent name and grid position.

- Observation: The tentative `id + tent_id + name` cleanup target has already been resolved locally.
  Evidence: `docs/epics/scoped-identity-cleanup/ExecPlan.md` records Milestone 7 removing `site.site_id`, `tent.tent_id`, `zone.zone_id`, and `schedule.schedule_id`; its post-cleanup interface says local `Tent` has `id`, display `name`, semantic `role`, active/default fields, and no text `tent_id`.


## Decision Log

- Decision: Refactor by feature, not by file type alone.
  Rationale: A pure `schemas.py`, `routes.py`, `helpers.py` split would reduce file length but preserve the wrong abstraction. The browser API has real features: auth, health/sync, sites/tents/devices, metrics, assets, commands/admin, plants, and breeding logbook. Each should have a route module and, where needed, schema and service/query modules.
  Date/Author: 2026-06-18 / Codex

- Decision: Keep existing public HTTP paths and generated browser contract stable during the mechanical split.
  Rationale: The frontend consumes generated hosted OpenAPI types. The refactor should not force product behavior changes until the structure is clean enough to make the tent/location fix deliberately.
  Date/Author: 2026-06-18 / Codex

- Decision: Do not add long-lived compatibility wrappers or alias modules.
  Rationale: `docs/rules/simple-clean-architecture.md` directs source-owned code toward direct cutover. Compatibility is only justified for real external contracts. Internal module imports and tests should move to the canonical modules in the same change.
  Date/Author: 2026-06-18 / Codex

- Decision: Add invariants after the code has been refactored to satisfy them.
  Rationale: The user explicitly wants the invariant work as a last step. Adding strict import boundaries before the refactor would create known-red tests without increasing safety. The final milestones should codify the new shape once it exists.
  Date/Author: 2026-06-18 / Codex

- Decision: Treat `apps/tests/invariants/` as human-owned even when this plan calls for new invariants.
  Rationale: `AGENTS.md` marks that directory as human-owned architectural rules. An implementation agent must not casually patch existing invariant files to make code pass. If invariant files are added or changed as part of this plan, the human operator must explicitly approve that milestone and review the rule text.
  Date/Author: 2026-06-18 / Codex

- Decision: The Breeding Logbook board should group by current tent, not inferred lifecycle stage.
  Rationale: A tent is a physical/logical container; stage is a plant lifecycle fact derived from plant timestamps and events. Using tent-name substrings to infer stage makes UI grouping feel plausible while encoding false domain knowledge. The board should present tent buckets directly and show lifecycle stage as a plant badge/detail, not as the grouping owner.
  Date/Author: 2026-06-18 / Operator

- Decision: Remove `location_key` / `location_label` from Breeding Logbook browser contracts in favor of explicit tent fields.
  Rationale: The current names hide the actual concept. Plant rows should expose current tent identity/display and nullable `grid_position` separately, for example `current_tent_id` or `current_tent_source_id`, `current_tent_name`, and `grid_position`. Bootstrap move/germinate targets should be named as tents, not generic locations.
  Date/Author: 2026-06-18 / Operator

- Decision: Preserve the scoped-identity cleanup result for tents.
  Rationale: `docs/rules/data-modeling.md` says Dirt-owned objects should not carry parallel text ids merely because they are convenient or readable. `Tent.id` is now the durable internal identity and FK target. `Tent.name` is the human-readable display value. Hosted/cloud boundaries may expose `source_tent_id` for cross-process sync, and temporary legacy bridge fields may exist where explicitly documented, but the browser API refactor must not recreate `/api/tents/{tent_id}` routes or generic tent aliases.
  Date/Author: 2026-06-19 / Operator and Codex


## Outcomes & Retrospective

Not started. Update this section at the end of each milestone with what changed, what validation passed, and whether the refactor is still reducing complexity rather than moving it around.


## Context and Orientation

The hosted control plane lives under `apps/control-plane/src/dirt_control`. `apps/control-plane/src/dirt_control/app.py` creates the FastAPI app, configures CORS, wires app state, and currently includes three routers:

    from dirt_control.api.browser import router as browser_router
    from dirt_control.api.dev_assets import router as dev_assets_router
    from dirt_control.api.gateway import router as gateway_router

`apps/control-plane/src/dirt_control/api/gateway.py` is the machine-facing gateway API. It receives outbound sync from the local `dirt-gateway` service and writes cloud projection tables. This plan is not primarily about the gateway API, although some generic invariants may eventually cover it too.

`apps/control-plane/src/dirt_control/api/browser.py` is the browser-facing hosted API consumed by the React app in `web-ui/`. It is currently the source for browser OpenAPI generation through `scripts/gen-hosted-contract`, which writes `contracts/hosted-browser-v1.json` and `web-ui/src/api-client/generated/hosted-schema.ts`.

The frontend must continue to use generated hosted schema types. Do not hand-author replacement browser response interfaces in `web-ui/src/api-client/cloud.ts` or other frontend files. If browser API response schemas change, update the FastAPI Pydantic model and rerun:

    scripts/gen-hosted-contract

The hwd app provides the architectural comparison point. `apps/hwd/src/dirt_hwd/app.py` is a composition root; `apps/hwd/src/dirt_hwd/deps.py` owns FastAPI dependency providers; `apps/hwd/src/dirt_hwd/api/ingest.py` is a small boundary adapter; and `apps/hwd/src/dirt_hwd/services/` contains named service modules. This plan should move the control-plane browser API toward that same separation without copying hwd blindly.

Existing invariant tests live under `apps/tests/invariants/`. That directory is human-owned. The current import-linter config enforces cross-app boundaries among `dirt_shared`, `dirt_hwd`, and `dirt_voice`, and an hwd-specific rule keeps `dirt_hwd.api` above `dirt_shared.db` and `dirt_shared.models`. The control-plane package is absent from that registry today.


## Plan of Work

Milestone 1 establishes safety before moving code. Inventory the browser API routes, schemas, helpers, and query clusters. Extend existing control-plane tests only where they protect externally visible behavior or boundary contracts. Do not write fixture-topology tests. The route response model test in `apps/control-plane/tests/test_control_plane_boundary_guardrails.py` should still pass after every milestone. Add or adjust focused tests in `apps/control-plane/tests/test_api.py` for areas that will be moved and are not currently characterized, especially breeding logbook bootstrap/location options, command enqueue idempotency, asset signed URL responses, metric history range validation, and plant/breeding response mapping.

Milestone 2 moves Pydantic browser schemas out of `browser.py`. Create a package such as:

    apps/control-plane/src/dirt_control/api/browser_schemas/
      __init__.py
      common.py
      auth.py
      health.py
      sites.py
      tents.py
      metrics.py
      plants.py
      breeding_logbook.py
      assets.py
      commands.py
      admin.py

`BrowserRequest`, `BrowserResponse`, shared literals, and common response primitives should live in `common.py`. Feature schema modules should import the common base types and any shared cloud-contract payloads they extend. Move tests away from importing schemas through `dirt_control.api.browser`; tests should import from the canonical schema modules. Regenerate hosted contracts and confirm the generated OpenAPI schema is semantically unchanged except for ordering.

Milestone 3 splits browser routes by feature while preserving paths. Convert `apps/control-plane/src/dirt_control/api/browser.py` into a package or an aggregate module. A target package shape is:

    apps/control-plane/src/dirt_control/api/browser/
      __init__.py
      auth.py
      health.py
      sites.py
      tents.py
      metrics.py
      plants.py
      breeding_logbook.py
      assets.py
      commands.py
      admin.py

The aggregate `dirt_control.api.browser.router` should remain the import used by `app.py` and existing tests. It should create `APIRouter(prefix="/api")` and include feature routers with relative paths. Feature modules should use small `APIRouter()` instances without their own `/api` prefix, or use clear sub-prefixes only when that keeps route paths identical. After this milestone, route handlers may still call old helper functions if needed, but the giant route list must no longer live in one file.

Milestone 4 extracts services and query/projection modules. Move direct SQLAlchemy query construction and application decisions out of browser route modules. Use focused modules under `apps/control-plane/src/dirt_control/services/` or `apps/control-plane/src/dirt_control/queries/`. Prefer services when the function performs a decision or write, and query modules when the function only assembles read-model data. A practical target is:

    apps/control-plane/src/dirt_control/services/browser_commands.py
    apps/control-plane/src/dirt_control/services/breeding_logbook.py
    apps/control-plane/src/dirt_control/services/browser_metrics.py
    apps/control-plane/src/dirt_control/services/browser_plants.py
    apps/control-plane/src/dirt_control/services/browser_assets.py
    apps/control-plane/src/dirt_control/services/browser_health.py

Do not create abstract repository interfaces unless there is more than one implementation. Direct functions or small service classes are acceptable. Route handlers should parse request state, receive dependencies, call a service/query function, and return a Pydantic response. Services may import `dirt_control.models`, `sqlalchemy`, and `AsyncSession`. Browser route modules should not.

Milestone 5 was completed by the scoped identity cleanup before this structural browser refactor began. The completed boundary is now an input to the remaining work, not an open design question:

- `_stage_for_tent_id()` and substring-based stage inference are gone.
- Hosted browser tent routes use `/api/tents/{source_tent_id}/...`, not `/api/tents/{tent_id}/...`.
- Breeding Logbook browser DTOs expose explicit tent fields such as `current_tent_id`, `current_tent_name`, and `grid_position`, not `location_key` / `location_label`.
- Frontend route/query keys use `sourceTentId` where the UI needs a hosted source identity.
- Plant lifecycle `stage_key` remains a plant fact used for badges, filters, and detail panels; it is not derived from tent names.
- Local `Tent` uses `id`, `name`, semantic fields such as `role`, active/default flags, and FKs. There is no local text `tent_id`.

The remaining browser refactor must preserve those choices while moving code. When route modules, schemas, services, or tests are split out of `browser.py`, carry forward the explicit `source_tent_id` / `current_tent_*` contract and keep temporary cloud command/storage bridge fields named as legacy bridges. Do not introduce compatibility wrappers that revive text tent aliases just to make the refactor easier.

Milestone 6 adds Stage 1 generic invariants for `dirt_control`. Update the invariant app registry so checks can resolve non-standard app source paths such as `dirt_control -> apps/control-plane/src/dirt_control`. Apply generic rules to `dirt_control` with deliberate allowlists for true composition roots and CLI/bootstrap files:

- no module-level stateful singleton construction outside composition roots
- no concrete wall-clock reads inside production logic except dependency defaults and approved boundary modules
- no ad hoc env reads outside settings and explicit CLI/bootstrap env boundary files
- no `asyncio.run()` outside command entrypoints
- no raw SQL string literals outside models, services, db helpers, migrations, and test infrastructure

Because `apps/tests/invariants/` is human-owned, the implementation of this milestone requires explicit human approval before editing those files. The plan should be updated with the exact invariant files changed and the rationale for any allowlist entry.

Milestone 7 adds Stage 2 control-plane import-boundary invariants. Extend `apps/tests/invariants/import_boundaries.invariant.ini` or add an equivalent protected rule so the control-plane API layer cannot reach into the database/model layer directly after Milestone 4. The intended rule is:

    dirt_control.api.browser may not import dirt_control.models, dirt_control.db, sqlalchemy, or sqlalchemy.ext.asyncio.

If the gateway API still legitimately owns projection upserts at this point, do not over-constrain `dirt_control.api.gateway` in the same rule unless it has also been refactored. The browser rule should specifically protect the user-facing API refactor completed by this plan. If later work refactors `gateway.py`, add gateway-specific rules in a separate plan or a clearly separate milestone.

Milestone 8 adds Stage 3 browser-specific shape invariants. These rules should encode the new architecture without making implementation miserable:

- The aggregate browser router module may include subrouters but must not define path operations itself.
- Browser route modules may not define Pydantic request/response DTO classes; DTOs live in `dirt_control.api.browser_schemas`.
- Browser route modules may not call SQLAlchemy `select(...)`, `insert(...)`, `update(...)`, `delete(...)`, or import `dirt_control.models`.
- Every browser route must declare an explicit `response_model`.
- Browser schema modules must keep `extra="forbid"` through `BrowserRequest` and `BrowserResponse`.

Prefer AST/import checks with useful failure messages over brittle line-count checks. Do not add a rule such as "no file over N lines" unless repeated regressions show dependency rules are insufficient.

Milestone 9 validates, deploys if requested, and records evidence. Run the full relevant backend, invariant, contract generation, frontend typecheck/lint/test, and optionally local hosted browser smoke. If behavior or API shape changed, regenerate contracts and update the frontend. Deploy only through `scripts/deploy-control-plane` when explicitly requested.


## Concrete Steps

Start every implementation session by reading required docs:

    cd /home/akcom/code/dirt
    sed -n '1,220p' docs/commands.md
    sed -n '1,220p' docs/rules/simple-clean-architecture.md
    sed -n '1,220p' docs/rules/boundary-contracts.md
    sed -n '1,220p' docs/hosted-control-plane.md
    sed -n '1,220p' docs/database.md
    sed -n '1,220p' docs/references/atlas/INDEX.md

Inventory the current browser API:

    wc -l apps/control-plane/src/dirt_control/api/browser.py
    rg -n "^(class|def|async def|@router|router\\.|[A-Z_]+ =)" apps/control-plane/src/dirt_control/api/browser.py
    rg -n "select\\(|from sqlalchemy|from dirt_control.models" apps/control-plane/src/dirt_control/api/browser.py

Run current focused validation before the first move:

    uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q
    scripts/gen-hosted-contract
    pnpm --dir web-ui typecheck

After schema moves, run:

    uv run pytest apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q
    scripts/gen-hosted-contract
    git diff -- contracts/hosted-browser-v1.json web-ui/src/api-client/generated/hosted-schema.ts

After route split and service extraction, run:

    uv run pytest apps/control-plane/tests -q
    uv run pytest apps/tests/invariants -q
    scripts/gen-hosted-contract
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test

Before committing:

    make fix
    git status --short
    git diff --check

If deployment is requested after implementation:

    scripts/deploy-control-plane


## Validation and Acceptance

The refactor is accepted only if behavior remains observable through tests and the running app:

- `uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q` passes after every milestone.
- `uv run pytest apps/control-plane/tests -q` passes before merge.
- `uv run pytest apps/tests/invariants -q` passes after invariant milestones.
- `scripts/gen-hosted-contract` completes, and any generated contract diff is intentional and explained in this plan.
- `pnpm --dir web-ui typecheck`, `pnpm --dir web-ui lint`, and `pnpm --dir web-ui test` pass.
- Existing browser routes keep the same HTTP paths and response models unless a product behavior change is explicitly recorded in `Decision Log`.
- A local hosted stack started with `make dev-up` can log in with `dev-admin` / `dev-password` and render the dashboard and breeding logbook surfaces that depend on browser API routes.

For the tent/location identity milestone, acceptance requires tests that fail under the old substring inference and vague location contract. At minimum, create or project tents whose names/ids do not imply lifecycle stage and assert that breeding logbook bootstrap and plant rows expose explicit tent fields, not inferred location stage buckets. Add a contract or frontend mapping test that proves board grouping uses current tent identity/name and that plant lifecycle `stage_key` remains a separate derived plant fact.

Because Milestone 5 is already complete via the scoped identity cleanup, acceptance for this plan requires the structural refactor to keep those contracts intact: local code should not refer to `Tent.tent_id`; hosted browser routes should remain `{source_tent_id}`-based; cloud/browser DTOs should name projected source identity explicitly; and generated OpenAPI/frontend types should continue to omit ambiguous `location_key` / `location_label` fields for Breeding Logbook rows.

For invariant milestones, acceptance requires a deliberate negative check before finalizing the rule when practical. For example, temporarily add a forbidden `from dirt_control.models import CloudTent` import to a browser route module and confirm the invariant fails with a clear message, then remove the temporary change before committing.


## Idempotence and Recovery

The schema and route split milestones are source-only and safe to repeat. If a move becomes confusing, stop and use `git diff` plus focused tests to identify the last passing boundary. Do not use `git reset --hard` unless the user explicitly asks for it.

Generated hosted contract files are safe to regenerate with `scripts/gen-hosted-contract`. If generated files change unexpectedly, inspect the FastAPI response models first. Do not patch `web-ui/src/api-client/generated/hosted-schema.ts` by hand.

The invariant milestones are intentionally last. If an invariant fails on existing control-plane code, either finish the refactor that the invariant is meant to protect or narrow the rule to the intended package slice with a documented rationale. Do not add broad allowlists that preserve the smell. Because invariant files are human-owned, update this plan and ask for human approval before changing them.

No production database changes are expected for the remaining browser API refactor milestones. The schema work that retired parallel local tent text identity lives in `docs/epics/scoped-identity-cleanup/ExecPlan.md` and its migrations. If future browser refactor work unexpectedly requires schema changes, follow `docs/database.md`, `docs/rules/data-modeling.md`, and `docs/references/atlas/INDEX.md`: edit SQLModel models, run the appropriate local/cloud `atlas migrate diff <name> --env ...`, review the migration, and deploy only through `scripts/deploy-control-plane`.

Deployment is retryable through `scripts/deploy-control-plane`. If a deploy fails, fix the code or migration and rerun the same script. Do not use ad hoc Railway commands.


## Artifacts and Notes

Initial inventory:

    apps/control-plane/src/dirt_control/api/browser.py has 3,593 lines.
    It contains request DTOs starting near line 83, response DTOs starting near line 176, route handlers from roughly line 705 through 2008, and helper/query/projection functions from roughly line 2014 onward.

Existing hwd comparison points:

    apps/hwd/src/dirt_hwd/app.py
    apps/hwd/src/dirt_hwd/deps.py
    apps/hwd/src/dirt_hwd/api/ingest.py
    apps/hwd/src/dirt_hwd/services/

Existing invariant comparison points:

    apps/tests/invariants/test_hwd_routes.py
    apps/tests/invariants/import_boundaries.invariant.ini
    apps/tests/invariants/test_import_boundaries.py
    apps/tests/invariants/test_no_module_level_singletons.py
    apps/tests/invariants/test_no_concrete_clock_in_production.py
    apps/tests/invariants/test_no_env_reads_outside_config.py
    apps/tests/invariants/test_no_asyncio_run_outside_entrypoints.py
    apps/tests/invariants/test_no_raw_sql_outside_data_layer.py

The current `dirt_control` package is not covered by the generic invariant app list in `apps/tests/invariants/_helpers.py`.


## Interfaces and Dependencies

At the end of this plan, these interfaces should exist:

- `dirt_control.api.browser.router`: aggregate browser router imported by `apps/control-plane/src/dirt_control/app.py`.
- `dirt_control.api.browser.<feature>.router`: focused feature routers for browser-authenticated routes.
- `dirt_control.api.browser_schemas.<feature>`: Pydantic request and response DTOs for browser API contracts.
- `dirt_control.services.browser_commands`: command creation/enqueueing and command response projection for browser-originated commands.
- `dirt_control.services.breeding_logbook`: breeding logbook read model and command validation/query helpers.
- `dirt_control.services.browser_metrics`: metric presentation/history query and response projection helpers.
- `dirt_control.services.browser_plants`: hosted plant list/detail/history query helpers.
- `dirt_control.services.browser_assets`: browser asset lookup/signing helpers.
- Breeding Logbook browser contracts that name tent concepts directly, such as `source_tent_id`, `current_tent_id`, `current_tent_name`, and nullable `grid_position`, instead of generic location key/label fields or stage-by-tent metadata.
- Invariants that include `dirt_control` in the app registry or equivalent source mapping.
- Import-boundary rules that prevent browser route modules from importing DB/models/SQLAlchemy directly.
- Browser-specific invariant rules that keep DTOs in schema modules, routes thin, and response models explicit.

External dependencies already present in the repo include FastAPI, Pydantic, SQLAlchemy/SQLModel, import-linter, pytest, Atlas, Vite, React, TanStack Router/Query, and generated OpenAPI TypeScript tooling. Do not add new framework dependencies for the refactor unless a milestone records a concrete need and the user approves it.


## Revision Notes

- 2026-06-18: Initial ExecPlan created from the browser API architecture review and invariant discussion.
- 2026-06-18: Updated Milestone 5 after operator review: the Breeding Logbook board should group by current tent, not inferred lifecycle stage; `location_key` / `location_label` should be replaced with explicit tent fields; and `id + tent_id + name` on Dirt-owned tent objects is a data-model cleanup target unless `tent_id` is proven external/domain-owned.
- 2026-06-19: Recorded scoped-identity cleanup dependency: hosted browser tent routes now use `{source_tent_id}` and source integer identity; future browser API refactor work must not assume text `/api/tents/{tent_id}` paths.
- 2026-06-19: Reconciled this plan after the scoped-identity cleanup completed. Milestone 5 is now marked complete/absorbed by that cleanup; the remaining browser refactor is structural and must preserve the post-cleanup `source_tent_id`, `current_tent_id`, `current_tent_name`, and `grid_position` contracts.
