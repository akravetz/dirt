# Breeding Logbook API Wire-Up

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, the Breeding Logbook at `/breeding-logbook` uses real hosted browser APIs instead of deterministic frontend mock data. An operator can review plants, seed lots, lineage, notes, events, and plant environment history from the synced cloud projection, then submit breeding logbook changes from the hosted UI. Those writes are not direct hosted database edits. The local Dirt system remains the durable source of truth for breeding records, while the hosted control plane accepts typed browser intents, queues typed cloud commands, the gateway claims and applies those commands locally, and the next sync refreshes the cloud projection.

The user-visible result is a Breeding Logbook that is useful with real data and honest about pending writes. Read views should show synced notes/events and lineage instead of mock placeholders. Write actions should show a pending marker immediately, but canonical plant and seed-lot facts should only change after local execution succeeds and the synced projection catches up. Text notes may appear as visually distinct pending notes in the local UI while awaiting sync.

This plan covers both read APIs and write APIs. It deliberately defers plant wiki content and photo attachments. The existing backend DTO contains `wiki_content`, but the current frontend does not render it. The current UI has an `Attach photo` button, but durable photo notes would require asset upload, local attachment persistence, cloud attachment projection, signed reads, and retention decisions; that work should be handled in a later focused plan.


## Progress

- [x] (2026-06-18) Reviewed `docs/epics/breeding-logbook-ui/api-audit.md`, current Breeding Logbook frontend mock queries and mock write helpers, hosted browser read DTOs/routes, gateway sync contracts, local breeding models, command claim/result flow, `.agents/PLANS.md`, and the relevant repository rules.
- [x] (2026-06-18) Resolved product decisions with the operator: close read projection gaps except wiki content, implement lineage/offspring summaries, use breeding-specific browser endpoints, make bulk sex first-class, make grid position nullable and send null from the UI, generate plant labels locally, require cull reason, defer photo attachments, and use conservative hybrid pending-write UX.
- [x] (2026-06-18) Drafted this ExecPlan.
- [x] (2026-06-18) Implemented Milestone 1: repaired and extended read projection contracts for all seed lots, cross events, plant notes, plant events, nullable grid positions, and cloud projection ingestion.
- [x] (2026-06-18) Implemented Milestone 2: exposed completed read endpoints and switched frontend query hooks from mock data to generated hosted API calls.
- [x] (2026-06-18) Implemented Milestone 3: added typed breeding command DTOs and breeding-specific browser write endpoints.
- [x] (2026-06-18) Implemented Milestone 4: taught the gateway to execute breeding commands against the local database and report command results.
- [x] (2026-06-18) Implemented Milestone 5: wired frontend mutations, pending markers, command polling, and projection refresh.
- [x] (2026-06-18) Implemented Milestone 6: validated end to end with tests, generated contracts, and local hosted browser flows.


## Surprises & Discoveries

- Observation: `api-audit.md` documented read routes and deferred mutation endpoints, but it intentionally did not design the durable command/sync path for writes.
  Evidence: The document states that durable writes need command DTOs, idempotency, local validation, gateway claim/result handling, and pending/failed behavior before mutation endpoints should exist.

- Observation: The new frontend still imports mock data directly and implements seven cache-local write paths.
  Evidence: `web-ui/src/features/breeding-logbook/breedingLogbookQueries.ts` imports `BREEDING_LOGBOOK_*` from `breedingLogbook.mockData.ts` and exports `applyMockBulkSex`, `applyMockBulkMove`, `applyMockBulkCull`, `applyMockAddSeedLot`, `applyMockSowPlants`, `applyMockTakeClones`, and `applyMockLogNote`.

- Observation: The current frontend uses `lineage.offspring`, but does not use `wiki_content`.
  Evidence: `web-ui/src/features/breeding-logbook/BreedingLogbookPage.tsx` renders `detail.lineage.offspring` in the detail panel. `web-ui/src/features/breeding-logbook/breedingLogbookTypes.ts` has no wiki content field.

- Observation: The current gateway catalog projection does not sync cross events, plant notes, or plant events.
  Evidence: `apps/shared/src/dirt_shared/cloud_contract.py` defines `CatalogRequest` with plants, plant locations, seed lots, and plant metric streams, but no cross-event, plant-note, or plant-event lists.

- Observation: Seed-lot projection currently misses seed lots with no current plants.
  Evidence: `apps/gateway/src/dirt_gateway/local.py` collects seed lots by joining `SeedLot` through `Plant` and current `PlantLocationHistory`. The browser seed-lot endpoint can return cloud seed lots with no current plants only after those lots are actually projected.

- Observation: Browser command creation is intentionally PTZ-only today.
  Evidence: `apps/control-plane/src/dirt_control/api/browser.py` defines `CommandCreateRequest` with `device_id: Literal["obsbot-main"]`, `capability_id: Literal["ptz_move"]`, and PTZ command types. `apps/control-plane/tests/test_api.py::test_command_creation_rejects_non_ptz_remote_control` enforces this safety boundary.

- Observation: Gateway command execution is also PTZ-only today.
  Evidence: `apps/gateway/src/dirt_gateway/commands.py` validates PTZ targets and dispatches only `PtzPresetPayload`, `PtzLookPayload`, `PtzZoomAbsolutePayload`, and `PtzZoomRelativePayload`.

- Observation: `PlantLocationHistory.grid_position` is currently required locally and in cloud contracts.
  Evidence: `apps/shared/src/dirt_shared/models/plant.py` has `grid_position: str` with a nonblank check, and `CatalogPlantLocation.grid_position` is `str`.

- Observation: The working tree had unrelated modified wiki and grow-state files before this plan was written.
  Evidence: `git status --short` showed modified files under `docs/grow-state.md` and `wiki/`. This plan does not depend on or alter those files.

- Observation: Local Atlas migration generation still needs the known `btree_gist` workaround for SQLModel exclusion constraints.
  Evidence: `atlas migrate diff breeding_logbook_nullable_grid_and_timeline --env local` failed because the default desired-state dev database lacked the `btree_gist` operator class. The migration was generated with the documented disposable Postgres dev URL after `CREATE EXTENSION IF NOT EXISTS btree_gist;`.


## Decision Log

- Decision: Close the known read projection gaps before cutting the frontend from mocks to real APIs.
  Rationale: Wiring the UI to lossy read routes would replace mock fidelity with missing real data. The first real read integration should include seed lots with no current plants, journal notes/events, and lineage/offspring summaries.
  Date/Author: 2026-06-18 / Operator

