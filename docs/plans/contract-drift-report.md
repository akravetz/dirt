# Contract Drift Report — 2026-04-22

**Method:** captured every safe GET from the live dirt-web backend
(:8001) via `scripts/capture-fixtures`, landed the results under
`web-ui/src/mocks/fixtures/`, and refactored `web-ui/src/mocks/handlers.ts`
to return the captured bodies for 200 paths (error branches and stateful
mutation handlers preserved). The `git diff` of `handlers.ts` + the new
`fixtures/` tree is the primary drift artifact.

**Prep incident:** `dirt-hwd` had been in `failed` state since ~02:05
MDT — a downstream effect of the camera.log disk-fill incident (PG ran
out of space, panicked into recovery, and hwd tripped systemd's
restart-rate limit). Manually restarted before capture so the sensor /
humidifier / device readings reflect a live system.

**Scope not reconciled in this pass:** /api/wiki/{tree,file,search}. The
MSW handlers are driven by an internal PAGES registry with backlink
derivation and search ranking; replacing them with captured fixtures
would remove the dynamism. Captures are recorded under `fixtures/wiki.*`
for reference; drift is noted below but not wired into `handlers.ts`.

**How to use this doc:** the drift table below classifies each endpoint
by drift kind. Playwright failures from `pnpm --dir web-ui test:e2e`
should be triaged against this table: *shape* drift items may require FE
code fixes; *value* drift items only require test loosening.

## Summary

