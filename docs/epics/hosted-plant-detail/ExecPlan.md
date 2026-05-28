# Hosted Plant Detail Page

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, an authenticated operator using the Railway-hosted UI can open a plant detail page for a plant that has a real soil-moisture stream. The first supported plants are the current main-tent plants because they already have per-plant ESP32 moisture data and wiki plant pages. The page shows the plant identity, current moisture state, a selectable 1h / 24h / 7d / 30d / 90d moisture trend using the same sparkline interaction pattern as the hosted dashboard, and the plant's wiki detail content.

This matters because the hosted UI is becoming the operator-facing control plane. Plant-level status should not depend on the retired local browser UI or on direct filesystem/database access. The architecture must remain flexible for later plants, tents, and grow runs without baking `a` through `d` into route code or cloud storage.

The work is complete when the hosted UI has a tent-scoped route such as `/tents/$tentId/plants/$plantId` that can be reached from the hosted dashboard for moisture-backed plants, `Plant A` through `Plant D` render from synced plant metadata rather than a hardcoded frontend list, the moisture graph uses the selected range and the plant's own metric stream, the plant wiki page renders from a cloud projection of `wiki/plants/plant-a.md` style content, and plants without a soil-moisture stream are not linked as detail pages.


## Progress

- [x] (2026-05-28T00:00Z) Created this ExecPlan from the request to recreate the old local plant detail page on the Railway-hosted UI with clean, durable architecture.
- [ ] Milestone 1: correct hosted metric stream identity so per-plant soil streams are distinguishable.
- [ ] Milestone 2: sync current-grow plant metadata to the hosted control plane.
- [ ] Milestone 3: expose browser-authenticated hosted plant list/detail/history APIs.
- [ ] Milestone 4: project plant wiki pages to the hosted control plane and compose them into plant detail responses.
- [ ] Milestone 5: build the hosted React plant detail route and dashboard links.
- [ ] Milestone 6: validate locally, deploy through the supported Railway script, and capture hosted acceptance evidence.


## Surprises & Discoveries

- Observation: Hosted metric rollups currently do not carry `device_id`, and both latest and rollup cloud uniqueness are keyed by `site_id`, `tent_id`, public `capability_id`, and `metric`.
  Evidence: `apps/control-plane/src/dirt_control/models/cloud.py` defines `CloudLatestMetric` uniqueness on `site_id, tent_id, capability_id, metric` and `CloudMetricRollup` uniqueness on `site_id, tent_id, capability_id, metric, bucket, bucket_start_at`; `apps/gateway/src/dirt_gateway/local.py` emits rollups grouped by `t.tent_id, c.capability_id, c.metric_name, c.unit, bucket_start_at`.

- Observation: The local plant model already contains the durable plant identity needed for this page.
  Evidence: `apps/shared/src/dirt_shared/models/plant.py` has `plant_id`, `name`, `display_order`, `status`, `purple`, moisture target bounds, and nullable `moisture_capability_id` scoped to a current `growrun`.

- Observation: The hosted frontend now consumes the control-plane OpenAPI schema and should not hand-author hosted DTO types.
  Evidence: `web-ui/src/api-client/hosted.ts` documents that `scripts/gen-hosted-contract` generates `web-ui/src/api-client/generated/hosted-schema.ts` from `apps/control-plane`.

- Observation: The hosted wiki route is currently a placeholder, while a separate hosted wiki ExecPlan already chose a site-scoped row-per-page projection.
  Evidence: `web-ui/src/routes/wiki.tsx` intentionally makes no network calls and shows "Wiki unavailable"; `docs/epics/hosted-website-control-plane/HostedWikiExecPlan.md` describes a `CloudWikiPage` projection and browser `/api/wiki/*` routes.


## Decision Log

- Decision: Treat hosted metric stream identity as `site_id + tent_id + device_id + capability_id + metric`.
  Rationale: Local `capability.capability_id` is unique per device, not per tent. All plant moisture nodes can truthfully expose `capability_id='soil_moisture_raw'`, so hosted storage and rollups must include `device_id` to avoid collapsing Plant A through Plant D into one trend.
  Date/Author: 2026-05-28 / Codex