- Decision: Defer plant wiki content.
  Rationale: The backend DTO currently has `wiki_content`, but the new Breeding Logbook frontend does not render it. Adding a visible wiki panel and mapping plant wiki pages is separate product work.
  Date/Author: 2026-06-18 / Operator

- Decision: Defer note photo attachments.
  Rationale: Durable photos require a larger asset workflow: browser upload, local note attachment storage, cloud projection, signed read URLs, and retention behavior. Text notes are enough for the first write integration.
  Date/Author: 2026-06-18 / Operator

- Decision: Use breeding-specific browser endpoints for writes instead of widening generic `/api/commands`.
  Rationale: Breeding-specific routes keep frontend requests screen-shaped and validation explicit while preserving the existing PTZ command safety boundary. The routes may enqueue cloud commands internally, but the browser should not construct low-level gateway payloads.
  Date/Author: 2026-06-18 / Operator

- Decision: Make `POST /api/breeding-logbook/plants:bulk-sex` a first-class mutation endpoint.
  Rationale: Bulk sex update is a visible UI action and should be atomic from the operator's perspective instead of N per-plant calls.
  Date/Author: 2026-06-18 / Operator

- Decision: Make plant location `grid_position` nullable and have the Breeding Logbook UI send `null` for now.
  Rationale: The UI does not yet manage exact grid placement. Requiring fake grid positions would create misleading data. Nullable grid positions truthfully represent "in this tent/location, exact grid slot unspecified."
  Date/Author: 2026-06-18 / Operator

- Decision: Generate new plant keys and names locally.
  Rationale: `plant.key` is the durable tag identifier. The local source of truth should own canonical suffix allocation and uniqueness, while the UI can show a read-only prefix preview.
  Date/Author: 2026-06-18 / Operator

- Decision: Require cull reason in the frontend and backend DTO.
  Rationale: The local database requires a nonblank `culled_reason` when `culled_at` is set, and a real operator reason is better than a generic default.
  Date/Author: 2026-06-18 / Operator

- Decision: Use hybrid pending-write UX.
  Rationale: The UI should acknowledge submitted actions immediately, but canonical facts should remain synced facts. Show pending operation markers and disable or label affected controls while waiting; do not mutate plant/seed-lot records as if the command already succeeded. Text notes may appear as pending timeline entries, visually distinct from synced notes.
  Date/Author: 2026-06-18 / Operator


## Outcomes & Retrospective

Milestone 1 completed on 2026-06-18. The shared gateway catalog DTO now carries required nullable plant location grid positions plus cross-event, plant-note, and plant-event lists/counts. Local plant locations allow null grid positions while preserving current/non-overlapping non-null slot safety. The gateway now projects all local seed lots, cross events, plant notes, and plant events, and hosted gateway ingestion upserts matching cloud projection rows with stable `(site_id, source_*_id)` uniqueness.

Validation passed:

- `uv run pytest apps/shared/tests/test_cloud_contract.py -q`
- `uv run pytest apps/gateway/tests/test_sync.py apps/gateway/tests/test_gateway_boundary_guardrails.py -q`
- `uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q`
- `uv run ruff check apps/shared/src/dirt_shared/cloud_contract.py apps/shared/src/dirt_shared/models/plant.py apps/gateway/src/dirt_gateway/local.py apps/control-plane/src/dirt_control/models/cloud.py apps/control-plane/src/dirt_control/models/__init__.py apps/control-plane/src/dirt_control/api/gateway.py apps/shared/tests/test_cloud_contract.py apps/gateway/tests/test_sync.py apps/control-plane/tests/test_api.py`
- `atlas migrate hash --env local`
- `atlas migrate hash --env cloud`
- `set -a; source .env; set +a; atlas migrate apply --env local --dry-run`

The local migration diff used the documented external disposable dev database workaround for `btree_gist`: `atlas migrate diff breeding_logbook_nullable_grid_and_timeline --env local --dev-url "postgres://postgres:dev@127.0.0.1:55433/dev?sslmode=disable&search_path=public"` after creating the extension in that disposable database. The default bare local diff command still hits the known Atlas desired-state extension limitation.

Milestone 2 completed on 2026-06-18. Hosted breeding logbook read routes now render nullable grid locations without `None`/`null`, derive plant row `last_note` from projected notes/events/reasons, return merged note/event timelines, keep `wiki_content` deferred/null, and build cross-backed parent and offspring summaries from projected cross/seed-lot/plant rows. Hosted plant/current-location browser DTOs were also made nullable for `grid_position` so Milestone 1 projection rows do not break non-logbook plant reads.

The frontend Breeding Logbook read hooks now call the generated hosted API client for bootstrap, plants, seed lots, plant detail by `plant.key`, and plant metric history. Snake_case hosted responses are mapped locally in `breedingLogbookQueries.ts` to the existing camelCase view model. Runtime read queries no longer import `breedingLogbook.mockData.ts`; temporary mock write helpers remain cache-local until write milestones replace them.

Validation passed:

- `uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q`
- `DIRT_CLOUD_ASSET_STORE=local scripts/gen-hosted-contract`
- `pnpm --dir web-ui typecheck`
- `pnpm --dir web-ui lint`
- `pnpm --dir web-ui test`
- `uv run ruff check apps/control-plane/src/dirt_control/api/browser.py apps/control-plane/tests/test_api.py`

Simplify pass used the sequential fallback because this runtime did not expose a subagent-spawn tool. The pass kept the read cutover direct and changed metric-history mapping to omit null-only buckets instead of inventing zero values.

Milestone 3 completed on 2026-06-18. The shared cloud contract now includes typed breeding command payload DTOs, breeding command types, and command-claim validation that rejects mismatched command type/payload pairs. Hosted browser write routes now exist for seed-lot creation, germination, cloning, bulk sex, bulk move, bulk cull, and plant note creation. Each route requires browser auth, accepts an `idempotency_key`, validates obvious cloud projection inputs, enqueues a typed `CloudCommand` with nullable device/capability fields, and returns the existing pollable `CommandResponse`. Generic `/api/commands` remains PTZ-only.

Validation passed:

- `uv run pytest apps/shared/tests/test_cloud_contract.py -q`
- `uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q`
- `DIRT_CLOUD_ASSET_STORE=local scripts/gen-hosted-contract`
- `uv run ruff check apps/shared/src/dirt_shared/cloud_contract.py apps/control-plane/src/dirt_control/api/browser.py apps/shared/tests/test_cloud_contract.py apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py`

