# Data Model Proposal — webapp-v1 (Postgres cutover + Atlas migrations)

Scope: what SQL and FS-backed data does the new SPA need, what types and constraints should they have in a real DB, and how do we get there from the current SQLite store?

**Framing change from the prior draft.** The prior version extended the SQLite schema in place using the hand-rolled `_COLUMN_MIGRATIONS` tuple in `db.py`. This version starts from the premise that we're moving to **Postgres 16+** with **Atlas-managed migrations** before freezing the contract, and designs the schema against Postgres-native types (`timestamptz`, `boolean`, `text`, `jsonb`, explicit enum types, CHECK constraints) instead of SQLite's dynamic typing. See [ADR-006](../adrs/006-postgres-and-atlas.md) for the decision rationale.

Sibling doc: [`API.md`](./API.md). Read that first — this one references endpoints by name.

Reference: `docs/references/atlas/INDEX.md` for Atlas-specific patterns.

---

## 0. Migration framing (cutover, not a reorg)

We're doing two things at once — DB engine swap (SQLite → Postgres) and schema additions (`plant` table, `growstate` columns). This is deliberate: the worst time to compound migration debt is while it's already limited to one engine. Doing both in one cutover means:

- One downtime window, not two.
- New tables are born in Postgres with real types (timestamptz, bool, enum, jsonb, CHECK constraints) instead of being added to SQLite and then ported.
- The 138k+ existing `sensorreading` rows + 2k `humidifier_on` rows get migrated once.

### Cutover sequence (planned)

1. Stand up Postgres (systemd user unit or Docker — both fine). Set `DATABASE_URL=postgresql+asyncpg://...`.
2. Author SQLModel model changes in a feature branch. `atlas migrate diff` generates the initial migration from a scratch pg dev-db (one file containing the full target schema).
3. `atlas migrate apply` against a second scratch pg, confirm green.
4. Write `scripts/sqlite_to_postgres.py` — one-shot, idempotent, takes source SQLite path + target pg URL. Copies `sensorreading`, `snapshot`, `sensornode`, `sensorcalibration`, `growstate` row-by-row with explicit type coercion (the naive-datetime columns in SQLite become `timestamptz` assumed UTC, which matches current writer intent). Dry-run flag + row-count verification.
5. **Cutover window (target <2 min):**
   - `systemctl --user stop dirt-hwd dirt-web dirt-voice dirt-daily-report.timer` (drain serial/humidifier writes).
   - `pg_dump` current pg (empty or staging) for rollback.
   - `python scripts/sqlite_to_postgres.py --source var/dirt.db --target $DATABASE_URL`.
   - Edit `.env` to flip `DATABASE_URL`.
   - `systemctl --user start dirt-hwd dirt-web dirt-voice`; restart timers.
   - Verify: `sensorreading` row counts match; `humidifier_on` latest row is recent; SPA auth works.
6. Keep `var/dirt.db` around for 2 weeks as a rollback artifact. Rename to `var/dirt.db.pre-pg-cutover` so it's out of the write path but trivially accessible.

Rollback path: `.env` flip back, restart services. Data written to pg during the test window gets discarded; we accept that.

### What stops after the cutover

- The `_COLUMN_MIGRATIONS` tuple in `apps/shared/src/dirt_shared/db.py` — deleted.
- The `SQLModel.metadata.create_all` call in `init_db()` — deleted (Atlas owns DDL now; app only connects).
- The `char(58)` workaround in `readings.py` `_BUCKET_SQL` — deleted (use `date_trunc` + `to_char`).
- Per-service `init_db()` on boot — replaced with a startup `SELECT 1` health check and loud-fail if the schema version doesn't match.

---

## 1. What we already have in SQLite

Capturing pre-migration so the move-script author has an exact spec.

