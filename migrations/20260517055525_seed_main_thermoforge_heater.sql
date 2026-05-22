-- Seed the main tent AC Infinity ThermoForge as a scheduled heater.
-- The Controller 69 Pro MAC is the stable BLE identity.

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
main AS (
  SELECT t."id"
  FROM "tent" AS t
  JOIN home ON home."id" = t."site_id"
  WHERE t."tent_id" = 'main'
)
INSERT INTO "zone" ("site_id", "tent_id", "zone_id", "name", "zone_type", "active")
SELECT home."id", main."id", 'heat', 'Heat', 'root_zone', true
FROM home, main
ON CONFLICT ON CONSTRAINT "uq_zone_scope_zone_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "zone_type" = EXCLUDED."zone_type",
  "active" = EXCLUDED."active",
  "updated_at" = now();

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
main AS (
  SELECT t."id"
  FROM "tent" AS t
  JOIN home ON home."id" = t."site_id"
  WHERE t."tent_id" = 'main'
),
heat_zone AS (
  SELECT z."id"
  FROM "zone" AS z
  JOIN home ON home."id" = z."site_id"
  JOIN main ON main."id" = z."tent_id"
  WHERE z."zone_id" = 'heat'
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
  "provider_uid_kind",
  "provider_uid"
)
SELECT
  home."id",
  main."id",
  heat_zone."id",
  'ac-infinity-thermoforge-main',
  'AC Infinity ThermoForge main',
  'actuator',
  'ac_infinity_ble',
  true,
  jsonb_build_object('model', 'ThermoForge'),
  'mac',
  '80:B5:4E:4D:27:CA'
FROM home, main, heat_zone
ON CONFLICT ON CONSTRAINT "uq_device_site_device_id" DO UPDATE SET
  "tent_id" = EXCLUDED."tent_id",
  "zone_id" = EXCLUDED."zone_id",
  "name" = EXCLUDED."name",
  "kind" = EXCLUDED."kind",
  "controller" = EXCLUDED."controller",
  "enabled" = EXCLUDED."enabled",
  "metadata" = EXCLUDED."metadata",
  "provider_uid_kind" = EXCLUDED."provider_uid_kind",
  "provider_uid" = EXCLUDED."provider_uid",
  "updated_at" = now();

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
thermoforge AS (
  SELECT d."id"
  FROM "device" AS d
  JOIN home ON home."id" = d."site_id"
  WHERE d."device_id" = 'ac-infinity-thermoforge-main'
),
capability_rows AS (
  SELECT *
  FROM (VALUES
    (
      'power',
      'Heater Power',
      'actuator',
      'heater_on',
      'bool',
      'ac_infinity',
      true,
      '{}'::jsonb
    ),
    (
      'heat_level',
      'Heater Heat Level',
      'actuator',
      'heater_heat_level',
      'level',
      'ac_infinity',
      true,
      '{}'::jsonb
    )
  ) AS v(
    "capability_id",
    "name",
    "kind",
    "metric_name",
    "unit",
    "source",
    "enabled",
    "metadata"
  )
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
  thermoforge."id",
  capability_rows."capability_id",
  capability_rows."name",
  capability_rows."kind",
  capability_rows."metric_name",
  capability_rows."unit",
  capability_rows."source",
  capability_rows."enabled",
  capability_rows."metadata"
FROM thermoforge, capability_rows
ON CONFLICT ON CONSTRAINT "uq_capability_device_capability_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "kind" = EXCLUDED."kind",
  "metric_name" = EXCLUDED."metric_name",
  "unit" = EXCLUDED."unit",
  "source" = EXCLUDED."source",
  "enabled" = EXCLUDED."enabled",
  "metadata" = EXCLUDED."metadata";

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
main AS (
  SELECT t."id"
  FROM "tent" AS t
  JOIN home ON home."id" = t."site_id"
  WHERE t."tent_id" = 'main'
),
thermoforge AS (
  SELECT d."id"
  FROM "device" AS d
  JOIN home ON home."id" = d."site_id"
  WHERE d."device_id" = 'ac-infinity-thermoforge-main'
),
power_capability AS (
  SELECT c."id"
  FROM "capability" AS c
  JOIN thermoforge ON thermoforge."id" = c."device_id"
  WHERE c."capability_id" = 'power'
)
INSERT INTO "schedule" (
  "site_id",
  "tent_id",
  "device_id",
  "capability_id",
  "schedule_id",
  "kind",
  "starts_local",
  "ends_local",
  "timezone",
  "enabled"
)
SELECT
  home."id",
  main."id",
  thermoforge."id",
  power_capability."id",
  'main-thermoforge-night',
  'heater',
  '21:00'::time,
  '09:00'::time,
  'America/Denver',
  true
FROM home, main, thermoforge, power_capability
ON CONFLICT ON CONSTRAINT "uq_schedule_tent_schedule_id" DO UPDATE SET
  "device_id" = EXCLUDED."device_id",
  "capability_id" = EXCLUDED."capability_id",
  "kind" = EXCLUDED."kind",
  "starts_local" = EXCLUDED."starts_local",
  "ends_local" = EXCLUDED."ends_local",
  "timezone" = EXCLUDED."timezone",
  "enabled" = EXCLUDED."enabled",
  "updated_at" = now();
