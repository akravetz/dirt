# Postgres Cutover — Implementation Plan

Sibling docs: [`data_model.md`](./data_model.md) (WHY + target schema), [`API.md`](./API.md) (the SPA contract that depends on this).

## 0. Objective + framing

Move `dirt` from SQLite + hand-rolled `_COLUMN_MIGRATIONS` to Postgres 17 + Atlas-managed migrations, in a single maintenance window, before the webapp-rewrite Phase 1 contract freeze. Reason: all the new tables (`plant`) + type improvements (`timestamptz`, enums, CHECK, real FKs) land cleanly in pg but are awkward to retrofit onto sqlite; doing both at once avoids a second migration cycle.

**Success criteria:**
- `systemctl --user is-active dirt-hwd dirt-web dirt-voice dirt-camera` all green after cutover.
- `uv run pytest -q` green (all per-app suites + invariants) against a pg test DB.
- ESP32 ingest POSTs succeed end-to-end; a sensor value written after cutover is readable via SPA-era endpoints.
- Humidifier loop tick writes `humidifier_on` rows; SPA `/api/humidifier/state` reads them back.
- Daily report timer fires successfully at 14:00 MDT.
- No data loss: post-cutover `sensorreading` row count >= pre-cutover count + whatever was written during the cutover window (expected: 0 since services were stopped).
- Rollback path rehearsed once before cutover.

---

## 1. Pre-flight — already done

- Postgres 17.9 installed, systemd-enabled, listening on `127.0.0.1:5432`.
- `dirt` role + `dirt` database created; scram-sha-256 TCP auth verified.
- Creds in `.env` (`DIRT_PG_{HOST,PORT,USER,PASSWORD,DATABASE}`); `DATABASE_URL` line present but commented — services still on sqlite.
- Atlas v1.2 installed at `~/.local/bin/atlas`; reference pack at `docs/references/atlas/INDEX.md`.
- Data model target spec frozen (per your sign-off).

---

## 2. Workstreams

Work is organized in dependency order. Every item ends with a concrete deliverable. Items marked **[cutover-blocking]** must ship in the single cutover commit; items marked **[pre-cutover]** can land earlier without touching running services.

### WS-0 — ADR + dev-environment scaffolding [pre-cutover]

Before writing any code, capture the decision so it survives.

**Deliverables:**
- `docs/adrs/006-postgres-and-atlas.md` — short ADR: problem (sqlite datetime + migration debt), decision (pg + Atlas + SQLModel-authoritative), alternatives considered (keep sqlite + Alembic; keep sqlite + hand-rolled), consequences.
- Atlas dev-db: docker-ephemeral via `docker://postgres/17/dev?search_path=public`. Docker already installed (see §8).

### WS-1 — SQLModel rewrite [cutover-blocking]

Rewrite the five model files in `apps/shared/src/dirt_shared/models/` to match the target schema. This is the point at which the repo can no longer run against sqlite; all subsequent work lives on the `pg-cutover` branch.

**Model-by-model:**

- **`grow_state.py`** — add `id` surrogate PK, `is_current bool`, `strain`, `location`, `plant_count`, `created_at`. Drop the `id=1` CHECK DEFAULT. Add the partial unique index via `sa_column_kwargs` or an explicit `Index` declaration.
- **`sensor_node.py`** — add `id bigint` surrogate PK (SQLModel: `id: int | None = Field(default=None, primary_key=True, sa_column=Column(BigInteger, Identity(always=True)))`); keep `location` as UNIQUE column retyped to the new `sensor_location` enum; IP → `INET`.
- **`sensor_reading.py`** — drop `location: str`; add `sensornode_id: int = Field(foreign_key="sensornode.id")`; rename `timestamp` → `ts`; `source` → `sensor_source` enum.
- **`sensor_calibration.py`** — drop composite PK; add `id` surrogate + `sensornode_id` FK; add `UNIQUE (sensornode_id, metric)` + `updated_at`.
- **`plant.py`** — NEW. Two FKs (`growstate_id`, `sensornode_id` UNIQUE); `code` + `UNIQUE (growstate_id, code)`.
- **`snapshot.py`** — rename `timestamp` → `ts`; PK style alignment; add UNIQUE on `file_path`.