| Table | Purpose | Rows in live DB | Used by mockup? |
|---|---|---|---|
| `growstate` | Singleton (id=1): germination_date, flower_start_date, lights_on_local, lights_off_local | 1 | Yes — drives day/week/stage in the top bar. (The login field-notes block is pre-auth and fully hardcoded in the SPA — no DB dependency.) |
| `sensorreading` | Append-only, one row per (ts, location, metric, value). Index on ts, metric, location. | 138k+ | Yes — every gauge, sparkline, humidifier chart, plant moisture chart. |
| `sensornode` | Per-ESP32 metadata: ip, firmware_version, uptime_ms, last_seen. Upserted on each POST. | 4 (plant-a..d) | Yes — drives system table rows for plant nodes. |
| `sensorcalibration` | Per-(location, metric) two-point linear calibration. Auto-widens at ingest. | 4 (one per plant) | Yes — converts `soil_moisture_raw` → %. |
| `snapshot` | Archive of timestamped JPEG snapshots on disk. | Many | No — mockup uses live feed, not snapshot archive. Keep the table; `/api/feed/snapshot/latest` exposes the newest. |

### Metrics currently recorded in `sensorreading`

From live DB (`SELECT metric, location, COUNT(*) FROM sensorreading GROUP BY metric, location`):

| metric | location(s) | source | Notes |
|---|---|---|---|
| `temperature_f` | `tent` | arduino | Gauge + sparkline. |
| `humidity_pct` | `tent` | arduino | Gauge + sparkline. |
| `vpd_kpa` | `tent` | arduino | Gauge + sparkline (derived in serial_reader). |
| `pressure_hpa` | `tent` | arduino | Not in mockup; kept for completeness. |
| `dew_point_f` | `tent` | arduino | Not in mockup. |
| `humidifier_on` | `tent` | kasa | Binary 0/1 per humidifier loop tick — drives humidifier tile + duty-cycle strip. |
| `soil_moisture_raw` | `plant-a..d` | esp32 | Raw ADC; calibrated via `sensorcalibration` to %. |

### Filesystem (unchanged by the pg cutover)

- `wiki/` (70 `.md` files) — agent-maintained markdown with YAML frontmatter. Drives wiki page + plant-detail drawer content.
- `~/.config/dirt/camera.json` — PTZ preset definitions.
- `var/snapshots/` — archived JPEGs, indexed by the `snapshot` table.
- `var/raw/photos/<date>/` — daily report captures.
- `var/sessions/voice/*.jsonl` — voice channel turns.

---

## 2. Postgres target schema

### Type mapping philosophy

Every column gets the type that actually matches its semantics — no more SQLite-style string-typed timestamps or integer-typed booleans. Specifically:

| Semantic | SQLite today | Postgres target |
|---|---|---|
| UTC timestamp | `DATETIME` (stored TEXT, naive) | `timestamptz` (always UTC on wire) |
| Local time-of-day | `TEXT` `'HH:MM:SS'` | `time` |
| Calendar date | `DATE` (TEXT) | `date` |
| Boolean flag | `INTEGER 0/1` | `boolean` |
| Enum-like TEXT | `TEXT` with hand-validated values | Postgres `ENUM` type |
| Opaque structured blob | rare today | `jsonb` |
| Exact numeric | `REAL` | `real` / `double precision` / `numeric(p,s)` per column |

### Schema

