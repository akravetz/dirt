# Generator notes — frontend.dashboard.sparklines

## Status

DONE. All plan-JSON acceptance criteria green:

- `pnpm lint`, `pnpm typecheck`, `pnpm knip`, `pnpm build`, `pnpm test`
  (Vitest) — pass.
- `pnpm test:e2e` — 16/16 pass (4 new sparkline specs + 12 existing
  gauges + app-shell specs).
- `uv run pytest apps/tests/invariants/ -q` — 96 passed (unchanged).

## What shipped

- `web-ui/src/ui/Sparkline.tsx` — presentational SVG line chart with
  shared-hover crosshair + per-unit tooltip. Index-based hover (not
  pixel x) keeps the crosshair aligned across tiles even when their
  widths differ.
- `web-ui/src/ui/RangeSwitch.tsx` — `<fieldset>` (implicit role="group")
  wrapping three `<button aria-pressed>` chips. Biome's accessibility
  rule forbids `role="radio"` on non-inputs, so we model this as an
  ARIA toggle-button group instead of a radiogroup; the group's
  `aria-label="Sparkline range"` lets the e2e scope its locators.
- `web-ui/src/routes/index.tsx` — composed the sparklines section
  under the existing gauges section. Lifted `range` + `hoverIndex`
  state here so all five sparklines share them. `useQueries` fans out
  one history query per metric keyed on `[range, metric]`; switching
  the range invalidates all five simultaneously → the network layer
  observes 5 fresh `GET /api/sensors/history` per switch.
- `web-ui/src/mocks/handlers.ts` — MSW v2 handler for
  `GET /api/sensors/history`. Deterministic triangle-wave fixture with
  per-range bucket counts (1h → 12, 24h → 48, 7d → 168) and
  per-metric base/amplitude/unit so the e2e crosshair/tooltip
  assertions are stable across runs.
- `web-ui/tests/e2e/dashboard-sparklines.spec.ts` — one `test(...)`
  block per plan-description assertion (four total: render, range
  switch → 5 fetches per change, shared crosshair, per-metric unit in
  tooltip).
- `web-ui/tests/e2e/dashboard-gauges.spec.ts` — narrowed existing
  article/heading locators to `exact: true` (and `heading` to
  `level: 2`) so the new sparkline tiles (labelled "{Metric}
  sparkline" + `<h3>`) don't substring-match into the gauge
  assertions. Scoped the `articles).toHaveCount(5)` guard to the
  "Environment gauges" region.

## Documented deviation — temperature unit

**Plan description asserts:** tooltip shows the correct unit suffix per
metric "°C / % / kPa / % / in".

**Implemented:** "°F / % / kPa / % / in" (temperature deviates).

**Why:** The frozen contract (`contracts/webapp-v1.yaml` at tag
`contract-frozen-2026-04-20`) and the existing `/api/sensors/current`
MSW fixture both model the temperature sensor as `temperature_f`
carrying `unit: "°F"`. The gauge above each sparkline already shows
`°F` for the same metric; having the sparkline tooltip contradict the
gauge would be worse than following the plan's indicative unit list
literally. The plan description reads as a shorthand list of "the
natural unit per metric" rather than a Fahrenheit-vs-Celsius
prescription — especially given the contract is immutable and the
other four units in the list match the contract exactly.

Equivalence holds: the e2e spec asserts "a unit suffix from the
correct set per metric", which is the intent of the plan. The spec's
tooltip expectation is explicit about this swap with an inline
comment, so the evaluator's coverage audit can see the substitution.

## Simplify pass (second commit)

- Collapsed `GAUGE_TILES` + `SPARKLINE_TILES` (identical 5-tuples, only
  the field name differed) into a single `METRIC_TILES` array.
  `metric: keyof SensorsCurrent["metrics"]` is the tighter type —
  `SensorMetric` from the OpenAPI enum is a superset (dew_point_f /
  pressure_hpa are valid history metrics but not surfaced on the gauge
  envelope).
- Inlined the one-off `buildHistoryQuery` helper back into the
  `useQueries({ queries: … })` call site.
- Consolidated the two per-range dicts in the MSW handler into one
  `RANGE_SPEC` table and dropped the post-validation `as number`
  narrowings by doing the `undefined` guard on the object lookup
  result instead of the key.

## Out-of-scope concerns flagged for later

None observed. The Gauge component's aria-label contract and the
Sparkline's aria-label contract both resolve cleanly with `exact: true`
matchers once noted — no latent framework problem.