No cloud migration was added for Milestone 3. `CloudCommand.device_id` and `CloudCommand.capability_id` were already nullable; `CloudCommand.tent_id` remains non-null, with `"breeding-logbook"` used only as a command-target label for site-wide breeding commands.

Milestone 4 completed on 2026-06-18. The gateway command orchestrator now branches validation and execution by command family: PTZ commands retain existing device/capability/preset validation and PTZ execution, while breeding commands reject PTZ hardware targets and execute through `BreedingCommandExecutor`. Local `CommandService` ledger rows still use `cloud-command:{command_id}` idempotency keys and now store local breeding command types such as `breeding.seed_lot.create`, `breeding.plants.germinate`, and `breeding.plant_note.create`.

The breeding executor applies each claimed command in a single local DB transaction. It resolves local site/tent identities before writing location rows, creates/reuses plant lines for purchased and cross seed lots, creates cross events and seed lots, generates deterministic local plant/clone keys from line or mother prefixes while skipping occupied suffixes, writes nullable-grid current locations, updates sex/move/cull facts, closes current locations on move/cull, and creates plant notes/events. Clone-taken events are attached to the mother plant with clone keys in event metadata. Move-to-flower lifecycle handling is explicit: moving into a flower tent sets `flower_started_at` only when it was previously null.

Validation passed:

- `uv run pytest apps/gateway/tests/test_sync.py -q`
- `uv run pytest apps/gateway/tests/test_sync.py apps/gateway/tests/test_gateway_boundary_guardrails.py -q`
- `uv run pytest apps/gateway/tests/test_gateway_boundary_guardrails.py -q`
- `uv run pytest apps/shared/tests/test_cloud_contract.py -q`
- `uv run ruff format apps/gateway/src/dirt_gateway/breeding_commands.py apps/gateway/src/dirt_gateway/commands.py apps/gateway/src/dirt_gateway/main.py apps/gateway/tests/test_sync.py`
- `uv run ruff check apps/gateway/src/dirt_gateway/breeding_commands.py apps/gateway/src/dirt_gateway/commands.py apps/gateway/src/dirt_gateway/main.py apps/gateway/tests/test_sync.py`
- `git diff --check -- apps/gateway/src/dirt_gateway/breeding_commands.py apps/gateway/src/dirt_gateway/commands.py apps/gateway/src/dirt_gateway/main.py apps/gateway/tests/test_sync.py docs/epics/breeding-logbook-ui/api-wireup-ExecPlan.md`

Simplify pass used the sequential fallback because this runtime did not expose a subagent-spawn tool. The pass kept the executor direct, made tent stage-role checks tolerant of labels such as `flowering`, and replaced test-only `type: ignore` query calls with SQLModel `col()` helpers.

Milestone 5 completed on 2026-06-18. The frontend now submits breeding-logbook writes through generated hosted API types instead of cache-local mock helpers. Add Seeds, Germinate, Clone, Bulk Sex, Bulk Move, Bulk Cull, and Log Note all build typed request bodies with per-action idempotency keys. Germinate, Clone, and Bulk Move send explicit `grid_position: null` at the generated-schema boundary while using an `openapi-fetch` body serializer workaround so the actual JSON preserves required null fields.

Pending commands live in React Query cache, are polled through `GET /api/commands/{command_id}`, and schedule bounded projection refreshes after terminal success. Affected plant rows show pending/failed markers, destructive actions are blocked while active commands affect selected plants, canonical plant facts remain unchanged until projection refresh, and note commands render distinct pending timeline entries until the synced note appears or an error is shown. The obsolete runtime mock data file was deleted during invariant cleanup.

Validation passed:

- `DIRT_CLOUD_ASSET_STORE=local scripts/gen-hosted-contract`
- `uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q`
- `pnpm --dir web-ui typecheck`
- `pnpm --dir web-ui lint`
- `pnpm --dir web-ui test`
- `uv run pytest apps/tests/invariants -q`
- `git diff --check`

Milestone 6 completed on 2026-06-18. Full relevant automated validation passed, including shared cloud-contract tests, gateway sync/guardrail tests, control-plane API/guardrail tests, TypeScript typecheck/lint/tests, and human-owned invariants.

Local browser validation used `agent-browser` against `http://192.168.1.79:5171/breeding-logbook` with `dev-admin` / `dev-password`. The normal `make dev-up` harness intentionally sets `DIRT_CLOUD_GATEWAY_COMMAND_CLAIM_ENABLED=false`, so the write-path validation restarted the local control-plane API with command claiming enabled, ran Vite with `VITE_DIRT_API_BASE_URL=http://192.168.1.79:8021`, and ran a local gateway pointed at the same API. The source data for the browser run came from an isolated temporary Postgres database, `dirt_e2e_breeding_logbook`, migrated with local Atlas migrations and seeded with projected breeding rows.

Browser evidence:

- Plants table rendered real projected rows, including a seed lot with no current plants and nullable-grid labels that render as tent/location names instead of fake slots.
- Plant detail for `DBG-F1-001` showed real projected notes/events, lineage parents, offspring fallback, disabled photo attachment, and plant metric stream UI.
- A browser-submitted text note showed as a distinct pending timeline note, then gateway execution succeeded and the synced plant row `last_note` updated to `E2E note from browser validation`.
- A browser-submitted Bulk Sex command showed queued command summary plus a row pending marker without optimistic fact changes, then gateway execution and projection refresh updated `DBG-F1-001` to female.


## Context and Orientation

Dirt has a hosted control plane and frontend, but the local system owns durable breeding records. Local durable records live in `apps/shared/src/dirt_shared/models/plant.py`: `PlantLine`, `CrossEvent`, `SeedLot`, `Plant`, `PlantLocationHistory`, `PlantNote`, `PlantEvent`, and `PlantMetricStream`. The gateway reads those local rows in `apps/gateway/src/dirt_gateway/local.py`, validates them through Pydantic DTOs in `apps/shared/src/dirt_shared/cloud_contract.py`, and syncs them to hosted cloud tables through `apps/control-plane/src/dirt_control/api/gateway.py`.

Hosted browser read DTOs and routes live in `apps/control-plane/src/dirt_control/api/browser.py`. Generated OpenAPI output is written by `scripts/gen-hosted-contract` into `contracts/hosted-browser-v1.json` and `web-ui/src/api-client/generated/hosted-schema.ts`. The frontend should consume generated hosted types and the existing API-client patterns, not handwritten cloud response interfaces.

