# Data Model Proposal — webapp-v1

Scope: what SQL and FS-backed data does the new SPA need that we already have, what do we need to add, and what do we need to *mock* because the hardware or agent pipeline hasn't caught up yet?

Sibling doc: [`API.md`](./API.md). Read that first — this one references endpoints by name.

---

## 1. What we already have

### SQL (SQLite at `var/dirt.db`)

| Table | Purpose | Rows today | Used by mockup? |
|---|---|---|---|
| `growstate` | Singleton (id=1): germination_date, flower_start_date, lights_on_local, lights_off_local | 1 | Yes — drives day/week/stage in top bar + login field-notes. |
| `sensorreading` | Append-only, one row per (ts, location, metric, value). Index on ts, metric, location. | 138k+ | Yes — every gauge, sparkline, humidifier chart, plant moisture chart. |
| `sensornode` | Per-ESP32 metadata: ip, firmware_version, uptime_ms, last_seen. Upserted on each POST. | 4 (plant-a..d) | Yes — drives system table rows for plant nodes. |
| `sensorcalibration` | Per-(location, metric) two-point linear calibration. Auto-widens at ingest. | 4 (one per plant) | Yes — converts `soil_moisture_raw` → %. |
| `snapshot` | Archive of timestamped JPEG snapshots on disk. | Many | No — mockup uses live feed, not snapshot archive. Keep the table; `/api/feed/snapshot/latest` exposes the newest. |

### Metrics currently recorded in `sensorreading`
From live DB:

| metric | location(s) | source | Notes |
|---|---|---|---|
| `temperature_f` | `tent` | arduino | Used by gauge + sparkline. |
| `humidity_pct` | `tent` | arduino | Used by gauge + sparkline. |
| `vpd_kpa` | `tent` | arduino | Used by gauge + sparkline (derived in serial_reader). |
| `pressure_hpa` | `tent` | arduino | Not in mockup; kept for completeness. |
| `dew_point_f` | `tent` | arduino | Not in mockup. |
| `humidifier_on` | `tent` | kasa | Binary 0/1 per humidifier loop tick — drives the humidifier tile + duty-cycle strip. |
| `soil_moisture_raw` | `plant-a..d` | esp32 | Raw ADC; calibrated via `sensorcalibration` to %. Drives plant cards + plant-detail moisture chart. |

### Filesystem

- `wiki/` (70 `.md` files) — agent-maintained markdown. Each has YAML-ish frontmatter (`title`, `type`, `sources`, `related`, `created`, `updated`). Drives the wiki page 100%. `wiki/plants/plant-{a..d}.md` is the source for plant-detail drawer content.
- `~/.config/dirt/camera.json` — PTZ preset definitions. Drives the PTZ preset list.
- `var/snapshots/` — archived JPEGs, indexed by the `snapshot` table.
- `var/raw/photos/<date>/{overview,plant-a,...}.jpg` — daily report captures. Not used by the SPA.
- `var/sessions/voice/YYYY-MM-DD.jsonl` — voice channel turns. Not used by the SPA directly, but "Claudia is listening" status on system table maps to whether `dirt-voice.service` is active.

---

## 2. Data the mockup needs that we **don't have today**

Grouped by urgency. "Flag" = not collected, propose either mock or deferred; "Add" = a small DB/FS change.

### 2a. Grow identity (strain, location, plant count)

**Needed by:** `GET /api/grow/current`, login field-notes block, top-bar tag line.

**Today:** `growstate` has only date/time columns. Strain ("Sirius Black × BS01"), location ("Denver, MT · closet tent"), and plant count (4) are not in the DB — they're implicit in wiki copy.

**Proposal:** **Add** columns to `growstate`:
- `strain: str`
- `location: str`
- `plant_count: int` (default 4; must equal the number of rows in the new `plant` table, see below).

Add these via `_COLUMN_MIGRATIONS` in `db.py` (same pattern used for `lights_on_local`). Seed from a config default on first migration.

Alternative considered: keep these in `dirt_shared.config.Settings`. Rejected: future second-grow support will need per-grow strain/location, and `Settings` is process-wide.

### 2b. Per-plant metadata (sticker color, primary/secondary status, purple flag, label)

**Needed by:** `GET /api/plants`, `GET /api/plants/{id}`, dashboard plant cards, plant-detail drawer.