**Python enum classes**: add `apps/shared/src/dirt_shared/models/enums.py` with `GrowStage`, `PlantStatus`, `PlantSticker`, `SensorLocation`, `SensorSource`. Use `enum.StrEnum` (Python 3.11+, serializes transparently to JSON).

**Deliverable:** Models compile; `uv run python -c "from dirt_shared.models import *"` green. Nothing else works yet.

### WS-2 — Atlas config + external schema loader [pre-cutover, partial]

**Deliverables:**
- `atlas.hcl` at repo root with `env "local"`, `env "ci"`, `env "prod"` blocks; `data "external_schema" "sqlmodel"` pointing at the loader script. Set `diff.concurrent_index.create = true` + `drop = true` (eliminates PG101/PG102 lint noise, per the reference pack).
- `scripts/atlas-load-sqlmodel.py` — imports `dirt_shared.models.*`, emits the SQLAlchemy metadata as HCL to stdout via `atlas_provider_sqlalchemy.ddl`.
- `migrations/` directory (initially empty, gitignored `atlas.sum` initially).
- `pyproject.toml` root — add `atlas-provider-sqlalchemy` to dev deps.

This can land on `main` before the cutover because it reads models but doesn't run anything against the live DB.

### WS-3 — Initial migration + seed data [cutover-blocking]