The existing Breeding Logbook frontend lives in `web-ui/src/features/breeding-logbook/`:

- `BreedingLogbookPage.tsx` renders table, board, bulk toolbar, Add seeds, Add plants, detail journal, and pending future controls.
- `breedingLogbookTypes.ts` defines frontend-facing types that currently mirror mock data.
- `breedingLogbookQueries.ts` currently returns mock data and mutates the React Query cache with mock helper functions.
- `breedingLogbook.mockData.ts` is the temporary deterministic fixture source.

Current read routes exist under `/api/breeding-logbook/...`:

- `GET /api/breeding-logbook/bootstrap`
- `GET /api/breeding-logbook/plants?include_culled=false&group_by=stage`
- `GET /api/breeding-logbook/seed-lots`
- `GET /api/breeding-logbook/plants/{plant_key}`
- `GET /api/breeding-logbook/plants/{plant_key}/metrics/history?range=24h`

Those routes are not enough yet. The current implementation uses static lookups, has empty `events`, has placeholder `offspring`, has `wiki_content=null`, and only sees seed lots that the gateway projected. This plan keeps `wiki_content` deferred, but it must implement real notes/events and lineage/offspring summaries.

The existing cloud command infrastructure uses `CloudCommand` rows in `apps/control-plane/src/dirt_control/models/cloud.py`, browser `/api/commands` routes in `browser.py`, gateway claim/result routes in `apps/control-plane/src/dirt_control/api/gateway.py`, shared command DTOs in `cloud_contract.py`, and gateway execution in `apps/gateway/src/dirt_gateway/commands.py`. Today this path is PTZ-only by design. Breeding writes should reuse the command ledger, claim/result lifecycle, idempotency, and audit concepts, but through new breeding-specific browser endpoints and typed breeding command payloads.

Required documents before implementation:

- `docs/commands.md` before running commands.
- `docs/database.md`, `docs/rules/data-modeling.md`, and `docs/references/atlas/INDEX.md` before editing SQLModel models, migrations, or Atlas files.
- `docs/rules/boundary-contracts.md` before editing browser, gateway, command, outbox, or generated-client payloads.
- `docs/rules/simple-clean-architecture.md` before choosing abstractions or compatibility.
- `docs/references/tanstack-router-v1/INDEX.md`, `docs/references/modern-idiomatic-typescript/INDEX.md`, and `docs/references/tailwind-v4/INDEX.md` before frontend changes.


## Plan of Work

### Milestone 1: Complete Read Projection Contracts

After this milestone, the hosted cloud projection contains all non-wiki facts the Breeding Logbook read API needs: all seed lots, current locations with nullable grid positions, cross events for lineage, plant notes, and plant events.

Edit `apps/shared/src/dirt_shared/cloud_contract.py`:

- Change `CatalogPlantLocation.grid_position` from `str` to required nullable `str | None = Field(...)`.
- Add `CatalogCrossEvent`:
  - `source_cross_event_id: int`
  - `resulting_line_source_id: int`
  - `seed_parent_source_plant_id: int`
  - `pollen_parent_source_plant_id: int`
  - `pollinated_at: datetime`
  - `pollen_parent_is_reversed: bool | None = Field(...)`
  - `notes: str | None = Field(...)`
- Add `CatalogPlantNote`:
  - `source_note_id: int`
  - `source_plant_id: int`
  - `observed_at: datetime`
  - `body: str`
  - `created_by: str | None = Field(...)`
- Add `CatalogPlantEvent`:
  - `source_event_id: int`
  - `source_plant_id: int`
  - the seven boolean kind fields from `PlantEvent`
  - `occurred_at: datetime`
  - `reason: str | None = Field(...)`
  - `notes: str | None = Field(...)`
  - `metadata: dict[str, Any]`
- Add `cross_events`, `plant_notes`, and `plant_events` lists to `CatalogRequest`.
- Add `cross_events`, `plant_notes`, and `plant_events` counts to `CatalogResponse`.

Edit local storage and schema:

- In `apps/shared/src/dirt_shared/models/plant.py`, change `PlantLocationHistory.grid_position` to nullable.
- Replace the nonblank check with a nullable-safe check: `grid_position IS NULL OR btrim(grid_position) <> ''`.
- Adjust unique and exclusion constraints so a tent may contain multiple current rows with `grid_position IS NULL`, while non-null grid positions remain unique and non-overlapping. The current `ux_plant_location_current_grid_position_per_tent` and `ex_plant_location_no_overlap_per_tent_grid_position` cannot keep treating null as an exact slot.
- Generate an Atlas migration under `migrations/` for the nullable grid-position change.

Edit cloud storage:

- Add `CloudCrossEvent`, `CloudPlantNote`, and `CloudPlantEvent` table models in `apps/control-plane/src/dirt_control/models/cloud.py`.
- Change `CloudPlantLocation.grid_position` to nullable and add the matching cloud migration under `cloud/migrations/`.
- Use stable uniqueness:
  - cross events: `(site_id, source_cross_event_id)`
  - plant notes: `(site_id, source_note_id)`
  - plant events: `(site_id, source_event_id)`

Edit gateway collection in `apps/gateway/src/dirt_gateway/local.py`:

- Change seed-lot collection so it collects all local `SeedLot` rows for the configured site context, not only lots joined through current plants.
- Add `_collect_cross_events`, `_collect_plant_notes`, and `_collect_plant_events`.
- Include those lists in `CatalogRequest`.
- Preserve required nullable fields explicitly; do not omit null keys.

Edit hosted gateway ingestion in `apps/control-plane/src/dirt_control/api/gateway.py`:

- Upsert `CloudCrossEvent`, `CloudPlantNote`, and `CloudPlantEvent` from the new catalog lists.
- Upsert nullable plant location `grid_position`.
- Include the new counts in `CatalogResponse`.
- Keep DTO validation at the boundary. Do not accept or store raw dictionaries for owned payloads without validating into Pydantic models first.

Tests for this milestone:

- Update `apps/shared/tests/test_cloud_contract.py` to require the new DTO fields, including required nullable fields.
- Update `apps/gateway/tests/test_sync.py` so a seed lot without current plants is projected.
- Add gateway sync tests for notes/events/cross-events projection.
- Update `apps/control-plane/tests/test_api.py` for catalog upsert of notes/events/cross-events and nullable grid positions.
- Update boundary guardrail tests if response model coverage changes.

### Milestone 2: Complete Read Browser APIs and Frontend Read Cutover

