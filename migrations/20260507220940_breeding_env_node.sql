WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
breeding AS (
  SELECT "id" FROM "tent"
  WHERE "site_id" = (SELECT "id" FROM home) AND "tent_id" = 'breeding'
)
INSERT INTO "zone" ("site_id", "tent_id", "zone_id", "name", "zone_type", "active")
SELECT home."id", breeding."id", 'canopy', 'Canopy', 'canopy', true
FROM home, breeding
ON CONFLICT ON CONSTRAINT "uq_zone_scope_zone_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "zone_type" = EXCLUDED."zone_type",
  "active" = EXCLUDED."active",
  "updated_at" = now();

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
breeding AS (
  SELECT "id" FROM "tent"
  WHERE "site_id" = (SELECT "id" FROM home) AND "tent_id" = 'breeding'
),
breeding_canopy AS (
  SELECT "id" FROM "zone"
  WHERE "site_id" = (SELECT "id" FROM home)
    AND "tent_id" = (SELECT "id" FROM breeding)
    AND "zone_id" = 'canopy'
)
INSERT INTO "device" (
  "site_id",
  "tent_id",
  "zone_id",
  "device_id",
  "name",
  "kind",
  "controller",
  "enabled",
  "metadata"
)
SELECT
  home."id",
  breeding."id",
  breeding_canopy."id",
  'breeding-env-node',
  'ESP32-C3 · breeding env',
  'env_sensor',
  'esp32',
  true,
  '{}'::jsonb
FROM home, breeding, breeding_canopy
ON CONFLICT ON CONSTRAINT "uq_device_site_device_id" DO UPDATE SET
  "tent_id" = EXCLUDED."tent_id",
  "zone_id" = EXCLUDED."zone_id",
  "name" = EXCLUDED."name",
  "kind" = EXCLUDED."kind",
  "controller" = EXCLUDED."controller",
  "enabled" = EXCLUDED."enabled",
  "metadata" = EXCLUDED."metadata",
  "updated_at" = now();

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
device AS (
  SELECT "id" FROM "device"
  WHERE "site_id" = (SELECT "id" FROM home)
    AND "device_id" = 'breeding-env-node'
)
INSERT INTO "capability" (
  "device_id",
  "capability_id",
  "name",
  "kind",
  "metric_name",
  "unit",
  "source",
  "enabled",
  "metadata"
)
SELECT
  device."id",
  v."capability_id",
  v."name",
  'measurement',
  v."metric_name",
  v."unit",
  v."source",
  true,
  '{}'::jsonb
FROM device
JOIN (VALUES
  ('temperature_c', 'Temperature C', 'temperature_c', 'degC', 'esp32'),
  ('temperature_f', 'Temperature F', 'temperature_f', 'degF', 'derived'),
  ('humidity_pct', 'Humidity', 'humidity_pct', 'pct', 'esp32'),
  ('vpd_kpa', 'VPD', 'vpd_kpa', 'kPa', 'derived'),
  ('dew_point_f', 'Dew Point', 'dew_point_f', 'degF', 'derived')
) AS v("capability_id", "name", "metric_name", "unit", "source") ON true
ON CONFLICT ON CONSTRAINT "uq_capability_device_capability_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "kind" = EXCLUDED."kind",
  "metric_name" = EXCLUDED."metric_name",
  "unit" = EXCLUDED."unit",
  "source" = EXCLUDED."source",
  "enabled" = EXCLUDED."enabled",
  "metadata" = EXCLUDED."metadata";
