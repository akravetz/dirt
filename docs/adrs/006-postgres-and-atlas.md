# ADR 006: Postgres + Atlas migrations

## Status

Accepted — 2026-04-19. Cutover planned for same day.

Superseded in part — 2026-05-04. Postgres + Atlas remain the accepted
database/migration architecture, but later scoped telemetry migrations retired
the initial `sensornode`, `sensor_location`, and `sensornode_id` compatibility
schema. Use [`../database.md`](../database.md) for the current table shape.

## Context

From project inception we used SQLite (via `aiosqlite` + SQLModel) with schema maintained by `SQLModel.metadata.create_all` plus a hand-rolled idempotent-ALTER tuple (`_COLUMN_MIGRATIONS` in `apps/shared/src/dirt_shared/db.py`) for post-deploy column additions.

Two pain points became structural as we prepared the Phase 1 contract freeze for the webapp rewrite:

1. **SQLite datetime handling.** SQLite stores datetimes as TEXT. The 5-minute bucketed sensor-history query in `apps/shared/src/dirt_shared/services/readings.py:_BUCKET_SQL` already contains two workarounds: a `char(58)` literal to prevent SQLAlchemy from parsing `:00` as a named bind parameter, and a `cutoff.replace(tzinfo=None).isoformat(sep=" ")` coercion to match SQLite's naive space-separated format lexically. Window functions (`LAG()` over an ordered partition) needed for the humidifier duty-cycle chart are cumbersome in SQLite. `date_trunc` and proper `timestamptz` arithmetic are absent.

2. **Migration debt.** The new `plant` table, three new `growstate` columns, and the set of enum types (`grow_stage`, `plant_status`, `plant_sticker`, `sensor_location`, `sensor_source`) that the webapp-v1 schema requires cannot be cleanly expressed via `_COLUMN_MIGRATIONS`'s idempotent-`ADD COLUMN` pattern. Enums in SQLite require TEXT + `CHECK` constraints; bigint surrogate PKs with identity columns don't exist natively. Building this into the existing pattern would multiply the tuple size ~5× and introduce behaviors (constraint validation, FK semantics) that SQLite doesn't enforce by default.

Doing two migrations (add new tables to sqlite now → move to pg later) was considered and rejected: the types and constraints we want (enums, CHECK, real FK, `inet`, `timestamptz`, partial unique indexes) are exactly what's brittle to express on sqlite. Single engine swap is cleaner than a two-step.

## Decision

**Postgres 17 as the database engine; Atlas as the migration tool; SQLModel as the authoritative schema.**

### Engine