**Deliverables:**
- `atlas migrate diff init --env local` → generates `migrations/<ts>_init.sql` with full target schema.
- **Hand-append** the seed INSERTs to the generated file (Atlas can't infer these from models):
  ```sql
  -- Seed growstate (one row, is_current=true). Values come from current .env / wiki.
  INSERT INTO growstate (germination_date, strain, location, plant_count, is_current) VALUES
    ('2026-03-15', 'Sirius Black × BS01', 'Denver, MT · closet tent', 4, true);

  -- Seed sensornode (one row per sensor_location enum value).
  INSERT INTO sensornode (location) VALUES
    ('tent'), ('plant-a'), ('plant-b'), ('plant-c'), ('plant-d'), ('reservoir');

  -- Seed plant (4 rows, joined by sensornode.location; this runs AFTER sensornode).
  INSERT INTO plant (growstate_id, sensornode_id, code, name, sticker_color, status, purple, label)
    SELECT g.id, n.id, p.code, p.name, p.sticker_color::plant_sticker, p.status::plant_status, p.purple, p.label
    FROM growstate g
      CROSS JOIN sensornode n
      JOIN (VALUES
        ('a', 'Plant A', 'yellow', 'primary',   true,  'Purple Keeper Candidate', 'plant-a'),
        ('b', 'Plant B', 'orange', 'secondary', false, NULL,                      'plant-b'),
        ('c', 'Plant C', 'pink',   'secondary', false, NULL,                      'plant-c'),
        ('d', 'Plant D', 'blue',   'primary',   true,  'Purple Keeper Candidate', 'plant-d')
      ) AS p(code, name, sticker_color, status, purple, label, location) ON n.location::text = p.location
    WHERE g.is_current = true;
  ```
- Re-compute `atlas.sum` (`atlas migrate hash --env local`).
- `atlas migrate lint --env local --latest 1` → green (or silence expected noise explicitly).

Rehearse the migration against a throwaway pg: drop DB, create empty, `atlas migrate apply`, inspect. Commit only after rehearsal passes.

### WS-4 — Driver + connection layer [cutover-blocking]

**Files touched:** `apps/shared/src/dirt_shared/db.py`, `apps/shared/src/dirt_shared/config.py`, `pyproject.toml` (shared).

**Deliverables:**
- Add `asyncpg`, drop `aiosqlite` from `apps/shared/pyproject.toml`.
- `db.py`: delete `_COLUMN_MIGRATIONS` and the full `init_db()` body. Replace with:
  ```python
  async def init_db() -> None:
      """Verify the DB is reachable and on an expected schema version.
      Atlas owns DDL now — this function no longer creates tables."""
      async with engine.begin() as conn:
          await conn.execute(text("SELECT 1"))
          # Optional: assert migrations/atlas.sum matches `atlas_schema_revisions.version`
          # to loudly fail if the app starts against an un-migrated DB.
  ```
- `config.py`: no functional change but verify `database_url` is now set from `.env`'s uncommented `DATABASE_URL`. The sqlite fallback in `_derive_data_paths()` becomes dead code post-cutover but can stay until the next cleanup pass.

### WS-5 — Service layer — readings + calibration [cutover-blocking]

**File:** `apps/shared/src/dirt_shared/services/readings.py`.

**Changes:**
- `ingest_reading(location, metrics, source, ...)` → needs to map `location` → `sensornode_id` before inserting readings. New internal helper:
  ```python
  async def _get_or_upsert_sensornode_id(session, location: SensorLocation, ip, firmware, uptime) -> int:
      node = (await session.exec(select(SensorNode).where(SensorNode.location == location))).first()
      if node is None:
          node = SensorNode(location=location)
      node.ip = ip; node.firmware_version = firmware; node.uptime_ms = uptime
      node.last_seen = datetime.now(UTC)
      session.add(node)
      await session.flush()  # force id generation so sensorreading.sensornode_id can reference it
      return node.id
  ```
  Then insert readings with `sensornode_id=node_id`. Single transaction, single commit.
- `get_latest_reading(metric, location='tent')` → add `location` parameter with `'tent'` default (covers current callers). Join through `sensornode`.
- `_update_calibration(session, sensornode_id, metric, value)` → swap location→sensornode_id.
- `_BUCKET_SQL` — rewrite using `date_trunc`. The 5-min bucket query becomes:
  ```sql
  SELECT date_trunc('hour', ts) + make_interval(mins => (EXTRACT(minute FROM ts)::int / 5) * 5) AS bucket,
         AVG(value) AS avg_value
  FROM sensorreading
  WHERE ts >= :cutoff AND metric = :metric
  GROUP BY bucket ORDER BY bucket;
  ```
  `char(58)` hack deleted; space-vs-T comment deleted; the cutoff string wart in `_get_metric_series` deleted. Net line count down ~30.
- `is_sensor_stale()` — unchanged logic, swap to `SELECT value ... LIMIT 10` semantics (already works).

### WS-6 — Service layer — new services [cutover-blocking]

Per the data model proposal:
- `apps/shared/src/dirt_shared/services/plants.py` — plant CRUD + moisture join.
- `apps/shared/src/dirt_shared/services/humidifier_state.py` — `LAG() OVER (ORDER BY ts)` windowed transition query.
- `apps/shared/src/dirt_shared/services/system_status.py` — heartbeat collation.
- `apps/shared/src/dirt_shared/services/plant_detail.py` — parse `wiki/plants/plant-{code}.md` with mtime cache.
- `apps/shared/src/dirt_shared/services/wiki.py` — tree + file + search + backlinks.
- `apps/shared/src/dirt_shared/services/mock_sensors.py` — fan + reservoir generators.

Each gets a unit-test file alongside; see WS-10 for the test fixture story.

### WS-7 — HWD rewrites [cutover-blocking]

**Files:** `apps/hwd/src/dirt_hwd/services/humidifier.py`, `apps/hwd/src/dirt_hwd/services/serial_reader.py`, `apps/hwd/src/dirt_hwd/api/ingest.py`.

**Changes:**
- `humidifier.py:_record()` — it currently writes `SensorReading(location='tent', metric='humidifier_on', ...)`. New version resolves `tent` sensornode id once at startup (cache it) and writes `sensornode_id=TENT_NODE_ID`.
- `serial_reader.py` — same pattern: resolve `tent` once at startup.
- `ingest.py` — no change (it just calls `ingest_reading` which now handles the translation).

**Important invariant:** this is the only place we're allowed to edit `apps/hwd/` for the foreseeable future (per CLAUDE.md's off-limits rule). All the changes must land in the cutover commit; after that, hwd is frozen again.