```sql
-- ============================================================
-- ENUM types (declared once, referenced by many tables)
-- ============================================================

CREATE TYPE grow_stage          AS ENUM ('veg', 'flower_early', 'flower_late');
CREATE TYPE plant_status        AS ENUM ('primary', 'secondary', 'retired');
CREATE TYPE plant_sticker       AS ENUM ('yellow', 'orange', 'pink', 'blue');
CREATE TYPE sensor_location     AS ENUM ('tent', 'plant-a', 'plant-b', 'plant-c', 'plant-d', 'reservoir');
CREATE TYPE sensor_source       AS ENUM ('arduino', 'esp32', 'kasa', 'mock');

-- ============================================================
-- PK / FK discipline
-- ============================================================
-- Every table has a surrogate `id bigint GENERATED ALWAYS AS IDENTITY`
-- primary key. Natural keys (plant code, sensor node location) live as
-- separate columns with their own UNIQUE constraint. Every cross-table
-- reference is a real FK on those surrogate keys, not on the natural key.
--
-- Singletons (growstate) use a partial unique index to enforce "exactly
-- one row of kind X" rather than pinning id=1; future-proofs multi-grow
-- history without another schema migration.

-- ============================================================
-- growstate ("the current grow"; future-proofed for multi-grow)
-- ============================================================

CREATE TABLE growstate (
    id                  bigint      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    germination_date    date        NOT NULL,
    flower_start_date   date        NULL,
    lights_on_local     time        NOT NULL DEFAULT '05:00:00',
    lights_off_local    time        NOT NULL DEFAULT '23:00:00',
    strain              text        NOT NULL DEFAULT 'Sirius Black × BS01',
    location            text        NOT NULL DEFAULT 'Denver, MT · closet tent',
    plant_count         smallint    NOT NULL DEFAULT 4 CHECK (plant_count BETWEEN 1 AND 16),
    is_current          boolean     NOT NULL DEFAULT false,
    created_at          timestamptz NOT NULL DEFAULT now()
);

-- Exactly one grow can be flagged current. Partial unique index permits
-- any number of historical (is_current=false) rows.
CREATE UNIQUE INDEX ux_growstate_is_current
    ON growstate (is_current) WHERE is_current = true;

-- Initial seed (data migration): one row, is_current=true, values from
-- current wiki/config.

-- ============================================================
-- sensornode (seeded with one row per sensor_location enum value)
-- ============================================================

CREATE TABLE sensornode (
    id                  bigint              GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    location            sensor_location     NOT NULL UNIQUE,
    ip                  inet                NULL,
    firmware_version    text                NULL,
    uptime_ms           bigint              NULL,
    last_seen           timestamptz         NULL
);

CREATE INDEX ix_sensornode_last_seen ON sensornode (last_seen DESC);

-- Initial seed (data migration): one row per sensor_location enum value,
-- so that every downstream FK target exists from day one. The ESP32
-- nodes overwrite their own row via the ingest upsert; the 'tent' and
-- 'reservoir' rows stay minimally populated (no ip/firmware) until
-- real hardware shows up.
--   ('tent',      NULL, NULL, NULL, NULL)
--   ('plant-a',   NULL, NULL, NULL, NULL)
--   ('plant-b',   NULL, NULL, NULL, NULL)
--   ('plant-c',   NULL, NULL, NULL, NULL)
--   ('plant-d',   NULL, NULL, NULL, NULL)
--   ('reservoir', NULL, NULL, NULL, NULL)

-- ============================================================
-- plant (seeded with 4 rows; one per plant-{a,b,c,d} sensornode)
-- ============================================================

CREATE TABLE plant (
    id                      bigint              GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    growstate_id            bigint              NOT NULL REFERENCES growstate(id) ON DELETE RESTRICT,
    sensornode_id           bigint              NOT NULL UNIQUE REFERENCES sensornode(id) ON DELETE RESTRICT,
    code                    char(1)             NOT NULL CHECK (code ~ '^[a-z]$'),
    name                    text                NOT NULL,
    sticker_color           plant_sticker       NOT NULL,
    status                  plant_status        NOT NULL DEFAULT 'secondary',
    purple                  boolean             NOT NULL DEFAULT false,
    label                   text                NULL,                          -- drawer tagline
    moisture_target_low     real                NOT NULL DEFAULT 55,
    moisture_target_high    real                NOT NULL DEFAULT 70,
    created_at              timestamptz         NOT NULL DEFAULT now(),
    updated_at              timestamptz         NOT NULL DEFAULT now(),
    CHECK (moisture_target_low >= 0 AND moisture_target_low < moisture_target_high),
    CHECK (moisture_target_high <= 100),
    UNIQUE (growstate_id, code)          -- code 'a' unique per-grow, not globally
);

CREATE INDEX ix_plant_status        ON plant (status);
CREATE INDEX ix_plant_growstate_id  ON plant (growstate_id);

-- Initial seed (data migration, joined to the growstate + sensornode rows
-- above by their surrogate ids):
--   (growstate#1, sensornode#plant-a, 'a', 'Plant A', 'yellow', 'primary',   true,  'Purple Keeper Candidate')
--   (growstate#1, sensornode#plant-b, 'b', 'Plant B', 'orange', 'secondary', false, NULL)
--   (growstate#1, sensornode#plant-c, 'c', 'Plant C', 'pink',   'secondary', false, NULL)
--   (growstate#1, sensornode#plant-d, 'd', 'Plant D', 'blue',   'primary',   true,  'Purple Keeper Candidate')

-- ============================================================
-- sensorreading (hot table — 138k+ rows, append-only; FK to sensornode)
-- ============================================================

CREATE TABLE sensorreading (
    id              bigint              GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ts              timestamptz         NOT NULL DEFAULT now(),
    sensornode_id   bigint              NOT NULL REFERENCES sensornode(id) ON DELETE RESTRICT,
    metric          text                NOT NULL,
    value           double precision    NOT NULL,
    source          sensor_source       NOT NULL
);

-- BRIN is intentional: ts is monotonically increasing (append-only),
-- exactly what BRIN is good at. Much smaller than B-tree for time-range
-- scans on a 150k+ row table, negligible write cost.
CREATE INDEX ix_sensorreading_ts         ON sensorreading USING BRIN (ts);
CREATE INDEX ix_sensorreading_metric_ts  ON sensorreading (metric, ts DESC);
CREATE INDEX ix_sensorreading_node_ts    ON sensorreading (sensornode_id, ts DESC);

-- Ingest ordering (dirt-hwd `ingest_reading()` in readings.py): within one
-- transaction, upsert `sensornode` FIRST, then insert `sensorreading` rows.
-- Both statements commit together; FK is satisfied. The seed rows above
-- cover the cold-start case (first reading before a node ever POSTed).

-- ============================================================
-- sensorcalibration (composite business key preserved as UNIQUE)
-- ============================================================

CREATE TABLE sensorcalibration (
    id              bigint              GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sensornode_id   bigint              NOT NULL REFERENCES sensornode(id) ON DELETE CASCADE,
    metric          text                NOT NULL,
    raw_low         double precision    NOT NULL,
    raw_high        double precision    NOT NULL,
    updated_at      timestamptz         NOT NULL DEFAULT now(),
    CHECK (raw_high > raw_low),
    UNIQUE (sensornode_id, metric)       -- old composite natural key, now a constraint
);

-- CASCADE on delete: if a sensornode is ever actually deleted (not expected
-- in normal operation), its calibration rows are meaningless and go with it.

-- ============================================================
-- snapshot (daily report + interval archive)
-- ============================================================

CREATE TABLE snapshot (
    id          bigint          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    ts          timestamptz     NOT NULL DEFAULT now(),
    file_path   text            NOT NULL UNIQUE
);

CREATE INDEX ix_snapshot_ts ON snapshot (ts DESC);
```