- PostgreSQL 17 installed from Debian trixie's `postgresql` package (`17.9-0+deb13u1`). Runs as the system `postgresql.service`, enabled for boot, listens on `127.0.0.1:5432`. Data dir `/var/lib/postgresql/17/main`, log `/var/log/postgresql/postgresql-17-main.log`.
- Single role `dirt` (scram-sha-256), single database `dirt`. Credentials in `.env` as `DIRT_PG_{HOST,PORT,USER,PASSWORD,DATABASE}`; app reads `DATABASE_URL=postgresql+asyncpg://...` composed from these.
- Driver: `asyncpg` (via SQLAlchemy's asyncpg dialect). `aiosqlite` is dropped from `apps/shared/pyproject.toml`.

### Migrations

- **Atlas** (v1.2+, community edition OSS) at `~/.local/bin/atlas`. Reference pack: `docs/references/atlas/INDEX.md`.
- **SQLModel models are the single source of truth.** Atlas reads `SQLModel.metadata` via the `atlas-provider-sqlalchemy` external schema loader (`scripts/atlas-load-sqlmodel.py` imports `dirt_shared.models` and emits HCL to stdout). No hand-authored HCL.
- Migration files: plain SQL at `migrations/*.sql`, integrity-hashed in `atlas.sum`. Versioned with `atlas migrate diff`, applied with `atlas migrate apply`, CI-gated via `atlas migrate lint --latest 1`.
- **Dev-database: Docker-ephemeral.** Atlas spins a short-lived `postgres:17` container per `migrate diff` invocation via `docker://postgres/17/dev?search_path=public`. Matches Atlas's recommended cleanroom pattern; blast radius cannot reach prod by definition. Docker 26.1 installed; `akcom` is in the `docker` group.
- The app boot path no longer calls `SQLModel.metadata.create_all`. `init_db()` in `db.py` is replaced by a `SELECT 1` health check. Atlas owns all DDL.

### Schema ownership invariant

A new invariant test (`apps/tests/invariants/test_schema_managed_by_atlas.py`) asserts:
- `apps/shared/src/dirt_shared/db.py` contains neither `create_all` nor `_COLUMN_MIGRATIONS`.
- `migrations/` exists with ≥1 `.sql` file.
- `atlas.hcl` exists at repo root.

This prevents a future agent from silently re-introducing the old pattern.

## Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| **Postgres + Atlas** (chosen) | Real `timestamptz`/`inet`/enums/window functions/CHECK. Atlas's declarative diff + plain-SQL output is reviewable without a Python DSL. | One more system service to run; Docker dep for dev-db. |
| Keep SQLite, add Alembic | Smaller delta; Alembic is canonical in Python ecosystem. | Doesn't fix the datetime pain. Alembic migrations are Python DSL, not plain SQL — less universally readable. |
| Keep SQLite, keep `_COLUMN_MIGRATIONS` | Zero net change. | Doesn't scale to enums + FKs + identity columns; every new table adds more idempotent-DDL boilerplate. |
| Postgres + Alembic | Fixes datetime; canonical Python ecosystem. | Alembic autogenerate often misses intent (check constraints, renames); Python DSL is harder to review; dual source of truth (SQLAlchemy models + Alembic revision files). |
| Postgres HCL hand-authored, no SQLModel | Pure Atlas workflow. | Two sources of truth — HCL and SQLModel — which will drift. Rejected explicitly. |

## Consequences

- **The `char(58)` hack and space-vs-T datetime coercion in `readings.py` are deleted.** Bucket queries use `date_trunc('hour' | '5 minutes', ts)` natively.
- **Humidifier state/cycles queries become one window function** (`LAG(value) OVER (ORDER BY ts)`) instead of a Python-side N-pass scan over rows.
- **Real FKs between `sensorreading → sensornode`, `plant → sensornode / growstate`, `sensorcalibration → sensornode`.** Bad `sensornode_id` values fail at insert, not at some later business-logic assertion.
- **Enum types** (`grow_stage`, `plant_status`, `plant_sticker`, `sensor_location`, `sensor_source`) replace free-form TEXT columns. Writes outside the allowed set error at the DB layer.
- **Schema changes go through a PR.** `atlas migrate diff` writes plain `.sql` files that are readable + reviewable; `atlas migrate lint` catches destructive ops, non-concurrent indexes, missing NOT NULL defaults.
- **The dev-db is ephemeral** — nothing persists between `migrate diff` calls. Small runtime cost (~3-5 s container startup per invocation).
- **`DIRT_DATA_DIR / 'dirt.db'` is no longer created or read.** The post-cutover codepath expects `DATABASE_URL` to be set. The sqlite fallback in `config.py:_derive_data_paths` stays as dead code until the next cleanup pass (removing it now would couple the cutover commit to a test-environment update).
- **Tests gain a pg dependency.** Session-scoped pg template DB + per-test `CREATE DATABASE ... TEMPLATE` in `conftest.py`. Tests no longer work offline without a running pg instance; that's an accepted cost.
- **Cutover is a single maintenance window** (~2–5 min of hwd/web downtime). Runbook + rollback procedure in `docs/proposals/pg-cutover-plan.md`.
- **Existing data migrates 1:1.** `scripts/sqlite_to_postgres.py` streams `sensorreading` via `COPY FROM STDIN`, UPSERTs `sensornode`/`growstate` against the seeded rows, bulk-inserts `sensorcalibration`/`snapshot`. Pre-cutover sqlite file is renamed to `var/dirt.db.pre-pg-cutover` and retained for 2 weeks as rollback artifact.

### Later schema evolution

- 2026-05-04 scoped device/capability cleanup migrated current telemetry to
  `sensorreading.capability_id -> capability -> device`, moved heartbeat
  ownership to `device.last_seen`, and removed `sensornode`,
  `sensor_location`, and `sensorreading.sensornode_id`. The historical
  consequences above describe the initial Postgres cutover, not the current
  telemetry query contract.
