# API.md — first-pass proposal

**Status**: draft 1 for review. Derived from the `debug/webapp.zip` mockup + today's `apps/web/` inventory. Nothing frozen yet.

This document proposes the **dirt-web JSON API** that the new Vite+React UI will consume. It classifies every endpoint as **KEEP**, **MODIFY**, **ADD**, or **REMOVE**, and proposes request/response shapes for everything except pure REMOVE.

## Cross-cutting conventions

- **Base path**: all new endpoints live under `/api/*`. The old `/sensors/current`, `/feed/image`, `/feed/status` HTMX fragments (no `/api` prefix) are all **REMOVE**.
- **Auth**: cookie-session middleware (already built, `apps/web/src/dirt_web/auth.py`). A single `dirt_session` httponly cookie covers the whole UI. MCP mount at `/mcp` keeps its own bearer token — unchanged.
- **Content-type**: JSON request/response everywhere except `/api/feed/live.jpg` (image/jpeg) and `/api/snapshots/latest.jpg` (image/jpeg). No form-posts in the new API.
- **Timestamps**: all timestamps are ISO-8601 UTC strings with `Z` suffix (e.g. `2026-04-19T17:23:00Z`). Clients convert to local for display.
- **Stage / targets**: every sensor-value endpoint returns the current stage's target band alongside the reading so the UI never has to replicate the stage → band map. Source: `grow_state.current_targets()`.
- **Staleness envelope**: every reading exposes `{value, ts, stale: bool, age_s}`. `stale=true` when age > the metric's staleness threshold (tent=300s, plants=600s — see `daily_sensors.py` precedent).
- **Errors**: 401 for unauthenticated, 403 for authenticated-but-forbidden (future multi-user), 404 for missing resource, 422 for validation (FastAPI default), 503 for transiently-unavailable hardware (PTZ daemon down, capture failed). Body shape: `{"error": "<slug>", "detail": "<human msg>"}`.
- **Pagination**: none needed in v1. Wiki tree + daily list are small; sensor history is bounded by `range`.
- **MOCK markers**: endpoints flagged **MOCK** return synthetic data we are not yet collecting (fan %, reservoir level, runoff pH, etc.). They ship with the same shape as the real endpoint so the UI never has to change when real data is wired up. See `data_model.md` for the backing gaps.

---

## Quick classification index

| Path | Verb | Class | Notes |
|---|---|---|---|
| `/api/auth/login` | POST | **MODIFY** | JSON body, replaces form-post `/login` |
| `/api/auth/logout` | POST | **MODIFY** | was GET, becomes POST for CSRF hygiene |
| `/api/auth/me` | GET | **ADD** | UI-side session probe |
| `/api/sensors/current` | GET | **ADD** | gauge-ready envelope (replaces HTMX fragment) |
| `/api/sensors/history` | GET | **MODIFY** | rename of `/api/sensors/readings`, multi-metric shape, same query param |
| `/api/humidifier/state` | GET | **ADD** | current on/off + cycle-in-progress + 24h stats |
| `/api/humidifier/history` | GET | **ADD** | duty-cycle strip series |
| `/api/plants` | GET | **ADD** | summary list for dashboard strip |
| `/api/plants/{id}` | GET | **ADD** | drawer payload |
| `/api/plants/{id}/history` | GET | **ADD** | soil-moisture time-series for drawer chart |
| `/api/system/devices` | GET | **ADD** | status table (sensors + camera + mic + plug) |
| `/api/feed/live.jpg` | GET | **MODIFY** | renamed from `/feed/live`, same semantics |
| `/api/snapshots/latest.jpg` | GET | **MODIFY** | renamed from `/api/snapshots/latest`, explicit `.jpg` suffix |
| `/api/ptz/state` | GET | **ADD** | current yaw/pitch/zoom + last preset |
| `/api/ptz/presets` | GET | **ADD** | static list (overview + plant_a–d) |
| `/api/ptz/preset` | POST | **ADD** | goto preset by id |
| `/api/ptz/nudge` | POST | **ADD** | relative pan/tilt |
| `/api/ptz/zoom` | POST | **ADD** | zoom absolute or relative |
| `/api/ptz/look` | POST | **ADD** | click-to-look at normalized (x,y) |
| `/api/wiki/tree` | GET | **ADD** | folder tree with counts |
| `/api/wiki/file` | GET | **ADD** | parsed markdown (frontmatter + body + backlinks) |
| `/api/wiki/search` | GET | **ADD** | fuzzy filename + content match |
| `/` | GET (HTML) | **REMOVE** | replaced by `web-ui/` static build |
| `/login` (GET/POST HTML) | GET, POST | **REMOVE** | replaced by SPA login route hitting `/api/auth/login` |
| `/logout` (GET HTML) | GET | **REMOVE** | replaced by POST `/api/auth/logout` |
| `/sensors/current` (HTML fragment) | GET | **REMOVE** | replaced by JSON `/api/sensors/current` |
| `/feed/image` (HTML fragment) | GET | **REMOVE** | UI embeds `/api/feed/live.jpg` directly |
| `/feed/status` (HTML fragment) | GET | **REMOVE** | UI reads `ts` from sensors/snapshots endpoints |
| `/api/sensors/readings` | GET | **REMOVE** | superseded by `/api/sensors/history` (renamed) |