### Notes on type choices

- **`bigint GENERATED ALWAYS AS IDENTITY` over `bigserial`.** SQL-standard, no orphan backing sequence to fix permissions on, rejects manual inserts that bypass the sequence (`INSERT INTO foo (id, ...)` errors unless you write `OVERRIDING SYSTEM VALUE`). Modern-Postgres idiom since pg 10; `bigserial` is the legacy macro.
- **`timestamptz` everywhere** and `ts` (not `timestamp`) as the column name. All wire-level datetimes are UTC. Clients that need local time (tent TZ, America/Denver) convert at presentation.
- **`sensor_location` enum.** Today the string is free-form; in practice only 6 values exist. Applied only where the natural key is written — `sensornode.location`. Adding a new location = one migration that widens the enum + one insert.
- **BRIN index on `sensorreading.ts`.** Append-only + monotonic-ts is the textbook BRIN use case; the composite `(metric, ts DESC)` and `(sensornode_id, ts DESC)` cover the "latest value for metric / for node" query patterns.
- **`inet` for IP.** Native, validated, indexable. Cheap.
- **`plant.code CHECK (code ~ '^[a-z]$')`.** Prevents 'Plant-A', 'plant_a', 'A' drift on the stable-label column. Paired with `UNIQUE (growstate_id, code)` so grow #2 can also have plants a–d.
- **`plant.sensornode_id UNIQUE`.** Enforces the 1:1 between a plant row and its ESP32 node via a real FK, not a name-matching convention.
- **`plant.growstate_id` FK.** Ties every plant to a specific grow. Lets a future multi-grow flow insert new plants without schema change.
- **`growstate.is_current` + partial unique index.** Exactly-one-current-grow invariant is enforced in the DB (`CREATE UNIQUE INDEX ... WHERE is_current = true`). Multi-grow flow = `UPDATE growstate SET is_current=false WHERE is_current=true; INSERT INTO growstate (..., is_current=true) ...` — both in one transaction, partial index accepts the swap.
- **CHECK constraints on moisture bands.** `moisture_target_low >= moisture_target_high` is rejected at the DB, not in Python.