- Decision: Add a hosted plant projection to the existing catalog sync instead of hardcoding current main-tent plants in the browser.
  Rationale: Plants are scoped identity data like tents, devices, capabilities, and schedules. Syncing them through the gateway keeps the cloud inspectable and lets future plants appear without frontend code changes.
  Date/Author: 2026-05-28 / Codex

- Decision: A plant detail page is available only when the plant has a synced soil-moisture stream.
  Rationale: The first version is specifically a moisture trend page. Showing detail links for plants without the backing stream would create empty pages and misleading affordances.
  Date/Author: 2026-05-28 / Codex

- Decision: Do not store wiki Markdown on `CloudPlant`.
  Rationale: Plant identity and wiki documents are separate domain concepts. Store plant metadata in a plant table and wiki page content in the hosted wiki projection, then compose them at the browser API boundary.
  Date/Author: 2026-05-28 / Codex

- Decision: Implement only the wiki projection slice needed by plant detail if the full hosted wiki plan has not landed by implementation time.
  Rationale: The plant page needs `wiki/plants/*.md` content, but that should still use the same `CloudWikiPage` shape chosen for the full hosted wiki rather than inventing a plant-only markdown field.
  Date/Author: 2026-05-28 / Codex


## Outcomes & Retrospective

Not yet implemented. Update this section after each milestone with the actual behavior, any residual gaps, and the evidence used to accept or defer work.


## Context and Orientation

The hosted control plane is the Railway-deployed API and web UI. Local services push read-only projections outward through `dirt-gateway`; the hosted API never reaches into the local network. The relevant pieces are:

- `apps/gateway/src/dirt_gateway/local.py`: collects local catalog, latest metrics, rollups, and assets from the local PostgreSQL database.
- `apps/shared/src/dirt_shared/cloud_contract.py`: Pydantic DTOs for gateway-to-control-plane payloads.
- `apps/control-plane/src/dirt_control/api/gateway.py`: authenticated gateway routes that upsert cloud projections.
- `apps/control-plane/src/dirt_control/models/cloud.py`: SQLModel tables for cloud-side projected state.
- `apps/control-plane/src/dirt_control/api/browser.py`: browser-authenticated hosted API routes consumed by React.
- `scripts/gen-hosted-contract`: regenerates `contracts/hosted-browser-v1.json` and `web-ui/src/api-client/generated/hosted-schema.ts` from the FastAPI app.
- `web-ui/src/api-client/hosted.ts`: typed `openapi-fetch` client for hosted browser routes.
- `web-ui/src/routes/index.tsx`: hosted dashboard route that already fetches current metrics, metric history, devices, assets, and sync status.
- `web-ui/src/ui/RangeSwitch.tsx`, `web-ui/src/ui/Sparkline.tsx`, and `web-ui/src/ui/HoverTimestamp.tsx`: existing UI primitives for range selection and interactive sparklines.

The local plant source of truth is `apps/shared/src/dirt_shared/models/plant.py`. A `Plant` row belongs to a `GrowRun`, `Site`, and `Tent`. Its durable public identifier is `plant_id`, sorted by `display_order`. `moisture_capability_id` points at the local numeric `Capability.id` for that plant's canonical soil-moisture stream. The local public stream identifiers needed by hosted cloud are on `Capability.capability_id`, `Capability.metric_name`, and the owning `Device.device_id`.

The current main-tent plant wiki pages live at `wiki/plants/plant-a.md`, `wiki/plants/plant-b.md`, `wiki/plants/plant-c.md`, and `wiki/plants/plant-d.md`. They contain Markdown frontmatter and body content. The first hosted plant detail route can use the convention `wiki/plants/plant-{plant_id}.md` for main-tent plants, but the cloud contract should carry an explicit nullable `wiki_path` so later plants are not forced into the same filename pattern.

Before implementation, read the documentation required by `AGENTS.md`:

    sed -n '1,220p' docs/commands.md
    sed -n '1,220p' docs/database.md
    sed -n '1,220p' docs/rules/simple-clean-architecture.md
    sed -n '1,220p' docs/rules/boundary-contracts.md
    sed -n '1,220p' docs/references/atlas/INDEX.md
    sed -n '1,220p' docs/references/tanstack-router-v1/INDEX.md
    sed -n '1,220p' docs/references/modern-idiomatic-typescript/INDEX.md
    sed -n '1,220p' docs/references/tailwind-v4/INDEX.md

