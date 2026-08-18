# Add truthful multi-plant substrate history charts

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.


## Purpose / Big Picture

After this change, the hosted tent page shows soil moisture, substrate EC, and substrate pH history for every currently mapped sentinel probe. Each metric has one chart with one distinguishable line per plant, and the existing 1-hour, 24-hour, 7-day, 30-day, and 90-day range selector controls the panel. Plant-detail telemetry uses the same truthful timestamped history model.

The change also removes the abstractions that currently hide sensor identity. Today the generic tent history endpoint can return several physical streams as one anonymous point list, and the tent UI silently overwrites values that share a timestamp. Plant-detail mapping then discards timestamps and invents replacements. The completed design has one canonical mapped-plant history service, a batched tent collection route, a direct multi-series `Sparkline` contract, and no compatibility paths for deleted source-owned APIs.

The behavior is observable through focused API and React tests, the local hosted dashboard, the generated OpenAPI contract, and the deployed hosted tent page.


## Progress

- [x] (2026-08-18 08:04Z) Audited the existing metric presentation, rollup, mapped-plant history, tent UI, plant UI, and Sparkline paths.
- [x] (2026-08-18 08:09Z) Milestone 1: encoded the repository-owned service-consumer rule in root `AGENTS.md` and its operational/data-safety boundary in `docs/rules/simple-clean-architecture.md`; focused sanity validation and simplify review passed.
- [ ] Milestone 2: implement the canonical backend history contract, batch collection endpoint, presentation cleanup, migrations, and dead backend-path removal.
- [ ] Milestone 3: cut the frontend over to timestamped multi-series history and add the tent substrate-sentinel panel.
- [ ] Milestone 4: perform simplification review, full validation, local browser acceptance, hosted deployment, final worktree commit, and push to `main`.


## Surprises & Discoveries

- Observation: `metric_history()` can return rows from multiple device/capability streams, but `MetricHistoryResponse` contains no stream identity.
  Evidence: `apps/control-plane/src/dirt_control/services/browser_metrics.py` filters device and capability only when optional query parameters are supplied, while `web-ui/src/features/tents/TentsWorkspace.tsx::toSparklinePoints` keys rows only by bucket timestamp.

- Observation: `history_enabled` currently means both “retain/sync history” and “show a generic tent history tile.”
  Evidence: substrate presentation rows are history-enabled and assigned to `plant_water`, even though their real identity is owned by `plant_metric_stream`.

- Observation: the plant-detail frontend throws away API timestamps, gaps, presentation metadata, and stream identity, then generates `mock-${index}` timestamps.
  Evidence: `web-ui/src/features/plants/plantsQueries.ts::mapMetricHistory` and `web-ui/src/features/plants/PlantsWorkspace.tsx::SparklineCard`.

- Observation: the repository has no frontend consumer for the tent-scoped single-plant detail and history routes. The live plant UI uses breeding-logbook routes.
  Evidence: repository-wide route search and generated-client references.

- Observation: the gateway already retains the desired rollups: 5-minute for 24 hours, hourly for 7 days, 4-hour for 30 days, and daily for 90 days.
  Evidence: `apps/gateway/src/dirt_gateway/local.py::ROLLUP_SPECS`.

- Observation: prior test guidance used “public contracts,” which could be misread as including repository-owned HTTP APIs.
  Evidence: Milestone 1 replaced it with the precise term “outside-owned contracts,” preserving direct cutovers for all Dirt-owned browser and service APIs.


## Decision Log

- Decision: Dirt application services have no external consumers. All service and browser API consumers are source-owned in this repository, so owned contract changes use a direct cutover and delete obsolete call sites, tests, routes, generated types, aliases, and wrappers in the same plan.
  Rationale: this is an explicit operator fact and preference. Preserving compatibility for hypothetical consumers creates dead architecture. Persisted-data migration safety, deployment ordering, and operator-visible rollback safety still apply.
  Date/Author: 2026-08-18 / operator and Codex.

- Decision: nullable dashboard-group fields express whether a history-enabled metric belongs in generic tent history. Substrate rows remain history-enabled but have all dashboard-group fields cleared.
  Rationale: this separates history availability from dashboard membership without introducing another overlapping boolean.
  Date/Author: 2026-08-18 / Codex.

- Decision: the canonical mapped history representation is plant identity plus metric streams, with presentation metadata once per stream and timestamped display-value points. The new tent response is a small collection envelope over that same representation.
  Rationale: it models the domain, supports plant detail and tent charts, avoids chart-specific backend DTOs, and prevents per-point repetition of units and raw/display extrema that no owned consumer uses.
  Date/Author: 2026-08-18 / Codex.

