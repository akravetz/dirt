-- Seed the main tent dehumidifier as a DB-known Kasa actuator.
-- The MAC is the stable identity; IP is only a fast connection hint.
-- This device is climate-controller-owned and intentionally has no schedule.

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
main_tent AS (
  SELECT t."id"
  FROM "tent" AS t
  JOIN home ON home."id" = t."site_id"
  WHERE t."tent_id" = 'main'
),
canopy AS (
  SELECT z."id"
  FROM "zone" AS z
  JOIN home ON home."id" = z."site_id"
  JOIN main_tent ON main_tent."id" = z."tent_id"
  WHERE z."zone_id" = 'canopy'
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
  "metadata",
  "ip",
  "provider_uid_kind",
  "provider_uid",
  "firmware_version"
)
SELECT
  home."id",
  main_tent."id",
  canopy."id",
  'kasa-dehumidifier-main',
  'Kasa main dehumidifier',
  'actuator',
  'kasa',
  true,
  jsonb_build_object(
    'kasa_alias', 'tent-dehumidifier',
    'model', 'EP10',
    'hardware_version', '1.0 (US)',
    'firmware_version', '1.1.1 Build 250908 Rel.112508',
    'device_type', 'IOT.SMARTPLUGSWITCH'
  ),
  '192.168.1.208'::inet,
  'mac',
  '58:04:4F:10:3D:19',
  '1.1.1 Build 250908 Rel.112508'
FROM home, main_tent, canopy
ON CONFLICT ON CONSTRAINT "uq_device_site_device_id" DO UPDATE SET
  "tent_id" = EXCLUDED."tent_id",
  "zone_id" = EXCLUDED."zone_id",
  "name" = EXCLUDED."name",
  "kind" = EXCLUDED."kind",
  "controller" = EXCLUDED."controller",
  "enabled" = EXCLUDED."enabled",
  "metadata" = EXCLUDED."metadata",
  "ip" = EXCLUDED."ip",
  "provider_uid_kind" = EXCLUDED."provider_uid_kind",
  "provider_uid" = EXCLUDED."provider_uid",
  "firmware_version" = EXCLUDED."firmware_version",
  "updated_at" = now();

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
dehumidifier AS (
  SELECT d."id"
  FROM "device" AS d
  JOIN home ON home."id" = d."site_id"
  WHERE d."device_id" = 'kasa-dehumidifier-main'
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
  dehumidifier."id",
  'power',
  'Dehumidifier Power',
  'actuator',
  'dehumidifier_on',
  'bool',
  'kasa',
  true,
  '{}'::jsonb
FROM dehumidifier
ON CONFLICT ON CONSTRAINT "uq_capability_device_capability_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "kind" = EXCLUDED."kind",
  "metric_name" = EXCLUDED."metric_name",
  "unit" = EXCLUDED."unit",
  "source" = EXCLUDED."source",
  "enabled" = EXCLUDED."enabled",
  "metadata" = EXCLUDED."metadata";