---

## Auth

### `POST /api/auth/login` — **MODIFY**

Replaces form-post `/login` handler.

Request:
```json
{ "username": "alex", "password": "••••••••" }
```

Response 200 (sets `dirt_session` cookie):
```json
{ "username": "alex" }
```

Response 401:
```json
{ "error": "invalid_credentials", "detail": "username or password incorrect" }
```

### `POST /api/auth/logout` — **MODIFY** (was GET)

No body. Clears cookie, returns 204.

### `GET /api/auth/me` — **ADD**

Used by SPA on cold load to decide login vs dashboard.

Response 200:
```json
{ "username": "alex" }
```

Response 401: empty body (SPA redirects to `/login`).

---

## Sensors

### `GET /api/sensors/current` — **ADD**

Dashboard gauges. One envelope per metric.

Response 200:
```json
{
  "stage": "veg",
  "grow_day": 36,
  "lights": { "on": true, "minutes_until_off": 174 },
  "metrics": {
    "temperature_f": {
      "value": 72.4, "unit": "°F",
      "target": { "lo": 70, "hi": 82 },
      "status": "warn",
      "ts": "2026-04-19T17:23:00Z", "stale": false, "age_s": 12
    },
    "humidity_pct": { "value": 65, "unit": "%",  "target": { "lo": 45, "hi": 55 }, "status": "warn",  "ts": "...", "stale": false, "age_s": 12 },
    "vpd_kpa":      { "value": 0.94, "unit": "kPa", "target": { "lo": 0.8, "hi": 1.2 }, "status": "ok", "ts": "...", "stale": false, "age_s": 12 },
    "fan_pct":      { "value": 48, "unit": "%", "target": null, "status": "ok", "ts": "...", "stale": false, "age_s": 0, "_mock": true },
    "reservoir_in": { "value": 6.2, "unit": "in", "target": null, "status": "ok", "ts": "...", "stale": false, "age_s": 0, "_mock": true }
  }
}
```

- `status` ∈ `{"ok","warn","err"}`. Rule: `ok` if value inside target; `warn` if outside target but within target ± (target span); `err` if stale OR outside the wider band OR reading missing.
- `target: null` means "no target configured" (fan, reservoir).
- `_mock: true` flags fields backed by synthetic data until hardware is wired. UI renders them normally; we just know to hide them if we want later.
- `grow_day` = days since `GrowState.germination_date`, 1-indexed.

### `GET /api/sensors/history` — **MODIFY** (renamed from `/api/sensors/readings`)

Same query shape (`range=1h|24h|7d|30d`) but the response standardizes on the envelope above so charts can render target bands.

Request: `?range=24h&metrics=temperature_f,humidity_pct,vpd_kpa,fan_pct,reservoir_in`

- `metrics` is a comma-separated allowlist; if omitted, returns all five dashboard metrics.
- `range`: `1h` | `24h` | `7d` | `30d`.

Response 200:
```json
{
  "range": "24h",
  "labels": ["2026-04-18T18:00:00Z", "..."],
  "series": {
    "temperature_f": { "values": [72.1, 72.3, ...], "target": { "lo": 70, "hi": 82 }, "unit": "°F" },
    "humidity_pct":  { "values": [64, 65, ...],     "target": { "lo": 45, "hi": 55 }, "unit": "%" },
    "vpd_kpa":       { "values": [0.92, 0.94, ...], "target": { "lo": 0.8, "hi": 1.2 }, "unit": "kPa" },
    "fan_pct":       { "values": [48, 49, ...], "target": null, "unit": "%", "_mock": true },
    "reservoir_in":  { "values": [6.3, 6.2, ...], "target": null, "unit": "in", "_mock": true }
  }
}
```

