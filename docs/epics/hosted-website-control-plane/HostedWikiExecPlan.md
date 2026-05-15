# Expose the Grow Wiki on the Hosted Web UI

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, an authenticated operator using the hosted web UI at `https://sirius-forge.com/` can open `/wiki`, browse the grow wiki tree, read Markdown pages, follow backlinks, and search from Cmd+K without needing network access to the local `dirt-web` service. Today the hosted wiki route calls the cloud API for `/api/wiki/tree`, `/api/wiki/file`, and `/api/wiki/search`, but those routes do not exist in `control-plane-api`, so the hosted UI returns 404s.

The architectural goal is deliberately narrow: expose the wiki as a site-scoped, read-only cloud projection. The cloud must not become an editable CMS, and it must not reach into the local network. The local box remains the source of truth for `wiki/`; `dirt-gateway` periodically validates and pushes a typed snapshot of page rows outbound to the hosted control plane; the hosted browser API derives the existing tree, file, backlinks, and search responses from those page rows behind browser authentication.

The user-visible acceptance signal is simple: after gateway sync and hosted deployment, `/wiki` works in hosted mode with the same basic behavior as local wiki browsing. A direct unauthenticated request to hosted `/api/wiki/tree` must still be rejected, and an authenticated request must return the projected tree instead of 404.


## Progress

- [x] (2026-05-15) Created this ExecPlan from the hosted UI parity wiki split-out discussion.
- [ ] Milestone 1: define and test typed wiki projection contracts.
- [ ] Milestone 2: collect local wiki page projections in `dirt-gateway`.
- [ ] Milestone 3: store site-scoped wiki page rows in the cloud database.
- [ ] Milestone 4: expose hosted browser-authenticated `/api/wiki/*` routes.
- [ ] Milestone 5: wire frontend behavior to the hosted route and generated hosted contract as needed.
- [ ] Milestone 6: validate locally, deploy through the supported script, and capture hosted wiki acceptance evidence.


## Surprises & Discoveries

- Observation: The local wiki API is filesystem-backed and already returns typed response models.
  Evidence: `apps/web/src/dirt_web/api/wiki.py` wraps `dirt_shared.services.wiki` and returns `WikiTreeResponse`, `WikiFile`, and `WikiSearchResponse` from `dirt_contracts.webapp_v1.models`.

- Observation: The hosted UI currently fails because the same `/api/wiki/*` paths are absent from `apps/control-plane/src/dirt_control/api/browser.py`.
  Evidence: `docs/epics/hosted-website-control-plane/UIParityExecPlan.md` records hosted `GET https://api.sirius-forge.com/api/wiki/tree` returning 404 while local `GET http://192.168.1.79:8001/api/wiki/tree` returned 200.

- Observation: The hosted browser contract migration has already chosen the control-plane FastAPI OpenAPI schema as the hosted frontend source of truth.
  Evidence: `docs/epics/hosted-website-control-plane/GeneratedApiMigrationExecPlan.md` records the decision to generate `web-ui/src/api-client/generated/hosted-schema.ts` from `apps/control-plane`.

- Observation: `dirt-control-plane` does not currently depend on `dirt-contracts`.
  Evidence: `apps/control-plane/pyproject.toml` lists FastAPI, Pydantic, SQLModel, and control-plane dependencies, but not `dirt-contracts`.


## Decision Log

- Decision: Implement hosted wiki as a site-scoped row-per-page projection, not as static public files, inbound proxying, or a full CMS.
  Rationale: The original hosted-control-plane boundary is outbound-only. Row-per-page storage keeps the cloud inspectable and lets the browser API derive tree, file, backlinks, and substring search without mirroring the entire local database or inventing editing behavior.
  Date/Author: 2026-05-15 / Codex

- Decision: Store only canonical page content and minimal metadata in cloud rows; derive tree, backlinks, and search at request time in `control-plane-api`.
  Rationale: The wiki is small enough that separate folder, backlink, and search-index tables would overbuild the first pass. Derived responses avoid consistency bugs between precomputed indexes and page content.
  Date/Author: 2026-05-15 / Codex

