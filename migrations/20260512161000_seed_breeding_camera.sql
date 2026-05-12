-- Register the dirt2 breeding-tent PTZ camera in the scoped device catalog so
-- camera capture policy can derive the tent light schedule from existing
-- device/schedule site+tents relationships.
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
  'obsbot-breeding',
  'OBSBOT breeding camera',
  'camera',
  'dirt-camera',
  true,
  '{"host":"dirt2"}'::jsonb
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
    AND "device_id" = 'obsbot-breeding'
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
  'camera_action',
  NULL,
  NULL,
  'dirt-camera',
  true,
  '{}'::jsonb
FROM device
JOIN (VALUES
  ('camera_capture', 'Camera Capture'),
  ('ptz_move', 'PTZ Move')
) AS v("capability_id", "name") ON true
ON CONFLICT ON CONSTRAINT "uq_capability_device_capability_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "kind" = EXCLUDED."kind",
  "metric_name" = EXCLUDED."metric_name",
  "unit" = EXCLUDED."unit",
  "source" = EXCLUDED."source",
  "enabled" = EXCLUDED."enabled",
  "metadata" = EXCLUDED."metadata";