### WS-8 — Web + voice + daily-report rewrites [cutover-blocking]

**Files:** `apps/web/src/dirt_web/api/sensors.py`, `apps/voice/src/dirt_voice/tools/sensors.py`, `apps/shared/src/dirt_shared/services/daily_sensors.py`, `apps/shared/src/dirt_shared/services/daily_report.py`.

Most of these are just "pass `location='tent'` to `get_latest_reading`" or "swap `SensorReading.location == 'tent'` for a `JOIN sensornode ON sensornode.location = 'tent'`" one-liners. Audit each call-site with:
```
grep -rn "SensorReading\|get_latest_reading\|.location == \|.location =" apps/ --include="*.py"
```

### WS-9 — MCP server [cutover-blocking]

`apps/mcp/` reads through the same `readings` service functions. Should just-work after WS-5 & WS-6 land. Verify with the MCP test suite.

### WS-10 — Test fixture rework [cutover-blocking]

Current pattern: each test builds its own in-memory `sqlite+aiosqlite` engine via `create_async_engine` in a local fixture, runs `SQLModel.metadata.create_all`, passes the engine by injection. (See `apps/shared/tests/test_daily_sensors.py:26-32`.) This pattern does NOT work against pg because pg can't be in-memory and `create_all` doesn't produce our seeded schema.

**New pattern** — template-database clone:
- Root `conftest.py` (new fixture): at the start of a pytest session, create a template DB `dirt_test_template` and apply all migrations to it once (`atlas migrate apply --env test --url .../dirt_test_template`). That DB is read-only for the session.
- Per-test: `CREATE DATABASE test_<random> TEMPLATE dirt_test_template;` (sub-100ms). Yield an engine pointing at it. Drop at teardown.
- Tests that take an engine by injection: replace the in-line `create_async_engine` fixture with the shared `pg_engine` fixture.
- Tests that rely on the module-level `engine` in `db.py`: add an `autouse` fixture that monkeypatches `dirt_shared.db.engine` for the test's duration.

