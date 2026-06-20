# Control-plane browser API refactor

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, the hosted control-plane browser API is organized by feature instead of being concentrated in one transport-audience module. A developer or coding agent can add or debug a browser route by opening a focused router, schema, and service module instead of scanning `apps/control-plane/src/dirt_control/api/browser.py`, which is currently 3,593 lines and mixes request DTOs, response DTOs, FastAPI route handlers, SQLAlchemy query construction, command queueing, asset signing, metric presentation, plant projection, breeding logbook projection, admin operations, and formatting helpers.

This matters because the hosted control plane is now a real operator interface. The current structure makes small product fixes, such as the germination "Into tent" dropdown, trace through unrelated helper code and, before the scoped identity cleanup, hidden string heuristics like `_stage_for_tent_id()`. That investigation also exposed a deeper data-model smell: Dirt-owned objects such as tents carried an internal integer `id`, a parallel Dirt-owned text `tent_id`, and a human `name`. The scoped identity cleanup has since retired the local text `tent_id`; the browser refactor must preserve that simpler model instead of reintroducing text identity through route names, DTOs, or helper abstractions. The desired end state is similar in spirit to `dirt_hwd`: FastAPI route modules are HTTP boundary adapters; service/query modules own data access and application decisions; Pydantic schemas live in explicit contract modules; durable objects use one internal identity plus clear display fields; and architectural invariants prevent the browser API from regressing into another mega-module.

The work is complete when `apps/control-plane/src/dirt_control/api/browser.py` is retired or reduced to a thin compatibility-free aggregate, the browser API is split into feature routers with stable existing paths and OpenAPI output, direct DB/model access no longer lives in browser route modules, and invariant checks cover `dirt_control` with staged rules that preserve the new architecture.


## Progress

- [x] (2026-06-18) Created this ExecPlan after reviewing `browser.py`, the hwd FastAPI architecture, existing invariant tests, `.agents/PLANS.md`, and `docs/rules/simple-clean-architecture.md`.
- [x] (2026-06-19 13:11Z) Milestone 1: inventoried the browser API and added focused characterization tests for current browser route behavior before moving code.
- [x] (2026-06-19 13:23Z) Milestone 2: split browser schemas out of `browser.py` without changing route behavior or generated OpenAPI shape.
- [x] (2026-06-19 13:33Z) Milestone 3: split browser routes by feature while keeping existing paths and route response models stable.
- [x] (2026-06-19 13:54Z) Milestone 4: extracted data access and application decisions from browser route modules into focused control-plane services/query modules.
- [x] (2026-06-19) Milestone 5: removed the tent/location identity smell and made breeding logbook grouping explicitly tent-based as part of `docs/epics/scoped-identity-cleanup/ExecPlan.md`; future browser API refactor milestones must preserve that completed boundary.
- [x] (2026-06-19 14:06Z) Milestone 6: added Stage 1 generic invariants for `dirt_control`.
- [x] (2026-06-19 14:15Z) Milestone 7: added Stage 2 control-plane import-boundary invariants.
- [x] (2026-06-19 14:32Z) Milestone 8: added Stage 3 browser-specific shape invariants and removed obsolete compatibility structure.
- [x] (2026-06-19 14:35Z) Milestone 9: validated locally, regenerated hosted contracts, and recorded final evidence. No deploy was requested or run.


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

- Observation: Existing control-plane API coverage was broader than the Milestone 1 risk list implied.
  Evidence: Before adding tests, `apps/control-plane/tests/test_api.py` already covered breeding write idempotency, plant detail/history mapping, command flows, asset upload completion, and metric history range behavior. Milestone 1 therefore tightened boundary assertions instead of adding broad duplicate snapshots.

- Observation: `scripts/gen-hosted-contract` can report that Biome fixed the generated TypeScript schema even when the generated contract has no net diff.
  Evidence: The Milestone 1 run printed `Fixed 1 file`, but `git diff -- contracts/hosted-browser-v1.json web-ui/src/api-client/generated/hosted-schema.ts` was empty.

- Observation: The hosted contract generator carried a stale source comment that named the deleted `browser.py` file.
  Evidence: Milestone 3 converted `dirt_control.api.browser` into a package; `scripts/gen-hosted-contract` now documents `dirt_control.api.browser` as the source instead of `apps/control-plane/src/dirt_control/api/browser.py`.

