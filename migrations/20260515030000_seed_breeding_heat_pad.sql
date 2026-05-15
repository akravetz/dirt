-- Seed the breeding tent heat pad as its own scheduled Kasa actuator.
-- The MAC is the stable identity; IP is only a fast connection hint.

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
breeding AS (
  SELECT t."id"
  FROM "tent" AS t
  JOIN home ON home."id" = t."site_id"
  WHERE t."tent_id" = 'breeding'
)
INSERT INTO "zone" ("site_id", "tent_id", "zone_id", "name", "zone_type", "active")
SELECT home."id", breeding."id", 'heat', 'Heat', 'root_zone', true
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
  SELECT t."id"
  FROM "tent" AS t
  JOIN home ON home."id" = t."site_id"
  WHERE t."tent_id" = 'breeding'
),
heat_zone AS (
  SELECT z."id"
  FROM "zone" AS z
  JOIN home ON home."id" = z."site_id"
  JOIN breeding ON breeding."id" = z."tent_id"
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
  "ip",
  "provider_uid_kind",
  "provider_uid",
  "firmware_version"
)
SELECT
  home."id",
  breeding."id",
  heat_zone."id",
  'kasa-heat-pad-breeding',
  'Kasa breeding heat pad',
  'actuator',
  'kasa',
  true,
  jsonb_build_object(
    'kasa_alias', 'breeding-heater',
    'model', 'EP10',
    'hardware_version', '1.0 (US)',
    'firmware_version', '1.1.1 Build 250908 Rel.112508',
    'device_type', 'IOT.SMARTPLUGSWITCH'
  ),
  '192.168.1.202'::inet,
  'mac',
  '58:04:4F:10:49:A9',
  '1.1.1 Build 250908 Rel.112508'
FROM home, breeding, heat_zone
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
heat_pad AS (
  SELECT d."id"
  FROM "device" AS d
  JOIN home ON home."id" = d."site_id"
  WHERE d."device_id" = 'kasa-heat-pad-breeding'
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
  heat_pad."id",
  'heat_pad_power',
  'Heat Pad Power',
  'actuator',
  'heat_pad_on',
  'bool',
  'kasa',
  true,
  '{}'::jsonb
FROM heat_pad
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
breeding AS (
  SELECT t."id"
  FROM "tent" AS t
  JOIN home ON home."id" = t."site_id"
  WHERE t."tent_id" = 'breeding'
),
heat_pad AS (
  SELECT d."id"
  FROM "device" AS d
  JOIN home ON home."id" = d."site_id"
  WHERE d."device_id" = 'kasa-heat-pad-breeding'
),
heat_pad_power AS (
  SELECT c."id"
  FROM "capability" AS c
  JOIN heat_pad ON heat_pad."id" = c."device_id"
  WHERE c."capability_id" = 'heat_pad_power'
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
  breeding."id",
  heat_pad."id",
  heat_pad_power."id",
  'breeding-heat-pad-night',
  'heat_pad',
  '00:00'::time,
  '06:00'::time,
  'America/Denver',
  true
FROM home, breeding, heat_pad, heat_pad_power
ON CONFLICT ON CONSTRAINT "uq_schedule_tent_schedule_id" DO UPDATE SET
  "device_id" = EXCLUDED."device_id",
  "capability_id" = EXCLUDED."capability_id",
  "kind" = EXCLUDED."kind",
  "starts_local" = EXCLUDED."starts_local",
  "ends_local" = EXCLUDED."ends_local",
  "timezone" = EXCLUDED."timezone",
  "enabled" = EXCLUDED."enabled",
  "updated_at" = now();
