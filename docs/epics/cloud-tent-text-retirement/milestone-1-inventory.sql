-- Cloud scoped text bridge retirement, Milestone 1 inventory.
--
-- Run against the hosted control-plane database before Milestone 2 backfills.
-- The result set counts rows where a legacy source-owned text scope value is
-- present while the canonical source ID is missing. cloud_asset is included as
-- a schema gap because source_tent_id/source_zone_id do not exist there yet.

SELECT
  'cloud_tent.tent_id' AS legacy_path,
  'source_tent_id_missing' AS inventory_gap,
  COUNT(*) AS row_count
FROM cloud_tent
WHERE source_tent_id IS NULL
  AND NULLIF(tent_id, '') IS NOT NULL

UNION ALL
SELECT
  'cloud_zone.tent_id',
  'source_tent_id_missing',
  COUNT(*)
FROM cloud_zone
WHERE source_tent_id IS NULL
  AND NULLIF(tent_id, '') IS NOT NULL

UNION ALL
SELECT
  'cloud_zone.zone_id',
  'source_zone_id_missing',
  COUNT(*)
FROM cloud_zone
WHERE source_zone_id IS NULL
  AND NULLIF(zone_id, '') IS NOT NULL

UNION ALL
SELECT
  'cloud_device.tent_id',
  'source_tent_id_missing',
  COUNT(*)
FROM cloud_device
WHERE source_tent_id IS NULL
  AND NULLIF(tent_id, '') IS NOT NULL

UNION ALL
SELECT
  'cloud_device.zone_id',
  'source_zone_id_missing',
  COUNT(*)
FROM cloud_device
WHERE source_zone_id IS NULL
  AND NULLIF(zone_id, '') IS NOT NULL

UNION ALL
SELECT
  'cloud_capability.tent_id',
  'source_tent_id_missing',
  COUNT(*)
FROM cloud_capability
WHERE source_tent_id IS NULL
  AND NULLIF(tent_id, '') IS NOT NULL

UNION ALL
SELECT
  'cloud_schedule.tent_id',
  'source_tent_id_missing',
  COUNT(*)
FROM cloud_schedule
WHERE source_tent_id IS NULL
  AND NULLIF(tent_id, '') IS NOT NULL

UNION ALL
SELECT
  'cloud_schedule.zone_id',
  'source_zone_id_missing',
  COUNT(*)
FROM cloud_schedule
WHERE source_zone_id IS NULL
  AND NULLIF(zone_id, '') IS NOT NULL

UNION ALL
SELECT
  'cloud_schedule.schedule_id',
  'source_schedule_id_missing',
  COUNT(*)
FROM cloud_schedule
WHERE source_schedule_id IS NULL
  AND NULLIF(schedule_id, '') IS NOT NULL

UNION ALL
SELECT
  'cloud_plant_location.tent_id',
  'source_tent_id_missing',
  COUNT(*)
FROM cloud_plant_location
WHERE source_tent_id IS NULL
  AND NULLIF(tent_id, '') IS NOT NULL

UNION ALL
SELECT
  'cloud_latest_metric.tent_id',
  'source_tent_id_missing',
  COUNT(*)
FROM cloud_latest_metric
WHERE source_tent_id IS NULL
  AND NULLIF(tent_id, '') IS NOT NULL

UNION ALL
SELECT
  'cloud_latest_metric.zone_id',
  'source_zone_id_missing',
  COUNT(*)
FROM cloud_latest_metric
WHERE source_zone_id IS NULL
  AND NULLIF(zone_id, '') IS NOT NULL

UNION ALL
SELECT
  'cloud_metric_rollup.tent_id',
  'source_tent_id_missing',
  COUNT(*)
FROM cloud_metric_rollup
WHERE source_tent_id IS NULL
  AND NULLIF(tent_id, '') IS NOT NULL

UNION ALL
SELECT
  'cloud_asset.tent_id',
  'source_tent_id_column_absent',
  COUNT(*)
FROM cloud_asset
WHERE NULLIF(tent_id, '') IS NOT NULL

UNION ALL
SELECT
  'cloud_asset.zone_id',
  'source_zone_id_column_absent',
  COUNT(*)
FROM cloud_asset
WHERE NULLIF(zone_id, '') IS NOT NULL

UNION ALL
SELECT
  'cloud_command.tent_id',
  'source_tent_id_missing',
  COUNT(*)
FROM cloud_command
WHERE source_tent_id IS NULL
  AND NULLIF(tent_id, '') IS NOT NULL

ORDER BY legacy_path, inventory_gap;