After this milestone, `/breeding-logbook` loads from real hosted read APIs and no longer imports `breedingLogbook.mockData.ts` for normal runtime reads.

Edit `apps/control-plane/src/dirt_control/api/browser.py`:

- Keep `BreedingLogbookBootstrapResponse`, `BreedingLogbookPlantListResponse`, `BreedingLogbookSeedLotListResponse`, `BreedingLogbookPlantDetailResponse`, and `PlantMetricHistoryResponse`.
- Add any missing response fields needed by the current UI, but do not add wiki-specific UI fields yet.
- Make `BreedingLogbookLocationOptionResponse.grid_position` required nullable.
- Make plant row `location_label` handle nullable grid positions. Use the tent name/id when there is no grid slot instead of rendering `"None"`.
- Populate `last_note` from latest `CloudPlantNote.body`, falling back to latest meaningful event text, then cull/selection reason.
- Populate `events` by merging `CloudPlantNote` and `CloudPlantEvent` rows for the detail plant, ordered newest first.
- Map event tags:
  - notes -> `note`
  - sex observations -> `sex`
  - transplant/selection/cull-related lifecycle events -> `stage`
  - seed production/cross events -> `cross`
  - clone taken -> `germ` or add a frontend/backend tag if the UI needs distinct clone display. Prefer extending the tag union only if it improves the visible timeline.
- Populate `lineage.parents` from cross-event parents when the plant's source seed lot was produced by a projected cross event; otherwise fall back to the existing line label.
- Populate `lineage.offspring` from projected cross events where this plant is either parent. Summarize produced seed lots and descended plant counts. Use `"No offspring logged"` when none exist.
- Keep `wiki_content=None` or remove it only if the generated contract and frontend are cut over together. Do not add a new wiki panel in this plan.

Edit frontend API code:

- Find the existing hosted API-client pattern in `web-ui/src/api-client/` and follow it.
- Regenerate hosted contract with `scripts/gen-hosted-contract`.
- Replace mock fetch functions in `web-ui/src/features/breeding-logbook/breedingLogbookQueries.ts` with real calls to:
  - `GET /api/breeding-logbook/bootstrap`
  - `GET /api/breeding-logbook/plants`
  - `GET /api/breeding-logbook/seed-lots`
  - `GET /api/breeding-logbook/plants/{plant_key}`
  - `GET /api/breeding-logbook/plants/{plant_key}/metrics/history`
- Add mapping functions from generated snake_case hosted responses to the existing frontend camelCase view model, or convert the feature to generated response shapes if that is simpler. Keep the mapping local to the feature or API-client layer; do not scatter snake/camel conversion through components.
- Change detail state and query keys to address plants by `plant.key` for API calls. The UI may keep `id` for React keys and selection if useful, but browser routes must request by `plant.key`.
- Remove or quarantine `breedingLogbook.mockData.ts` so it is not used by runtime query functions. If tests still need deterministic data, keep it test-only with a name that cannot be mistaken for production data.

Tests for this milestone:

- Update control-plane tests so read routes return real notes/events/lineage.
- Update frontend tests to mock the hosted API client or query functions through a test seam, not MSW.
- Run typecheck and lint to ensure generated hosted schema and frontend mapping agree.

### Milestone 3: Browser Write Endpoints and Typed Breeding Commands

After this milestone, the hosted control plane exposes breeding-specific browser write endpoints. Each endpoint validates a screen-shaped Pydantic request, enqueues a typed `CloudCommand`, and returns a command envelope the frontend can poll.

Do not expand the generic `/api/commands` browser endpoint to accept arbitrary breeding payloads. Keep PTZ safety tests intact.

Edit `apps/shared/src/dirt_shared/cloud_contract.py`:

- Expand `CommandType` to include breeding command types:
  - `breeding_seed_lot_create`
  - `breeding_plants_germinate`
  - `breeding_plants_clone`
  - `breeding_plants_bulk_sex`
  - `breeding_plants_bulk_move`
  - `breeding_plants_bulk_cull`
  - `breeding_plant_note_create`
- Add typed command payload models:
  - `BreedingCreateSeedLotPayload`
  - `BreedingGerminatePlantsPayload`
  - `BreedingClonePlantsPayload`
  - `BreedingBulkSexPayload`
  - `BreedingBulkMovePayload`
  - `BreedingBulkCullPayload`
  - `BreedingCreatePlantNotePayload`
- Define `BreedingCommandPayload` as a union of those models and expand `ClaimedCommand.payload` to `PtzCommandPayload | BreedingCommandPayload`.
- Update `ClaimedCommand` validation so each command type requires the matching payload class.

Payload details:

- `BreedingCreateSeedLotPayload` should support purchased and cross sources. For purchased seed lots, include `generation`, `prefix`, `strain`, `cultivar` or source label fields consistent with `PlantLine`, optional `vendor_name`, `acquired_at`, optional `seed_count`, `sex_type_key`, and optional notes. For cross seed lots, include `seed_parent_plant_key`, `pollen_parent_plant_key`, `generation`, `prefix`, optional `pollinated_at`, optional `pollen_parent_is_reversed`, optional `seed_count`, `sex_type_key`, and optional notes. Keep request fields close to domain facts, not UI labels.
- `BreedingGerminatePlantsPayload` should include `seed_lot_source_id` or seed-lot id from the browser response, `count`, `tent_id`, `grid_position: None`, and optional date. It should not include exact plant keys or names.
- `BreedingClonePlantsPayload` should include `mother_plant_key`, `count`, `tent_id`, `grid_position: None`, and optional date. It should not include exact clone keys or names.
- `BreedingBulkSexPayload` should include nonempty `plant_keys` and `sex_key`.
- `BreedingBulkMovePayload` should include nonempty `plant_keys`, `tent_id`, and `grid_position: None`.
- `BreedingBulkCullPayload` should include nonempty `plant_keys` and required nonblank `reason`.
- `BreedingCreatePlantNotePayload` should include `plant_key`, required nonblank `body`, and optional `observed_at`. It should not include attachments in this plan.

Edit `apps/control-plane/src/dirt_control/api/browser.py`:

- Add browser request DTOs for:
  - `POST /api/breeding-logbook/seed-lots`
  - `POST /api/breeding-logbook/plants:germinate`
  - `POST /api/breeding-logbook/plants:clone`
  - `POST /api/breeding-logbook/plants:bulk-sex`
  - `POST /api/breeding-logbook/plants:bulk-move`
  - `POST /api/breeding-logbook/plants:bulk-cull`
  - `POST /api/breeding-logbook/plants/{plant_key}/notes`