If implementing wiki projection work, also read:

    sed -n '1,220p' wiki/AGENTS.md
    sed -n '1,220p' docs/epics/hosted-website-control-plane/HostedWikiExecPlan.md


## Plan of Work

Milestone 1 corrects hosted metric stream identity. Extend `LatestMetricItem` and `RollupItem` in `apps/shared/src/dirt_shared/cloud_contract.py` so `device_id` is required for owned metric streams. If a concrete existing non-device metric is found, keep the field required-but-nullable with `Field(...)`, but the local collector should provide a value for every metric coming from `capability -> device`. Update `apps/gateway/src/dirt_gateway/local.py` to group rollups by `Device.device_id` as well as `Capability.capability_id`, and to emit `device_id` on rollups. Add `device_id` to `CloudMetricRollup` in `apps/control-plane/src/dirt_control/models/cloud.py`; update `CloudLatestMetric`, `CloudMetricRollup`, and `CloudCapability` uniqueness/key construction so device-owned capability identifiers are not assumed tent-unique. Update gateway upserts in `apps/control-plane/src/dirt_control/api/gateway.py` and browser history reads in `apps/control-plane/src/dirt_control/api/browser.py`.

Milestone 1 should use a direct cutover. Do not add compatibility wrappers that preserve the old stream key as a second source of truth. Existing hosted rollups that lack `device_id` can remain for dashboard history until they age out, but plant detail queries must require a plant row with a concrete `device_id` and must ignore old rollups where `device_id` is null.

Milestone 2 syncs plant metadata. Add a `CatalogPlant` DTO to `apps/shared/src/dirt_shared/cloud_contract.py` and a `plants: list[CatalogPlant]` field to `CatalogRequest`. The DTO should include `tent_id`, `grow_run_id`, `plant_id`, `name`, `display_order`, nullable `sticker_color`, `status`, `purple`, `moisture_target_low`, `moisture_target_high`, nullable `moisture_device_id`, nullable `moisture_capability_id`, nullable `wiki_path`, and `is_active`. Build these rows in `GatewayLocalServiceBundle.collect_catalog()` by querying the current grow run for each tent and joining `Plant.moisture_capability_id -> Capability -> Device` when present. Add `CloudPlant` to `apps/control-plane/src/dirt_control/models/cloud.py`, keyed by `site_id + tent_id + grow_run_id + plant_id`, and upsert it from the catalog route.

Milestone 3 exposes browser plant APIs from the hosted control plane. Add Pydantic browser response models in `apps/control-plane/src/dirt_control/api/browser.py`, keeping `extra="forbid"` through `BrowserResponse`. Add:

    GET /api/tents/{tent_id}/plants
    GET /api/tents/{tent_id}/plants/{plant_id}
    GET /api/tents/{tent_id}/plants/{plant_id}/moisture/history?range=24h

The list route should return current synced plants for the tent with a boolean such as `has_moisture_stream`. The dashboard should link only rows where that boolean is true. The detail and history routes should return 404 when the plant does not exist, and 404 or 409 when it exists but lacks a moisture stream; choose one behavior and document it in this plan's decision log during implementation. The history route should use the same `METRIC_HISTORY_RANGES` bucket/window mapping as the dashboard and filter by the plant's `moisture_device_id`, `moisture_capability_id`, and `metric='soil_moisture_raw'`.

Milestone 4 makes wiki content available to the plant page. If the full hosted wiki projection from `docs/epics/hosted-website-control-plane/HostedWikiExecPlan.md` is already implemented, consume `CloudWikiPage` by `CloudPlant.wiki_path`. If not, implement the smallest compatible slice of that plan:

- Add `WikiProjectionPage`, `WikiProjectionRequest`, and `WikiProjectionResponse` DTOs to `apps/shared/src/dirt_shared/cloud_contract.py`.
- Add `CloudWikiPage` to `apps/control-plane/src/dirt_control/models/cloud.py` with `site_id`, `path`, `title`, `frontmatter` JSON, `body_markdown`, `sha256`, `source_updated_at`, `synced_at`, `created_at`, and `updated_at`.
- Add `GatewayLocalServiceBundle.collect_wiki_pages(site_id)` that projects only `wiki/plants/*.md` for this milestone, with explicit exclusion of `wiki/AGENTS.md` and any raw/private paths.
- Add `PUT /api/gateway/v1/wiki` and wire the gateway sync event if the general route does not already exist.
- Compose optional wiki content into the hosted plant detail response by joining `CloudPlant.wiki_path` to `CloudWikiPage.path`.

This milestone must not make the hosted wiki an editable CMS. The repository `wiki/` directory remains the source of truth, and the hosted control plane stores a read-only projection.

Milestone 5 builds the React UI. Add a file-based TanStack Router route under `web-ui/src/routes/`, likely `tents.$tentId.plants.$plantId.tsx`, using `createFileRoute("/tents/$tentId/plants/$plantId")`. Use `Route.useParams()` for `tentId` and `plantId`; do not rely on a global plant id because plant identity is scoped to a tent and grow run. Fetch detail and history through `createHostedApiClient()` and generated hosted types from `web-ui/src/api-client/generated/hosted-schema.ts`. Reuse `RangeSwitch`, `Sparkline`, and `HoverTimestamp` rather than creating a second chart system. Add a small dashboard "Plants" section to `web-ui/src/routes/index.tsx` that consumes `GET /api/tents/{tent_id}/plants`, renders moisture-backed plants, and navigates to `/tents/$tentId/plants/$plantId`.

The UI should be direct and operational: identity, current moisture, target band, freshness, range switch, graph, and wiki document content. It should not add marketing copy, decorative cards, or a second nested dashboard. If Markdown rendering needs a library, add a small reusable `MarkdownDocument` component and install a maintained renderer such as `react-markdown`; keep that component reusable by the future hosted `/wiki` route.

Milestone 6 validates, deploys, and records evidence. Run focused unit and integration tests before deployment. Start the local hosted stack with `make dev-up`, log in through the real local browser session, and verify the route with `agent-browser`. Deploy only through `scripts/deploy-control-plane`; do not use ad hoc Railway commands.


## Concrete Steps

Start from the repository root:

    cd /home/akcom/code/dirt

Inspect the current stream data and confirm that plant moisture capabilities are device-scoped:

    rg -n "soil_moisture_raw|moisture_capability_id|CloudMetricRollup|LatestMetricItem|RollupItem" apps migrations cloud/migrations

For any SQL inspection, use the credentials from `.env` without printing secrets:

    set -a; source .env; set +a
    PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt -P pager=off -c "\d plant" -c "\d capability" -c "\d sensorreading"

Implement Milestone 1 files:

    apps/shared/src/dirt_shared/cloud_contract.py
    apps/gateway/src/dirt_gateway/local.py
    apps/gateway/src/dirt_gateway/sync.py
    apps/gateway/src/dirt_gateway/cloud.py
    apps/gateway/src/dirt_gateway/protocols.py
    apps/control-plane/src/dirt_control/models/cloud.py
    apps/control-plane/src/dirt_control/api/gateway.py
    apps/control-plane/src/dirt_control/api/browser.py
    cloud/migrations/

Generate the cloud migration using the repo's Atlas workflow, then review it:

    atlas migrate diff hosted_metric_stream_identity --env cloud
    atlas migrate hash --env cloud
    atlas migrate apply --env cloud --dry-run

If `--env cloud` is not configured for local dry-runs in the current worktree, inspect `atlas.hcl` and follow the hosted-control-plane plan's migration pattern. Do not hand-apply DDL from app code.

Add plant projection and browser routes:

    apps/shared/src/dirt_shared/cloud_contract.py
    apps/gateway/src/dirt_gateway/local.py
    apps/control-plane/src/dirt_control/models/cloud.py
    apps/control-plane/src/dirt_control/api/gateway.py
    apps/control-plane/src/dirt_control/api/browser.py
    apps/control-plane/tests/test_api.py
    apps/gateway/tests/test_sync.py
    apps/shared/tests/test_cloud_contract.py

Regenerate hosted browser contracts after every browser API shape change:

    scripts/gen-hosted-contract