### What's intentionally not doing

- **No partitioning on `sensorreading` (yet).** 150k rows/year is laughable for a modern pg. When it's 50M rows, revisit monthly range partitioning on `ts`.
- **No separate `device` table covering OBSBOT / Jabra / Kasa plug.** The system-devices endpoint collates heterogeneous hardware (sensor nodes from DB + camera socket probe + voice session file + kasa last-seen) at query time. Modeling non-sensor devices as rows would require another table + ingest path for each; not worth it yet.
- **No FK from `sensorreading.source` to a `source` dimension table.** The `sensor_source` enum is the right shape: it's a small closed set, not independently queryable.
- **No `updated_at` on `sensorreading`.** It's append-only; readings are never updated.

---

## 3. Atlas migrations — workflow shape

SQLModel stays authoritative. Atlas reads the SQLAlchemy metadata via its external schema loader, diffs against the DB, and writes plain SQL migration files to `migrations/`.

### Repo layout after the cutover

```
atlas.hcl                       # Atlas config: envs, dev URL, external schema loader pointer
migrations/                     # versioned SQL files written by `atlas migrate diff`
  20260420000000_init.sql
  20260421120000_add_plant_table.sql
  atlas.sum                     # integrity hash
scripts/
  atlas-load-sqlmodel.py        # stdout: HCL rendered from our SQLModel metadata
  sqlite_to_postgres.py         # one-shot cutover data mover
apps/shared/src/dirt_shared/
  models/                       # the authoritative SQLModel classes
  db.py                         # connection + session only; no DDL anymore
```

### `atlas.hcl` shape

```hcl
# Read model metadata from Python stdout.
data "external_schema" "sqlmodel" {
  program = [
    "uv", "run", "--package", "dirt-shared",
    "python", "scripts/atlas-load-sqlmodel.py",
  ]
}

# Local dev: edit models, `atlas migrate diff` uses a scratch pg container.
env "local" {
  src = data.external_schema.sqlmodel.url
  dev = "docker://postgres/16/dirt_dev?search_path=public"
  url = "postgres://dirt:dirt@localhost:5432/dirt?sslmode=disable"

  migration {
    dir = "file://migrations"
  }
}

# CI: same src + dev, no url (CI runs diff + lint, doesn't apply).
env "ci" {
  src = data.external_schema.sqlmodel.url
  dev = "docker://postgres/16/dirt_dev?search_path=public"

  migration {
    dir = "file://migrations"
  }
}
```

### Daily authoring loop

1. Edit a SQLModel class in `apps/shared/src/dirt_shared/models/`.
2. `atlas migrate diff <description> --env local` — Atlas spins up its own pg container, applies all existing migrations, diffs that state against the Python-derived HCL, writes a new `.sql` file.
3. Review the generated SQL (plain files, no Python DSL). Hand-edit if Atlas missed an intent — e.g. backfill statements that Atlas can't infer.
4. `atlas migrate apply --env local` — runs pending migrations against the local dev Postgres.
5. Commit the new migration file + the updated `atlas.sum`.

### CI gating

GitHub Actions job: spin up `postgres:16` service container, run `atlas migrate apply --env ci --url <service>` against it, then `atlas migrate lint --env ci --latest 1`. Lint catches destructive ops, non-concurrent indexes, and missing NOT NULL defaults on populated tables.

### Why this pattern

- **One source of truth.** Python models. Forgetting to update the HCL is impossible because there is no HCL to forget.
- **Readable migrations.** Plain SQL. Reviewable in a PR without knowing a migration DSL. Runnable from `psql` without Python if we ever need to.
- **Linted risk.** Atlas flags "this migration drops a column / changes a type / non-concurrently builds an index on a 10M-row table" before we commit.

