# Breeding Logbook Browser API Audit

Milestone 4 proposes a screen-shaped browser API for the Breeding Logbook route while the frontend remains mock-backed. The hosted control plane is a cloud projection, not the local source of truth, so this audit only covers read contracts. Durable writes need a later command/sync design that sends intent back to the local system and then observes the synced projection.

## Current Frontend Query Map

| Frontend hook/query | Current mock source | Proposed browser endpoint | Response DTO |
|---|---|---|---|
| `useBreedingLogbookBootstrapQuery` / `fetchBreedingLogbookBootstrap` | `BREEDING_LOGBOOK_BOOTSTRAP` | `GET /api/breeding-logbook/bootstrap` | `BreedingLogbookBootstrapResponse` |
| `useBreedingLogbookPlantsQuery` / `fetchBreedingLogbookPlants` | `BREEDING_LOGBOOK_PLANTS` | `GET /api/breeding-logbook/plants?include_culled=false&group_by=stage` | `BreedingLogbookPlantListResponse` |
| `useBreedingLogbookSeedLotsQuery` / `fetchBreedingLogbookSeedLots` | `BREEDING_LOGBOOK_SEED_LOTS` | `GET /api/breeding-logbook/seed-lots` | `BreedingLogbookSeedLotListResponse` |
| `useBreedingLogbookPlantDetailQuery(plantId)` / `fetchBreedingLogbookPlantDetail` | `BREEDING_LOGBOOK_SELECTED_PLANT_DETAIL` or derived mock detail | `GET /api/breeding-logbook/plants/{plant_key}` plus `GET /api/breeding-logbook/plants/{plant_key}/metrics/history?range=24h` when real history is wired | `BreedingLogbookPlantDetailResponse` plus `PlantMetricHistoryResponse` |

The current detail hook embeds `metricHistory` in the mock detail object. The real API keeps plant detail and metric history as two screen-level reads: detail carries identity, lineage, latest environment summaries, events, telemetry stream metadata, and wiki projection; history carries the time-windowed series for the environment panel.

## Read Endpoints

### `GET /api/breeding-logbook/bootstrap`

Purpose: one startup call for lookup data and global render metadata.

Returns:

- `today` and `today_label`.
- Plant sex lookup rows: `unknown`, `male`, `female`, `herm`, `reversed`.
- Seed-lot sex type lookup rows: `unknown`, `feminized`, `regular`.
- Stage lookup rows: `germinating`, `veg`, `flower`, `breeding`, `harvested`, `culled`.
- Location options derived from active cloud tents.

Current implementation note: lookup rows are static in the browser DTO layer because the hosted projection does not currently sync the lookup tables. Location `stage_key` is inferred from tent id, which is enough for contract shape but should become a synced/local-owned location policy before durable writes.

### `GET /api/breeding-logbook/plants?include_culled=false&group_by=stage`

Purpose: one population read for the table and board, without forcing the frontend to join plants, current locations, line rows, seed lots, and telemetry counts.

Returns:

- `active_count`, `culled_count`, `group_by`.
- Plant rows with stable human key, display name, generation, parent/lineage label, sex key, lifecycle-derived stage, stage day, lifecycle dates, current location label, seed-lot label, latest note summary, and telemetry summary.

Current implementation note: rows are backed by `cloud_plant`, current `cloud_plant_location`, `cloud_plant_line`, `cloud_seed_lot`, and active plant metric stream counts. Plants without a current projected location cannot be returned yet. `last_note` is only populated from existing projected reason fields; journal notes/events are not synced into the cloud projection yet.

### `GET /api/breeding-logbook/seed-lots`

Purpose: one seed-lot inventory read for Add Seeds/Add Plants forms, including seed lots with no current plants.

Returns:

- Seed-lot id, label, prefix, generation, source kind, source label, parents/lineage label, sex type key, and seed count.

Current implementation note: backed by `cloud_seed_lot` joined to `cloud_plant_line`. This intentionally does not depend on current plant rows, fixing the old projection gap where lots were only visible through current plants. Parent labels are line-derived until explicit seed-lot parent/cross summaries are synced.

### `GET /api/breeding-logbook/plants/{plant_key}`

Purpose: one detail screen read for plant identity, lineage, current facts, latest environment summaries, and projected supporting content.

Returns:

- `plant`: the same row shape used by the population endpoint.
- `lineage`: parent summary and offspring summary.
- `metrics`: latest environment summaries for the detail cards.
- `events`: journal timeline events.
- `telemetry`: mapped plant metric streams with latest readings.
- `wiki_content`: projected wiki page content when available.

Current implementation note: backed by the same current cloud plant projection and existing mapped telemetry helpers. `events` is currently empty, `offspring` is a placeholder summary, and `wiki_content` remains `null` because the existing plant detail path also does not map plant wiki pages yet.

### `GET /api/breeding-logbook/plants/{plant_key}/metrics/history?range=24h`

Purpose: one plant-scoped history read for the detail environment panel.

Returns:

- `range`, selected rollup `bucket`, and mapped telemetry streams with history points using the existing display conversions.

Current implementation note: reuses the existing `PlantMetricHistoryResponse` contract and rollup mapping, but resolves the plant by site-wide `plant_key` instead of requiring a tent path segment.

## Future Mutation Endpoints

These are intentionally out of scope for Milestone 4 and are not implemented:

- `POST /api/breeding-logbook/seed-lots`
- `POST /api/breeding-logbook/plants:germinate`
- `POST /api/breeding-logbook/plants:clone`
- `PATCH /api/breeding-logbook/plants/{plant_key}/sex`
- `POST /api/breeding-logbook/plants:bulk-move`
- `POST /api/breeding-logbook/plants:bulk-cull`
- `POST /api/breeding-logbook/plants/{plant_key}/notes`

These cannot be simple hosted table writes. The local Dirt system owns durable breeding records, hardware context, and sync projection. A later design needs command DTOs, idempotency, local validation, gateway claim/result handling, and clear behavior for pending/failed writes before these endpoints should exist.

## Contract Expectations Added

Milestone 4 added read-only DTOs and minimal browser routes in `apps/control-plane/src/dirt_control/api/browser.py`:

- `BreedingLogbookBootstrapResponse`
- `BreedingLogbookPlantListResponse`
- `BreedingLogbookSeedLotListResponse`
- `BreedingLogbookPlantDetailResponse`
- `PlantMetricHistoryResponse` reused for the logbook history route

All new owned response payloads inherit `BrowserResponse`, so Pydantic forbids unexpected fields. Focused tests cover route response models, required nullable fields, unknown-field rejection, auth, list/detail/seed-lot/history shape, and the seed-lot list behavior that includes lots with no current plants.