**Today:** Plant identity exists only as `location='plant-a'` in `sensorreading`/`sensornode`. Sticker color, primary/secondary, "purple keeper" flag, and the drawer tagline ("Purple Keeper Candidate") live in prose inside `wiki/plants/plant-{a..d}.md` and in the mockup's hard-coded `PLANTS` array.

**Proposal:** **Add** a new `plant` table.

```sql
CREATE TABLE plant (
    id           TEXT PRIMARY KEY,        -- 'a' | 'b' | 'c' | 'd'
    name         TEXT NOT NULL,           -- 'Plant A'
    sticker_color TEXT NOT NULL,          -- 'yellow' | 'orange' | 'pink' | 'blue'
    status       TEXT NOT NULL,           -- 'primary' | 'secondary' | 'retired'
    purple       INTEGER NOT NULL,        -- 0 | 1 (SQLite bool)
    label        TEXT,                    -- 'Purple Keeper Candidate' — short drawer tagline
    location     TEXT NOT NULL,           -- FK-ish back to sensorreading.location; 'plant-a' etc.
    moisture_target_low  REAL NOT NULL DEFAULT 55,
    moisture_target_high REAL NOT NULL DEFAULT 70,
    created_at   DATETIME NOT NULL,
    updated_at   DATETIME NOT NULL
);
```

Seed 4 rows on first boot: `{a:yellow, b:orange, c:pink, d:blue}`, `status` / `purple` / `label` pulled from the mockup's initial values and then user-editable via SQL (no admin UI in V1).

Why SQL and not FS: the SPA's plant strip hits this endpoint on every dashboard load; parsing 4 markdown files + extracting frontmatter + guessing at `status` from prose is fragile. SQL is the source of truth; wiki is prose.

**Flag:** the `wiki/plants/plant-{a..d}.md` pages contain the longer-form `Vitals` table and `Timeline` entries that the plant-detail drawer also renders. Those stay as parse-on-read (see §2g).

### 2c. Inline fan percent

**Needed by:** gauge #4 (`fan_pct`), sparkline #4.

**Today:** The AC Infinity inline fan is not wired to the backend. See `wiki/hardware/ac-infinity-fan-control.md` — it's listed as a planned integration.

**Flag:** **Mock with server-side stub.** Return a plausible 45–52 % range that drifts slowly (sine wave keyed off minute-of-day so the sparkline has shape). Add a `TODO: replace with real fan telemetry` marker in the handler. When real telemetry lands, it'll flow through `sensorreading metric='fan_pct'` and the mock can retire with no client change.

Alternative: omit the fan gauge from V1. Rejected because the mockup clearly wants 5 gauges; losing one breaks the layout.

### 2d. Reservoir level (inches)

**Needed by:** gauge #5 (`reservoir_in`), sparkline #5.

**Today:** Reservoir level is manually observed — the wiki has daily notes like "refilled reservoir to 9 in". No sensor, no table. `wiki/hardware/reservoir-level.md` exists but describes a future setup.

