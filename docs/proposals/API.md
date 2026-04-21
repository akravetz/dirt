# API Proposal — webapp-v1

Scope: JSON API that the Vite/React SPA in `web-ui/` consumes to reproduce the `debug/webapp.zip` mockup against real backend data. This doc is a first-pass sketch. Open questions are marked **?**.

Not in scope here: OpenAPI YAML (will be generated from this after sign-off), FastAPI route files (`apps/web/src/dirt_web/api/*.py` rewrites), TS client generation.

---

## Conventions

**Prefix.** All endpoints live under `/api/*`. The old HTMX/template routes (`/login`, `/feed/image`, `/feed/status`, `/sensors/current`) go away — they return HTML fragments that the SPA doesn't need.

**Auth.** Keep the cookie-session middleware in `apps/web/src/dirt_web/auth.py` — it's already in place, runs on every non-`/mcp`, non-`/api/ingest` request, and redirects to `/login` on 401. For the SPA we change the *login* path to JSON (no redirect) but leave the cookie contract identical. The `AuthMiddleware` will stop redirecting for `/api/*` paths and instead return `401 {"error":"unauthorized"}`. SPA catches the 401 and routes to `/login`. `/api/auth/*` itself is public (no auth required).

**Response envelope.** Keep it flat — no `{data: ...}` wrapper. Errors follow FastAPI's default `{"detail": "..."}` so existing `HTTPException` calls continue to work.

**Timestamps.** ISO 8601 with `Z` suffix (UTC). No naive datetimes on the wire.