Build frontend route and dashboard link:

    web-ui/src/routes/index.tsx
    web-ui/src/routes/tents.$tentId.plants.$plantId.tsx
    web-ui/src/ui/RangeSwitch.tsx
    web-ui/src/ui/Sparkline.tsx
    web-ui/src/ui/HoverTimestamp.tsx
    web-ui/src/ui/MarkdownDocument.tsx
    web-ui/src/ui/TopBar.tsx

Only edit shared UI primitives when a real reuse gap exists. Otherwise consume them unchanged from the new route.

Run focused validation while implementing:

    uv run pytest apps/shared/tests/test_cloud_contract.py -q
    uv run pytest apps/gateway/tests/test_sync.py apps/gateway/tests/test_gateway_boundary_guardrails.py -q
    uv run pytest apps/control-plane/tests -q
    uv run pytest apps/tests/invariants -q
    scripts/gen-hosted-contract
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test
    pnpm --dir web-ui build

Run the local hosted stack for browser verification:

    make dev-up
    make dev-status

Use the Web URL from `make dev-status`, log in as `dev-admin` / `dev-password`, and use `agent-browser` to verify dashboard plant links and `/tents/main/plants/a`.

Before committing implementation work:

    make fix
    git status --short
    git add <changed-files>
    git commit -m "feat: add hosted plant detail page"

Deploy only after local validation is complete and the user is ready for a hosted rollout:

    scripts/deploy-control-plane


## Validation and Acceptance

Backend acceptance:

- `CatalogRequest` validates plant rows with required nullable fields and rejects unknown keys.
- Gateway catalog sync upserts `CloudPlant` rows for current grow-run plants and records `moisture_device_id + moisture_capability_id` for main-tent A-D.
- Latest metrics and rollups keep separate rows for Plant A, Plant B, Plant C, and Plant D even though their public `capability_id` values are all `soil_moisture_raw`.
- `GET /api/tents/main/plants` requires browser auth and returns main-tent plants ordered by `display_order`.
- Plants with no moisture stream are returned with `has_moisture_stream=false` or omitted only if the route contract explicitly says it is a moisture-backed list. Do not leave this ambiguous.
- `GET /api/tents/main/plants/a` requires browser auth and returns plant metadata, latest moisture if available, target bounds, freshness, and optional wiki content.
- `GET /api/tents/main/plants/a/moisture/history?range=24h` returns only Plant A soil-moisture buckets, not a tent-wide aggregate of every plant node.
- Invalid ranges return 400, missing plants return 404, and unauthenticated browser calls return 401.

Frontend acceptance:

- The hosted dashboard shows a compact Plants section for the selected tent when moisture-backed plant rows exist.
- Clicking Plant A navigates to `/tents/main/plants/a` and renders without a full page reload.
- The detail page has a range switch with the same allowed ranges as the dashboard.
- Hovering the moisture sparkline shows the crosshair and timestamp/value behavior expected from the existing `Sparkline` component.
- Wiki content from `wiki/plants/plant-a.md` is visible on the page when the projection exists; the page still renders a useful metadata and graph view if the wiki page is missing.
- A plant without a moisture stream is not linked from the dashboard and does not show an empty graph page.
- The page works at desktop and mobile widths without overlapping text, clipped buttons, or chart layout shifts.

Deployment acceptance:

- `scripts/deploy-control-plane` completes successfully.
- After one normal gateway sync cycle, authenticated hosted `/api/tents/main/plants` returns the expected plant rows.
- Authenticated hosted `/tents/main/plants/a` loads in the browser and shows a Plant A moisture trend and wiki content.
- Unauthenticated hosted plant API calls return 401.


## Idempotence and Recovery

`scripts/gen-hosted-contract` is safe to repeat and should be the only way to update `contracts/hosted-browser-v1.json` and `web-ui/src/api-client/generated/hosted-schema.ts`.

Gateway projection syncs must be idempotent. Re-sending the same catalog, latest metrics, rollups, plants, and wiki pages should update existing cloud rows rather than duplicating them.