Caveat: the external schema loader needs our Python env loaded to run. For production apply (`atlas migrate apply --env prod`) we're already on the box that has `uv` + the workspace installed, so this is fine. We are not shipping Atlas apply as a container image without Python.

---

## 4. Data the mockup needs that we **don't have today**

(Structural changes from the prior draft: all "propose ADD COLUMN" statements now become "propose column on target Postgres schema above" — the mechanism is Atlas, not hand-written ALTER.)

### 4a. Grow identity (strain, location, plant count)

**Needed by:** `GET /api/grow/current`, top-bar tag line. (The login field-notes block is pre-auth and fully hardcoded in the SPA — no DB dependency; update the constant on a grow flip.)

**Target:** `growstate.strain`, `growstate.location`, `growstate.plant_count` — included in the Postgres schema above. Seeded from current wiki values during the cutover data move. Editable later via a small admin page or SQL.

**Derived-on-read (not columns):** `grow_week_number` = `(today − germination_date) // 7 + 1`; `flower_week_number` = `(today − flower_start_date) // 7 + 1` when in flower, else `null`. Both are computed in `GrowStateService.get_grow_current_payload()` and exposed directly by `GrowCurrentPayload` (session-3 rename + new field, already landed).

### 4b. Per-plant metadata (sticker color, status, purple, label)

**Needed by:** `GET /api/plants`, `GET /api/plants/{id}`, dashboard plant cards, plant-detail drawer.

**Target:** new `plant` table (see above). Seeded with 4 rows during the cutover. Natural key `code` ('a'..'d') is a separate column with `UNIQUE (growstate_id, code)`; surrogate `id bigint` is the PK and the reference point for any future per-plant FKs (e.g. plant-scoped wiki mirrors). Uses Postgres `plant_status` + `plant_sticker` enums — writes outside the allowed set error at the DB layer, not at the Python layer. FK to `sensornode(id)` is `UNIQUE`, enforcing the plant↔node 1:1 in the DB instead of relying on a matching `'plant-a'` string convention across tables.

### 4c. Inline fan percent

**Needed by:** gauge #4 (`fan_pct`), sparkline #4.

**Today:** AC Infinity inline fan not wired to the backend.

**Flag:** **Mock with server-side stub** (`dirt_shared.services.mock_sensors`). The mock returns a plausible 45–52% range drifting slowly, keyed off minute-of-day. It does NOT write to `sensorreading`. When real hardware lands, it writes `sensorreading(metric='fan_pct', location='tent', source='esp32')` and the mock is deleted. API shape is unchanged.

### 4d. Reservoir level (inches)

**Needed by:** gauge #5 (`reservoir_in`), sparkline #5.

**Today:** Manually observed; no sensor.

**Flag:** **Mock with server-side stub** (`dirt_shared.services.mock_sensors`). Keyed off hours-since-midnight with a morning reset. Does not write to `sensorreading`. Retires when an ultrasonic ESP32 lands and writes `sensorreading(location='reservoir', metric='level_in')` — which is why `sensor_location` enum already has `'reservoir'`.

### 4e. Humidifier cycles/24h + state transitions

**Needed by:** humidifier tile + history strip.

**Today:** Already in `sensorreading` as `metric='humidifier_on'`.

**Proposal:** No new storage. Compute on read using Postgres window functions — a single query with `LAG(value) OVER (ORDER BY ts)` identifies transitions. This is the big datetime-handling win of the pg cutover: `date_trunc('hour', ts)` and `LAG` work correctly and fast, where the SQLite version needs `char(58)` hackery and manual grouping.

### 4f. System device statuses

**Needed by:** system-devices table (8 rows).

No new storage (same conclusion as the prior draft). A `dirt_shared.services.system_status` service collates:
- `sensornode.last_seen` for plant nodes.
- Latest tent `sensorreading` for Arduino.
- Camera daemon socket `get_state` for OBSBOT.
- Tail of `var/sessions/voice/*.jsonl` for Jabra/Claudia.
- Latest `humidifier_on` row + `humidifier` log stream for the Kasa plug.

### 4g. Plant-detail vitals + timeline + note

**Needed by:** `GET /api/plants/{id}` → vitals, timeline, note.

