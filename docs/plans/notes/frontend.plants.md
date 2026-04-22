# frontend.plants cluster — generator notes

Cluster summary: implemented two composed features in order — the
dashboard plants strip and the plant-detail drawer it opens — on branch
`feat/fe/plants-cluster`. Both features land against the frozen
contract; MSW fixtures in `web-ui/src/mocks/handlers.ts` keep the
dev/e2e loop self-contained while the matching BE endpoints
(`backend.plants.list`, `backend.plants.detail`, `backend.plants.moisture`)
are built in parallel. 30 Playwright tests green across the full suite.

Shared scaffolding added in feature 1 and reused in feature 2:

- `web-ui/src/ui/plant-types.ts` — colocated `PlantCode` /
  `StickerColor` literal unions plus `STICKER_BG` / `STICKER_FILL` /
  `STICKER_STROKE` Tailwind-class lookups. Sticker palette tokens
  (`--color-sticker-{yellow,orange,pink,blue}`) added to
  `web-ui/src/styles.css` @theme.
- MSW handler for `GET /api/plants` in feature 1; handlers for
  `GET /api/plants/{code}` and `GET /api/plants/{code}/moisture` added
  in feature 2.

## 1. frontend.dashboard.plants_strip

### Done
- `web-ui/src/ui/PlantCard.tsx` — button-as-card with sticker chip
  (`span[role=img][aria-label=sticker][data-color=...]`), name, and
  soil-moisture bar rendered as an SVG `role="progressbar"` so
  `aria-valuenow` semantically encodes the fixture's `moisture_pct`
  without tripping TS-16 (no inline `style` attrs).
- `web-ui/src/ui/PlantsStrip.tsx` — region landmark
  (`section[aria-label=Plants]`) containing four `PlantCard`s in a
  responsive 1→2→4 grid.
- Composed into `web-ui/src/routes/index.tsx` under the humidifier
  duty-cycle strip.
- `web-ui/src/mocks/handlers.ts` — `GET /api/plants` fixture with four
  plants (A yellow, B orange, C pink, D blue) and distinct moisture
  values (62/48/54/66).
- `web-ui/tests/e2e/dashboard-plants-strip.spec.ts` — four `test(...)`
  blocks, one per distinct assertion in the plan description:
  1. four cards render below the sparklines
  2. each card's sticker chip colour matches the fixture's
     `sticker_color`
  3. each card's moisture bar reflects `moisture.current_pct` via
     `aria-valuenow`
  4. clicking Plant A fires `GET /api/plants/a`

### Design choices
- The "click triggers fetch" behavior is wired via the dashboard
  route's `selectedPlant` state + a conditional `useQuery` in
  `routes/index.tsx`. Flipping state from `null` → `"a"` enables the
  query, which issues the GET. This is the same pattern frontend.
  plant_detail builds on — no separate `prefetchQuery`/`useQueryClient`
  indirection. (The initial implementation used `prefetchQuery` before
  feature 2 landed; it was replaced by the `enabled`-gated `useQuery`
  when the drawer composed against the same cache entry.)
- Progressbar uses an SVG with `viewBox="0 0 100 4"` + `rect width={pct}`.
  This gives a percent-based width without an inline HTML `style` attr
  (TS-16), and the `aria-valuenow=${pct}` is the semantic handle for
  the e2e.

### Not done / deferred
- No visual-diff reference screenshot for the strip itself — the
  plan's acceptance block only lists `kind: "e2e"`. The strip's visual
  lives inside the cluster reference at `docs/plans/refs/dashboard.png`
  (captured during earlier features) which shows the four-card strip
  in context below the sparklines.

## 2. frontend.plant_detail

