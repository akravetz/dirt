# Database

Read before writing SQL, editing `apps/shared/src/dirt_shared/models/`, or running `atlas migrate`.

## Live database

PostgreSQL 17 at `127.0.0.1:5432`, database `dirt`. Managed as a system service (`systemctl status postgresql`).

- **Credentials**: `DIRT_PG_{HOST,PORT,USER,PASSWORD,DATABASE}` in `.env`. The app composes `DATABASE_URL=postgresql+asyncpg://...` at startup (see `apps/shared/src/dirt_shared/config.py:_derive_data_paths`).
- **Connect**: `set -a; source .env; set +a; PGPASSWORD=$DIRT_PG_PASSWORD psql -h 127.0.0.1 -U dirt -d dirt`

## Schema cheat sheet

Most-queried tables. **Always confirm with `\d <table>` before guessing**; this list is a starting point, not a contract.

Scoped identity cleanup note: source models and new code treat Dirt-owned
local objects as integer-primary-key objects. `site.site_id`, `tent.tent_id`,
`zone.zone_id`, and `schedule.schedule_id` are retired by generated migration
`migrations/20260619045533_scoped_identity_cleanup.sql`; do not apply that
destructive migration to the live/local database without operator confirmation.
If the migration has not been applied yet, a live `\d` may still show the old
columns even though the post-cleanup source contract below is the intended
shape.

- **`sensorreading`** — append-only capability-owned fact table, ~20 rows / 20s. Columns: `id, ts, capability_id, metric, value, source`. Current reads join through `capability -> device -> tent`. Common `metric` values: `temperature_c`, `temperature_f`, `humidity_pct`, `vpd_kpa`, `dew_point_f`, `fan_pct`, `humidifier_on`, `humidifier_intensity_pct`, `reservoir_in`, plus per-plant `soil_moisture_raw` / `soil_moisture_pct`.
- **`site` / `tent` / `zone` / `device` / `capability`** — scoped local identity model. `site`, `tent`, and `zone` rows use integer `id` as their Dirt-owned identity. Human labels live in `name`; tent semantics live in `tent.role`; firmware and camera ingest route by `device.device_id`, then derive placement from the configured `device` row.
- **`schedule`** — scoped local schedules. `schedule.id` is the schedule identity; schedule selection uses owner fields such as `site_id`, `tent_id`, `device_id`, `capability_id`, `kind`, and `enabled`. Lights-loop and grow-current responses compose local on/off times from the enabled lights schedule for the relevant tent/device.
- **`plant` / `plant_line` / `seed_lot` / `plant_location_history`** — durable breeding records. `plant.id` is the database identity; `plant.key` is the unique human-readable tag printed on plants and used in notes/photos. Current tent occupancy is `plant_location_history.end_at IS NULL`; grow stage comes from current plants' lifecycle timestamps (`germinated_at`, `flower_started_at`) plus the scoped lights `schedule`.
- **`sensorcalibration`** — two-point raw sensor calibration. `capability_id` is the canonical scoped owner; legacy `sensornode_id` ownership has been retired from the current schema.
- **`snapshot`** — timestamped JPEG metadata with nullable scoped ownership fields: `site_id`, `tent_id`, `zone_id`, `device_id`, `view_id`, and `kind`.

## Common query patterns

```sql
-- latest scoped reading for a metric
SELECT sr.ts, c.metric_name, sr.value
FROM sensorreading sr
JOIN capability c ON c.id = sr.capability_id
JOIN device d ON d.id = c.device_id
JOIN tent t ON t.id = d.tent_id
WHERE t.is_default = true
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
WHERE t.is_default = true
ORDER BY snap.ts DESC
LIMIT 1;

-- current plants in a tent
SELECT l.grid_position, p.id, p.key, pl.strain, pl.cultivar
FROM plant_location_history l
JOIN plant p ON p.id = l.plant_id
JOIN plant_line pl ON pl.id = p.line_id
JOIN tent t ON t.id = l.tent_id
WHERE t.is_default = true
  AND l.end_at IS NULL
ORDER BY l.grid_position, p.key;
```

## Schema changes (Atlas workflow)

1. Edit SQLModel classes in `apps/shared/src/dirt_shared/models/`
2. `atlas migrate diff <name> --env local` (writes plain SQL to `migrations/`)
3. Review the generated file
4. Take a compressed custom-format `pg_dump` backup before live applies
5. `atlas migrate apply --env local`

**NEVER run DDL from app code** — `apps/tests/invariants/test_schema_managed_by_atlas.py` enforces this. Full workflow + HCL reference: `docs/references/atlas/INDEX.md`.

**Dev-db for Atlas diffs**: Docker-ephemeral `docker://postgres/17/dev?search_path=public`. Atlas spins a short-lived container per `migrate diff` — blast radius cannot reach prod.

## Backups + rollback

- **Pre-migration backups**: manual for now, but use compressed custom format instead of plain SQL. These are short-lived rollback artifacts for destructive local applies, not archival history:
  ```bash
  set -a; source .env; set +a
  mkdir -p var/db-backups
  PGPASSWORD=$DIRT_PG_PASSWORD pg_dump \
    -h 127.0.0.1 -U dirt -d dirt \
    -Fc --compress=zstd:level=6 \
    -f var/db-backups/dirt-$(date +%F-%H%M%S)-pre-change.dump
  ```
- **Restore compressed dumps** into a fresh database with `pg_restore`; do not restore over the live database casually:
  ```bash
  createdb dirt_restore
  pg_restore -h 127.0.0.1 -U dirt -d dirt_restore var/db-backups/<backup>.dump
  ```
- **High-volume data**: if a migration does not touch append-only fact tables, it can be reasonable to omit their data from the rollback artifact with `--exclude-table-data=<table>` while still dumping schema. Do this deliberately and record the omission in the plan/outcome; do not exclude data for tables being migrated.
- **Plain SQL dumps**: use only when human-readable SQL is specifically needed. For routine pre-DDL safety, prefer `-Fc` because it is compressed by default and restores through `pg_restore`.
- **Disaster recovery**: manual `pg_dump` files are not a point-in-time recovery strategy. If Dirt needs real archival recovery, set up base backups plus WAL archiving or a managed PostgreSQL backup tool; this remains deferred per `docs/proposals/pg-cutover-plan.md` §6 non-scope.
- **Legacy sensor cleanup**: migration `20260504144109_scoped_firmware_legacy_removal.sql` removed `sensornode`, `sensor_location`, and `sensorreading.sensornode_id` after converting historical `reservoir_depth_cm` rows to canonical `reservoir_in` (`value / 2.54`) and deleting known trash `pressure_hpa` / one-off plant-a `humidity_pct` null-capability rows. It was applied live on 2026-05-04 after plain SQL `pg_dump` backup `var/db-backups/dirt-20260504-092029-pre-scoped-firmware-legacy-removal.sql`; future backups should use the compressed custom-format command above.
- **Rollback artifact**: pre-cutover sqlite preserved at `var/dirt.db.pre-pg-cutover` through ~2026-05-03; restore procedure in [ADR-006](adrs/006-postgres-and-atlas.md).
- **Why Postgres + Atlas**: [ADR-006](adrs/006-postgres-and-atlas.md).
