# Database

Read before writing SQL, editing `apps/shared/src/dirt_shared/models/`, or running `atlas migrate`.

## Live database

PostgreSQL 17 at `127.0.0.1:5432`, database `dirt`. Managed as a system service (`systemctl status postgresql`).

- **Credentials**: `DIRT_PG_{HOST,PORT,USER,PASSWORD,DATABASE}` in `.env`. The app composes `DATABASE_URL=postgresql+asyncpg://...` at startup (see `apps/shared/src/dirt_shared/config.py:_derive_data_paths`).
- **Connect**: `set -a; source .env; set +a; PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt`

## Schema cheat sheet

Most-queried tables. **Always confirm with `\d <table>` before guessing**; this list is a starting point, not a contract.

- **`sensorreading`** — append-only capability-owned fact table, ~20 rows / 20s. Columns: `id, ts, capability_id, metric, value, source`. Current reads join through `capability -> device -> tent`. Common `metric` values: `temperature_c`, `temperature_f`, `humidity_pct`, `vpd_kpa`, `dew_point_f`, `fan_duty_pct`, `humidifier_on`, `humidifier_mist_level`, `reservoir_in`, plus per-plant `soil_moisture_raw` / `soil_moisture_pct`.
- **`site` / `tent` / `zone` / `device` / `capability`** — scoped local identity model. The current physical box is `site.site_id='homebox'`; the default grow tent is `tent.tent_id='main'`; `tent.tent_id='breeding'` exists but has no hardware loops unless explicitly wired.
- **`growrun`** — scoped grow cycle table holding `germination_date`, `flower_start_date`, `timezone`, `strain`, `plant_count`, and per-tent `is_current`. Source of truth for grow stage (see `apps/shared/src/dirt_shared/services/grow_state.py`). The recurring lights photoperiod lives in `schedule`, not on `growrun`.
- **`schedule`** — scoped local schedules. The main lights photoperiod is materialized as `schedule_id='main-lights-photoperiod'` for `homebox/main`; lights-loop and grow-current responses compose local on/off times from the enabled lights schedule.
- **`plant`** — one row per plant in a `growrun`, with `plant_id` / `code` (`a`-`d` for the current main grow), scope FKs, and `moisture_capability_id` as the canonical moisture stream owner.
- **`sensorcalibration`** — two-point raw sensor calibration. `capability_id` is the canonical scoped owner; legacy `sensornode_id` ownership has been retired from the current schema.
- **`snapshot`** — timestamped JPEG metadata with nullable scoped ownership fields: `site_id`, `tent_id`, `zone_id`, `device_id`, `growrun_id`, `view_id`, and `kind`.

## Common query patterns

```sql
-- latest scoped reading for a metric
SELECT sr.ts, c.metric_name, sr.value
FROM sensorreading sr
JOIN capability c ON c.id = sr.capability_id
JOIN device d ON d.id = c.device_id
JOIN tent t ON t.id = d.tent_id
WHERE t.tent_id = 'main'
  AND c.metric_name = 'temperature_f'
  AND sr.ts > NOW() - INTERVAL '30 minutes'
ORDER BY sr.ts DESC;

-- device freshness (post-USB-unplug etc.)
SELECT device_id, ip, firmware_version, last_seen, NOW() - last_seen AS staleness
FROM device
WHERE controller IN ('esp32', 'govee')
ORDER BY device_id;

-- scoped latest snapshot
SELECT snap.ts, snap.file_path, snap.view_id, snap.kind
FROM snapshot snap
JOIN tent t ON t.id = snap.tent_id
WHERE t.tent_id = 'main'
ORDER BY snap.ts DESC
LIMIT 1;
```

## Schema changes (Atlas workflow)

1. Edit SQLModel classes in `apps/shared/src/dirt_shared/models/`
2. `atlas migrate diff <name> --env local` (writes plain SQL to `migrations/`)
3. Review the generated file
4. Take a normal `pg_dump` backup before live applies
5. `atlas migrate apply --env local`

**NEVER run DDL from app code** — `apps/tests/invariants/test_schema_managed_by_atlas.py` enforces this. Full workflow + HCL reference: `docs/references/atlas/INDEX.md`.

**Dev-db for Atlas diffs**: Docker-ephemeral `docker://postgres/17/dev?search_path=public`. Atlas spins a short-lived container per `migrate diff` — blast radius cannot reach prod.

## Backups + rollback

- **Backups**: manual for now (`pg_dump dirt > var/db-backups/dirt-$(date +%F).sql`). Automation deferred per `docs/proposals/pg-cutover-plan.md` §6 non-scope.
- **Legacy sensor cleanup**: migration `20260504144109_scoped_firmware_legacy_removal.sql` removes `sensornode`, `sensor_location`, and `sensorreading.sensornode_id` after converting historical `reservoir_depth_cm` rows to canonical `reservoir_in` (`value / 2.54`) and deleting known trash `pressure_hpa` / one-off plant-a `humidity_pct` null-capability rows. As of this edit, live apply still requires explicit confirmation and a normal pre-apply `pg_dump`.
- **Rollback artifact**: pre-cutover sqlite preserved at `var/dirt.db.pre-pg-cutover` through ~2026-05-03; restore procedure in [ADR-006](adrs/006-postgres-and-atlas.md).
- **Why Postgres + Atlas**: [ADR-006](adrs/006-postgres-and-atlas.md).