- Shared `labels` array across series (same bucketing) — lets the sparkline crosshair sync without extra bookkeeping.
- Bucketing: `1h` → 1-min buckets (60pts), `24h` → 15-min (96pts), `7d` → 1-hour (168pts), `30d` → 4-hour (180pts). Matches the existing `get_sensor_history` bucketing today.

### `GET /api/sensors/readings` — **REMOVE**

Superseded by `/api/sensors/history`.

---

## Humidifier

### `GET /api/humidifier/state` — **ADD**

Drives the dashboard tile ("ON · 4m 12s · 18 cycles / 24h").

Response 200:
```json
{
  "on": true,
  "since": "2026-04-19T17:19:00Z",
  "cycle_duration_s": 252,
  "last_24h": { "cycles": 18, "on_pct": 34 },
  "last_reason": "vpd_below_upper_band",
  "target_band_kpa": { "lo": 0.7, "hi": 1.1 },
  "ts": "2026-04-19T17:23:12Z"
}
```

- Derivation: scan `SensorReading` rows where `metric="humidifier_on"` for the last 24h, count 0→1 transitions for `cycles`, sum the 1-valued portions for `on_pct`. Current `on` + `since` come from the most-recent row; `last_reason` from the tail of `var/logs/humidifier/<today>.jsonl`. No new writes required.
- `target_band_kpa` reflects lights-aware band (day band vs lights-off offset) — already computed inside the humidifier loop, just needs to be readable.

### `GET /api/humidifier/history?range=1h|24h|7d` — **ADD**

Binary duty-cycle strip on the dashboard.

Response 200:
```json
{
  "range": "24h",
  "labels": ["2026-04-18T18:00:00Z", "..."],
  "values": [0, 0, 1, 1, 0, 1, ...]
}
```

- Same bucketing as `/api/sensors/history`. Each bucket = 1 if the plug was ON for ≥50% of that bucket's span, else 0. Source: `SensorReading` rows with `metric="humidifier_on"`.

---

## Plants

### `GET /api/plants` — **ADD**

Dashboard plants strip.

Response 200:
```json
{
  "grow_day": 36,
  "plants": [
    {
      "id": "a",
      "name": "Plant A",
      "soil_moisture_pct": 62,
      "soil_moisture_ts": "2026-04-19T17:22:31Z",
      "soil_stale": false,
      "status": "primary",
      "purple": true
    },
    { "id": "b", "name": "Plant B", "soil_moisture_pct": 48, "soil_moisture_ts": "...", "soil_stale": false, "status": "secondary", "purple": false },
    { "id": "c", "name": "Plant C", "soil_moisture_pct": 54, "soil_moisture_ts": "...", "soil_stale": false, "status": "secondary", "purple": false },
    { "id": "d", "name": "Plant D", "soil_moisture_pct": 66, "soil_moisture_ts": "...", "soil_stale": false, "status": "primary", "purple": true }
  ]
}
```

- `id` lowercased letter; `name` is display string.
- `soil_moisture_pct` = calibrated % from `SensorReading(metric="soil_moisture_raw")` + `SensorCalibration`.
- `status` ∈ `{"primary","secondary"}`, `purple` bool — **backed by the new `Plant` table** proposed in `data_model.md`. Until that table exists, return hard-coded values keyed by id (this lets the UI ship verbatim).

### `GET /api/plants/{id}` — **ADD**

Plant-detail drawer payload. `{id}` ∈ `{a,b,c,d}`.

Response 200:
```json
{
  "id": "a",
  "name": "Plant A",
  "label": "Purple Keeper Candidate",
  "status": "primary",
  "purple": true,
  "strain": "Sirius Black × BS01",
  "day": 36,
  "notes": "Topped on day 28; LST target ~day 45.",
  "vitals": {
    "soil_moisture_pct": { "value": 62, "target": { "lo": 55, "hi": 70 }, "status": "ok", "ts": "..." },
    "runoff_ph":         { "value": 5.9, "target": { "lo": 5.5, "hi": 6.0 }, "status": "ok", "ts": "2026-04-18T18:30:00Z", "_mock": true },
    "distance_from_light_in": { "value": 24, "target": { "lo": 20, "hi": 26 }, "status": "ok", "ts": "...", "_mock": true },
    "node_count":        { "value": 5, "note": "topped at 4", "_mock": true }
  },
  "timeline": [
    { "date": "2026-03-27", "day": 13, "text": "Pre-transplant; 2–3 true leaf sets", "highlight": false },
    { "date": "2026-03-29", "day": 15, "text": "Transplanted into Autopot XL (coco/perlite 60/40)", "highlight": false },
    { "date": "2026-04-11", "day": 28, "text": "Topped above node 4", "highlight": true }
  ],
  "quote": {
    "text": "Day 28 was the right call — plant had visible 5th node emerging…",
    "source": "daily log, 2026-04-11"
  },
  "wiki_path": "wiki/plants/plant-a.md",
  "ptz_preset_id": "plant_a"
}
```