- Decision: use one batched stream lookup and one batched rollup lookup for tent history, matching exact `(device_id, capability_id, metric)` identities.
  Rationale: the current three independent `IN` sets can admit Cartesian lookalikes, while looping the existing one-plant service would create N+1 queries.
  Date/Author: 2026-08-18 / Codex.

- Decision: generic tent metric history is an intentional tent-level aggregate when more than one physical stream supplies the same presented metric; it must never return anonymous duplicate points.
  Rationale: the existing generic dashboard models tent metrics, whereas plant-mapped substrate telemetry requires explicit plant series.
  Date/Author: 2026-08-18 / Codex.

- Decision: evolve `Sparkline` directly from one `points` prop to a required `series[]` prop and update every owned caller and test in the same milestone.
  Rationale: multi-series display is now a real shared responsibility. An optional legacy prop, wrapper, or second chart component would be a shim.
  Date/Author: 2026-08-18 / Codex.

- Decision: shared chart hover identity is a timestamp, not a point-array index.
  Rationale: series can contain gaps or non-identical samples. Timestamp identity is stable across charts and ranges.
  Date/Author: 2026-08-18 / Codex.

- Decision: use existing rollups at their finest retained useful resolution: 1h and 24h use 5m, 7d uses 1h, 30d uses 4h, and 90d uses 1d.
  Rationale: irrigation rises occur over minutes, and no ingestion or storage change is needed.
  Date/Author: 2026-08-18 / Codex.


## Outcomes & Retrospective

Milestone 1 established the compatibility preference through progressive disclosure: one concise always-loaded instruction and one canonical deep explanation. The simplify review removed duplicate root guidance and retained concrete migration, deployment, rollback, and outside-owned-protocol safety exceptions.


## Context and Orientation

The hosted API is `apps/control-plane/`. FastAPI browser routes live under `apps/control-plane/src/dirt_control/api/browser/`, Pydantic response contracts under `api/browser_schemas/`, and query/assembly logic under `services/`. Hosted PostgreSQL stores projected rollups in `CloudMetricRollup`, current plant locations in cloud plant projection tables, active sensor-to-plant mappings in `CloudPlantMetricStream`, and presentation in `CloudMetricPresentation`.

The local gateway in `apps/gateway/` aggregates readings into retained rollups and projects them to the hosted service. It already sends substrate moisture, temperature, EC, and pH because their presentation rows are history-enabled. This feature does not add another time-series table or change firmware.

The web app is `web-ui/`. `web-ui/src/features/tents/TentsWorkspace.tsx` renders the tent dashboard and generic history cards. `web-ui/src/features/plants/` maps and renders plant detail. `web-ui/src/ui/Sparkline.tsx` is the only chart primitive and currently assumes one series. Hosted browser types are generated from the control-plane OpenAPI document into `web-ui/src/api-client/generated/hosted-schema.ts` by `scripts/gen-hosted-contract`; handwritten hosted response interfaces are forbidden.

A “mapped stream” is the exact tuple of device ID, capability ID, and metric assigned to a plant through `plant_metric_stream` locally and `cloud_plant_metric_stream` in hosted state. A “sentinel” is a current plant with one of those active substrate probe mappings. The UI should derive sentinels from mappings, not hard-coded plant keys or device IDs.


## Plan of Work

### Milestone 1: Encode the source-owned compatibility rule

Add a short always-loaded statement to root `AGENTS.md`: Dirt has no external application-service or browser-API consumers, and agents must directly update every repository-owned producer and consumer rather than preserving hypothetical compatibility. Point to the detailed rule in `docs/rules/simple-clean-architecture.md`.

Expand that deep-dive rule with the operational boundary: no external consumers does not waive Atlas data migrations, safe deploy ordering, backups for destructive persisted-data changes, or explicit compatibility requested by the operator. Do not duplicate the rule across multiple deep-dive files.

Acceptance: a future agent sees the fact in root instructions, has one canonical detailed explanation, and is not taught to ignore real data/deploy safety.

### Milestone 2: Build one truthful backend history path

Move range policy, substrate unit conversion, stream-key handling, and shared history assembly out of boundary schema modules into a focused metric-history service module. Type accepted range keys in FastAPI/Pydantic so invalid values fail at the boundary. Remove the unused `supported_ranges` response field and helper; the frontend owns labels/order and compiles against the generated range union.

Change the global presentation route from the falsely scoped `/api/tents/{source_tent_id}/metrics/presentation` path to `/api/metrics/presentation`, updating owned tests and deleting the old route. Presentation assembly includes history rows in generic tent groups only when all group fields are non-null, treats all-null group fields as intentional exclusion, and fails loudly on partial group configuration.