- Observation: The command storage/browser response still has a legacy tent-text bridge even though browser routes no longer expose text tent identity.
  Evidence: Milestone 4 moved `legacy_tent_id_for_browser_source_tent_id()` and `legacy_target_tent_id` response construction into `dirt_control.services.browser_commands`; browser route modules no longer own the bridge.

- Observation: Enrolling `dirt_control` in the broad invariant `APPS` tuple would also opt it into unrelated invariant families that are outside Stage 1.
  Evidence: A Milestone 6 implementation attempt exposed pre-existing control-plane issues in dependency/no-patching invariants. The final change added `STAGE1_GENERIC_APPS` for the five Stage 1 generic rules while preserving the existing broad `APPS` list for already-covered packages.

- Observation: Import-linter can own the Stage 2 browser rule if external packages are included.
  Evidence: A temporary config with `include_external_packages = True` caught a direct `from sqlalchemy import select` probe in `dirt_hwd.api.ingest`. The final Milestone 7 revision enables external packages in `apps/tests/invariants/import_boundaries.invariant.ini`, adds `dirt_control` as a root package, extends the `dirt_hwd.api` rule to forbid direct SQLAlchemy imports, and adds the equivalent `dirt_control.api.browser` rule. The custom AST import-boundary test was removed.


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

- Milestone 1 completed the safety pass without moving production code. `apps/control-plane/tests/test_api.py` now more directly protects breeding logbook bootstrap/location options, metric-history request validation, command enqueue idempotency, and browser signed-asset response shape. Focused backend tests passed, hosted contract generation produced no net generated diff, and `web-ui` typecheck passed.
- Milestone 2 moved browser request/response DTOs and shared browser schema constants into feature modules under `apps/control-plane/src/dirt_control/api/browser_schemas/`. `browser.py` remains the route aggregate/handler module for now and imports schema classes from the canonical package. Focused backend tests passed, hosted contract generation produced no net generated diff, `web-ui` typecheck passed, and a targeted Ruff check passed.
- Milestone 3 converted `dirt_control.api.browser` into an aggregate package with focused feature route modules. The public `dirt_control.api.browser.router` import remains stable, route modules still call direct SQLAlchemy/model/helper code as intended before Milestone 4, and shared helper/projection code lives temporarily in `browser/_shared.py`. Focused backend tests, targeted Ruff, hosted contract generation, hosted contract diff check, `web-ui` typecheck, and structural route checks passed.
- Milestone 4 removed `api/browser/_shared.py`, added focused service modules under `dirt_control.services`, and left browser route modules as HTTP boundary adapters that delegate to services. Browser route modules no longer import `dirt_control.models`, SQLAlchemy, `AsyncSession`, SQL builder functions, or `_shared`. Existing browser paths, response models, and generated contract output were preserved. Control-plane tests, current invariants, targeted Ruff, hosted contract generation, hosted contract diff check, `web-ui` typecheck/lint/test, and `git diff --check` passed.
- Milestone 6 added Stage 1 generic invariant coverage for `dirt_control`. The invariant helper now has explicit source mapping for non-standard app paths, including `dirt_control -> apps/control-plane/src/dirt_control`, and the five Stage 1 rules now run against `dirt_control`. `ensure_gateway_credential()` was fixed to use an injected clock default instead of a body-level `datetime.now()` fallback. Invariants, control-plane tests, targeted Ruff, `git diff --check`, and a negative env-read probe check all passed.
- Milestone 7 added import-linter API data-layer boundary rules. `dirt_hwd.api` may not directly import `dirt_shared.db`, `dirt_shared.models`, or `sqlalchemy`; `dirt_control.api.browser` may not directly import `dirt_control.db`, `dirt_control.models`, or `sqlalchemy`. Indirect route-to-service-to-model imports remain legal, and `dirt_control.api.gateway` is intentionally outside this browser rule. A previous custom AST import-boundary test was removed in favor of the shared import-linter contract. Focused and full invariant suites, control-plane tests, targeted Ruff, `git diff --check`, and negative forbidden-import probes passed.
- Milestone 8 added browser-specific shape invariants for the refactored browser API. The new rules protect aggregate router composition, DTO placement in `browser_schemas`, no SQLAlchemy statement-builder calls in browser route modules, explicit browser route response models, and strict `BrowserRequest` / `BrowserResponse` `extra="forbid"` behavior. No source issue was exposed and no compatibility cleanup was needed beyond the structure already removed in Milestones 2-4. Focused and full invariant suites, control-plane tests, targeted Ruff, `git diff --check`, and required negative probes passed.
- Milestone 9 completed final local validation. The full Python test suite, control-plane tests, invariant tests, hosted contract regeneration, hosted contract diff check, frontend typecheck/lint/test, and `git diff --check` all passed. `scripts/gen-hosted-contract` again reported that Biome fixed the generated TypeScript schema, but generated contract/schema diff was empty. No hosted deploy was requested or run, and no local hosted browser smoke was run.


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