Alternative considered: per-test transactional rollback (one DB, SAVEPOINT per test). Rejected: breaks tests that exercise transaction boundaries (ingest's commit, migration tests), and SQLAlchemy async session + nested savepoint + connection pool is a known source of test flakes.

**Deliverable:** `uv run pytest -q` green end-to-end against pg test DBs.

### WS-11 — Data migration script [cutover-blocking]

**File:** `scripts/sqlite_to_postgres.py`.

**Contract:**
```
uv run python scripts/sqlite_to_postgres.py \
  --source var/dirt.db \
  --target postgresql+asyncpg://dirt:...@127.0.0.1:5432/dirt \
  [--dry-run]
```

**Ordering** (all inside one pg transaction, rolled back on any error):
1. Assert source sqlite is non-empty; assert target pg is already migrated (schema present, seed rows present, no non-seed rows yet — fail loudly if user data exists).
2. **growstate** — take the single sqlite row, UPDATE the already-seeded `is_current=true` row with its `germination_date` + `flower_start_date` + lights times.
3. **sensornode** — for each of the 4 sqlite rows, UPDATE by location to populate `ip`, `firmware_version`, `uptime_ms`, `last_seen` on the already-seeded pg row.
4. **sensorcalibration** — for each sqlite row, INSERT into pg joining `sensornode_id = (SELECT id FROM sensornode WHERE location = :location)`. Expected 4 rows.
5. **sensorreading** — the hot path. Stream rows from sqlite in batches of ~5000; for each batch, resolve `sensornode_id` via a dict built once at startup from the 6 seeded `(location, id)` pairs; `COPY FROM STDIN` into pg (not row-by-row `INSERT` — 138k rows). Parse SQLite's naive-TEXT timestamps as UTC; hand to pg as `timestamptz`. Expected ~138k rows.
6. **snapshot** — bulk INSERT (table is small). Rename `timestamp` → `ts`.
7. Verify: row counts match source (within the same transaction). If OK, COMMIT; else ROLLBACK + report diff.

**Idempotency:** re-running against a populated pg DB must fail fast in step 1 (detects non-seed data). No partial-state recovery.

**Test strategy:** copy the live `var/dirt.db` to `var/dirt.db.migration-test`, spin up a throwaway test DB on pg (`createdb dirt_migration_test`), run the script end-to-end, verify row counts + spot-check a few recent `sensorreading` rows.

### WS-12 — Invariant test for DB-related architecture [pre-cutover]

New `apps/tests/invariants/test_schema_managed_by_atlas.py`:
- Assert `apps/shared/src/dirt_shared/db.py` does NOT contain `create_all`, `metadata.create_all`, or `_COLUMN_MIGRATIONS`.
- Assert `migrations/` exists and has >=1 `.sql` file.
- Assert `atlas.hcl` exists at repo root.

This prevents a future agent from silently re-introducing the old pattern.

---

## 3. Cutover runbook

Executed as a single maintenance window by the operator (you) with the feature branch already reviewed and merge-ready.

```bash
# ---------- 0. Pre-flight checks (no changes) ----------
systemctl --user is-active dirt-hwd dirt-web dirt-voice dirt-camera     # all active?
git status                                                              # clean working tree?
atlas migrate status --env prod                                         # empty: no migrations applied
psql -h 127.0.0.1 -U dirt -d dirt -c "\dt"                              # empty: no tables yet
cp var/dirt.db /tmp/dirt.db.cutover-dry-run                             # local rehearsal copy

# ---------- 1. Rehearse the data move against a disposable pg DB ----------
createdb -h 127.0.0.1 -U dirt dirt_dryrun
atlas migrate apply --env prod --url "postgresql://dirt:...@127.0.0.1:5432/dirt_dryrun"
uv run python scripts/sqlite_to_postgres.py \
    --source /tmp/dirt.db.cutover-dry-run \
    --target postgresql+asyncpg://dirt:...@127.0.0.1:5432/dirt_dryrun
# Expected output: row counts match source, no errors, exit 0.
dropdb -h 127.0.0.1 -U dirt dirt_dryrun
# (If ANY step above failed, abort. Do not proceed.)

# ---------- 2. Stop services (begin maintenance window; ~target <2 min downtime) ----------
systemctl --user stop dirt-hwd dirt-web dirt-voice dirt-daily-report.timer
# dirt-camera can stay up; it doesn't touch the DB.

# ---------- 3. Rename sqlite for rollback safety (don't delete!) ----------
mv var/dirt.db var/dirt.db.pre-pg-cutover
# Writing processes are stopped so the file is quiescent.

# ---------- 4. Apply schema + seed data to production pg ----------
atlas migrate apply --env prod
# Verify: psql dirt -c "SELECT count(*) FROM sensornode;" → 6
#        psql dirt -c "SELECT count(*) FROM plant;"      → 4
#        psql dirt -c "SELECT count(*) FROM growstate WHERE is_current;" → 1

# ---------- 5. Move data from sqlite to pg ----------
uv run python scripts/sqlite_to_postgres.py \
    --source var/dirt.db.pre-pg-cutover \
    --target postgresql+asyncpg://dirt:...@127.0.0.1:5432/dirt
# Expected: ~138k sensorreading rows, 4 sensorcalibration, 1 growstate updated,
# 4 sensornode updated, many snapshot rows. Script exits 0 on success.

# ---------- 6. Flip the switch ----------
# In .env: uncomment the `DATABASE_URL=postgresql+asyncpg://...` line.
# In the same commit: merge the `pg-cutover` branch into main.
git checkout main
git merge --ff-only pg-cutover
# (or squash-merge via the PR UI; either is fine)

# ---------- 7. Start services ----------
systemctl --user start dirt-hwd dirt-web dirt-voice
systemctl --user restart dirt-daily-report.timer
# Give hwd 30s to post its first reading.

# ---------- 8. Smoke tests ----------
# Ingest still works:
journalctl --user -u dirt-hwd -n 50 | grep -i "ingest\|sensor\|error"
# Web serves:
curl -s http://localhost:8001/feed/live -o /tmp/live.jpg && file /tmp/live.jpg
# MCP still mounts:
curl -s http://localhost:8001/mcp/health
# A new reading landed post-cutover:
psql -h 127.0.0.1 -U dirt -d dirt \
     -c "SELECT COUNT(*) FROM sensorreading WHERE ts > NOW() - INTERVAL '2 min';"
# (Expected: > 0; temperature + humidity + vpd + dew_point_f + pressure_hpa per 20s)

# ---------- 9. End of maintenance window ----------
# Announce: cutover complete. Monitor journal for 1 hour; check next daily-report run.
```

**Target window:** 2–5 minutes of hwd/web downtime. Longest step is `sqlite_to_postgres.py` (estimated 30–60s for 138k rows via `COPY`).

---

## 4. Rollback

**Trigger:** any smoke test fails, or service logs show crash loops, or data integrity issue surfaces.

```bash
systemctl --user stop dirt-hwd dirt-web dirt-voice dirt-daily-report.timer

# In .env: re-comment the DATABASE_URL line.
git revert <cutover-commit>   # OR: git checkout main~1 -- .env apps/ scripts/ migrations/
mv var/dirt.db.pre-pg-cutover var/dirt.db   # restore sqlite file

systemctl --user start dirt-hwd dirt-web dirt-voice
systemctl --user restart dirt-daily-report.timer
```

Data written to pg during the aborted cutover window is discarded. The pg DB stays around as forensic artifact. Re-investigation happens on a feature branch with a fresh `dirt_recovery` pg DB; live services run on sqlite while we fix.

**Rollback validity window:** keep `var/dirt.db.pre-pg-cutover` for 2 weeks. After that, delete (hwd has written 2 weeks of pg-only data; a rollback would lose that).

---

## 5. Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| `sqlite_to_postgres.py` corrupts timestamps (TZ drift) | Low | High | Rehearse against `/tmp/dirt.db.cutover-dry-run`. Spot-check 5 recent rows post-migration against the source. SQLite timestamps are naive UTC per writer intent (confirmed in `readings.py:_utcnow`); coercion to timestamptz is `AT TIME ZONE 'UTC'`. |
| Service fails to start post-cutover (missed code site) | Medium | Medium | `uv run pytest -q` green before cutover catches ~95%. For the long tail, the smoke tests in §3 step 8 will reveal it in under 2 min. Rollback is fast. |
| Atlas lint flags a destructive change we didn't anticipate | Low | Low | Always fresh init migration — no destructive ops in the first migration. Lint runs in WS-3 rehearsal. |
| Seeded `plant` row count ≠ 4 (join against sensornode failed) | Low | High | WS-3 rehearsal. Assertion in §3 step 4. |
| Daily report timer fires during cutover window | Low | Medium | Explicitly stop `dirt-daily-report.timer` in step 2. Window is not at 14:00 MDT. |
| `dirt-voice` loses its wake pipeline context | Very low | Low | Voice channel doesn't write to the DB; restart restores state. |
| Test DB template creation flakes in CI | Medium | Low | WS-10 rehearses locally first; CI pg service container + `CREATE DATABASE ... TEMPLATE` is a well-trod path. |
| `apps/hwd/` edits violate the Phase 2 invariant | N/A | N/A | Phase 2 hasn't started. The cutover commit predates the contract freeze. Invariants `test_import_boundaries.py` + `test_hwd_routes.py` still apply and stay green. |

---

## 6. Non-scope

Explicitly **not** in this cutover (can be follow-ups):

- Backup automation for pg (`pg_dump` on a timer to `var/db-backups/`). Manual-only for now; existing sqlite backups stay in `var/db-backups/` historically.
- Moving pg data dir onto a different disk / volume.
- Replication, read replicas, connection pooling (pgbouncer). Single instance, single connection pool via SQLAlchemy is fine at our scale.
- Partitioning `sensorreading` by month. Revisit at 10M rows.
- Postgres-native FTS for wiki search — V1 stays with linear substring scan.
- Deleting `apps/shared/src/dirt_shared/config.py`'s sqlite fallback path. Leave as dead code until a Phase-2 cleanup pass.
- New tables for non-sensor devices (OBSBOT / Jabra / Kasa). System-status service collates at query time; modeling is deferred until there's an actual join-needy use case.

---

## 7. Estimate + sequencing

Best-guess wall-clock, single-operator, fully focused:

| Phase | Work | Rough hours |
|---|---|---|
| WS-0 | ADR + dev-env decisions | 0.5 |
| WS-1 | SQLModel rewrite | 2 |
| WS-2 | Atlas config + loader | 1 |
| WS-3 | Initial migration + seed + rehearsal | 1.5 |
| WS-4 | Driver + connection layer | 0.5 |
| WS-5 | Readings service rewrite | 2 |
| WS-6 | New service modules | 4 |
| WS-7 | HWD rewrites | 1 |
| WS-8 | Web/voice/daily-report updates | 1.5 |
| WS-9 | MCP verification | 0.5 |
| WS-10 | Test fixture rework | 3 |
| WS-11 | Data migration script + rehearsal | 2.5 |
| WS-12 | Invariant test | 0.5 |
| **Sum (dev)** | | **~20h** |
| Cutover runbook execution | Operator work | 0.5 |

Call it ~3 focused work days + a 30-minute cutover window. The riskiest items (longest tail) are WS-10 (test fixture rework — pg test-DB patterns have edge cases) and WS-11 (bulk data move — has to be right or we lose history).

**Recommended sequencing for commits:**
1. One PR: WS-0, WS-2, WS-12 (no service impact; can land on main).
2. Feature branch `pg-cutover`: WS-1, WS-3, WS-4, WS-5, WS-6, WS-7, WS-8, WS-9, WS-10, WS-11 as individual commits (easier bisection later).
3. Branch stays ~3 days; no parallel main-branch changes to the DB layer during this time.
4. Cutover = squash-merge of the feature branch + the `.env` edit in the same commit.

---

## 8. Decisions (resolved 2026-04-19)

1. **Atlas dev-db** → Docker-ephemeral via `docker://postgres/17/dev?search_path=public` (Atlas's recommended pattern). Docker 26 installed from Debian repos, `akcom` in the `docker` group. `atlas migrate diff` spins up a short-lived `postgres:17` container per invocation; blast radius cannot reach prod by definition.
2. **ADR number** → `docs/adrs/006-postgres-and-atlas.md` (next sequential — 005 is agent-architecture).
3. **Cutover window** → no external constraint; any morning block while the operator is at the keyboard. Avoid 14:00 MDT (daily report timer).
4. **PR strategy** → branch-of-commits on `pg-cutover`, squash at merge. Easier bisection during development, one atomic commit on `main`.
5. **Test pg DB** → `dirt_test_template` rebuilt per pytest session (session-scoped fixture). Cheap (<1 s) and eliminates "template drifted" failure modes.

All five resolved. Ready to start WS-0 / WS-2 / WS-12 as the first PR.