**Target:** **Parse-on-read from `wiki/plants/plant-{id}.md`** with an mtime-keyed cache. Not stored in pg. Pg has the plant's live metadata (status, sticker, purple, moisture targets); the wiki has the narrative (vitals table, timeline entries, note quote). Two sources, two contracts.

If that parse proves flaky, the fallback is a `plant_detail` table (`id, body jsonb, parsed_at timestamptz`) written by a nightly job. Keep the API shape identical so that's a swap, not a contract change.

### 4h. Voice channel status

**Needed by:** system table row "Jabra Speak 410 (Claudia)".

**Target:** FS-backed — tail today's `var/sessions/voice/YYYY-MM-DD.jsonl`. No DB.

### 4i. Wiki backlinks

**Needed by:** `GET /api/wiki/file` → `backlinks` field.

**Target:** on-the-fly grep over `wiki/**/*.md`, mtime-keyed cache. No DB.

### 4j. Wiki search index

**Needed by:** `GET /api/wiki/search`.

**Target:** linear substring scan V1 (~70 files, <5ms). If slow later: Postgres full-text search across a `wiki_file(path, title, body_tsv tsvector)` materialized table, refreshed by a file watcher or daily job. Skipping this in V1 because FTS complexity exceeds the need.

---

## 5. Summary of changes

### Database engine + tooling

| Change | Why |
|---|---|
| SQLite → **Postgres 16+** | Real `timestamptz`, window functions, CHECK constraints, enums. Remove the `char(58)` and space-vs-T hacks in `readings.py`. |
| Hand-rolled `_COLUMN_MIGRATIONS` → **Atlas** | Versioned, reviewable SQL migrations. Lint catches destructive changes. SQLModel stays authoritative. |
| Drop `SQLModel.metadata.create_all` from `init_db` | Atlas owns DDL; app only connects. |
| Add `asyncpg` dep; drop `aiosqlite` | Async Postgres driver for SQLAlchemy. |

### Schema additions (applied via the initial Atlas migration)

| Change | Why |
|---|---|
| Every table: **surrogate `id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY`** | Uniform PK discipline; FKs are always on `bigint`. Natural keys (`plant.code`, `sensornode.location`) become separate columns with their own UNIQUE constraint. |
| `growstate` — ADD `strain`, `location`, `plant_count`, `is_current boolean`, `created_at` | Top bar / login; `is_current` + partial unique index enforces singleton semantics with a real PK and future-proofs multi-grow without another schema change. |
| NEW enum types `grow_stage`, `plant_status`, `plant_sticker`, `sensor_location`, `sensor_source` | Replace free-form string columns with validated enums. |
| NEW TABLE `plant` with `growstate_id` + `sensornode_id` FKs, `code` natural key, sticker/status/purple/label/targets + timestamps; 4 seed rows | `/api/plants`, plant-detail drawer. `UNIQUE (growstate_id, code)` lets multi-grow reuse the A–D labels. `UNIQUE sensornode_id` enforces plant↔node 1:1. |
| `sensorreading` — drop `location text`, add **`sensornode_id bigint REFERENCES sensornode(id)`** | Real FK, not a string convention. Seed `sensornode` covers cold-start; write path upserts node before reading in the same transaction. |
| Convert `sensorreading.source` to `sensor_source` enum | Defense-in-depth against bad writes. |
| Rename `sensorreading.timestamp` → `ts` | Postgres convention; `timestamp` is a reserved-adjacent keyword in some ORM contexts and it's less typing. |
| `sensorreading` — add `(metric, ts DESC)` and `(sensornode_id, ts DESC)` composite B-tree indexes; BRIN on `ts` | Append-only monotonic-ts is the classic BRIN use case; composites cover the "latest for metric/node" patterns. |
| `sensornode` — add surrogate PK + `UNIQUE (location)` on the enum column; IP becomes `inet` | Uniform PK discipline; native IP validation. Seeded with one row per enum value so every FK target exists from day one. |
| `sensorcalibration` — drop composite natural PK, add surrogate PK + `UNIQUE (sensornode_id, metric)`; add `updated_at`, CHECK `raw_high > raw_low`; FK `sensornode_id` with `ON DELETE CASCADE` | PK discipline; composite uniqueness preserved as constraint; auditability; prevent degenerate rows. |
| `snapshot.file_path` — add UNIQUE | Avoid double-recording the same file after a bug. |