- Decision: Keep the hosted browser route paths and response semantics aligned with the existing local `/api/wiki/tree`, `/api/wiki/file`, and `/api/wiki/search` API.
  Rationale: `web-ui/src/routes/wiki.tsx` already has a functional route, sidebar, document renderer, recent-file handling, and command palette. The cloud should satisfy that contract instead of creating a second hosted-only wiki UI.
  Date/Author: 2026-05-15 / Codex

- Decision: Add explicit exclusion policy before first production sync.
  Rationale: Wiki contents are operational notes. The plan should not assume every local Markdown file is safe for cloud sync just because the route is authenticated.
  Date/Author: 2026-05-15 / Codex


## Outcomes & Retrospective

Not yet implemented. Update this section after each milestone with what changed, what still differs between local and hosted wiki behavior, and any accepted follow-up work.


## Context and Orientation

The wiki source of truth is the repository-root `wiki/` directory. `wiki/AGENTS.md` describes the wiki operating model and the file layout. The local API reads this directory through `apps/shared/src/dirt_shared/services/wiki.py`, which supports:

- `get_tree()` for folders and loose root Markdown files.
- `get_file(path)` for frontmatter, Markdown body, subtitle, and backlinks.
- `search(q)` for substring search over path, title, and body.

The local browser API lives in `apps/web/src/dirt_web/api/wiki.py` and exposes:

- `GET /api/wiki/tree`
- `GET /api/wiki/file?path=...`
- `GET /api/wiki/search?q=...`

The React route `web-ui/src/routes/wiki.tsx` consumes those paths through `createDirtApiClient()`, maps the response into `WikiSidebar`, `WikiDoc`, and `CmdKPalette`, and keeps recent wiki files in local storage. The UI should not need a hosted-only document renderer.

The hosted control plane lives in `apps/control-plane`. Its browser routes are in `apps/control-plane/src/dirt_control/api/browser.py`, and its database models are in `apps/control-plane/src/dirt_control/models/cloud.py`. Hosted browser routes require `require_browser_user`; wiki routes must use the same authentication dependency.

The outbound gateway lives in `apps/gateway`. `GatewaySyncService` in `apps/gateway/src/dirt_gateway/sync.py` collects typed projections from `GatewayLocalServiceBundle` in `apps/gateway/src/dirt_gateway/local.py`, stores them in the local outbox, and dispatches them to `HttpCloudGatewayClient` in `apps/gateway/src/dirt_gateway/cloud.py`.

The boundary-contract rule is `docs/rules/boundary-contracts.md`: owned payloads that cross process, network, persistence, or generated-client boundaries use Pydantic DTOs, validate at producer and consumer boundaries, and avoid raw `dict[str, Any]` except for truly opaque data.


## Plan of Work

Milestone 1 defines the contracts. Add gateway DTOs to `apps/shared/src/dirt_shared/cloud_contract.py` for a full wiki projection. The minimum shape is `WikiProjectionRequest(site_id, generated_at, pages, excluded_paths, content_hash)` and `WikiProjectionPage(path, title, frontmatter, body_markdown, sha256, source_updated_at)`. Add a response DTO such as `WikiProjectionResponse(upserted, deleted, synced_at)`. Use `CloudContractModel` so `extra="forbid"` applies. Add focused tests in `apps/shared/tests/test_cloud_contract.py` that validate required nullable fields and reject unknown keys.

Milestone 2 collects the local projection. Add a method to `LocalGatewayServices` and `GatewayLocalServiceBundle`, for example `collect_wiki(site_id: str) -> WikiProjectionRequest`. It should walk the local wiki with `dirt_shared.services.wiki`, collect Markdown pages, parse titles/frontmatter using existing service behavior, compute stable SHA-256 hashes, and apply an explicit exclusion policy. The first exclusion policy must at least omit `wiki/AGENTS.md` and should support a small configurable denylist if sensitive local-only pages are identified. Add gateway tests that seed a temporary wiki through `DIRT_WIKI_DIR`, collect the projection, and assert paths, title extraction, body Markdown, hashes, and exclusions.

Milestone 3 adds cloud storage. Create an Atlas cloud migration under `cloud/migrations/` and a SQLModel table in `apps/control-plane/src/dirt_control/models/cloud.py`, for example `CloudWikiPage`. The table should be keyed by `site_id` and `path`, store `title`, `frontmatter` JSON, `body_markdown`, `sha256`, `source_updated_at`, `synced_at`, `created_at`, and `updated_at`, and index `site_id`. The gateway route should replace the page set for the site atomically enough that deleted local files disappear from hosted results. For the first pass, deleting rows absent from the incoming projection inside the same request is acceptable.

