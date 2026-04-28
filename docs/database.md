# Database

Read before writing SQL, editing `apps/shared/src/dirt_shared/models/`, or running `atlas migrate`.

## Live database

PostgreSQL 17 at `127.0.0.1:5432`, database `dirt`. Managed as a system service (`systemctl status postgresql`).

- **Credentials**: `DIRT_PG_{HOST,PORT,USER,PASSWORD,DATABASE}` in `.env`. The app composes `DATABASE_URL=postgresql+asyncpg://...` at startup (see `apps/shared/src/dirt_shared/config.py:_derive_data_paths`).
- **Connect**: `set -a; source .env; set +a; PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt`

## Schema cheat sheet

Most-queried tables. **Always confirm with `\d <table>` before guessing**; this list is a starting point, not a contract.

- **`sensornode`** — one row per `SensorLocation` enum (`tent`, `plant-a/b/c/d`, `reservoir`). Columns: `id, location, ip, firmware_version, uptime_ms, last_seen`. No `name` / `kind` columns — those are display strings constructed in app code (e.g. `device_status` log events).
- **`sensorreading`** — append-only fact table, ~20 rows / 20s. Columns: `id, ts, sensornode_id, metric, value, source`. Location lives on `sensornode` — join via `sensornode_id`. Common `metric` values: `temperature_c`, `temperature_f`, `humidity_pct`, `vpd_kpa`, `dew_point_f`, `fan_duty_pct`, `humidifier_on`, `humidifier_mist_level`, plus per-plant `soil_moisture_pct` etc.
- **`growstate`** — single-row table holding `germination_date`, `flower_start_date`, `lights_on_local`, `lights_off_local`, `timezone`. Source of truth for grow stage (see `apps/shared/src/dirt_shared/services/grow_state.py`).
- **`plant`** — one row per A–D, FK to `sensornode`. **`snapshot`** — daily-photo metadata.

## Common query patterns

```sql
-- latest reading per metric for a location
SELECT sr.ts, sr.metric, sr.value
FROM sensorreading sr JOIN sensornode sn ON sn.id = sr.sensornode_id
WHERE sn.location = 'tent' AND sr.ts > NOW() - INTERVAL '30 minutes'
ORDER BY sr.ts DESC;

-- node freshness (post-USB-unplug etc.)
SELECT location, ip, last_seen, NOW() - last_seen AS staleness
FROM sensornode ORDER BY location;
```

## Schema changes (Atlas workflow)

1. Edit SQLModel classes in `apps/shared/src/dirt_shared/models/`
2. `atlas migrate diff <name> --env local` (writes plain SQL to `migrations/`)
3. Review the generated file
4. `atlas migrate apply --env local`

**NEVER run DDL from app code** — `apps/tests/invariants/test_schema_managed_by_atlas.py` enforces this. Full workflow + HCL reference: `docs/references/atlas/INDEX.md`.

**Dev-db for Atlas diffs**: Docker-ephemeral `docker://postgres/17/dev?search_path=public`. Atlas spins a short-lived container per `migrate diff` — blast radius cannot reach prod.

## Backups + rollback

- **Backups**: manual for now (`pg_dump dirt > var/db-backups/dirt-$(date +%F).sql`). Automation deferred per `docs/proposals/pg-cutover-plan.md` §6 non-scope.
- **Rollback artifact**: pre-cutover sqlite preserved at `var/dirt.db.pre-pg-cutover` through ~2026-05-03; restore procedure in [ADR-006](adrs/006-postgres-and-atlas.md).
- **Why Postgres + Atlas**: [ADR-006](adrs/006-postgres-and-atlas.md).