- Each request must include `idempotency_key`.
- Each route must require browser auth, check `settings.command_creation_enabled`, validate the visible cloud projection enough to reject obvious bad input, and enqueue a `CloudCommand`.
- Use a shared private helper such as `_enqueue_breeding_command(...)` only if it removes real duplication around command row creation, idempotency lookup, expiry, and audit event writing. Keep operation-specific validation explicit at the route.
- Return the existing `CommandResponse` shape or a breeding-specific wrapper that includes the command. Prefer reusing `CommandResponse` if it is sufficient for polling and error display.
- Use a longer expiry than PTZ commands if needed. PTZ commands expire in 60 seconds; breeding writes are not hardware motion and may reasonably survive a longer gateway polling delay. Choose an explicit constant such as `BREEDING_COMMAND_EXPIRY_SECONDS = 3600` and record it in the code/tests.
- Set `device_id=None` and `capability_id=None` for breeding commands. Set `tent_id` to the target tent when there is one, or a stable value such as `"breeding-logbook"` if the command is site-wide. The plan should prefer nullable/scoped semantics where existing `CloudCommand` allows them, but note that `CloudCommand.tent_id` is currently non-null. If making it nullable is simpler and truthful, include a cloud migration and tests; otherwise use a documented site-wide sentinel tent id only as a short-term command target label, not as durable plant location data.

Tests for this milestone:

- Add control-plane tests for every endpoint:
  - auth required
  - commands disabled returns 503
  - idempotency returns the same command
  - invalid plant keys/seed lots/sex keys/tents/counts/reasons return 4xx
  - payload stored in `CloudCommand` matches the typed command DTO
  - generic `/api/commands` still rejects non-PTZ remote control
- Add shared cloud-contract tests for command payload validation and unknown-field rejection.

### Milestone 4: Gateway Breeding Command Execution

After this milestone, the gateway can claim breeding commands, apply them to the local database, and report success or failure. PTZ command execution should continue to work.

Refactor `apps/gateway/src/dirt_gateway/commands.py` carefully:

- Keep `GatewayCommandService` as the poll/claim/result orchestrator if practical.
- Split command execution by command family:
  - PTZ commands keep the existing target validation and PTZ executor.
  - Breeding commands go to a new local service, for example `BreedingCommandExecutor`.
- Do not let PTZ device/capability validation reject breeding commands. Validation should branch by command type.
- Keep local `CommandService` ledger rows for idempotency, but store breeding local command types such as `breeding.seed_lot.create`, `breeding.plants.germinate`, etc.

Add a local breeding service, recommended path `apps/gateway/src/dirt_gateway/breeding_commands.py` or a shared service under `apps/shared/src/dirt_shared/services/breeding_logbook.py` if tests and local reuse justify it. Prefer a shared service only if it owns pure local database behavior and can be tested without cloud concerns.

Local execution behavior:

- Resolve site and tent scoped integer IDs through existing scoped identity tables. Do not store hosted string IDs directly in local FK columns.
- For `breeding_seed_lot_create`:
  - Purchased source: create or reuse a `PlantLine` for the submitted source facts, then create a `SeedLot` with `is_purchased=True`, `sex_type_key`, vendor/acquired/seed count/notes.
  - Cross source: resolve seed and pollen parent plants by `plant.key`, create or reuse a resulting `PlantLine`, create `CrossEvent`, then create `SeedLot` with `produced_by_cross_event_id`.
  - Return `source_seed_lot_id`, line id, and display label facts in the command result.
- For `breeding_plants_germinate`:
  - Resolve seed lot and line.
  - Generate plant keys and names locally from the seed-lot/line prefix and next available suffix. The algorithm must be deterministic, unique, and tested against existing keys.
  - Create `Plant` rows with `source_seed_lot_id`, `line_id`, `sex_key="unknown"`, `germinated_at`, and lifecycle timestamps appropriate to the target tent/stage.
  - Create current `PlantLocationHistory` rows with `grid_position=None`.
  - Return created plant keys.
- For `breeding_plants_clone`:
  - Resolve mother plant by key.
  - Generate clone keys and names locally from a local prefix derived from the mother or submitted prefix policy. The UI should only preview the prefix; local code owns the suffixes.
  - Create `Plant` rows with `clone_source_plant_id`, inherited `line_id` and `sex_key`, `rooted_at` or clone date as appropriate, and current nullable-grid location.
  - Add a `PlantEvent` with `is_clone_taken=True` on the mother or clone as the existing event model best supports. Be explicit in tests.
- For `breeding_plants_bulk_sex`:
  - Resolve all plant keys.
  - Validate `sex_key` through `plant_lku_sex`.
  - Update `Plant.sex_key`.
  - Add `PlantEvent` rows with `is_sex_observation=True`.
- For `breeding_plants_bulk_move`:
  - Resolve plants and target tent.
  - Close current `PlantLocationHistory` rows by setting `end_at`.
  - Insert new current rows with `grid_position=None`.
  - Update lifecycle timestamps only when the move semantically starts a stage and the timestamp is currently null. Keep this explicit and tested.
  - Add transplant/stage `PlantEvent` rows.
- For `breeding_plants_bulk_cull`:
  - Resolve plants.
  - Set `culled_at` and required `culled_reason`.
  - Close current locations or move to no current location according to local model choice. Prefer closing current location and relying on `culled_at` for stage rather than inserting a fake "removed" location.
  - Add stage/event rows if useful for timeline projection.
- For `breeding_plant_note_create`:
  - Create `PlantNote` with `body`, `observed_at`, and `created_by` from the cloud requester if available.
  - Return note id and observed timestamp.

Idempotency:

- Gateway already enqueues local command ledger rows with `idempotency_key=f"cloud-command:{command_id}"`. The local executor should be safe if a claimed command is retried after a process restart.
- For commands that create multiple rows, execute inside one database transaction.
- The command result should include enough created local IDs/keys for debugging but should not be the source of frontend truth; the projection is.

Tests for this milestone:

- Add gateway tests for each breeding command type using a temporary local database/session fixture.
- Test duplicate command claim/report behavior continues to be idempotent.
- Test PTZ commands still pass existing gateway command tests.
- Test invalid local state returns a failed or rejected command result with a useful error string.

### Milestone 5: Frontend Mutations and Pending UX

After this milestone, the Breeding Logbook UI submits real mutations and shows pending state honestly.