Milestone 1 inventory:

    apps/control-plane/src/dirt_control/api/browser.py has 3,746 lines.
    It contains 35 browser path operations: 23 GET routes and 12 POST routes.
    It contains 59 classes: 43 response contracts including BrowserResponse, 12 request/common DTOs, and 4 internal projection/state helper classes.
    It contains 123 def / async def entries: 35 route handlers and 88 helper/query/projection functions.
    It contains 48 select(...) call sites. Query clusters remain health/auth/sync, sites/tents/devices/lights/assets, metrics, breeding logbook, plants, commands, and admin.

Milestone 1 validation:

    uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q
    59 passed in 15.75s

    scripts/gen-hosted-contract
    Completed successfully; no net diff in contracts/hosted-browser-v1.json or web-ui/src/api-client/generated/hosted-schema.ts.

    pnpm --dir web-ui typecheck
    Completed successfully.

Milestone 2 schema package:

    apps/control-plane/src/dirt_control/api/browser_schemas/common.py
    apps/control-plane/src/dirt_control/api/browser_schemas/auth.py
    apps/control-plane/src/dirt_control/api/browser_schemas/health.py
    apps/control-plane/src/dirt_control/api/browser_schemas/sites.py
    apps/control-plane/src/dirt_control/api/browser_schemas/tents.py
    apps/control-plane/src/dirt_control/api/browser_schemas/metrics.py
    apps/control-plane/src/dirt_control/api/browser_schemas/plants.py
    apps/control-plane/src/dirt_control/api/browser_schemas/breeding_logbook.py
    apps/control-plane/src/dirt_control/api/browser_schemas/assets.py
    apps/control-plane/src/dirt_control/api/browser_schemas/commands.py
    apps/control-plane/src/dirt_control/api/browser_schemas/admin.py

Milestone 2 validation:

    uv run pytest apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q
    5 passed in 0.07s

    uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q
    59 passed in 15.07s

    scripts/gen-hosted-contract
    Completed successfully; no net diff in contracts/hosted-browser-v1.json or web-ui/src/api-client/generated/hosted-schema.ts.

    pnpm --dir web-ui typecheck
    Completed successfully.

    uv run ruff check apps/control-plane/src/dirt_control/api/browser.py apps/control-plane/src/dirt_control/api/browser_schemas apps/control-plane/tests/test_control_plane_boundary_guardrails.py
    All checks passed.

Milestone 3 route package:

    apps/control-plane/src/dirt_control/api/browser/__init__.py
    apps/control-plane/src/dirt_control/api/browser/_shared.py
    apps/control-plane/src/dirt_control/api/browser/auth.py
    apps/control-plane/src/dirt_control/api/browser/health.py
    apps/control-plane/src/dirt_control/api/browser/sites.py
    apps/control-plane/src/dirt_control/api/browser/tents.py
    apps/control-plane/src/dirt_control/api/browser/metrics.py
    apps/control-plane/src/dirt_control/api/browser/plants.py
    apps/control-plane/src/dirt_control/api/browser/breeding_logbook.py
    apps/control-plane/src/dirt_control/api/browser/assets.py
    apps/control-plane/src/dirt_control/api/browser/commands.py
    apps/control-plane/src/dirt_control/api/browser/admin.py