Milestone 4 adds cloud gateway and browser routes. Add `PUT /api/gateway/v1/wiki` to `apps/control-plane/src/dirt_control/api/gateway.py`; authenticate with `require_gateway`, call `require_gateway_scope`, validate the DTO, upsert rows, delete missing rows for that site, commit, and return `WikiProjectionResponse`. Add `HttpCloudGatewayClient.put_wiki()`, extend `CloudGatewayClient`, include a `"wiki"` projection in `GatewaySyncService`, and add the event model to `_READ_ONLY_EVENT_MODELS`. In `apps/control-plane/src/dirt_control/api/browser.py`, add browser-authenticated `GET /api/wiki/tree`, `GET /api/wiki/file`, and `GET /api/wiki/search` routes. Define local Pydantic browser response models matching the existing local wiki JSON shape, or introduce a small shared hosted browser DTO module if that pattern has already landed by implementation time.

Milestone 5 aligns the frontend contract. Run `scripts/gen-hosted-contract` so `contracts/hosted-browser-v1.json` and `web-ui/src/api-client/generated/hosted-schema.ts` include `/api/wiki/*`. If `web-ui/src/routes/wiki.tsx` can continue to use `createDirtApiClient()` safely because hosted and local route shapes are identical, keep the frontend change minimal and document that choice. If the generated-hosted-client guardrails require hosted routes to use `createHostedApiClient()`, add a small API-client selector while preserving the same UI components and view models. Do not add hand-written hosted wiki TypeScript interfaces.

Milestone 6 validates and deploys. Run focused backend tests, regenerate hosted contracts, run frontend typecheck/build if frontend files changed, run `scripts/agent-fix`, then deploy through `scripts/deploy-control-plane`. After deployment and one gateway sync cycle, use `agent-browser` to verify hosted `/wiki`: sidebar loads, opening `wiki/overview.md` renders Markdown, search returns expected results, unauthenticated `/api/wiki/tree` is rejected, and authenticated `/api/wiki/tree` returns 200.


## Concrete Steps

Start from the repository root:

    cd /home/akcom/code/dirt

Read the required docs before implementation:

    sed -n '1,220p' docs/commands.md
    sed -n '1,220p' docs/rules/boundary-contracts.md
    sed -n '1,220p' wiki/AGENTS.md
    sed -n '1,220p' docs/database.md
    sed -n '1,220p' docs/references/atlas/INDEX.md
    sed -n '1,220p' docs/references/modern-idiomatic-typescript/INDEX.md
    sed -n '1,220p' docs/references/tanstack-router-v1/INDEX.md

Inspect the local wiki route and service:

    sed -n '1,240p' apps/web/src/dirt_web/api/wiki.py
    sed -n '1,460p' apps/shared/src/dirt_shared/services/wiki.py

Implement Milestone 1 and 2:

    uv run pytest apps/shared/tests/test_cloud_contract.py -q
    uv run pytest apps/gateway/tests/test_sync.py -q
    uv run pytest apps/gateway/tests/test_gateway_boundary_guardrails.py -q

Implement Milestone 3 and 4:

    uv run pytest apps/control-plane/tests -q
    uv run pytest apps/tests/invariants -q

Regenerate hosted browser types after adding hosted browser routes:

    scripts/gen-hosted-contract

If `web-ui/src/routes/wiki.tsx` or API-client code changes:

    pnpm --dir web-ui typecheck
    pnpm --dir web-ui build

Before committing implementation changes:

    scripts/agent-fix

Deploy only after tests pass and the user is ready for hosted rollout:

    scripts/deploy-control-plane


## Validation and Acceptance

Backend acceptance:

- `PUT /api/gateway/v1/wiki` requires gateway auth and rejects a projection whose `site_id` is outside the gateway credential scope.
- A valid wiki projection upserts changed pages and deletes rows for pages removed from the incoming projection for that site.
- `GET /api/wiki/tree` requires browser auth and returns folders plus root files derived from `CloudWikiPage` rows.
- `GET /api/wiki/file?path=wiki/overview.md` requires browser auth and returns title, frontmatter, Markdown body, and backlinks.
- `GET /api/wiki/file?path=../secrets` returns 400.
- `GET /api/wiki/file?path=wiki/missing.md` returns 404.
- `GET /api/wiki/search?q=vpd` requires browser auth and returns ranked title/path/content matches with snippets.