Cloud migrations must be reviewed before apply. If a cloud migration changes uniqueness on metric tables, write it so existing dashboard data is preserved when possible, but do not keep an old uniqueness path that continues to collapse per-plant streams. If old plant rollups cannot be reconstructed because `device_id` was not stored, let new gateway rollups repopulate plant history after deployment and record that in `Outcomes & Retrospective`.

If frontend generated types drift unexpectedly, inspect `apps/control-plane/src/dirt_control/api/browser.py` response models first. Do not patch `web-ui/src/api-client/generated/hosted-schema.ts` by hand.

If the local hosted stack is already running, use `make dev-status` to get its URL and avoid starting a duplicate. If it is unhealthy, use `make dev-down` followed by `make dev-up`.

If `make fix` or pre-commit hooks modify generated or formatted files, re-add the modified files and retry the commit. Do not use `--no-verify`.


## Artifacts and Notes

Initial repository inspection for this plan found these relevant facts:

- `web-ui/src/routes/index.tsx` already owns the hosted dashboard and the current dashboard history graph implementation.
- `web-ui/src/ui/RangeSwitch.tsx` defines the existing `SparklineRange` union: `1h`, `24h`, `7d`, `30d`, and `90d`.
- `apps/control-plane/src/dirt_control/api/browser.py` defines `METRIC_HISTORY_RANGES` with the same range labels and bucket windows.
- `apps/shared/src/dirt_shared/models/plant.py` is already scoped to grow runs and has nullable `moisture_capability_id`.
- `migrations/20260504000618_multi_tent_controller.sql` seeds `plant-a-node` through `plant-d-node` with the same public `capability_id='soil_moisture_raw'`, confirming that hosted stream identity must include `device_id`.
- `web-ui/package.json` currently has no Markdown rendering dependency. Add one only if implementing rendered Markdown in the plant page; otherwise keep the first version's wiki section plain but readable and record the tradeoff here.

Update this section with command excerpts, API response snippets, browser screenshots, and deployment URLs as implementation proceeds.


## Interfaces and Dependencies

New or changed shared cloud contracts:

- `CatalogRequest.plants: list[CatalogPlant]`
- `CatalogPlant`
- `LatestMetricItem.device_id`
- `RollupItem.device_id`
- Optional wiki projection DTOs if not already implemented by the hosted wiki plan: `WikiProjectionPage`, `WikiProjectionRequest`, `WikiProjectionResponse`

New or changed cloud tables:

- `CloudPlant`
- `CloudMetricRollup.device_id`
- Updated uniqueness/key construction for `CloudCapability`, `CloudLatestMetric`, and `CloudMetricRollup`
- `CloudWikiPage` if the hosted wiki projection is not already present

New or changed gateway routes:

- Existing `PUT /api/gateway/v1/catalog` accepts and upserts plant rows.
- Existing `POST /api/gateway/v1/metrics/latest` stores device-scoped metric rows.
- Existing `POST /api/gateway/v1/metrics/rollups` stores device-scoped rollups.
- Optional `PUT /api/gateway/v1/wiki` if the hosted wiki projection is implemented here.

New browser routes:

- `GET /api/tents/{tent_id}/plants`
- `GET /api/tents/{tent_id}/plants/{plant_id}`
- `GET /api/tents/{tent_id}/plants/{plant_id}/moisture/history`

New or changed frontend files:

- `web-ui/src/routes/tents.$tentId.plants.$plantId.tsx`
- `web-ui/src/routes/index.tsx`
- `web-ui/src/ui/MarkdownDocument.tsx` if Markdown rendering is added
- `web-ui/src/api-client/generated/hosted-schema.ts` generated by `scripts/gen-hosted-contract`
- `web-ui/src/routeTree.gen.ts` may be regenerated by the TanStack Router plugin; never hand-edit it.

External dependencies:

- PostgreSQL 17 through existing local and Railway databases.
- Atlas for schema migrations.
- `@tanstack/react-router` v1 file-based routing.
- TanStack Query through `@tanstack/react-query`.
- Optional Markdown renderer such as `react-markdown` if selected during implementation.


## Revision Notes

- 2026-05-28 / Codex: Initial plan created. The plan explicitly includes hosted metric stream identity correction because plant moisture nodes share the same public capability id and cannot be graphed correctly until rollups are device-scoped.
