# Migrate Hosted Frontend to Generated API Types

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, the hosted React frontend will consume the hosted control-plane API through OpenAPI-generated TypeScript types instead of the hand-written interfaces in `web-ui/src/api-client/cloud.ts`. A future agent should be able to add or change a hosted browser route in `apps/control-plane/src/dirt_control/api/browser.py`, run `scripts/gen-hosted-contract`, and have TypeScript reveal every frontend call site, mock fixture, and adapter that must change.

The user-visible behavior should remain the same during this migration: hosted dashboard and hosted live/PTZ screens still load sites, tents, current metrics, metric history, devices, light schedules, latest assets, sync status, and PTZ commands. The difference is architectural. The shape authority moves to FastAPI response/request models and the generated `web-ui/src/api-client/generated/hosted-schema.ts` artifact. Handwritten hosted response types disappear, and any remaining UI-only model is explicitly a view model derived from generated DTOs.

This plan intentionally covers five steps:

1. Replace `cloudGet<T>` and handwritten `Cloud*` API types with generated hosted API calls.
2. Migrate route/query code to typed generated paths.
3. Keep small UI mappers only where component view models differ from hosted DTOs.
4. Update MSW hosted fixtures and tests to use generated hosted schema types.
5. Add missing hosted API routes in `apps/control-plane` before the frontend depends on them.


## Progress

- [x] (2026-05-13T00:00:00-06:00) Created this ExecPlan from the hosted generated API migration discussion.
- [ ] Milestone 1: establish the generated hosted client as the only browser fetch path for hosted routes.
- [ ] Milestone 2: migrate hosted dashboard and live/PTZ queries to generated path calls.
- [ ] Milestone 3: split generated DTOs from UI view models with explicit mappers.
- [ ] Milestone 4: type MSW hosted fixtures and fixture tests from the generated hosted schema.
- [ ] Milestone 5: add missing control-plane routes before frontend use, regenerate, and remove the old cloud client.


## Surprises & Discoveries

- Observation: The hosted frontend currently uses hand-written interfaces and generic fetch helpers for cloud API calls.
  Evidence: `web-ui/src/api-client/cloud.ts` exports `CloudSite`, `CloudTent`, `CloudMetric`, `CloudDevice`, `CloudAsset`, `CloudSyncStatus`, `CloudCommand`, `CloudCommandCreate`, `cloudGet<T>()`, and `cloudPost<T>()`.

- Observation: Hosted dashboard and live/PTZ are the only current app routes importing `web-ui/src/api-client/cloud.ts`.
  Evidence: `rg "api-client/cloud|cloudGet|Cloud[A-Z]" web-ui/src` finds imports in `web-ui/src/routes/index.tsx` and `web-ui/src/routes/live.tsx`, plus hosted fixture tests under `web-ui/src/mocks/__tests__/handlers.test.ts`.

- Observation: A generated hosted client wrapper already exists in the current working tree, but the plan must be robust if an implementer starts from a commit where the scrub has not landed.
  Evidence: Expected files are `scripts/gen-hosted-contract`, `contracts/hosted-browser-v1.json`, `web-ui/src/api-client/generated/hosted-schema.ts`, and `web-ui/src/api-client/hosted.ts`.

- Observation: The current handwritten `cloudGet` preserves the `cloud_fixture` query parameter used by MSW hosted scenarios.
  Evidence: `appendFixtureParam()` in `web-ui/src/api-client/cloud.ts` appends `cloud_fixture` from `window.location.search` to every hosted request. A generated-client migration must preserve this behavior without adding `cloud_fixture` to production OpenAPI route schemas.


## Decision Log

- Decision: Use the control-plane FastAPI OpenAPI schema as the hosted browser contract source of truth.
  Rationale: Hosted browser routes already live in `apps/control-plane/src/dirt_control/api/browser.py` with Pydantic request/response models. Generating the TypeScript schema from that app avoids keeping a separate handwritten frontend contract in sync.
  Date/Author: 2026-05-13 / Codex

- Decision: Keep generated DTOs at the API boundary and introduce view-model mappers only when the UI needs a different shape.
  Rationale: Components should not invent network contracts, but it is valid for the UI to have display-specific models such as metric cards, freshness labels, or normalized PTZ command button state.
  Date/Author: 2026-05-13 / Codex

- Decision: Preserve hosted MSW scenario selection outside the OpenAPI contract.
  Rationale: `cloud_fixture` is a dev/test fixture knob, not a production API parameter. The generated client should append it through a wrapper or middleware so route calls remain typed against production schemas.
  Date/Author: 2026-05-13 / Codex

