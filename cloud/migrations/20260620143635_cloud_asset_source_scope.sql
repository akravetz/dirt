-- Modify "cloud_asset" table
ALTER TABLE "cloud_asset" ADD COLUMN "source_tent_id" bigint NULL, ADD COLUMN "source_zone_id" bigint NULL;
-- Backfill source identities that were added before this migration but left nullable.
UPDATE "cloud_tent"
SET "source_tent_id" = "tent_id"::bigint
WHERE "source_tent_id" IS NULL
  AND "tent_id" ~ '^[0-9]+$';

UPDATE "cloud_zone"
SET "source_zone_id" = "zone_id"::bigint
WHERE "source_zone_id" IS NULL
  AND "zone_id" ~ '^[0-9]+$';

UPDATE "cloud_schedule"
SET "source_schedule_id" = "schedule_id"::bigint
WHERE "source_schedule_id" IS NULL
  AND "schedule_id" ~ '^[0-9]+$';

UPDATE "cloud_zone" AS zone
SET "source_tent_id" = tent."source_tent_id"
FROM "cloud_tent" AS tent
WHERE zone."source_tent_id" IS NULL
  AND tent."site_id" = zone."site_id"
  AND tent."tent_id" = zone."tent_id"
  AND tent."source_tent_id" IS NOT NULL;

UPDATE "cloud_device" AS device
SET "source_tent_id" = tent."source_tent_id"
FROM "cloud_tent" AS tent
WHERE device."source_tent_id" IS NULL
  AND tent."site_id" = device."site_id"
  AND tent."tent_id" = device."tent_id"
  AND tent."source_tent_id" IS NOT NULL;

UPDATE "cloud_device" AS device
SET "source_zone_id" = zone."source_zone_id"
FROM "cloud_zone" AS zone
WHERE device."source_zone_id" IS NULL
  AND device."zone_id" IS NOT NULL
  AND zone."site_id" = device."site_id"
  AND zone."tent_id" = device."tent_id"
  AND zone."zone_id" = device."zone_id"
  AND zone."source_zone_id" IS NOT NULL;

UPDATE "cloud_capability" AS capability
SET "source_tent_id" = tent."source_tent_id"
FROM "cloud_tent" AS tent
WHERE capability."source_tent_id" IS NULL
  AND tent."site_id" = capability."site_id"
  AND tent."tent_id" = capability."tent_id"
  AND tent."source_tent_id" IS NOT NULL;

UPDATE "cloud_schedule" AS schedule
SET "source_site_id" = site."source_site_id"
FROM "cloud_site" AS site
WHERE schedule."source_site_id" IS NULL
  AND site."site_id" = schedule."site_id"
  AND site."source_site_id" IS NOT NULL;

UPDATE "cloud_schedule" AS schedule
SET "source_tent_id" = tent."source_tent_id"
FROM "cloud_tent" AS tent
WHERE schedule."source_tent_id" IS NULL
  AND tent."site_id" = schedule."site_id"
  AND tent."tent_id" = schedule."tent_id"
  AND tent."source_tent_id" IS NOT NULL;

UPDATE "cloud_schedule" AS schedule
SET "source_zone_id" = zone."source_zone_id"
FROM "cloud_zone" AS zone
WHERE schedule."source_zone_id" IS NULL
  AND schedule."zone_id" IS NOT NULL
  AND zone."site_id" = schedule."site_id"
  AND zone."tent_id" = schedule."tent_id"
  AND zone."zone_id" = schedule."zone_id"
  AND zone."source_zone_id" IS NOT NULL;

UPDATE "cloud_plant_location" AS location
SET "source_tent_id" = tent."source_tent_id"
FROM "cloud_tent" AS tent
WHERE location."source_tent_id" IS NULL
  AND tent."site_id" = location."site_id"
  AND tent."tent_id" = location."tent_id"
  AND tent."source_tent_id" IS NOT NULL;

UPDATE "cloud_latest_metric" AS metric
SET "source_site_id" = site."source_site_id"
FROM "cloud_site" AS site
WHERE metric."source_site_id" IS NULL
  AND site."site_id" = metric."site_id"
  AND site."source_site_id" IS NOT NULL;

UPDATE "cloud_latest_metric" AS metric
SET "source_tent_id" = tent."source_tent_id"
FROM "cloud_tent" AS tent
WHERE metric."source_tent_id" IS NULL
  AND tent."site_id" = metric."site_id"
  AND tent."tent_id" = metric."tent_id"
  AND tent."source_tent_id" IS NOT NULL;

UPDATE "cloud_latest_metric" AS metric
SET "source_zone_id" = zone."source_zone_id"
FROM "cloud_zone" AS zone
WHERE metric."source_zone_id" IS NULL
  AND metric."zone_id" IS NOT NULL
  AND zone."site_id" = metric."site_id"
  AND zone."tent_id" = metric."tent_id"
  AND zone."zone_id" = metric."zone_id"
  AND zone."source_zone_id" IS NOT NULL;

UPDATE "cloud_metric_rollup" AS rollup
SET "source_site_id" = site."source_site_id"
FROM "cloud_site" AS site
WHERE rollup."source_site_id" IS NULL
  AND site."site_id" = rollup."site_id"
  AND site."source_site_id" IS NOT NULL;

UPDATE "cloud_metric_rollup" AS rollup
SET "source_tent_id" = tent."source_tent_id"
FROM "cloud_tent" AS tent
WHERE rollup."source_tent_id" IS NULL
  AND tent."site_id" = rollup."site_id"
  AND tent."tent_id" = rollup."tent_id"
  AND tent."source_tent_id" IS NOT NULL;

UPDATE "cloud_command" AS command
SET "source_tent_id" = tent."source_tent_id"
FROM "cloud_tent" AS tent
WHERE command."source_tent_id" IS NULL
  AND tent."site_id" = command."site_id"
  AND tent."tent_id" = command."tent_id"
  AND tent."source_tent_id" IS NOT NULL;

UPDATE "cloud_asset" AS asset
SET "source_tent_id" = tent."source_tent_id"
FROM "cloud_tent" AS tent
WHERE asset."source_tent_id" IS NULL
  AND tent."site_id" = asset."site_id"
  AND tent."tent_id" = asset."tent_id"
  AND tent."source_tent_id" IS NOT NULL;

UPDATE "cloud_asset" AS asset
SET "source_zone_id" = zone."source_zone_id"
FROM "cloud_zone" AS zone
WHERE asset."source_zone_id" IS NULL
  AND asset."zone_id" IS NOT NULL
  AND zone."site_id" = asset."site_id"
  AND zone."tent_id" = asset."tent_id"
  AND zone."zone_id" = asset."zone_id"
  AND zone."source_zone_id" IS NOT NULL;