- `timeline`, `quote`, `label` are pulled from the wiki page's parsed markdown (see `Wiki` section below) or from the `Plant` table's structured fields — `data_model.md` proposes making `timeline` a DB table so it's queryable without re-parsing. For v1 stub, pull from parsed markdown.
- `_mock` flags stay until real ingest arrives.

### `GET /api/plants/{id}/history?range=24h|7d|30d` — **ADD**

Soil-moisture chart on the drawer.

Response 200:
```json
{
  "range": "24h",
  "labels": ["..."],
  "values": [62.1, 61.8, 50.3, ...],
  "target": { "lo": 55, "hi": 70 },
  "irrigation_events": [
    { "ts": "2026-04-19T06:05:00Z", "delta_pct": 22 },
    { "ts": "2026-04-19T12:10:00Z", "delta_pct": 18 }
  ],
  "mean_pct": 58
}
```

- `irrigation_events` = detected positive jumps >10% over 2 buckets. Mocked list if detection isn't wired; UI can ignore empty arrays gracefully.

---

## System / devices

### `GET /api/system/devices` — **ADD**

Populates the dashboard's system table.

Response 200:
```json
{
  "devices": [
    { "id": "arduino",    "label": "Arduino Nano + DHT22",     "status": "online",   "last_seen": "2026-04-19T17:23:00Z", "source": "serial" },
    { "id": "esp32_a",    "label": "ESP32-C3 · plant_a",       "status": "online",   "last_seen": "...", "source": "ingest" },
    { "id": "esp32_b",    "label": "ESP32-C3 · plant_b",       "status": "online",   "last_seen": "...", "source": "ingest" },
    { "id": "esp32_c",    "label": "ESP32-C3 · plant_c",       "status": "online",   "last_seen": "...", "source": "ingest" },
    { "id": "esp32_d",    "label": "ESP32-C3 · plant_d",       "status": "online",   "last_seen": "...", "source": "ingest" },
    { "id": "obsbot",     "label": "OBSBOT Tiny 2 Lite",       "status": "online",   "last_seen": "...", "source": "ptz_daemon" },
    { "id": "jabra",      "label": "Jabra Speak 410 (Claudia)", "status": "listening", "last_seen": "...", "source": "voice_service" },
    { "id": "humidifier", "label": "Humidifier (Kasa EP10)",   "status": "online",   "last_seen": "...", "source": "humidifier_loop" }
  ]
}
```

- `status` ∈ `{"online","listening","offline","warn","error"}`.
- `arduino` / `esp32_*` come from `SensorNode.last_seen` (threshold: offline if >120s for arduino, >300s for ESP32s).
- `obsbot`: checks `systemctl --user is-active dirt-camera` (or daemon heartbeat socket).
- `jabra`: checks `systemctl --user is-active dirt-voice`.
- `humidifier`: checks the humidifier loop's own last-tick timestamp + Kasa reachability — requires a light touch to expose this from the hwd daemon. **Proposal**: have hwd write a heartbeat row to a new `DeviceHeartbeat` table (see `data_model.md`) so dirt-web doesn't need to reach into hwd's memory or ping the Kasa plug itself.

---

## Feed

### `GET /api/feed/live.jpg` — **MODIFY** (renamed from `/feed/live`)

Unchanged semantics — binary JPEG of the current frame via the camera daemon. Rename to `/api/*` and add explicit `.jpg` suffix for UI clarity + caching. 503 if daemon is down.

### `GET /api/snapshots/latest.jpg` — **MODIFY** (renamed from `/api/snapshots/latest`)

Unchanged semantics — most-recent stored snapshot from disk + DB.

Headers: include `Last-Modified` so the UI can cache.

---

## PTZ