Frontend acceptance:

- In hosted mode, `/wiki` no longer shows the 404-backed empty/error behavior for `/api/wiki/tree`.
- Selecting a page from the sidebar updates `?path=...` and renders the Markdown document.
- Cmd+K search does not call the API for empty input and does call hosted `/api/wiki/search` for non-empty input.
- Existing local wiki behavior still works against local `dirt-web`.

Deployment acceptance:

- `scripts/deploy-control-plane` completes smoke checks.
- After a real gateway sync, authenticated hosted `/api/wiki/tree` returns 200 with expected wiki paths.
- Unauthenticated hosted `/api/wiki/tree` returns 401.
- `agent-browser` screenshots show the hosted wiki sidebar and at least one rendered page.


## Idempotence and Recovery

Gateway wiki projection is safe to run repeatedly. The idempotency key should be based on the stable projection content hash, so unchanged wiki content does not create distinct durable work. Replaying the same projection should leave the same `CloudWikiPage` rows.

Cloud upsert is safe to retry after network failures. The route should update rows by `(site_id, path)` and delete rows absent from the incoming page list only after validating the full request. If a request fails before commit, the previous wiki projection remains visible.

If a bad page is synced, fix the local wiki file or exclusion policy and run another gateway sync. Do not manually edit cloud rows except during incident recovery. If the hosted route must be disabled during an incident, the frontend can show the existing wiki load/error state while dashboard and live routes continue operating.

If sensitive content is discovered after sync, add the path to the exclusion policy, run a sync that deletes absent rows, and rotate hosted browser credentials only if there is evidence that an unauthorized browser session had access.


## Artifacts and Notes

Initial design evidence:

    apps/web/src/dirt_web/api/wiki.py exposes local /api/wiki/tree, /api/wiki/file, and /api/wiki/search.
    apps/shared/src/dirt_shared/services/wiki.py reads wiki/ from disk and derives tree, file, backlinks, and search.
    apps/control-plane/src/dirt_control/api/browser.py currently has no /api/wiki/* routes.
    docs/epics/hosted-website-control-plane/UIParityExecPlan.md records hosted /api/wiki/tree returning 404.

Record implementation evidence here as milestones land: migration name, test commands and short outputs, generated contract command output, deployment timestamp, and hosted browser screenshot paths.


## Interfaces and Dependencies

New or changed shared contracts:

- `apps/shared/src/dirt_shared/cloud_contract.py`
- `WikiProjectionPage`
- `WikiProjectionRequest`
- `WikiProjectionResponse`

New or changed gateway interfaces:

- `apps/gateway/src/dirt_gateway/protocols.py`
- `GatewayLocalServiceBundle.collect_wiki()`
- `HttpCloudGatewayClient.put_wiki()`
- `GatewaySyncService` `"wiki"` projection and dispatch handling

New or changed cloud persistence:

- `apps/control-plane/src/dirt_control/models/cloud.py`
- `CloudWikiPage`
- `cloud/migrations/*_cloud_wiki_page.sql` or equivalent Atlas-generated migration

New or changed cloud routes:

- `PUT /api/gateway/v1/wiki`
- `GET /api/wiki/tree`
- `GET /api/wiki/file`
- `GET /api/wiki/search`

Generated frontend contract artifacts:

- `contracts/hosted-browser-v1.json`
- `web-ui/src/api-client/generated/hosted-schema.ts`

Validation commands:

- `uv run pytest apps/shared/tests/test_cloud_contract.py -q`
- `uv run pytest apps/gateway/tests/test_sync.py -q`
- `uv run pytest apps/control-plane/tests -q`
- `uv run pytest apps/tests/invariants -q`
- `scripts/gen-hosted-contract`
- `pnpm --dir web-ui typecheck`
- `pnpm --dir web-ui build`


## Revision Notes

- 2026-05-15: Initial plan created. The plan chooses authenticated row-per-page cloud projection with derived hosted wiki API responses, preserving outbound-only gateway architecture and the existing `/api/wiki/*` browser route shape.