**Ranges.** Any history endpoint takes `?range=1h|24h|7d` (mirrors the mockup's three-button switcher). `30d` stays supported server-side but isn't in the UI.

**Paths.** Mockup uses `wiki/foo/bar.md` (with `wiki/` prefix). The FS-backed endpoints normalize this — accept both `foo/bar.md` and `wiki/foo/bar.md`, reject any path that escapes `wiki/`.

---

## Summary table

| Endpoint | Method | Today | Action |
|---|---|---|---|
| `/api/auth/login` | POST | form-post `/login` returns HTML | **ADD** (JSON) |
| `/api/auth/logout` | POST | GET `/logout` redirects | **MODIFY** (method + JSON) |
| `/api/auth/me` | GET | — | **ADD** |
| `/api/grow/current` | GET | — | **ADD** |
| `/api/sensors/current` | GET | `/sensors/current` returns HTML fragment | **MODIFY** (JSON, envelope with target+status) |
| `/api/sensors/history` | GET | `/api/sensors/readings` exists | **MODIFY** (rename, param, shape) |
| `/api/humidifier/state` | GET | — | **ADD** |
| `/api/humidifier/history` | GET | — | **ADD** |
| `/api/plants` | GET | — | **ADD** |
| `/api/plants/{code}` | GET | — | **ADD** |
| `/api/plants/{code}/moisture` | GET | — | **ADD** |
| `/api/system/devices` | GET | — | **ADD** |
| `/api/feed/live.jpg` | GET | `/feed/live` | **MODIFY** (rename to `.jpg`, keep behavior) |
| `/api/feed/snapshot/latest` | GET | `/api/snapshots/latest` | **MODIFY** (rename) |
| `/api/ptz/state` | GET | — | **ADD** |
| `/api/ptz/preset/{id}` | POST | — | **ADD** |
| `/api/ptz/look` | POST | — | **ADD** |
| `/api/ptz/zoom` | POST | — | **ADD** |
| `/api/wiki/tree` | GET | — | **ADD** |
| `/api/wiki/file` | GET | — | **ADD** |
| `/api/wiki/search` | GET | — | **ADD** |
| `/feed/image` | GET | HTMX fragment | **REMOVE** |
| `/feed/status` | GET | HTMX fragment | **REMOVE** |
| `/login`, `/logout` (HTML) | GET/POST | Jinja template | **REMOVE** (SPA owns /login route) |
| `/` (index.html) | GET | Jinja dashboard | **REMOVE** (SPA shell served by Vite build) |

`/api/ingest/sensors` (on `dirt-hwd` :8000) is not touched.  
`/mcp` mount is not touched.

---

## 1. Auth — `/api/auth/*`

### POST /api/auth/login
```jsonc
// request
{
  "username": "alex",
  "password": "..."
}
// 200
{
  "username": "alex"
}
// 401
{ "detail": "invalid credentials" }
```
Sets `dirt_session` cookie (httponly, samesite=lax) on success. Cookie shape is unchanged from today.

### POST /api/auth/logout
```jsonc
// request: empty body
// 204 no content; clears dirt_session cookie
```

### GET /api/auth/me
```jsonc
// 200
{ "username": "alex" }
// 401 if no valid session
```

**FE boot lifecycle.** On app mount, the SPA calls `GET /api/auth/me` once. 200 → hydrate authed state and render the tab router; 401 → route to `/login`. Do **not** persist auth state in `localStorage` (the mockup's `dirt-auth` flag is a prototyping shortcut). The cookie is the sole source of truth; TS-09 restricts `localStorage` access to `shared/storage.ts` anyway.

---

## 2. Grow identity — `/api/grow/current`

Drives the top-bar tag line "Day 29 · Sirius Black × BS01". Requires auth.

**Login field-notes block is fully static / hardcoded in the SPA.** The login page is pre-auth and mustn't depend on this endpoint. The mockup's field-notes copy (`grow / day / plants / loc / agent · Claudia · listening`) is branding, not live data — keep it as a static constant in the login component. If it ever needs to change with the grow, bump the constant during a grow flip.

### GET /api/grow/current
```jsonc
{
  "germination_date": "2026-03-15",
  "flower_start_date": null,              // or "2026-06-01"
  "day_number": 36,                        // = today - germination_date + 1
  "grow_week_number": 6,                   // 1-indexed since germination_date (week 1 = days 1–7)
  "flower_week_number": null,              // 1-indexed since flower_start_date, or null while in veg
  "stage": "veg",                          // "veg" | "flower_early" | "flower_late"
  "strain": "Sirius Black × BS01",
  "location": "Denver, MT · closet tent",
  "plant_count": 4,
  "lights": {
    "on": true,
    "on_local": "05:00:00",
    "off_local": "23:00:00",
    "minutes_until_off": 258
  }
}
```

Reads today's stage/day from `dirt_shared.services.grow_state`. Strain + location + plant_count live on `growstate` (resolved per data_model proposal). `GrowCurrentPayload.grow_week_number` + `flower_week_number` are already computed by `get_grow_current_payload()` — the BE endpoint just threads the payload through.

---

## 3. Sensors — `/api/sensors/*`

### GET /api/sensors/current

Drives the five dashboard gauges + humidifier tile header. The mockup's `SENSORS` array is the source of truth for which metrics appear.

```jsonc
{
  "ts": "2026-04-19T22:45:25Z",
  "stale": false,                        // is_sensor_stale() — sensor stuck flag
  "metrics": {
    "temperature_f": {
      "value": 72.4,
      "unit": "°F",
      "target": [70, 82],                // null if no band for this stage
      "status": "ok",                    // "ok" | "warn" | "crit"
      "ts": "2026-04-19T22:45:25Z"       // per-metric ts (dew_point might lag)
    },
    "humidity_pct": { "value": 65, "unit": "%", "target": [45, 55], "status": "warn", "ts": "..." },
    "vpd_kpa":      { "value": 0.94, "unit": "kPa", "target": [0.8, 1.2], "status": "ok", "ts": "..." },
    "fan_pct":      { "value": 48, "unit": "%", "target": null, "status": "ok", "ts": "..." },
    "reservoir_in": { "value": 6.2, "unit": "in", "target": null, "status": "ok", "ts": "..." }
  }
}
```

Notes:
- Target bands come from `STAGE_TARGETS` in `grow_state.py` for `temperature_f / humidity_pct / vpd_kpa`. `fan_pct` and `reservoir_in` have no bands today.
- `status` is server-computed: `ok` if in band, `warn` if within ±50% of band width outside, `crit` if further. Makes the client a pure renderer — no threshold drift between the two.
- `fan_pct` and `reservoir_in` are **not in the DB today** — see data_model proposal. Initial plan: mock with stable values (48 %, 6.2 in) behind a server-side `MockSensorProvider` that the OpenAPI contract treats as real.

### GET /api/sensors/history?range=1h|24h|7d&metric=...

Drives the five sparklines (single-metric each) *and* the dashboard page's shared crosshair hover. The mockup does one request per sparkline but we can keep it flexible:

```jsonc
// GET /api/sensors/history?range=24h&metric=temperature_f
{
  "range": "24h",
  "metric": "temperature_f",
  "unit": "°F",
  "points": [
    { "ts": "2026-04-18T23:00:00Z", "value": 71.2 },
    { "ts": "2026-04-18T23:05:00Z", "value": 71.5 },
    ...
  ]
}
```

Allowed `metric` values: `temperature_f | humidity_pct | vpd_kpa | dew_point_f | pressure_hpa | fan_pct | reservoir_in`.

Bucketing matches today's `_BUCKET_SQL`: raw for 1h, 5-min avg for 24h, hourly for 7d.

**Delta from today.** Today's `/api/sensors/readings` returns every metric in one payload with `{labels, values}` arrays. New shape is one-metric-at-a-time with `{ts, value}` point arrays. One N+1 concern (five requests per sparkline panel) — worth accepting because the sparklines also re-fetch independently on the range switch and a combined endpoint forces them all through one loader.

**Open question (?):** Do we also want a bulk variant `GET /api/sensors/history?range=24h&metric=temperature_f,humidity_pct,...` for the dashboard's initial load? Lean: no — add if profiling shows it's needed.

---

## 4. Humidifier — `/api/humidifier/*`

The mockup shows a binary on/off tile + a cycle-count header + a duty-cycle strip chart. Today, `humidifier_on` (0/1) is already being written to `sensorreading` every loop tick (see the `GROUP BY` output: 2,116 rows). We've got the data, we just need to expose it.

### GET /api/humidifier/state
```jsonc
{
  "on": true,
  "since": "2026-04-19T22:41:13Z",       // last transition timestamp
  "duration_s": 252,                      // time since `since`
  "cycles_24h": 18,                       // count of off→on transitions in last 24h
  "ts": "2026-04-19T22:45:25Z"
}
```
Computed from `sensorreading WHERE metric='humidifier_on'` by counting transitions.

### GET /api/humidifier/history?range=1h|24h|7d
```jsonc
{
  "range": "24h",
  "points": [
    { "ts": "2026-04-18T23:00:00Z", "on": false },
    { "ts": "2026-04-18T23:12:04Z", "on": true },
    ...
  ]
}
```
Returns transitions only (not sampled state at every bucket) — the UI rectangles render from `(ts, on)` pairs, treating each pair as "on from ts until next ts".

---

## 5. Plants — `/api/plants/*`

Drives the dashboard plants strip (A–D cards) and the plant-detail drawer.

### GET /api/plants
```jsonc
{
  "day": 36,
  "plants": [
    {
      "code": "a",                       // stable 'a'/'b'/'c'/'d' — use in URLs
      "name": "Plant A",
      "sticker_color": "yellow",
      "status": "primary",               // "primary" | "secondary" | "retired"
      "purple": true,
      "moisture_pct": 62,                 // latest calibrated pct (null if no cal)
      "moisture_ts": "2026-04-19T22:45:25Z"
    },
    { "code": "b", "name": "Plant B", "sticker_color": "orange", "status": "secondary", "purple": false, "moisture_pct": 48, "moisture_ts": "..." },
    { "code": "c", "name": "Plant C", "sticker_color": "pink", "status": "secondary", "purple": false, "moisture_pct": 54, "moisture_ts": "..." },
    { "code": "d", "name": "Plant D", "sticker_color": "blue", "status": "primary", "purple": true, "moisture_pct": 66, "moisture_ts": "..." }
  ]
}
```

`code` is the stable lowercase letter and the URL path param for `/api/plants/{code}`. The surrogate `plant.id` bigint is DB-internal — never appears on the wire. Moisture pct comes from the `sensorreading soil_moisture_raw` + `sensorcalibration` join.

### GET /api/plants/{code}

Full plant-detail-drawer payload. `code` is `a|b|c|d`.

```jsonc
{
  "code": "a",
  "name": "Plant A",
  "sticker_color": "yellow",
  "status": "primary",
  "purple": true,
  "day": 36,
  "label": "Purple Keeper Candidate",   // tagline shown in drawer header

  "moisture": {
    "current_pct": 62,
    "target": [55, 70],                  // soil moisture target band
    "status": "ok",                      // same ok|warn|crit
    "ts": "2026-04-19T22:45:25Z"
  },

  "timeline": [
    { "date": "2026-03-27", "day": 13, "text": "Pre-transplant; 2–3 true leaf sets", "highlight": false },
    { "date": "2026-04-11", "day": 28, "text": "Topped above node 4", "highlight": true },
    ...
  ],

  "note": {
    "text": "Seven days post-topping, Plant A shows vigorous multi-branch canopy with clean medium-dark green leaves...",
    "updated": "2026-04-18"
  },

  "wiki_path": "wiki/plants/plant-a.md"
}
```

**Source of truth:** `wiki/plants/plant-{code}.md` is the agent-maintained plant page. `plant_detail.get_plant_detail(code)` parses its frontmatter + `## Timeline` bullet list + first paragraph of `## Current State` (used for the drawer's bottom note). `moisture.*` and `day` come from DB-live data joined by the endpoint. The drawer has no vitals table — the mockup never rendered one, and the wiki has no structured pH / distance / node-count source yet.

**Open question (?):** Do we want to *mirror* plant-wiki data into SQL (for fast queries + avoid parsing markdown on every hit), or parse-on-read? Lean: parse-on-read + short in-memory TTL cache. The wiki updates once a day at 14:00 MDT — cache invalidation is trivial.

### GET /api/plants/{code}/moisture?range=1h|24h|7d

Drives the plant-detail-drawer moisture chart.

```jsonc
{
  "code": "a",
  "range": "24h",
  "unit": "%",
  "target": [55, 70],
  "points": [
    { "ts": "2026-04-18T23:00:00Z", "value": 68.2 },
    ...
  ],
  "irrigation_events_24h": 12           // count of upward steps >= threshold (autopot cycle heuristic)
}
```

Derived from `sensorreading WHERE location='plant-a' AND metric='soil_moisture_raw'` + calibration. Irrigation event count is a simple "how many times did moisture jump up by >N%" heuristic — can be mocked in V1.

---

## 6. System — `/api/system/devices`

Drives the dashboard system table (8 rows in the mockup).

### GET /api/system/devices
```jsonc
{
  "ts": "2026-04-19T22:45:25Z",
  "devices": [
    { "name": "Arduino Nano + DHT22",      "kind": "env_sensor",   "status": "ok",     "last_seen": "2026-04-19T22:45:25Z" },
    { "name": "ESP32-C3 · plant_a",         "kind": "moisture_node","status": "ok",     "last_seen": "2026-04-19T22:45:25Z" },
    { "name": "ESP32-C3 · plant_b",         "kind": "moisture_node","status": "ok",     "last_seen": "..." },
    { "name": "ESP32-C3 · plant_c",         "kind": "moisture_node","status": "ok",     "last_seen": "..." },
    { "name": "ESP32-C3 · plant_d",         "kind": "moisture_node","status": "ok",     "last_seen": "..." },
    { "name": "OBSBOT Tiny 2 Lite",         "kind": "camera",       "status": "ok",     "last_seen": "2026-04-19T22:45:20Z" },
    { "name": "Jabra Speak 410 (Claudia)",  "kind": "voice",        "status": "listening","last_seen": "2026-04-19T22:45:10Z" },
    { "name": "Humidifier (Kasa EP10)",     "kind": "actuator",     "status": "warn",   "last_seen": "2026-04-19T22:45:23Z", "note": "not deployed" }
  ]
}
```

Sources:
- Env sensor (Arduino) → check the most recent `sensorreading WHERE metric='temperature_f' AND source='arduino'`.
- ESP32 plant nodes → existing `sensornode` table. `status=ok` if `last_seen < 2 min ago`, `warn` if `< 5 min`, `offline` otherwise.
- Camera → query `dirt-camera` daemon socket `get_state` and check `camera_connected`.
- Jabra → **not tracked today**. Mock `listening` if `dirt-voice.service` is active. See data_model proposal.
- Humidifier → check that the Kasa device is reachable; status comes from the most recent `humidifier` log stream event (have `reason` → if `failsafe_stale_sensor`, show warn).

Status taxonomy: `ok | listening | warn | offline` (listening is just ok+aria label; could collapse).

---

## 7. Live feed — `/api/feed/*`

### GET /api/feed/live.jpg

Returns a single JPEG. SPA refreshes via `<img src=".../live.jpg?t={{now}}">` on an interval (mockup picks 5–15s; we'll say 10s). No MJPEG stream — the existing one-shot capture matches today's `/feed/live` behavior.

```
200 Content-Type: image/jpeg
503 if camera daemon unreachable
```

**Rename:** today's `/feed/live` becomes `/api/feed/live.jpg`. The `.jpg` suffix helps the browser cache/refresh dance. The HTMX-fragment endpoints `/feed/image` and `/feed/status` are deleted.

### GET /api/feed/snapshot/latest

Returns the most recent archived snapshot from disk (today's `/api/snapshots/latest`, renamed).

```
200 Content-Type: image/jpeg
404 if no snapshots yet
```

---

## 8. PTZ — `/api/ptz/*`

Thin HTTP wrapper around `scripts/camera` (reality: we call the daemon socket from Python, same as `dirt_shared.services.capture._daemon_rpc`). The mockup is locked to click-to-look, so we don't need a `nudge` endpoint — but we add `look` (normalized click) and keep `zoom` + `preset` for completeness.

### GET /api/ptz/state
```jsonc
{
  "connected": true,
  "yaw": -55,                  // motor-frame degrees
  "pitch": -38,
  "zoom": 1.5,
  "preset": "plant_a",         // null if not at a preset (tolerance ~2°)
  "presets": [                 // static list — hard to change at runtime
    { "id": "overview", "label": "Overview", "description": "wide · full tent",            "yaw": 0,   "pitch": -10, "zoom": 1.0 },
    { "id": "plant_a",  "label": "Plant A",  "description": "Plant A close-up (yellow)",  "yaw": -55, "pitch": -38, "zoom": 1.5, "sticker_color": "yellow" },
    { "id": "plant_b",  "label": "Plant B",  "description": "...",                         "yaw": -20, "pitch": -40, "zoom": 1.5, "sticker_color": "orange" },
    { "id": "plant_c",  "label": "Plant C",  "description": "...",                         "yaw":  20, "pitch": -40, "zoom": 1.5, "sticker_color": "pink" },
    { "id": "plant_d",  "label": "Plant D",  "description": "...",                         "yaw":  55, "pitch": -38, "zoom": 1.5, "sticker_color": "blue" }
  ]
}
```
Reads `~/.config/dirt/camera.json` for the preset list (keep it in sync with the file; don't duplicate in code). `yaw`/`pitch` are motor-frame degrees, same axis convention as the top-level `yaw`/`pitch` fields; the FE uses them for the preset-row hint text (`y=-55° p=-38° z=1.5×`).

### POST /api/ptz/preset/{id}
```jsonc
// request: empty body
// 200
{ "ok": true, "preset": "plant_a", "yaw": -55, "pitch": -38, "zoom": 1.5 }
// 404
{ "detail": "unknown preset 'foo'" }
```

### POST /api/ptz/look

Click-to-look: re-centers the gimbal based on a normalized click point on the video frame.

```jsonc
// request — xy are -0.5..0.5, origin = frame center.
// UI computes: xy = (click - rect.center) / rect.size
{ "x": 0.12, "y": -0.08 }

// 200
{ "ok": true, "yaw": -47.8, "pitch": -34.8, "zoom": 1.5, "preset": null }
```

Server math: `yaw_delta = x * 60°, pitch_delta = y * 40°` — mirrors what the mockup does client-side. Server-side lets us keep a single source for the motion model and apply daemon limits uniformly.

### POST /api/ptz/zoom
```jsonc
// Absolute form:
{ "zoom": 1.8 }
// Relative form (alternative):
{ "delta": 0.2 }

// 200
{ "ok": true, "zoom": 1.8 }
// 400 if both or neither provided
```

---

## 9. Wiki — `/api/wiki/*`

Filesystem-backed (not DB). Server reads from `<repo>/wiki/`. All paths are normalized and rejected if they escape `wiki/`.

### GET /api/wiki/tree

Drives the sidebar file tree.

```jsonc
{
  "tree": [
    {
      "type": "folder",
      "name": "overview",
      "children": [
        { "type": "file", "name": "overview.md", "path": "wiki/overview.md", "title": "Grow Overview" },
        { "type": "file", "name": "index.md",    "path": "wiki/index.md",    "title": "Wiki Index" }
      ]
    },
    {
      "type": "folder",
      "name": "plants",
      "children": [
        { "type": "file", "name": "plant-a.md", "path": "wiki/plants/plant-a.md", "title": "Plant A", "sticker_color": "yellow" },
        ...
      ]
    },
    ...
  ]
}
```

Walks `wiki/` on disk (excludes `CLAUDE.md` and hidden files); extracts `title` from markdown frontmatter (stripping the `type: plant|concept|...` prefix if present — `"Plant A — Purple Keeper Candidate"` becomes just `"Plant A"` for plant pages, because the sidebar has limited width; we can adjust in iteration).

### GET /api/wiki/file?path=wiki/plants/plant-a.md

Drives the main pane.

```jsonc
{
  "path": "wiki/plants/plant-a.md",
  "title": "Plant A — Purple Keeper Candidate",
  "subtitle": "Formerly labeled Plant 1 in early documentation.", // optional; parsed from first italic line
  "frontmatter": {
    "title": "Plant A — Purple Keeper Candidate",
    "type": "plant",
    "sources": ["raw/chat-history/all-chat-summary.md"],
    "related": ["wiki/concepts/anthocyanin.md", "wiki/concepts/lst.md"],
    "created": "2026-04-06",
    "updated": "2026-04-18"
  },
  "body_markdown": "# Plant A\n\n*Formerly labeled...\n\n## Current State\n\n...",
  "backlinks": [                        // files that link back to this one
    { "path": "wiki/daily/2026-04-18.md", "title": "2026-04-18 · d35" }
  ]
}
```

**Key decision:** server returns *raw markdown* in `body_markdown` — the SPA renders it with a JS markdown library (e.g. `react-markdown`). This is simpler than a pre-rendered AST payload, and it lets the SPA re-implement link interception (intercept `wiki/*.md` clicks → client-side route).

Backlinks are computed by a grep pass across all `wiki/*.md` files for `](./... <path>)` or `related: [..., wiki/<path>, ...]`. Cache aggressively.

**FE note — drop the `lint ✓` footer badge.** The mockup's wiki doc footer renders `sources: ... · 3 backlinks · lint ✓`. Keep `sources` (from `frontmatter.sources`) and the backlinks count (from `backlinks.length`). Drop the `lint ✓` badge — no API field backs it and we're not plumbing lint status per file in V1.

### GET /api/wiki/search?q=...

Drives the Cmd+K palette.

```jsonc
{
  "q": "topping",
  "results": [
    {
      "path": "wiki/concepts/topping.md",
      "title": "Topping",
      "match_type": "title",             // "title" | "path" | "content"
      "snippet": null
    },
    {
      "path": "wiki/plants/plant-a.md",
      "title": "Plant A — Purple Keeper Candidate",
      "match_type": "content",
      "snippet": "...Topped above node 4; 5th node was emerging..."
    }
  ]
}
```

V1 implementation: naive substring scan over filenames + markdown bodies. ~70 files, will complete in single-digit ms. If that changes, swap in Postgres FTS via a `wiki_file(path, title, body_tsv tsvector)` materialized table.

**Open question (?):** Fuzzy match? Lean: no in V1 — mockup's search text is literal.

**FE note — Cmd+K empty-state "recent".** The mockup shows recent files as the empty-state list. Track recents client-side via `shared/storage.ts` (TS-09 restricts `localStorage` to this module) — push `path` on every wiki-file open, cap at the last 10, dedupe by path. No API field for this. Do not send `?q=` with an empty string to the server; short-circuit the recents list locally.

---

## 10. Routes to remove

- `GET /login` (Jinja template) — SPA owns this route; Vite build serves the HTML shell at `/login` via a SPA fallback.
- `POST /login` (form-post) — replaced by `POST /api/auth/login`.
- `GET /logout` (302 redirect) — replaced by `POST /api/auth/logout`.
- `GET /` (Jinja dashboard) — replaced by SPA shell at `/` with route `/dashboard`.
- `GET /feed/live` — renamed to `/api/feed/live.jpg`.
- `GET /feed/image` (HTMX fragment) — deleted; `<img>` handles refresh itself.
- `GET /feed/status` (HTMX fragment) — deleted; timestamp rendered client-side.
- `GET /sensors/current` (HTMX fragment) — replaced by `GET /api/sensors/current` (JSON).
- `GET /api/sensors/readings` — renamed to `GET /api/sensors/history` with per-metric param.
- `GET /api/snapshots/latest` — renamed to `GET /api/feed/snapshot/latest`.

The cookie-session middleware stays; the `/api/ingest/sensors` endpoint (on `dirt-hwd` :8000) stays; the `/mcp` mount stays.

---

## 11. Cross-cutting concerns

### Caching headers
- `GET /api/feed/live.jpg`: `Cache-Control: no-store`.
- `GET /api/sensors/current`, `/api/humidifier/state`, `/api/ptz/state`, `/api/system/devices`: `Cache-Control: no-store`.
- `GET /api/wiki/*`: `ETag` based on mtime of the file (tree uses a rollup hash of all mtimes).
- `GET /api/sensors/history`, `/api/humidifier/history`, `/api/plants/{code}/moisture`: short `Cache-Control: public, max-age=30` — the data bucket boundaries are coarser than that.

### Errors
Everything uses FastAPI's `HTTPException` → `{"detail": "..."}`. HTTP codes:
- 400 for bad input (invalid range, invalid metric, invalid preset id).
- 401 for missing/invalid session.
- 404 for unknown plant id, unknown preset id, unknown wiki path.
- 503 for camera daemon unreachable, humidifier Kasa unreachable.

### Rate limiting
Out of scope for V1. The UI is single-user; harden if we ever ship to multiple operators.

---

## Open questions (to resolve before OpenAPI freeze)

1. **Single-metric vs bulk sensor history** — lean single-metric; revisit if dashboard initial load is slow.
2. **Plant-detail source** — parse `wiki/plants/*.md` on read (lean: yes + TTL cache) vs mirror into SQL.
3. **Plant status taxonomy** — `primary|secondary` is from the mockup; do we need `discarded` / `culled` for later? Lean: add `retired` now, empty in V1.
4. **Strain / location on `/api/grow/current`** — promote to a new SQL column on `growstate`, or keep in `Settings`? Lean: add to `growstate`.
5. **Fan pct / reservoir in.** Mock, or wait for real hardware? Lean: mock with deterministic rotating values keyed off time so the chart moves; replace when wiring lands.
6. **Wiki file body**: raw markdown (this proposal) vs server-side rendered HTML. Lean: raw markdown. Server knows about frontmatter + backlinks; client owns rendering.
7. **Backlinks cache invalidation**: mtime-based or file-watcher? Lean: mtime, compute lazily on first request per mtime tick.

### Resolved (session 3, 2026-04-20 mockup-vs-API audit)

- **Login field-notes block** — hardcoded in the SPA's login component. Login page is pre-auth and doesn't call any API; copy is updated manually on a grow flip.
- **`week_number` semantics** — renamed to `grow_week_number` (1-indexed since `germination_date`). Added `flower_week_number: int | null` (1-indexed since `flower_start_date`, `null` while stage = `veg`). Rename + new field landed in `apps/shared/src/dirt_shared/services/grow_state.py` (session 3); `GrowCurrentPayload` now matches the contract shape and BE just threads the payload through.
- **`GET /api/auth/me` boot lifecycle** — SPA calls it once on mount; no `localStorage` auth persistence (cookie is the source of truth; TS-09 walls `localStorage` off to `shared/storage.ts`).
- **PTZ preset hints** — `/api/ptz/state.presets[]` entries now include `yaw`, `pitch`, `zoom` so the FE can render the `y=-55° p=-38° z=1.5×` hint line without hardcoding.
- **Wiki doc `lint ✓` badge** — dropped from the UI (no API backing). Footer keeps `sources` + backlinks count.
- **Cmd+K "recent" empty state** — client-side via `shared/storage.ts`; no API field. Do not request `/api/wiki/search?q=` with an empty string.