Edit `web-ui/src/features/breeding-logbook/breedingLogbookQueries.ts` or split mutation hooks into `breedingLogbookMutations.ts` if that improves readability:

- Replace mock write helpers with `useMutation` hooks for each endpoint.
- Generate idempotency keys per user action. Include operation name and enough stable client context to avoid accidental reuse, for example `breeding-logbook:<operation>:<timestamp>:<random>`. Keep keys stable across retry of the same submitted mutation where possible.
- On success, add the returned command to a pending-command store in React state or React Query cache.
- Poll `GET /api/commands/{command_id}` or a breeding-specific command status endpoint until terminal.
- Invalidate read queries after terminal success and after a short delay to allow the gateway projection to sync. Use a bounded retry/refresh loop rather than unbounded polling.

Pending UX:

- Show a pending marker near affected rows/actions after command creation.
- Disable repeated destructive actions while the same command is pending.
- Do not mutate canonical plant sex/location/cull state optimistically.
- For text notes only, show a visually distinct pending note in the timeline until the real note appears from projection or the command fails.
- On command failure/rejection/expiry, show an inline error and keep the synced facts unchanged.

Frontend behavior changes:

- Add Plants should show the generated prefix as read-only. The mutation request sends seed lot or mother plant, count, target tent, and `grid_position: null`, not exact plant keys.
- Add Seeds can still let the operator choose or enter the prefix for the resulting line/seed lot if that prefix is a seed-lot/line fact. It should not generate plant keys.
- Cull flow must require a nonblank reason before enabling submit.
- Attach photo stays disabled, hidden, or clearly nonfunctional for now. Do not submit attachments.

Tests for this milestone:

- Add frontend tests for mutation request shapes, cull reason gating, read-only plant prefix preview, pending note display, and failed command display.
- Avoid MSW unless the repo has reintroduced it deliberately. Prefer testing query/mutation functions through local test seams or mocked API-client functions.

### Milestone 6: End-to-End Validation

After this milestone, the full read/write path is proven locally.

Use the local hosted dev stack:

    make dev-up
    make dev-status

Open the Web URL from `make dev-status` with `agent-browser`, log in with `dev-admin` / `dev-password`, and navigate to `/breeding-logbook`.

Validate reads:

- Plants table and board render real projection data.
- Seed-lot list includes lots without current plants.
- Plant detail shows real notes/events when local fixtures contain them.
- Plant detail lineage shows real parents and offspring summary for a cross-backed plant.
- Metric history still renders.

Validate writes:

- Submit a text note. The UI shows a pending note, the command becomes queued/running/succeeded, the gateway applies it locally, and after sync the note appears as a synced timeline item.
- Submit bulk sex. The UI shows pending state, then synced plant sex changes after command success and projection refresh.
- Submit bulk move. The local plant gets a current `PlantLocationHistory` row with `grid_position=NULL`; the UI eventually reflects the new location.
- Submit bulk cull with a reason. The UI requires the reason, then synced plant stage becomes culled after success.
- Submit Add Seeds, Germinate, and Clone flows in a controlled dev database. Local generated plant keys are unique and appear after projection.

Record any manual browser evidence in `Artifacts and Notes`.


## Concrete Steps

Start from the repository root:

    cd /home/akcom/code/dirt

Inspect worktree state before editing:

    git status --short

Read required docs before implementation:

    sed -n '1,240p' docs/commands.md
    sed -n '1,260p' docs/database.md
    sed -n '1,260p' docs/rules/data-modeling.md
    sed -n '1,220p' docs/rules/boundary-contracts.md
    sed -n '1,240p' docs/rules/simple-clean-architecture.md
    sed -n '1,220p' docs/references/atlas/INDEX.md
    sed -n '1,220p' docs/references/tanstack-router-v1/INDEX.md
    sed -n '1,220p' docs/references/modern-idiomatic-typescript/INDEX.md
    sed -n '1,220p' docs/references/tailwind-v4/INDEX.md

Implement Milestone 1, then run focused backend validation:

    uv run pytest apps/shared/tests/test_cloud_contract.py -q
    uv run pytest apps/gateway/tests/test_sync.py apps/gateway/tests/test_gateway_boundary_guardrails.py -q
    uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q

Generate migrations through Atlas when SQLModel/cloud models change:

    atlas migrate diff breeding_logbook_nullable_grid_and_timeline --env local
    atlas migrate diff breeding_logbook_cloud_timeline_projection --env cloud
    atlas migrate hash --env local
    atlas migrate hash --env cloud
    atlas migrate apply --env local --dry-run

Regenerate hosted browser contract after route/DTO changes:

    DIRT_CLOUD_ASSET_STORE=local scripts/gen-hosted-contract

Run frontend validation after read and mutation cutovers:

    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test

Run full relevant validation near completion:

    uv run pytest apps/shared/tests/test_cloud_contract.py -q
    uv run pytest apps/gateway/tests/test_sync.py apps/gateway/tests/test_gateway_boundary_guardrails.py -q
    uv run pytest apps/control-plane/tests/test_api.py apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q
    uv run pytest apps/tests/invariants -q
    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test
    git diff --check

Run browser validation:

    make dev-up
    make dev-status
    agent-browser --session breeding-logbook-api open <Web URL>

Log in with:

    username: dev-admin
    password: dev-password

Navigate to:

    <Web URL>/breeding-logbook

Use `agent-browser snapshot -i -c` to discover selectors, then exercise read views and write flows. Do not use raw Playwright for agentic browser interaction.


## Validation and Acceptance

Read API acceptance:

- `GET /api/breeding-logbook/bootstrap` returns real location options with nullable `grid_position`.
- `GET /api/breeding-logbook/plants` returns real synced plant rows, active/culled counts, latest note/event summaries, nullable-grid location labels, and telemetry summaries.
- `GET /api/breeding-logbook/seed-lots` includes seed lots even when no current plants are sourced from them.
- `GET /api/breeding-logbook/plants/{plant_key}` returns real lineage parents, real offspring summary, real note/event timeline, metric summaries, telemetry streams, and `wiki_content` deferred/null.
- `GET /api/breeding-logbook/plants/{plant_key}/metrics/history` continues to return plant-scoped history by `plant_key`.
- All owned browser responses inherit `BrowserResponse` or otherwise forbid unexpected fields.
- Hosted OpenAPI and generated TypeScript schema include the final read shapes.

Write API acceptance:

- Browser write endpoints exist for seed-lot creation, germination, cloning, bulk sex, bulk move, bulk cull, and text notes.
- Each endpoint requires auth, `idempotency_key`, and operation-specific validation.
- Cull requires nonblank reason.
- Germinate and clone requests do not accept exact plant keys/names. Local execution generates them.
- Move/germinate/clone write `grid_position=NULL` until grid placement is designed.
- Each endpoint enqueues a typed breeding cloud command and returns a pollable command response.
- Generic `/api/commands` remains PTZ-only from the browser perspective.
- Gateway claim/result contracts validate typed breeding payloads with Pydantic.
- Gateway applies breeding commands locally in transactions and reports succeeded/failed/rejected/expired.

Frontend acceptance:

- `breedingLogbookQueries.ts` no longer imports runtime mock data for normal reads.
- The UI maps generated hosted API responses to the feature view model without handwritten hosted response interfaces in `web-ui/src/api-client/cloud.ts`.
- Bulk sex, move, cull, Add Seeds, Germinate, Clone, and Log Note submit real mutations.
- Pending markers appear after command creation.
- Canonical plant facts do not change optimistically before projection refresh.
- Pending text notes are visually distinct and reconcile with synced notes.
- Failed commands produce visible inline errors.
- Add Plants shows prefix preview as read-only and does not submit proposed plant keys.
- Photo attachment remains deferred and cannot create a misleading partial attachment record.

End-to-end acceptance:

- With the local hosted stack running, an operator can log in, open `/breeding-logbook`, see real synced data, submit a note, observe pending state, and then see the synced note appear after gateway execution and projection.
- At least one non-note mutation is verified end to end in local dev, preferably bulk sex because it is low-risk and visible.


## Idempotence and Recovery

Most implementation steps are safe to repeat:

- `scripts/gen-hosted-contract` overwrites generated artifacts deterministically.
- Focused tests can be rerun freely.
- Browser write endpoints should return the same command for the same authenticated user and `idempotency_key`.
- Gateway local command execution is protected by the local `CommandService` idempotency key `cloud-command:{command_id}`.

Migration work is not casually reversible:

- Before applying local schema migrations to the live local database, follow `docs/database.md` and take a compressed custom-format backup if the migration affects existing data.
- Use `atlas migrate apply --env local --dry-run` before live apply.
- Do not hand-edit applied migrations. Add a new migration if a previously applied migration needs correction.

Command execution recovery:

- If the gateway crashes after claiming a command but before reporting terminal status, the existing claim logic can reclaim previously claimed commands for the same gateway until expiry. Keep this behavior working for breeding commands.
- If local execution succeeds but result reporting fails, enqueue result reporting in the gateway outbox as PTZ commands do today.
- If projection sync lags after command success, the frontend should continue showing a terminal command status plus stale synced facts and retry invalidation for a bounded period.

Frontend recovery:

- Pending commands should survive component rerenders through React Query cache or route-level state. They do not need durable browser storage in the first implementation.
- If a pending command fails, leave synced data unchanged and show an error that lets the operator retry with a new idempotency key.


## Artifacts and Notes

Relevant current files:

- `docs/epics/breeding-logbook-ui/api-audit.md`
- `web-ui/src/features/breeding-logbook/BreedingLogbookPage.tsx`
- `web-ui/src/features/breeding-logbook/breedingLogbookQueries.ts`
- `web-ui/src/features/breeding-logbook/breedingLogbookTypes.ts`
- `apps/shared/src/dirt_shared/models/plant.py`
- `apps/shared/src/dirt_shared/cloud_contract.py`
- `apps/gateway/src/dirt_gateway/local.py`
- `apps/gateway/src/dirt_gateway/commands.py`
- `apps/control-plane/src/dirt_control/api/gateway.py`
- `apps/control-plane/src/dirt_control/api/browser.py`
- `apps/control-plane/src/dirt_control/models/cloud.py`

Current unresolved implementation details to settle during Milestone 4, with code evidence:

- `CloudCommand.tent_id` is currently non-null. Breeding commands that are not tent-specific need either a nullable cloud migration or a documented command-target sentinel. Prefer nullable if the implementation remains contained.
- Clone event placement should be explicit: the existing `PlantEvent` row belongs to one `plant_id`, so decide whether clone-taken events attach to the mother, each clone, or both. Prefer the simplest timeline behavior that the UI can explain.
- New plant key generation must inspect existing `plant.key` values and avoid racing duplicates. In the single gateway executor this is likely straightforward with a transaction and the existing unique constraint; tests should cover occupied suffixes.


## Interfaces and Dependencies

Final read interfaces:

- `GET /api/breeding-logbook/bootstrap`
- `GET /api/breeding-logbook/plants?include_culled=false&group_by=stage`
- `GET /api/breeding-logbook/seed-lots`
- `GET /api/breeding-logbook/plants/{plant_key}`
- `GET /api/breeding-logbook/plants/{plant_key}/metrics/history?range=24h`

Final write interfaces:

- `POST /api/breeding-logbook/seed-lots`
- `POST /api/breeding-logbook/plants:germinate`
- `POST /api/breeding-logbook/plants:clone`
- `POST /api/breeding-logbook/plants:bulk-sex`
- `POST /api/breeding-logbook/plants:bulk-move`
- `POST /api/breeding-logbook/plants:bulk-cull`
- `POST /api/breeding-logbook/plants/{plant_key}/notes`

Final shared gateway command types:

- `breeding_seed_lot_create`
- `breeding_plants_germinate`
- `breeding_plants_clone`
- `breeding_plants_bulk_sex`
- `breeding_plants_bulk_move`
- `breeding_plants_bulk_cull`
- `breeding_plant_note_create`

Final projection DTOs:

- `CatalogCrossEvent`
- `CatalogPlantNote`
- `CatalogPlantEvent`
- nullable `CatalogPlantLocation.grid_position`

Final cloud projection tables:

- `cloud_cross_event`
- `cloud_plant_note`
- `cloud_plant_event`
- nullable `cloud_plant_location.grid_position`

External dependencies:

- PostgreSQL 17 and Atlas migrations.
- Existing hosted control-plane session auth.
- Existing gateway claim/result polling.
- Existing generated hosted OpenAPI/TypeScript contract tooling.
- No new frontend DnD, upload, or photo dependency is required by this plan.


## Revision Notes

- 2026-06-18: Initial plan written after reviewing `api-audit.md`, frontend mock write paths, current read DTOs, local breeding models, and PTZ-only command infrastructure. Decisions from operator clarification are recorded in the Decision Log.