Milestone 3 validation:

    uv run pytest apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q
    5 passed in 0.07s

    uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q
    59 passed in 15.49s

    uv run ruff check apps/control-plane/src/dirt_control/api/browser apps/control-plane/src/dirt_control/api/browser_schemas apps/control-plane/tests/test_control_plane_boundary_guardrails.py
    All checks passed.

    scripts/gen-hosted-contract
    Completed successfully; no net diff in contracts/hosted-browser-v1.json or web-ui/src/api-client/generated/hosted-schema.ts.

    pnpm --dir web-ui typecheck
    Completed successfully.

    Structural route check
    Aggregate browser package has no path-operation decorators. The aggregate exposes 35 browser routes. All routes declare response_model; /api/auth/logout intentionally declares response_model=None for 204 responses.

Milestone 4 service package:

    apps/control-plane/src/dirt_control/services/__init__.py
    apps/control-plane/src/dirt_control/services/browser_auth.py
    apps/control-plane/src/dirt_control/services/browser_health.py
    apps/control-plane/src/dirt_control/services/browser_tents.py
    apps/control-plane/src/dirt_control/services/browser_metrics.py
    apps/control-plane/src/dirt_control/services/browser_plants.py
    apps/control-plane/src/dirt_control/services/breeding_logbook.py
    apps/control-plane/src/dirt_control/services/browser_assets.py
    apps/control-plane/src/dirt_control/services/browser_commands.py
    apps/control-plane/src/dirt_control/services/browser_admin.py

Milestone 4 validation:

    uv run pytest apps/control-plane/tests -q
    66 passed in 16.47s

    uv run pytest apps/tests/invariants -q
    41 passed in 3.58s

    uv run ruff check apps/control-plane/src/dirt_control/api/browser apps/control-plane/src/dirt_control/services apps/control-plane/src/dirt_control/api/browser_schemas apps/control-plane/tests/test_control_plane_boundary_guardrails.py
    All checks passed.

    scripts/gen-hosted-contract
    Completed successfully; no net diff in contracts/hosted-browser-v1.json or web-ui/src/api-client/generated/hosted-schema.ts.

    pnpm --dir web-ui typecheck
    Completed successfully.

    pnpm --dir web-ui lint
    Completed successfully.

    pnpm --dir web-ui test
    3 files passed; 12 tests passed.

    rg -n "dirt_control\\.models|from sqlalchemy|sqlalchemy\\.ext\\.asyncio|select\\(|insert\\(|update\\(|delete\\(|\\._shared" apps/control-plane/src/dirt_control/api/browser
    No matches. Browser route modules no longer import the database/model layer or private shared data helper module.

Milestone 6 invariant files changed:

    apps/tests/invariants/_helpers.py
    apps/tests/invariants/test_no_module_level_singletons.py
    apps/tests/invariants/test_no_concrete_clock_in_production.py
    apps/tests/invariants/test_no_env_reads_outside_config.py
    apps/tests/invariants/test_no_asyncio_run_outside_entrypoints.py
    apps/tests/invariants/test_no_raw_sql_outside_data_layer.py

Milestone 6 allowlist/source-map rationale:

    APP_SOURCE_DIRS maps dirt_control to control-plane/src/dirt_control because the package path does not follow the dirt_<name> -> apps/<name>/src convention.
    STAGE1_GENERIC_APPS applies only the Stage 1 generic invariant family to dirt_control while avoiding unrelated invariant families until their milestones.
    control-plane/src/dirt_control/app.py is a composition root because it builds the FastAPI app, lifespan, sessions, engine, and asset store.
    control-plane/src/dirt_control/bootstrap_gateway.py is an env/bootstrap boundary and short-lived command entrypoint used by scripts/deploy-control-plane.
    control-plane/src/dirt_control/models/, services/, and db.py are control-plane data-layer locations for raw SQL literal allowance.

Milestone 6 validation:

    uv run pytest apps/tests/invariants -q
    46 passed in 3.92s

    uv run pytest apps/control-plane/tests -q
    66 passed in 18.14s

    uv run ruff check apps/tests/invariants apps/control-plane/src/dirt_control
    All checks passed.

    git diff --check
    Completed successfully.

    Negative invariant check
    Temporarily added apps/control-plane/src/dirt_control/_invariant_probe.py with os.environ.get(...). uv run pytest apps/tests/invariants/test_no_env_reads_outside_config.py -q failed as expected for dirt_control, reporting the probe path and os.environ.get(...). The probe was removed, and the focused env invariant reran clean: 4 passed in 0.19s.