### Mocked data (server-side stubs, retire when hardware catches up)

| Field | Mock strategy | Retire when |
|---|---|---|
| `fan_pct` | Slow sine 45–52% keyed off minute-of-day; not persisted. | AC Infinity integration lands; writes `sensorreading metric='fan_pct'`. |
| `reservoir_in` | 4–9 in sawtooth keyed off time-of-day; not persisted. | Ultrasonic reservoir ESP32 deployed; writes `sensorreading location='reservoir' metric='level_in'`. |
| Plant vitals beyond soil moisture (pH, distance, nodes) | Parsed from `wiki/plants/plant-{id}.md`. Real observations, just not live-sensor-backed. | Per-plant pH probe + light-distance sensor wiring. |
| Plant timeline entries | Parsed from wiki. | N/A — timeline is always agent-authored narrative. |

### New server-side services

| Service | Responsibility |
|---|---|
| `dirt_shared.services.plants` | CRUD over `plant` + join moisture percentages via `sensorreading` + `sensorcalibration`. |
| `dirt_shared.services.plant_detail` | Parses `wiki/plants/plant-{id}.md` into vitals/timeline/note. mtime-keyed cache. |
| `dirt_shared.services.humidifier_state` | Reads `sensorreading humidifier_on` via `LAG()` window — current, cycles_24h, history transitions. |
| `dirt_shared.services.system_status` | Collates device heartbeats into one payload. |
| `dirt_shared.services.wiki` | Tree walk + file read with frontmatter split + backlinks grep + search. |
| `dirt_shared.services.mock_sensors` | `fan_pct` + `reservoir_in` deterministic generators. Clearly labeled, retire cleanly. |

### Unchanged by this proposal

- `snapshot` table rows + the `var/snapshots/` directory.
- `sensorcalibration` auto-widen logic in `readings.py`.
- The `/api/ingest/sensors` endpoint on `dirt-hwd`.
- All wiki markdown files.

---

## 6. Resolved decisions

All data-model questions closed as of 2026-04-19:

1. **Postgres hosting** → installed via `apt-get`; runs as the system `postgresql.service` (Debian package). Data dir `/var/lib/postgresql/17/main`. Enabled for boot.
2. **Atlas dev-db** → Docker-ephemeral via `docker://postgres/17/dev?search_path=public`. Matches Atlas's recommended pattern — cleanroom per diff, impossible to misconfigure into prod. Docker 26 installed + enabled + `akcom` in the `docker` group (2026-04-19).
3. **CI Postgres** → GitHub Actions `services:` block for `postgres:17`.
4. **Timezone** → `timestamptz` (UTC) in the DB; UTC on the wire; the frontend converts to America/Denver at render time.
5. **Mocked sensors in `/api/system/devices`** → not surfaced. Handlers log `stream=mock_sensors` server-side for auditability only.
6. **Per-plant `moisture_target_low/high`** → per-plant, columns on `plant`.
7. **`growstate.stage`** → computed on read from `flower_start_date`, never stored. The `grow_stage` enum exists only as an API return type.
8. **Historical grows** → out of scope for V1. Schema supports it (the `is_current` flag + `plant.growstate_id` FK let a future flip insert a new row without migration), but no API / UI surface yet.
9. **`sensor_source`** → enum (arduino, esp32, kasa, mock). Flip to a dimension table only if we ever need to join sources to ownership/provisioning metadata.

---

## 7. What this enables for the rest of Phase 1

- `GET /api/sensors/current` gets a real target-band lookup using a composite query that joins `plant` (for per-plant bands) with the latest `sensorreading` — all in one SQL call.
- `GET /api/humidifier/state` becomes a 5-line window query instead of an N-pass Python scan.
- `GET /api/plants` is one JOIN, not a per-plant loop.
- `/api/sensors/history` buckets via `date_trunc('hour' | '5 minutes', ts)` instead of the current `strftime` + `char(58)` workaround — simpler code, correct datetime handling.

These simplifications are the concrete dividend of the cutover; they're what justifies doing it now rather than pencilling it in for later.