Add matching local and cloud Atlas data migrations that clear `dashboard_group`, `dashboard_group_label`, and `dashboard_group_order` for `soil_moisture_pct`, `substrate_temp_c`, `substrate_ec_us_cm`, and `substrate_ph`. Keep `history_enabled=true` so rollups continue. Update Atlas sums through the documented Atlas workflow.

Replace anonymous duplicate generic history points with one intentional tent-level point per bucket. Aggregate sample counts and min/max; calculate average weighted by sample count; reject inconsistent units. Delete unused exact-stream query parameters from that generic browser route.

Create a canonical batched mapped-plant history loader. It accepts one or many plants, fetches their active mapped streams with presentation, fetches rollups for exact composite stream identities in one query, performs source-to-display conversion once, and returns a slim timestamped stream contract. Use it for the breeding-logbook plant history route and the new `GET /api/tents/{source_tent_id}/plants/metrics/history?range=...` collection route. The collection response includes current plant identity (`id`, `key`, `name`, `grid_position`) and its streams.

Delete the unused tent-scoped single-plant detail and history routes, their route-only services/DTOs/tests, and generated OpenAPI entries. Keep the tent plant-summary route. Remove the duplicated breeding history orchestration so both live routes use the canonical loader. Remove the confirmed unreachable rollup branch in `apps/gateway/src/dirt_gateway/sync.py`.

Regenerate `web-ui/src/api-client/generated/hosted-schema.ts`. Do not preserve old routes, response shapes, aliases, optional query parameters, or DTO wrappers.

Acceptance: three plants with identical timestamps remain three separate mapped streams in the collection response; inactive/unmapped and Cartesian-lookalike streams are absent; query count remains bounded as plant count grows; generic tent history has one point per timestamp; substrate metrics are absent from generic presentation groups; breeding history uses the slim timestamped contract; removed routes return 404 in tests.

### Milestone 3: Direct frontend multi-series cutover

Change `web-ui/src/ui/Sparkline.tsx` to accept chart metadata plus `series[]`, where each series carries stable ID, label, accent/color, and `{ts, value|null}` points. Preserve zero as data and null as a gap. Make hover input/output timestamp-based. Update both production callers and tests in the same cutover, then delete the old `points`, top-level single-series accent, hover-index, and duplicate hover-point contracts.

Update tent queries to fetch global presentation once and mapped plant history once per tent/range. Add a “Substrate sentinels” panel with shared range selection and three multi-series charts: soil moisture, substrate EC, and substrate pH. Each active mapped plant gets a stable distinguishable color and a readable legend. Do not hard-code sentinel plant or sensor identities. Preserve generic dashboard groups for non-plant tent metrics.

Split plant detail and plant history into separate TanStack Query keys with range included in the history key. Preserve real timestamps, null gaps, raw metric identity, unit, precision, y-domain, and backend presentation accent in the view model. Delete `metricHistoryKey`, fake timestamp construction, hard-coded metric accent mapping, unused fixed tone, the hard-coded moisture progress bar, missing-as-zero behavior, and the inert “Attach RS485 probe” button. Render every mapped plant stream through the canonical Sparkline.

Acceptance: the tent panel shows three chart cards with one series per mapped sentinel and works at all five ranges; shared hover labels represent the same timestamp; plant detail changes range without refetching unrelated detail; EC and pH display configured units/precision; no fake timestamps, compatibility Sparkline props, or duplicate accent types remain.

### Milestone 4: Simplify, validate, deploy, and release

Run the repository simplification process over the complete feature diff, applying only concrete reuse, quality, and efficiency improvements. Confirm no shims, stale routes, dead types, duplicate unit conversions, N+1 queries, or chart-specific backend abstractions remain.

Run focused tests, full control-plane/gateway tests, web typecheck/lint/tests/build, invariants, and `make fix`. Start the local hosted dev stack, log in through the real browser flow with `agent-browser`, inspect the tent page at mobile and desktop widths, exercise all five ranges, and capture evidence that three series remain distinct. Regenerate the hosted contract check after formatting.

Run `scripts/deploy-control-plane` exactly once after local acceptance. Confirm API and UI smoke checks. Then stage and commit all remaining files in the worktree—including the pre-existing README, lint, wiki, and daily-log changes explicitly authorized by the operator—inspect the complete staged diff, push `main` to `origin/main`, and confirm the remote ref.


## Concrete Steps

Run from `/home/akcom/code/dirt` unless a command says otherwise.