- Decision: Add missing hosted routes in `apps/control-plane` before frontend use.
  Rationale: The architectural smell came from the frontend hand-authoring types ahead of the contract. New frontend-visible hosted capabilities must start as Pydantic DTOs and FastAPI routes, then flow through `scripts/gen-hosted-contract`.
  Date/Author: 2026-05-13 / Codex


## Outcomes & Retrospective

Not yet implemented. At completion, update this section with the routes migrated, any API gaps discovered, and whether `web-ui/src/api-client/cloud.ts` was deleted or left as a temporary compatibility shim.


## Context and Orientation

The hosted control-plane browser API is implemented in `apps/control-plane/src/dirt_control/api/browser.py`. Its route decorators use Pydantic response models such as `SiteResponse`, `TentResponse`, `TentStateResponse`, `CurrentMetricResponse`, `MetricHistoryResponse`, `DeviceResponse`, `LightSchedulesResponse`, `AssetResponse`, `SyncStatusResponse`, `CommandCreateRequest`, and `CommandResponse`.

The generated hosted contract path is expected to be:

- `scripts/gen-hosted-contract` creates `contracts/hosted-browser-v1.json` from the control-plane FastAPI OpenAPI schema.
- The same script runs `openapi-typescript` and writes `web-ui/src/api-client/generated/hosted-schema.ts`.
- `web-ui/src/api-client/hosted.ts` wraps `openapi-fetch` as `createHostedApiClient()`.
- `web-ui/src/api-client/index.ts` exports `createHostedApiClient` and hosted schema aliases such as `hostedComponents`, `hostedOperations`, and `hostedPaths`.

If those files are missing when implementing this plan, first land the hosted contract-generation scrub: create `scripts/gen-hosted-contract`, generate `contracts/hosted-browser-v1.json` and `web-ui/src/api-client/generated/hosted-schema.ts`, add `createHostedApiClient()`, and note the command in `AGENTS.md`.

The current hosted frontend still imports `web-ui/src/api-client/cloud.ts` from:

- `web-ui/src/routes/index.tsx` for hosted dashboard data.
- `web-ui/src/routes/live.tsx` for hosted sync status, command list, and PTZ command creation.

The current hosted MSW fixtures live in:

- `web-ui/src/mocks/handlers.ts`
- `web-ui/src/mocks/__tests__/handlers.test.ts`

These fixtures currently define local test-only `Cloud*` interfaces. They should instead use generated hosted schema types where allowed by the frontend boundary rules. If an invariant forbids mocks importing from `@/api-client`, import type directly from `../api-client/generated/hosted-schema` or add a small `web-ui/src/mocks/hosted-types.ts` fixture-only type module if that better satisfies import boundaries.


## Plan of Work

Milestone 1 establishes the generated client as the only hosted request mechanism. Update `web-ui/src/api-client/hosted.ts` so it preserves the existing hosted behavior from `cloudGet`: credentials are included, `401` redirects to `/login`, errors are surfaced consistently to React Query, and `cloud_fixture` from the current page URL is appended in dev/test without polluting OpenAPI route types. Add helper types in this module only if they are consumed by application code; the `knip` invariant rejects unused exported types.

Milestone 2 migrates route/query code. In `web-ui/src/routes/index.tsx`, replace every `cloudGet<CloudX>()` call with `const hostedApi = createHostedApiClient()` and typed `hostedApi.GET(...)` calls. Use generated path literals such as `/api/sites`, `/api/tents`, `/api/tents/{tent_id}/metrics/current`, and `/api/tents/{tent_id}/metrics/history`. In `web-ui/src/routes/live.tsx`, replace `cloudGet` and `cloudPost` with generated `GET /api/sync/status`, `GET /api/commands`, and `POST /api/commands`.

Milestone 3 introduces explicit mappers where the UI should not consume DTOs directly. Keep local view types near the component or in a small route-local helper when display state differs from the generated DTO. Examples include converting metric freshness into `"live" | "stale"`, deriving status class names, sorting metrics into card order, or adapting command payloads for button handlers. Do not recreate one-to-one `Cloud*` copies of API DTOs.

Milestone 4 updates MSW fixtures. Replace test-only hosted response interfaces in `web-ui/src/mocks/__tests__/handlers.test.ts` and hosted fixture helper types in `web-ui/src/mocks/handlers.ts` with generated `components["schemas"][...]` aliases. Keep scenario-only types such as `CloudScenario` local because they model fixture behavior, not the API. Re-run fixture tests to prove the mock responses still satisfy the generated schema types.

