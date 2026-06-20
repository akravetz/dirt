-- Modify "cloud_asset" table
ALTER TABLE "cloud_asset" DROP COLUMN "tent_id", DROP COLUMN "zone_id";
-- Modify "cloud_capability" table
ALTER TABLE "cloud_capability" DROP COLUMN "tent_id";
-- Modify "cloud_command" table
ALTER TABLE "cloud_command" DROP COLUMN "tent_id";
-- Modify "cloud_device" table
ALTER TABLE "cloud_device" DROP COLUMN "tent_id", DROP COLUMN "zone_id";
-- Modify "cloud_latest_metric" table
ALTER TABLE "cloud_latest_metric" DROP COLUMN "tent_id", DROP COLUMN "zone_id";
-- Modify "cloud_metric_rollup" table
ALTER TABLE "cloud_metric_rollup" DROP COLUMN "tent_id";
-- Modify "cloud_plant_location" table
ALTER TABLE "cloud_plant_location" DROP COLUMN "tent_id";
-- Modify "cloud_schedule" table
ALTER TABLE "cloud_schedule" DROP COLUMN "tent_id", DROP COLUMN "zone_id", DROP COLUMN "schedule_id";
-- Modify "cloud_tent" table
ALTER TABLE "cloud_tent" DROP COLUMN "tent_id";
-- Modify "cloud_zone" table
ALTER TABLE "cloud_zone" DROP COLUMN "tent_id", DROP COLUMN "zone_id";