Milestone validation commands include:

    uv run pytest apps/control-plane/tests/test_api.py -q
    uv run pytest apps/control-plane/tests/test_control_plane_boundary_guardrails.py -q
    uv run pytest apps/control-plane/tests/test_cloud_metric_presentation_registry.py -q
    uv run pytest apps/gateway/tests -q
    scripts/gen-hosted-contract
    git diff --exit-code -- web-ui/src/api-client/generated/hosted-schema.ts

Frontend validation includes:

    pnpm --dir web-ui typecheck
    pnpm --dir web-ui lint
    pnpm --dir web-ui test
    pnpm --dir web-ui build

Repository and browser acceptance includes:

    uv run pytest apps/tests/invariants/ -q
    make fix
    make dev-up
    make dev-status
    agent-browser open <Web URL reported by make dev-status>

Log in with `dev-admin` / `dev-password`, open the tent page, exercise `1h`, `24h`, `7d`, `30d`, and `90d`, and inspect the panel at a mobile viewport and a desktop viewport. Stop with:

    make dev-down

Release commands are:

    scripts/deploy-control-plane
    git add -A
    git diff --cached --stat
    git diff --cached --check
    git commit -m "Release substrate sentinel history"
    git push origin main


## Validation and Acceptance

Backend tests must prove stream identity, exact tuple matching, display conversion, active mapping scope, range-to-bucket selection, and one batched collection path. At least one fixture must create three plants whose probe rollups have the same bucket timestamp and assert all three values survive. Another must create a rollup whose individual device, capability, and metric each appear in valid sets but whose exact tuple is unmapped, proving it is excluded.

Sparkline tests must prove multiple series share one domain, zero is drawn, null creates a gap, legend/labels identify series, and hover is synchronized by timestamp. Query tests must prove one collection request per tent/range and that range is in the TanStack Query key.

Human acceptance is the hosted tent page showing moisture, EC, and pH charts with the current mapped sentinels, useful minute-scale 24-hour irrigation detail, and no substrate duplicates among generic tent history tiles. Plant detail must show genuine timestamped stream history and an honest empty state when a metric has no data.

Deployment acceptance is successful completion of both smoke checks in `scripts/deploy-control-plane`, followed by `origin/main` pointing at the final local `main` commit.


## Idempotence and Recovery

The presentation data migrations are idempotent updates to a fixed metric set. Atlas applies each version once. If local development restore is needed, use `make dev-reset`; do not apply ad hoc DDL. Hosted deployment applies cloud migrations before the API/UI, which is safe because clearing nullable group metadata does not invalidate the old runtime while deployment is in progress.

Generated contract output and formatting commands are safe to repeat. Feature commits form rollback boundaries between milestones. Do not use `git reset --hard` or broad checkout commands because the starting worktree contains operator-owned changes. If a milestone fails, revert only files introduced by that milestone or send corrections to its worker.

If hosted deployment fails before smoke checks, inspect the deploy script output and Railway status, correct the source/configuration issue, and rerun the supported script. Do not bypass it with direct `railway up`. If the API is healthy but the UI fails, the same script is safe to rerun after correcting the build. Do not roll back the data migration merely to restore nullable dashboard groups; the old runtime already rejects missing groups only when it reads substrate rows, so deploy backend and frontend together through the supported flow.


## Artifacts and Notes

Starting branch state:

    main at 3074d11, matching origin/main

Starting unrelated dirty files include `README.md`, `scripts/lint.py`, existing wiki pages, and new `wiki/daily/2026-08-01.md` through `2026-08-17.md`. They are outside feature milestones and are intentionally included only in the operator-authorized final worktree commit.


## Interfaces and Dependencies

At completion the following source-owned interfaces exist:

- `GET /api/metrics/presentation` returns current metric and generic history-group presentation without a repeated supported-range list.
- `GET /api/tents/{source_tent_id}/metrics/history?metric=...&range=...` returns one intentional tent-level aggregate point per bucket and accepts no physical-stream selectors.
- `GET /api/tents/{source_tent_id}/plants/metrics/history?range=...` returns current plant identities and exact mapped metric streams.
- `GET /api/breeding-logbook/plants/{plant_key}/metrics/history?range=...` uses the same slim stream/point contract.
- `Sparkline` accepts `series[]` and timestamp-based hover state; there is no legacy single-series API.
- Range keys are exactly `1h`, `24h`, `7d`, `30d`, and `90d` in generated browser contracts.

No new external dependency is required. Existing PostgreSQL/Atlas, FastAPI/Pydantic, TanStack Query v5, React, Tailwind v4, and the generated OpenAPI client remain the platform.


## Revision Notes

- 2026-08-18: Initial plan written from the operator-approved architecture and read-only cleanup audit.