Milestone 5 handles API gaps and removal. If the frontend needs a hosted route that is not present in `web-ui/src/api-client/generated/hosted-schema.ts`, add it first to `apps/control-plane/src/dirt_control/api/browser.py` with Pydantic request/response models, add focused `apps/control-plane/tests` coverage, run `scripts/gen-hosted-contract`, and only then consume it from React. Once all imports are gone, delete `web-ui/src/api-client/cloud.ts` and add the smallest possible guardrail: an ESLint `no-restricted-imports` entry in `web-ui/eslint.config.ts` that rejects `@/api-client/cloud`.


## Concrete Steps

Work from the repository root:

    cd /home/akcom/code/dirt

Before editing TypeScript, read the framework anchors required by `AGENTS.md`:

    sed -n '1,220p' docs/references/modern-idiomatic-typescript/INDEX.md
    sed -n '1,220p' docs/references/tanstack-router-v1/INDEX.md
    sed -n '1,180p' docs/references/msw-v2/INDEX.md

Confirm the hosted schema generation path exists:

    test -x scripts/gen-hosted-contract
    scripts/gen-hosted-contract

Expected result:

    hosted contract regenerated

Milestone 1 concrete edits:

- Update `web-ui/src/api-client/hosted.ts`.
- Preserve `credentials: "include"`.
- Preserve redirect-on-401 behavior.
- Add a fixture-query middleware or equivalent helper that appends `cloud_fixture` from `window.location.search` to outgoing hosted requests when present.
- If a helper unwraps `openapi-fetch` results, it must include the response status in thrown errors and must not erase the generated data/error types at call sites.

Milestone 2 concrete edits:

- In `web-ui/src/routes/index.tsx`, replace `@/api-client/cloud` imports with `createHostedApiClient` and generated hosted schema aliases.
- Replace string-interpolated URLs with generated path calls and `params.path` / `params.query` objects.
- In `web-ui/src/routes/live.tsx`, migrate hosted sync and command queries/mutations to `createHostedApiClient`.
- Keep local `createDirtApiClient()` usage unchanged for the non-hosted local UI path.

Milestone 3 concrete edits:

- Keep UI view types route-local unless shared by multiple components.
- Name mappers by direction, for example `toMetricCards(metrics)` or `toCommandButtonState(command)`.
- Use generated types as inputs, for example `hostedComponents["schemas"]["CurrentMetricResponse"]`.
- Do not add one-to-one aliases named like the old `CloudMetric` unless the alias is a generated schema alias and removes duplication.

Milestone 4 concrete edits:

- In `web-ui/src/mocks/handlers.ts`, type hosted response literals with generated schema aliases.
- In `web-ui/src/mocks/__tests__/handlers.test.ts`, remove local `CloudSyncStatus`, `CloudMetric`, `CloudTent`, `CloudDevice`, `CloudLightSchedulesResponse`, and `CloudCommand` interfaces.
- Keep `CloudScenario` or rename it to `HostedFixtureScenario`; it is not an API DTO.

Milestone 5 concrete edits:

- Run this search:

    rg -n "api-client/cloud|cloudGet|cloudPost|Cloud[A-Z]" web-ui/src

- If no real imports remain, delete `web-ui/src/api-client/cloud.ts`.
- Add an app-local ESLint restriction in `web-ui/eslint.config.ts` using `no-restricted-imports`. Keep it narrow: reject `@/api-client/cloud` with a message like "Use `createHostedApiClient()` and generated hosted schema types instead." Do not add a new pytest invariant for this.
- If route gaps are found, add them in `apps/control-plane/src/dirt_control/api/browser.py`, test them in `apps/control-plane/tests`, regenerate, and then return to the frontend migration.


## Validation and Acceptance

Run these commands after each milestone that changes TypeScript:

    pnpm --dir web-ui exec biome check src/api-client src/routes src/mocks
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui test

Expected result: all commands exit 0. `pnpm --dir web-ui typecheck` must fail if a hosted route response shape changes without matching frontend updates.

Run this command after any control-plane route or DTO change:

    uv run pytest apps/control-plane/tests -q
    scripts/gen-hosted-contract
    pnpm --dir web-ui typecheck

Expected result: control-plane tests pass, generated files update deterministically, and frontend typecheck passes.