**Flag:** **Mock with server-side stub.** Return a monotonically-decreasing value 4..9 in, keyed off hours-since-midnight, that resets to 9 at a fixed time-of-day (the mockup's "09:14 refilled reservoir" note in daily/2026-04-18.md implies a morning refill cycle). Longer-term: an ESP32 ultrasonic module writes `sensorreading location='reservoir' metric='level_in'`, and the mock retires.

### 2e. Humidifier cycles/24h + state transitions

**Needed by:** humidifier tile ("18 cycles / 24h"), humidifier on/off duration, history strip.

**Today:** We have the data — `sensorreading metric='humidifier_on'` writes 0/1 every ~30s. Just haven't exposed it.

**Proposal:** **No new storage.** Compute on read:
- Current state: most recent `humidifier_on` row.
- `cycles_24h`: `COUNT` of transitions (`value != LAG(value)` where current = 1) in last 24h via a single window-function query.
- History: select rows where `value != LAG(value)` — i.e. transitions only — in the window. Keeps payload small.

If we find that computing on read is slow (unlikely at 2k rows over 24h), add a `humidifier_transition` derived table written by the humidifier loop at transition time.

### 2f. System device statuses

**Needed by:** system-devices table (8 rows).

Per-row coverage:
- **Arduino Nano + DHT22** — existing `sensorreading` tent rows. Status = ok if latest temperature_f < 2min old.
- **ESP32-C3 plant_{a..d}** — existing `sensornode.last_seen`. Status = ok if < 2min.
- **OBSBOT Tiny 2 Lite** — query the dirt-camera daemon's `get_state` and check `camera_connected`. No storage needed.
- **Jabra Speak 410 (Claudia)** — **not tracked today.** See §2h.
- **Humidifier (Kasa EP10)** — can be derived from the Kasa discovery call + the latest `humidifier_on` row. Actual "reachable" test requires a call to `Device.update()`; V1 can check the `humidifier` log stream instead (if the last event `<` 5min old, it's alive).

**Proposal:** no new SQL. Add a `dirt_shared.services.system_status` service that collates all of the above into one dict. Heartbeat sources:
- `sensornode.last_seen` (DB).
- Most recent `sensorreading` row for tent.
- Camera daemon socket.
- Voice service status from `systemctl --user is-active dirt-voice` OR (better) a tail of `var/sessions/voice/YYYY-MM-DD.jsonl` — if the file has a `wake` or session-start event in the last 30min, "listening".

**Flag:** "not deployed" is a human label ("Humidifier (Kasa EP10): not deployed" in the mockup). Clearly a moment-in-time status, not a permanent attribute. Status should be computed; the text "not deployed" is probably stale mockup copy.

### 2g. Plant-detail vitals + timeline + note

**Needed by:** `GET /api/plants/{id}` → vitals/timeline/note fields.

**Today:** These live in `wiki/plants/plant-{a..d}.md` as markdown sections (`## Vitals (live)`, `## Timeline`, bottom-quote). No structured storage.

**Proposal:** **Parse-on-read from the markdown.** The agent already writes these pages every daily report cycle (14:00 MDT). Parsing logic:

1. Read `wiki/plants/plant-{id}.md`.
2. Extract frontmatter YAML.
3. Walk blocks looking for `## Vitals (live)` followed by a table → convert to `vitals` array.
4. `## Timeline` followed by a bullet list → each `- YYYY-MM-DD — [Day N: ...]` becomes a `timeline` entry. The `**Topped above node 4**` bolding indicates `highlight: true`.
5. Final block paragraph → `note.text`.

In-memory TTL cache keyed on file mtime. Cache cost trivial (4 files, ~20KB each).

Alternative: Mirror into SQL. Rejected for V1 — it doubles the write path (agent + mirror) and the markdown is already the canonical source for humans.

### 2h. Voice channel status

**Needed by:** system table row "Jabra Speak 410 (Claudia)" — `listening | offline`.

**Today:** No DB row. Only `var/sessions/voice/YYYY-MM-DD.jsonl` has voice events.

**Proposal:** **FS-backed.** In the `system_status` service, tail today's session file and:
- If any event in the last 30min → `listening`.
- Else → `offline`.

Rationale: matches how the wiki already treats voice logs. No DB round-trip for a single row is worth adding a schema for.

### 2i. Wiki backlinks

**Needed by:** `GET /api/wiki/file` → `backlinks` field.

**Today:** Not computed anywhere.

**Proposal:** **On-the-fly grep pass.** For a given file path `P`, scan all `wiki/**/*.md` for:
- Markdown links `](<relative path to P>)` or `](./<...>/<P>)`,
- YAML frontmatter `related: [..., P, ...]`.

Cache by a composite key `(target_path_mtime, all_files_mtime_rollup)`. First uncached call hits ~70 files; LRU cache beyond that.

Alternative: a persistent `wiki_link` table, updated by a file watcher. Over-engineered for V1.

### 2j. Wiki search index

**Needed by:** `GET /api/wiki/search`.

**Today:** Not indexed.

**Proposal:** **Linear substring scan in V1** over filenames + body text. At ~70 files × ~10KB average, this is <5 ms. If slow: SQLite FTS5 virtual table, populated at boot and on a file watcher.

---

## 3. Summary of changes

### SQL schema changes

| Change | Why |
|---|---|
| `growstate` — ADD COLUMN `strain TEXT` | Top bar tag line, login field-notes. |
| `growstate` — ADD COLUMN `location TEXT` | Login field-notes. |
| `growstate` — ADD COLUMN `plant_count INTEGER` | `/api/grow/current` payload. |
| NEW TABLE `plant` | `/api/plants`, `/api/plants/{id}`. Columns: id, name, sticker_color, status, purple, label, location, moisture target lo/hi, created_at, updated_at. |

Apply via the `_COLUMN_MIGRATIONS` tuple in `db.py` + a new one-shot insert of the four plant rows.

### Mocked data (server-side stubs until hardware catches up)

| Field | Mock strategy | Retire when |
|---|---|---|
| `fan_pct` (sensor + history) | Slow sine 45–52% keyed off minute-of-day. | AC Infinity integration lands; writes `sensorreading metric='fan_pct'`. |
| `reservoir_in` (sensor + history) | 4–9 in sawtooth keyed off time-of-day. | Ultrasonic reservoir ESP32 deployed; writes `sensorreading location='reservoir' metric='level_in'`. |
| Plant `vitals` sub-rows beyond soil moisture (pH, distance from light, node count) | Parsed from `wiki/plants/plant-{id}.md` — which today the agent writes from conversation. They're "real" in the sense that a human observed them, but not live sensor-backed. | Per-plant pH probe + light-distance sensor wiring. Until then, the wiki is authoritative. |
| Plant `timeline` entries | Parsed from wiki. Same caveat. | N/A — timeline will always be agent-authored narrative, not sensor data. |

### New server-side services / logic

| Service | Responsibility |
|---|---|
| `dirt_shared.services.plants` | CRUD over the new `plant` table + join moisture percentages. |
| `dirt_shared.services.plant_detail` | Parses `wiki/plants/plant-{id}.md` into vitals/timeline/note. mtime-keyed cache. |
| `dirt_shared.services.humidifier_state` | Reads `sensorreading humidifier_on` → current, cycles_24h, history transitions. |
| `dirt_shared.services.system_status` | Collates device heartbeats (nodes, arduino, camera, voice, humidifier) into one payload. |
| `dirt_shared.services.wiki` | Tree walk + file read with frontmatter split + backlinks grep + search. |
| `dirt_shared.services.mock_sensors` | `fan_pct` and `reservoir_in` deterministic generators. Clearly labeled, retire cleanly. |

All of these are pure-read (`apps/web/` doesn't own `sensorreading` writes; `dirt-hwd` does). They belong in `apps/shared/` because the MCP server might want some of them later.

### No-op / leave-alone

- `snapshot` table — keep for the daily-report archive. Expose via `/api/feed/snapshot/latest` only.
- `sensorcalibration` — keep; computed during ingest on dirt-hwd.
- `sensornode` — keep; drives system table heartbeats.

---

## 4. Open questions (to resolve before freeze)

1. **Store strain/location in `growstate` vs a new `grow_identity` singleton table?** Lean: extend `growstate` — it's already the singleton for "current grow" identity; adding three columns is cheaper than a new table. Revisit if we build multi-grow history.
2. **Are mocked `fan_pct` / `reservoir_in` acceptable for a Phase-2 contract freeze?** If yes, they're part of the OpenAPI spec and the generator writes UI that expects them; when real telemetry lands, the shape doesn't change, only the data source. If no, we drop them from V1 and gauge #4/#5 stay empty or placeholder.
3. **Plant `status` taxonomy.** `primary | secondary`, or include `retired | culled`? Lean: include `retired` (for post-harvest), omit `culled` (not needed yet).
4. **Plant `purple` flag.** Boolean is clean. Is there a future "strength of purple expression" we'd want? Out of scope; flip to enum later if needed (no-op for bool → enum migration with `'confirmed' | 'partial' | 'none'`).
5. **Moisture `target` bands on plant table vs global constant.** Proposal stores per-plant. Alternative: global `MOISTURE_TARGET = (55, 70)`. Lean: per-plant, because soil volume / strain vigor / pot size all vary; cheaper now to have columns than to add later.
6. **Plant-detail timeline: max entries returned.** The wiki entry is growing with each daily report. Return all, or paginate? Lean: return all — the drawer scrolls.
7. **Wiki linking convention.** The wiki has both `](./foo.md)` relative links and `related: [wiki/foo.md, ...]` frontmatter. Backlinks computation must handle both. Do we also rewrite relative links to `wiki/foo.md` in the response body so the client has a uniform click handler? Lean: yes — the server normalizes. Client gets one shape.