The PTZ daemon already speaks a Unix-socket RPC (`scripts/camera` is its CLI). We add HTTP endpoints inside `dirt-web` that translate JSON requests into that RPC. Rationale: the UI is a browser, not a shell; `dirt-web` already has cookie auth; we don't want to expose a new socket on the network.

### `GET /api/ptz/state` — **ADD**

Response 200:
```json
{
  "yaw_deg": -55,
  "pitch_deg": -38,
  "zoom_x": 1.5,
  "last_preset": "plant_a",
  "moving": false,
  "ts": "2026-04-19T17:23:14Z"
}
```

503 if daemon is unreachable. Tail this endpoint (or use a WebSocket later) to animate the crosshair during a move; v1 can poll.

### `GET /api/ptz/presets` — **ADD**

Response 200:
```json
{
  "presets": [
    { "id": "overview", "label": "Overview", "hint": "wide · full tent" },
    { "id": "plant_a",  "label": "Plant A",  "hint": "y=-55° p=-38° z=1.5×" },
    { "id": "plant_b",  "label": "Plant B",  "hint": "y=-20° p=-40° z=1.5×" },
    { "id": "plant_c",  "label": "Plant C",  "hint": "y=+20° p=-40° z=1.5×" },
    { "id": "plant_d",  "label": "Plant D",  "hint": "y=+55° p=-38° z=1.5×" }
  ]
}
```

- Source: `presets.json` in the camera daemon's config (or a static import in `apps/web`). Static in v1 — no write endpoint.

### `POST /api/ptz/preset` — **ADD**

Request: `{ "id": "plant_a" }`

Response 202: `{ "accepted": true, "target": { "yaw_deg": -55, "pitch_deg": -38, "zoom_x": 1.5 } }`

### `POST /api/ptz/nudge` — **ADD**

Request: `{ "dyaw_deg": -10, "dpitch_deg": 0 }` (either/both)

Response 202: `{ "accepted": true, "target": { "yaw_deg": -65, "pitch_deg": -38, "zoom_x": 1.5 } }`

### `POST /api/ptz/zoom` — **ADD**

Request: `{ "delta_x": 0.2 }` OR `{ "absolute_x": 1.5 }` — one of.

Response 202: `{ "accepted": true, "zoom_x": 1.7 }`

### `POST /api/ptz/look` — **ADD**

Click-to-look. `x`, `y` are normalized to [-0.5, 0.5] (feed frame). Server maps to yaw/pitch delta scaled by current FOV.

Request: `{ "x": 0.15, "y": -0.08 }`

Response 202: `{ "accepted": true, "target": { "yaw_deg": -52, "pitch_deg": -40, "zoom_x": 1.5 } }`

---

## Wiki

All paths are **relative to `wiki/`** and normalized server-side. Path traversal (`..`, absolute paths) is rejected with 400.

### `GET /api/wiki/tree` — **ADD**

Response 200:
```json
{
  "folders": [
    { "name": "overview", "count": 3, "files": [
      { "name": "overview.md",     "path": "overview/overview.md",     "title": "Grow Overview" },
      { "name": "index.md",        "path": "overview/index.md",        "title": "Wiki Index" },
      { "name": "activity-log.md", "path": "overview/activity-log.md", "title": "Activity Log" }
    ]},
    { "name": "plants", "count": 4, "files": [
      { "name": "plant-a.md", "path": "plants/plant-a.md", "title": "Plant A — Purple Keeper Candidate", "chip": "a" },
      { "name": "plant-b.md", "path": "plants/plant-b.md", "title": "Plant B", "chip": "b" },
      { "name": "plant-c.md", "path": "plants/plant-c.md", "title": "Plant C", "chip": "c" },
      { "name": "plant-d.md", "path": "plants/plant-d.md", "title": "Plant D", "chip": "d" }
    ]},
    { "name": "daily",    "count": 14, "files": [...] },
    { "name": "concepts", "count": 9,  "files": [...] },
    { "name": "hardware", "count": 6,  "files": [...] },
    { "name": "decisions","count": 5,  "files": [...] },
    { "name": "environment","count": 4,"files": [...] }
  ],
  "total_files": 45,
  "updated_at": "2026-04-19T14:03:00Z"
}
```

- `title` = frontmatter `title` if present, else filename stem.
- `chip` = plant id a-d if the file is under `plants/`; otherwise omitted.

### `GET /api/wiki/file?path=plants/plant-a.md` — **ADD**