Before completion, run:

    rg -n "api-client/cloud|cloudGet|cloudPost|Cloud[A-Z]" web-ui/src

Expected result: no matches, except optional fixture scenario names if deliberately retained and not representing API DTOs.

Run the focused architectural checks:

    uv run pytest apps/tests/invariants -q
    pnpm --dir web-ui exec knip --config invariants/knip.json --no-progress

Expected result: no dead exported types, no unused `cloud.ts`, and no invariant failures.

Human acceptance:

- Start the frontend in hosted mode against MSW or a real hosted API.
- Open the hosted dashboard.
- Confirm sites and tents load.
- Switch from `main` to `breeding`.
- Confirm the network panel shows generated-route calls to `/api/sites`, `/api/tents`, `/api/tents/{tent_id}/metrics/current`, `/api/tents/{tent_id}/devices`, `/api/tents/{tent_id}/lights/schedules`, `/api/tents/{tent_id}/assets/latest`, and `/api/sync/status`.
- Open hosted live/PTZ.
- Submit a PTZ command and confirm the command list updates through `GET /api/commands`.


## Idempotence and Recovery

`scripts/gen-hosted-contract` is safe to repeat. It should overwrite `contracts/hosted-browser-v1.json` and `web-ui/src/api-client/generated/hosted-schema.ts` deterministically from the current FastAPI app.

If generated schema output changes unexpectedly, inspect `apps/control-plane/src/dirt_control/api/browser.py` route decorators and Pydantic models first. Do not patch `web-ui/src/api-client/generated/hosted-schema.ts` by hand.

If a route migration becomes too large, keep `cloud.ts` temporarily but remove one hosted route group at a time. The safe order is dashboard read routes first, live/PTZ command routes second, MSW fixture typing third, deletion last.

If `cloud_fixture` breaks, restore behavior in `web-ui/src/api-client/hosted.ts` instead of adding `cloud_fixture` to control-plane Pydantic query models. It is a frontend fixture concern.

If a missing route is discovered, stop the frontend migration for that route. Add the FastAPI route and response model first, test it, regenerate, and resume.


## Artifacts and Notes

Initial search evidence:

    rg -n "api-client/cloud|cloudGet|Cloud[A-Z]" web-ui/src

Important current call sites:

    web-ui/src/routes/index.tsx
    web-ui/src/routes/live.tsx
    web-ui/src/mocks/handlers.ts
    web-ui/src/mocks/__tests__/handlers.test.ts

Expected generated schema names include:

    components["schemas"]["SiteResponse"]
    components["schemas"]["TentResponse"]
    components["schemas"]["TentStateResponse"]
    components["schemas"]["CurrentMetricResponse"]
    components["schemas"]["MetricHistoryResponse"]
    components["schemas"]["DeviceResponse"]
    components["schemas"]["LightSchedulesResponse"]
    components["schemas"]["AssetResponse"]
    components["schemas"]["SyncStatusResponse"]
    components["schemas"]["CommandCreateRequest"]
    components["schemas"]["CommandResponse"]


## Interfaces and Dependencies

End-state interfaces:

- `scripts/gen-hosted-contract` exists and is the only supported hosted browser API generation command.
- `contracts/hosted-browser-v1.json` is generated from `apps/control-plane` FastAPI OpenAPI.
- `web-ui/src/api-client/generated/hosted-schema.ts` is generated from `contracts/hosted-browser-v1.json`.
- `web-ui/src/api-client/hosted.ts` exports `createHostedApiClient()`.
- `web-ui/src/routes/index.tsx` and `web-ui/src/routes/live.tsx` use generated hosted API calls for hosted mode.
- `web-ui/src/api-client/cloud.ts` is deleted after all imports are gone.
- `web-ui/src/mocks/handlers.ts` and `web-ui/src/mocks/__tests__/handlers.test.ts` use generated hosted schema types for hosted API response/request fixtures.
- New hosted frontend-visible routes are first implemented in `apps/control-plane/src/dirt_control/api/browser.py` with Pydantic DTOs and tests, then consumed from generated TypeScript.

External dependencies already present in the repo:

- `openapi-fetch` in `web-ui`.
- `openapi-typescript` in `web-ui`.
- FastAPI OpenAPI generation from `apps/control-plane`.
- MSW v2 for frontend fixtures.


## Revision Notes

- 2026-05-13 / Codex: Initial plan created for migrating hosted frontend code from handwritten cloud interfaces to generated OpenAPI types.
