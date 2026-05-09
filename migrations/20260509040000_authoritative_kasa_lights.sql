-- Add provider-neutral stable hardware identity for controller devices.
ALTER TABLE "device"
  ADD COLUMN "provider_uid_kind" text NULL,
  ADD COLUMN "provider_uid" text NULL;

CREATE UNIQUE INDEX "ux_device_provider_uid"
  ON "device" ("controller", "provider_uid_kind", "provider_uid")
  WHERE "provider_uid_kind" IS NOT NULL AND "provider_uid" IS NOT NULL;

-- Add the clone area as a first-class tent so it can own an independent
-- photoperiod and appear in local/hosted tent selectors.
WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
)
INSERT INTO "tent" ("site_id", "tent_id", "name", "role", "is_default", "active")
SELECT home."id", 'clones', 'Clone Tent', 'clone', false, true
FROM home
ON CONFLICT ON CONSTRAINT "uq_tent_site_tent_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "role" = EXCLUDED."role",
  "is_default" = EXCLUDED."is_default",
  "active" = EXCLUDED."active",
  "updated_at" = now();

-- Ensure each light-controlled scope has a lights zone.
WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
scopes AS (
  SELECT home."id" AS "site_id", t."id" AS "tent_id"
  FROM home
  JOIN "tent" AS t ON t."site_id" = home."id"
  WHERE t."tent_id" IN ('main', 'breeding', 'clones')
)
INSERT INTO "zone" ("site_id", "tent_id", "zone_id", "name", "zone_type", "active")
SELECT scopes."site_id", scopes."tent_id", 'lights', 'Lights', 'fixture', true
FROM scopes
ON CONFLICT ON CONSTRAINT "uq_zone_scope_zone_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "zone_type" = EXCLUDED."zone_type",
  "active" = EXCLUDED."active",
  "updated_at" = now();

-- Canonical Kasa EP10 light devices. The MAC is the stable identity; IP is
-- only a fast connection hint and may be refreshed by local discovery.
WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
device_rows AS (
  SELECT
    v."tent_id",
    v."device_id",
    v."name",
    v."ip"::inet AS "ip",
    v."mac",
    jsonb_build_object(
      'kasa_alias', v."alias",
      'model', 'EP10',
      'hardware_version', '1.0 (US)',
      'firmware_version', '1.1.1 Build 250908 Rel.112508'
    ) AS "metadata"
  FROM (VALUES
    ('main', 'kasa-lights-main', 'Kasa grow lights', '192.168.1.181', '6C:4C:BC:45:37:F6', 'lights'),
    ('clones', 'kasa-lights-clones', 'Kasa clone lights', '192.168.1.220', '10:5A:95:8B:E8:B7', 'clone-light'),
    ('breeding', 'kasa-lights-breeding', 'Kasa breeding tent lights', '192.168.1.180', '10:5A:95:8B:E6:76', 'breeding-tent-light')
  ) AS v("tent_id", "device_id", "name", "ip", "mac", "alias")
),
resolved AS (
  SELECT
    home."id" AS "site_pk",
    t."id" AS "tent_pk",
    z."id" AS "zone_pk",
    device_rows.*
  FROM home
  JOIN device_rows ON true
  JOIN "tent" AS t
    ON t."site_id" = home."id"
   AND t."tent_id" = device_rows."tent_id"
  JOIN "zone" AS z
    ON z."site_id" = home."id"
   AND z."tent_id" = t."id"
   AND z."zone_id" = 'lights'
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
  resolved."site_pk",
  resolved."tent_pk",
  resolved."zone_pk",
  resolved."device_id",
  resolved."name",
  'actuator',
  'kasa',
  true,
  resolved."metadata",
  resolved."ip",
  'mac',
  resolved."mac",
  '1.1.1 Build 250908 Rel.112508'
FROM resolved
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

-- All Kasa light plugs expose one actuator capability used by schedules.
WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
kasa_devices AS (
  SELECT d."id"
  FROM "device" AS d
  JOIN home ON home."id" = d."site_id"
  WHERE d."device_id" IN (
    'kasa-lights-main',
    'kasa-lights-clones',
    'kasa-lights-breeding'
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
  kasa_devices."id",
  'lights_power',
  'Lights Power',
  'actuator',
  NULL,
  NULL,
  'kasa',
  true,
  '{}'::jsonb
FROM kasa_devices
ON CONFLICT ON CONSTRAINT "uq_capability_device_capability_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "kind" = EXCLUDED."kind",
  "metric_name" = EXCLUDED."metric_name",
  "unit" = EXCLUDED."unit",
  "source" = EXCLUDED."source",
  "enabled" = EXCLUDED."enabled",
  "metadata" = EXCLUDED."metadata";

-- Enabled light schedules. Main remains 12/12; clone and breeding lights run
-- 18/6 from 06:00 to midnight in the local tent timezone.
WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
schedule_rows AS (
  SELECT *
  FROM (VALUES
    ('main', 'main-lights-photoperiod', 'kasa-lights-main', '09:00'::time, '21:00'::time),
    ('clones', 'clones-lights-photoperiod', 'kasa-lights-clones', '06:00'::time, '00:00'::time),
    ('breeding', 'breeding-lights-photoperiod', 'kasa-lights-breeding', '06:00'::time, '00:00'::time)
  ) AS v("tent_id", "schedule_id", "device_id", "starts_local", "ends_local")
),
resolved AS (
  SELECT
    home."id" AS "site_pk",
    t."id" AS "tent_pk",
    d."id" AS "device_pk",
    c."id" AS "capability_pk",
    schedule_rows."schedule_id",
    schedule_rows."starts_local",
    schedule_rows."ends_local"
  FROM home
  JOIN schedule_rows ON true
  JOIN "tent" AS t
    ON t."site_id" = home."id"
   AND t."tent_id" = schedule_rows."tent_id"
  JOIN "device" AS d
    ON d."site_id" = home."id"
   AND d."device_id" = schedule_rows."device_id"
  JOIN "capability" AS c
    ON c."device_id" = d."id"
   AND c."capability_id" = 'lights_power'
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
  resolved."site_pk",
  resolved."tent_pk",
  resolved."device_pk",
  resolved."capability_pk",
  resolved."schedule_id",
  'lights',
  resolved."starts_local",
  resolved."ends_local",
  'America/Denver',
  true
FROM resolved
ON CONFLICT ON CONSTRAINT "uq_schedule_tent_schedule_id" DO UPDATE SET
  "device_id" = EXCLUDED."device_id",
  "capability_id" = EXCLUDED."capability_id",
  "kind" = EXCLUDED."kind",
  "starts_local" = EXCLUDED."starts_local",
  "ends_local" = EXCLUDED."ends_local",
  "timezone" = EXCLUDED."timezone",
  "enabled" = EXCLUDED."enabled",
  "updated_at" = now();