Response 200:
```json
{
  "path": "plants/plant-a.md",
  "title": "Plant A — Purple Keeper Candidate",
  "subtitle": "Formerly labeled Plant 1 in early documentation.",
  "frontmatter": {
    "title": "Plant A — Purple Keeper Candidate",
    "type": "plant",
    "priority": "primary",
    "purple": true,
    "created": "2026-04-06",
    "updated": "2026-04-18",
    "related": ["concepts/anthocyanin", "concepts/lst", "daily/2026-04-11"]
  },
  "body_markdown": "# Plant A\n\n**Topped on day 28…** …",
  "backlinks": [
    { "path": "daily/2026-04-11.md", "title": "2026-04-11 · d22" },
    { "path": "concepts/anthocyanin.md", "title": "Anthocyanin" }
  ],
  "updated_at": "2026-04-18T14:07:00Z"
}
```

- Body returned as **raw markdown** — the SPA renders with its own markdown pipeline (consistent styling, link interception for wiki↔wiki navigation). Do not pre-render HTML on the server.
- `backlinks` computed by scanning the tree for `[[...]]` or `](...)` references to this path. Cheap with the existing `lint.py` index; can be cached in-memory with a mtime watcher.

### `GET /api/wiki/search?q=purple&limit=12` — **ADD**

Response 200:
```json
{
  "q": "purple",
  "results": [
    {
      "path": "plants/plant-a.md",
      "title": "Plant A — Purple Keeper Candidate",
      "match_type": "name",
      "snippet": null,
      "score": 0.92
    },
    {
      "path": "concepts/anthocyanin.md",
      "title": "Anthocyanin",
      "match_type": "content",
      "snippet": "…confirmed genetic **anthocyanin** expression in purple…",
      "score": 0.68
    }
  ]
}
```

- `match_type` ∈ `{"name","path","content"}`.
- `limit` default 12, max 50.
- v1: naive substring scan with per-file mtime cache. Good enough for ~50 files.

---

## MCP

`/mcp/*` stays mounted verbatim (bearer-auth, separate from cookie-auth). No changes proposed.

---

## REMOVE list (cleanup at end of Phase 2)

| Path | Reason |
|---|---|
| `GET /` (Jinja index) | Replaced by `web-ui/` static bundle served at `/` |
| `GET /login` (HTML) | SPA owns the login route |
| `POST /login` (form) | Replaced by JSON `POST /api/auth/login` |
| `GET /logout` | Replaced by `POST /api/auth/logout` |
| `GET /sensors/current` (HTMX) | Replaced by JSON `GET /api/sensors/current` |
| `GET /feed/image` (HTMX) | UI embeds `/api/feed/live.jpg` directly |
| `GET /feed/status` (HTMX) | UI reads `ts` from other envelopes |
| `GET /feed/live` | Renamed to `/api/feed/live.jpg` |
| `GET /api/sensors/readings` | Renamed to `/api/sensors/history` |
| `GET /api/snapshots/latest` | Renamed to `/api/snapshots/latest.jpg` |
| All `templates/*.jinja` | Dead after the routes above are deleted |

---

## Open questions for this review pass

1. **Staleness thresholds**: tent=300s, plant soil=600s, humidifier state=120s — copied from current precedent. Confirm or adjust?
2. **Target bands — who owns the source of truth?** Today bands live in Python (`grow_state.py:STAGE_TARGETS`). `data_model.md` proposes moving them to a DB table so the UI can expose an editor. Fine to defer?
3. **Humidifier target band exposure**: the current humidifier loop computes a lights-aware band internally. Should we expose it as a first-class field (proposed: yes, as `target_band_kpa` in `/api/humidifier/state`) or let the UI recompute from stage + lights?
4. **Plant structured vitals (pH, distance, nodes)**: mock for now, or carve a small ingest surface (e.g. `POST /api/plants/{id}/vitals`) so the user can type them in via the drawer? I lean toward mock for v1 since the rest of the stack is read-only.
5. **Wiki write endpoints**: none proposed — the wiki is agent-maintained by the daily-report pipeline + manual edits via editor. Confirm no in-UI editing in scope?
6. **PTZ websocket vs polling**: polling `/api/ptz/state` every 500ms during a move is cheap but ugly. Worth a tiny SSE endpoint in v1? I'd defer.
7. **Device heartbeat source for humidifier/camera/jabra**: do we introduce a `DeviceHeartbeat` table (proposed in `data_model.md`), or have dirt-web shell out to `systemctl --user is-active` per request? The table is cleaner but adds writes to hwd.
