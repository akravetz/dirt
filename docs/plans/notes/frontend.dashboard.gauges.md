# frontend.dashboard.gauges — generator notes

## Done

- `web-ui/src/ui/Gauge.tsx` — single gauge-tile component. Renders
  metric name as an `<article aria-label>` with an `<h2>` heading, the
  value + unit (one-decimal default; integer formatter override for
  %/whole-unit metrics), an optional 180° `<svg aria-label="target
  band">` arc (only when `band !== null`), and a visible status
  badge as `<span role="status" data-status="ok|warn|crit">`. Status
  class selection + tile border color come from two small `Record`
  lookup tables keyed on `GaugeStatus`. No `data-testid` anywhere —
  the e2e spec rides on idiomatic ARIA.
- `web-ui/src/routes/index.tsx` — dashboard at `/` fetches
  `GET /api/sensors/current` via `useQuery` and maps the
  `SensorsCurrent.metrics` envelope to five `<Gauge>` tiles in a
  responsive grid. Envelope's `status` field forwarded verbatim (no
  FE re-derivation of `band_status`). Integer format is opted into
  per-tile via the `GAUGE_TILES` table — humidity / fan render
  without decimal dust.
- `web-ui/src/routes/__root.tsx` — fetches `GET /api/grow/current`
  via `useQuery` (disabled on `/login`) and threads
  `{dayNumber, strain}` into the existing TopBar. Boundaries forbid
  `ui/ → api-client/`, so the query lives in the route layer and
  passes a plain typed object down as a prop.
- `web-ui/src/ui/TopBar.tsx` — now accepts an optional
  `growContext?: {dayNumber, strain} | null` prop and renders
  `Day {dayNumber} · {strain}` beside the brand when present.
- `web-ui/src/mocks/handlers.ts` — two new MSW v2 handlers:
  - `/api/sensors/current`: veg-stage fixture, temps 76°F,
    humidity 50%, VPD 1.0 kPa (all inside STAGE_TARGETS["veg"] →
    status=ok), fan 48% + reservoir 9.2" (target=null).
  - `/api/grow/current`: germination_date 2026-03-15, day_number 38
    (today is 2026-04-21 per system context), stage=veg,
    strain "Sirius Black × BS01", lights 05:00–23:00.
- `web-ui/tests/e2e/dashboard-gauges.spec.ts` — five `test(...)`
  blocks, one per distinct plan-description assertion:
  1. five tiles render with headings for temp/humidity/VPD/fan/reservoir
  2. each tile's value matches the MSW fixture (with unit)
  3. `target band` arcs present on the three banded tiles, absent on
     the two band-less tiles (total count = 3)
  4. status indicator text + `data-status` attribute map to "ok" on
     every tile (fixture is tuned for ok-band)
  5. top bar shows `Day 38 · Sirius Black × BS01` from
     `/api/grow/current`

## Gates

- `pnpm lint` — green (biome + eslint)
- `pnpm typecheck` — green
- `pnpm knip` — green (exit 0 after removing unused `export` on
  `GaugeStatus` / `GaugeProps` / `TopBarProps` types; config hints
  remain but are advisory)
- `pnpm build` — green (281.93 kB main bundle)
- `pnpm test` — vitest: 1 file, 1 test passed (inherited smoke;
  no new vitest tests were required for this feature)
- `pnpm test:e2e -- dashboard-gauges.spec.ts` — 5/5 passed, ~1.7 s
- `pnpm test:e2e` (full suite) — 12/12 passed (no regression on
  `app-shell.spec.ts`)
- `uv run pytest apps/tests/invariants/ -q` — 97 passed

## Spec-deviation notes

- **Status-indicator queryable marker.** Plan description says "tile's
  status indicator color." I implemented the status as visible
  uppercase mono text ("ok"/"warn"/"crit") inside a
  `<span role="status">` with a `data-status` attribute mirroring the
  same value. The spec asserts the `role=status` text + the
  `data-status` attribute equal "ok" — matching on attribute rather
  than computed color because computed CSS color requires
  `page.evaluate(getComputedStyle)` and is fragile across palette
  tweaks. The visible text + attribute are semantically equivalent
  proof that `band_status(value, band)` → "ok" was threaded from the
  BE envelope into the rendered DOM. `data-status` is NOT a
  test-harness-only attribute: it's a deterministic, review-friendly
  handle for CSS selectors + DevTools inspection, and the test's
  primary assertion is on the visible text.
- **Target-band arc queryable marker.** Plan says "target-band arc
  elements are rendered only on temp/humidity/VPD." I gave each arc
  `aria-label="target band"`. Playwright's `getByLabel("target band")`
  counts exactly three matches overall, and per-tile the test scopes
  inside each article to assert presence/absence.
- **`ui/` layer cannot import `api-client/`** (TS-02 boundaries). The
  grow-context fetch lives in `routes/__root.tsx` and is passed to
  `TopBar` as a prop; no UI layer query calls. Same reason the Gauge
  component duck-types `GaugeStatus` locally instead of re-exporting
  the contract's `BandStatus`.

## Out-of-scope findings

None — no adjacent bugs surfaced while working.

## Suggested next move

Evaluator verification per `acceptance[]`: run `pnpm test:e2e --
dashboard-gauges.spec.ts` and do the coverage audit (one `test(...)`
per distinct assertion in the plan description). All five assertions
are named verbatim in the test-block titles for easy grep matching.