Milestone 7 invariant files changed:

    apps/tests/invariants/import_boundaries.invariant.ini
    apps/tests/invariants/test_import_boundaries.py

Milestone 7 validation:

    uv run pytest apps/tests/invariants/test_import_boundaries.py -q
    1 passed in 0.19s

    uv run pytest apps/tests/invariants -q
    51 passed in 3.69s

    uv run pytest apps/control-plane/tests -q
    66 passed in 16.71s

    uv run ruff check apps/tests/invariants apps/control-plane/src/dirt_control
    All checks passed.

    git diff --check
    Completed successfully.

    Negative invariant checks
    Temporarily added `from sqlalchemy import select` to apps/hwd/src/dirt_hwd/api/ingest.py. uv run pytest apps/tests/invariants/test_import_boundaries.py -q failed as expected, reporting dirt_hwd.api.ingest -> sqlalchemy.
    Temporarily added `from dirt_control.models import CloudTent` to apps/control-plane/src/dirt_control/api/browser/sites.py. uv run pytest apps/tests/invariants/test_import_boundaries.py -q failed as expected, reporting dirt_control.api.browser.sites -> dirt_control.models.
    Both probes were removed and the focused import-boundary invariant reran clean.

Milestone 8 invariant file added:

    apps/tests/invariants/test_control_plane_browser_shape.py

Milestone 8 validation:

    uv run pytest apps/tests/invariants/test_control_plane_browser_shape.py -q
    5 passed in 0.09s

    uv run pytest apps/tests/invariants -q
    51 passed in 3.69s

    uv run pytest apps/control-plane/tests -q
    66 passed in 16.52s

    uv run ruff check apps/tests/invariants apps/control-plane/src/dirt_control
    All checks passed.

    git diff --check
    Completed successfully.

    Negative invariant checks
    Temporarily added a browser path operation to apps/control-plane/src/dirt_control/api/browser/__init__.py; the focused invariant failed with apps/control-plane/src/dirt_control/api/browser/__init__.py:31 uses router.get(...) in the aggregate module.
    Temporarily added a Pydantic DTO class to apps/control-plane/src/dirt_control/api/browser/sites.py; the focused invariant failed with class _InvariantProbeDto(pydantic.BaseModel).
    Temporarily removed response_model from the /sites route decorator; the focused invariant failed with router.get(...) omits response_model=....
    Temporarily added a SQLAlchemy select(...) call to apps/control-plane/src/dirt_control/api/browser/sites.py; the focused invariant failed with calls sqlalchemy.select(...).
    Temporarily changed BrowserResponse model_config extra to "allow"; the focused invariant failed with model_config extra is 'allow'; expected 'forbid'.
    All probes were removed and the focused invariant reran clean.

Milestone 9 final validation:

    uv run pytest -q
    723 passed, 1 skipped in 80.03s

    uv run pytest apps/control-plane/tests -q
    66 passed in 16.54s

    uv run pytest apps/tests/invariants -q
    51 passed in 3.69s

    scripts/gen-hosted-contract
    Completed successfully.

    git diff -- contracts/hosted-browser-v1.json web-ui/src/api-client/generated/hosted-schema.ts
    No output; generated hosted browser contract artifacts have no net diff.

    pnpm --dir web-ui typecheck
    Completed successfully.

    pnpm --dir web-ui lint
    Completed successfully.

    pnpm --dir web-ui test
    3 files passed; 12 tests passed.

    git diff --check
    Completed successfully.

    rg -n "dirt_control\\.models|from sqlalchemy|sqlalchemy\\.ext\\.asyncio|select\\(|insert\\(|update\\(|delete\\(|\\._shared" apps/control-plane/src/dirt_control/api/browser
    No matches. Browser route modules remain thin HTTP adapters.

    rg -n "location_key|location_label|/api/tents/\\{tent_id\\}" apps/control-plane/src/dirt_control apps/control-plane/tests web-ui/src
    Only the Milestone 1 negative assertions in apps/control-plane/tests/test_api.py remain.

Milestone 9 deployment/browser-smoke note:

    No hosted deploy was requested, so scripts/deploy-control-plane was not run.
    No local hosted browser smoke was run during this validation pass.

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