### Done
- `web-ui/src/ui/PlantDetail.tsx` — right-side drawer
  (`aside[role=dialog][aria-label="Plant detail"][aria-modal=true]`)
  with:
  - header: sticker + name `<h2>` + status `role="status"` tag +
    descriptive label
  - Moisture region: current value (huge Fraunces italic) + target-band
    text + irrigation count + SVG trend chart
  - Timeline region: `<ul>` of `<li aria-label="timeline entry">` rows
    (six entries per plant in the fixture)
  - optional Note section
  - footer: wiki path + Close button
- Focus-on-mount via `useRef` + `useEffect` so ESC works without an
  initial click.
- ESC handled via `onKeyDown` on the dialog (scoped handler; no
  document-level listener leaking across routes).
- `web-ui/src/mocks/handlers.ts` — `/api/plants/:code` fixture returning
  full `PlantDetail` payload (header + moisture + 6-entry timeline +
  note + wiki_path) and `/api/plants/:code/moisture` returning a
  deterministic sawtooth series + `irrigation_events_24h: 4`.
- `routes/index.tsx` wires two `useQuery`s keyed on `selectedPlant`
  (`plants.detail` + `plants.moisture`) and renders `<PlantDetail>`
  conditionally when both the selection and the detail payload are
  present. `onClose` flips `selectedPlant` back to `null`.
- `web-ui/tests/e2e/plant-detail.spec.ts` — five `test(...)` blocks,
  one per distinct assertion in the plan description:
  1. clicking Plant A's card opens the drawer
  2. header renders sticker + name + status tag from `/api/plants/a`
  3. moisture hero displays `moisture.current_pct`
  4. timeline list row count equals `response.timeline.length`
  5. pressing ESC closes the drawer

### Design choices
- The plan description says "primary/secondary tag" — I render the
  `status` enum (primary|secondary|retired) via a `STATUS_LABEL`
  lookup inside a `role="status"` span, and render the descriptive
  `label` string separately (fixture: "Primary · bushy"). The
  combination covers both readings of "tag".
- `PlantDetailPayload` is a local duck-typed interface (ui/ can't
  import api-client/ per boundaries). Drift surfaces at
  `routes/index.tsx`'s typecheck against the real generated client —
  the route is the interop seam.
- Moisture chart is drawn with a single `<path>` stroked in the plant's
  sticker colour; no axes, matching the mockup's botanical style.

### Not done / deferred
- Visual-diff (`kind: "visual"`, threshold 5%) is the evaluator's job;
  I did not capture a comparison screenshot myself. Layout follows the
  mockup (`docs/plans/refs/plant-detail-a.png`) structurally —
  sticker+name+tag header row, big italic moisture hero, chart band,
  timeline rows with date / day / text columns, note section, wiki
  path footer.
- Range switch inside the drawer: the mockup implies a fixed 24h
  window so I hard-coded `range: "24h"` on the moisture query. If a
  follow-up needs 1h/7d toggles, lift `plantRange` state alongside
  `range` in `routes/index.tsx` and plumb it through as a prop.

### Surprises
- None. The existing gauge/sparkline/humidifier components were great
  style references; following their ARIA conventions (role=region
  landmarks, named articles, no `data-testid`) made the e2e specs
  straightforward.

## Next

- BE lanes for `backend.plants.list` / `.detail` / `.moisture` need to
  match the contract shapes the MSW fixtures target. Specific fields
  the fixtures rely on and that the evaluator will audit:
  - `PlantsResponse.day` + `plants[].{code,name,sticker_color,status,
    purple,moisture_pct,moisture_ts}`
  - `PlantDetail.{code,name,sticker_color,status,purple,day,label,
    moisture,timeline,note,wiki_path}` — `timeline[].{date,day,text,
    highlight}`, `note.{text,updated}`
  - `PlantMoistureHistory.{code,range,unit,target,points,
    irrigation_events_24h}`
- When BE lands and contract_status.json is updated to remove
  `expected_missing` for the three plants endpoints, delete the FE MSW
  handlers (or keep them as dev-loop fallbacks — see
  `docs/references/msw-v2/INDEX.md` §Dirt-specific wiring on when to
  remove fixtures).