| Endpoint | Drift class | Notes |
| --- | --- | --- |
| `/api/auth/login` | none | creds unchanged; handler keeps gate logic |
| `/api/auth/logout` | none | |
| `/api/auth/me` | none | response shape `{username}` unchanged |
| `/api/grow/current` | value-only | `day_number` advances daily; `minutes_until_*` are **floats** (842.4, 1200.4) where MSW had ints (360, 0) |
| `/api/sensors/current` | value-only | `target` arrays are `[70.0, 82.0]` (floats) vs MSW `[70, 82]` (ints); semantically identical — `target` is typed as `[number, number]` |
| `/api/sensors/history` | value-only | point counts differ per range (1h→8, 7d→143 vs MSW's 12/168); shape `{range,metric,unit,points}` unchanged |
| `/api/humidifier/state` | value-only | `duration_s`, `cycles_24h` reflect a just-restarted system (149s / 1 cycle vs MSW's 7200s / 8 cycles) |
| `/api/humidifier/history` | value-only | point counts differ per range |
| `/api/plants` | value-only (MSW coverage gap) | `status` enum variant **"secondary"** appears for B+C; FE already types the full enum in `PlantDetail.tsx:41` — MSW simply hadn't modeled it. Not a shape drift — a fixture variety gap. |
| `/api/plants/:code` | value + behavioral | `timeline[].text` and `note.text` contain **markdown** (`**bold**`, `[link](url)`) in real data, plain text in MSW. FE renders these as plain text (`PlantDetail.tsx:200, 211`) — user-visible bug. `wiki_path` format differs (`"wiki/plants/plant-a.md"` vs `"/wiki/plants/a.md"`) but FE only displays it as text; no routing dependency. |
| `/api/plants/:code/moisture` | **behavioral** | 7d responses contain raw samples, **~17,000 points per plant** (1.3 MiB JSON). MSW had 168 aggregated. This may be a BE implementation oversight (should aggregate) or a legitimate choice (raw data → FE aggregates). Either way, the FE chart component gets a very different dataset. |
| `/api/system/devices` | value-only | device names + count differ; all shapes identical. Current capture has no `"warn"` status device — MSW intentionally included one for render coverage; that code path is now uncovered in MSW tests. |
| `/api/feed/live.jpg` | not captured | binary; out of scope |
| `/api/ptz/state` | value-only | `connected: false` in capture (camera daemon reachable? verify) vs MSW's `true`; preset coordinates are real (yaw: -25, pitch: -50, zoom: 1.0 for overview) vs MSW's placeholders. |
| `/api/ptz/preset/:id` | n/a | mutation handler, not refreshed |
| `/api/ptz/look` | n/a | mutation handler, not refreshed |
| `/api/ptz/zoom` | n/a | mutation handler, not refreshed |
| `/api/wiki/tree` | **value + one structural** | Real has 3 root files (`index.md`, `log.md`, `overview.md`) vs MSW's 2 (`log.md` missing from MSW). Real has different folders (`adrs/`, `concepts/`, `hardware/`, `plants/`, `daily/`, etc) vs MSW's minimal 3-folder sample. Shape `{tree:[...]}` unchanged; folder/file node shapes unchanged. |
| `/api/wiki/file` | value-only | Same 6-key shape `{path, title, subtitle, frontmatter, body_markdown, backlinks}`. Real backlinks are substantive (10+ entries); MSW's naive derivation produced few. |
| `/api/wiki/search` | value-only | Shape `{q, results:[...]}` unchanged. Real search surfaces different pages. |

## Notable findings

### 1. `PlantStatus` enum has `"secondary"` — not modeled in MSW

`plants.json` captures real plants B and C as `status: "secondary"`; MSW
only used `"primary"`. Check whether `routes/index.tsx` (dashboard strip)
and `routes/plants.$code.tsx` (detail page) handle this enum variant.
Spec coverage in `dashboard-plants-strip.spec.ts` was likely testing
only "primary" styling.

**Action:** grep for usages of `status === "primary"` in FE consumers;
add a branch for `"secondary"` if one doesn't exist.

### 2. `wiki_path` leading-slash mismatch

- Real BE: `"wiki/plants/plant-a.md"`
- MSW (previous): `"/wiki/plants/a.md"`

Two differences: no leading slash, and the filename is `plant-a.md` not
`a.md`. If FE code does `path.startsWith('/wiki/')` it's broken against
the real BE. If FE routes to `/wiki/${plant.code}.md` it will 404.

**Action:** search FE for `wiki_path` usage; update routing to use the
captured format.

### 3. Markdown in `PlantDetail.timeline[].text` and `note.text`

Real content: `"**Topped above node 4**; 5th node was emerging..."`,
`"See [2026-04-20](../daily/2026-04-20.md)."`.
MSW content: plain text, no markdown.

If the FE renders these as plain text, users see `**bold**` literally.
If it renders markdown, MSW tests weren't exercising the renderer.

**Action:** check `routes/plants.$code.tsx` for how timeline text and
the note are rendered; if markdown, good (now better-exercised); if
plain, either BE should strip markdown before returning or FE should
render markdown.

### 4. `minutes_until_*` are floats

`grow.current.lights.minutes_until_off = 842.4758936`. MSW had `360`
(int). If any FE code does integer math on these fields (e.g. `%`,
`toFixed(0)` without conversion) it still works. If it uses them as
display strings without formatting, users see ugly decimals. Contract
type is likely `number` — not a shape drift, but worth checking the
`routes/index.tsx` banner render.

### 5. 7-day plant moisture is 17k raw samples

`plants.c.moisture.7d.json` is 1.3 MiB with 17,114 points. MSW had 168
aggregated points. If the FE chart loads all points into memory and
renders them without downsampling, rendering will be slow and janky
over a 7d range. Either BE should aggregate server-side or FE needs a
decimation/windowing step.

**Action:** file a backend follow-up (`sensorreading` query should
time-bucket for 7d). This is the most impactful finding in the audit.

### 6. `dirt-hwd` restart resilience gap

Not strictly a contract issue, but the audit surfaced it: hwd's systemd
unit has `Restart=on-failure` with an aggressive rate limit. Any PG
hiccup >5s (recovery, upgrade, maintenance) will leave hwd in `failed`
until manual intervention. Recommend widening `StartLimitInterval` /
`RestartSec`, or adding a watchdog-style external probe. Separate from
the webapp rewrite; file under ops follow-ups.

## Playwright verdict (task 5)

Ran `pnpm --dir web-ui test:e2e` against the refreshed MSW. Result:
**33 pass / 12 fail.** Every failure is value-coupling, not shape drift —
confirming the BE↔MSW↔FE contract is shape-consistent.

Failing specs, all asserting hard-coded MSW fixture values the live BE
does not reproduce:

| Spec | Expected (MSW) | Received (live) | Class |
| --- | --- | --- | --- |
| `dashboard-gauges: tile values match` | "76.0" / "50" / "1.0" / "48" / "9.2" | 75.4 / 46.2 / 1.62 / 48.4 / 4.2 | value |
| `dashboard-gauges: all tiles "ok"` | ok × 5 | ok / ok / **crit** / ok / ok | value |
| `dashboard-gauges: Day 38` | "Day 38" | "Day 39" | value |
| `dashboard-humidifier: duration since last transition` | 7200s | 149s (just restarted) | value |
| `dashboard-humidifier: cycles_24h == 8` | 8 | 1 | value |
| `dashboard-humidifier: 12 duty rectangles (24h)` | 12 | 2 | value |
| `dashboard-humidifier: range switch refetches` | 12 initial / N after switch | 2 / N after switch | value |
| `dashboard-plants-strip: moisture bar == 62%` | 62 | 57 | value |
| `dashboard-system-table: warn badge` | expected a "warn" row | none (real data has no warn) | value (MSW coverage gap) |
| `plant-detail: label == "Primary · bushy"` | "Primary · bushy" | "Purple Keeper Candidate" | value |
| `plant-detail: moisture == 62` | 62 | 57 | value |
| `plant-detail: timeline length == 6` | 6 | 15 | value (spec hardcodes, should use `.length`) |

**Shape drift: 0.** This is the core result — every FE→API contract is
intact. The rewrite's OpenAPI-anchored parallel generation worked: BE
and MSW were built against the same shapes and still agree.

**Behavioral drift found outside the spec suite** (not triggered by any
test, but real):

- **Markdown rendered as plain text.** Real `/api/plants/:code` returns
  `timeline[].text` and `note.text` containing `**bold**` and
  `[link](url)` markdown. `web-ui/src/ui/PlantDetail.tsx:200, 211`
  renders both as `{text}` — users see the asterisks literally. No spec
  catches this because MSW fixtures were plain text.
- **7d plant moisture is un-aggregated.** `/api/plants/:code/moisture?range=7d`
  returns ~17,000 raw samples (1.3 MiB JSON). FE chart ingests all of
  them. No spec catches this because MSW fixtures had 168 aggregated
  points.

Both are drift-revealed issues. The first is a small BE or FE bug (strip
markdown at BE, or render markdown at FE). The second is a BE follow-up
(time-bucket samples server-side, keep response size bounded).

**Action taken this session:** None on the failing specs or on the
behavioral findings — scope was audit only. The 12 value-coupled specs
need to be loosened from "==" assertions on fixture values to shape-and-
presence assertions. That's spec-maintenance work, not drift remediation.

## Open items (not reconciled in this pass)

- **Wiki handlers** still run the local PAGES registry. Captured fixtures
  (`wiki.tree.json`, `wiki.file.*.json`, `wiki.search.*.json`) are in
  place for reference. Next audit could either (a) ingest the captured
  tree + file bodies into a new registry imported from JSON, or (b)
  replace the ranker with a "hit fixture for exact query, 404 otherwise"
  model. Recommend (a) — preserves interactive search behavior.
- **Playwright value-coupled specs** (`"Day 38"`, `"76.0"`, etc.) will
  fail against refreshed fixtures. Task 5 of this audit: run specs,
  triage failures as shape (fix FE) vs value (loosen spec) vs
  behavioral (fix BE or FE).
- **Error branches** (422/404/400) were not captured. The MSW handlers
  still return the same inline error shapes they always did. If BE
  error-body shapes have drifted, we won't catch it here. Low priority
  — error-body drift rarely matters, and the bounded set is easy to
  grep when needed.
