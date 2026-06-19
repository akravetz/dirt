-- Modify "cloud_capability" table
ALTER TABLE "cloud_capability" ADD COLUMN "source_tent_id" bigint NULL;
-- Modify "cloud_device" table
ALTER TABLE "cloud_device" ADD COLUMN "source_tent_id" bigint NULL, ADD COLUMN "source_zone_id" bigint NULL;
-- Modify "cloud_latest_metric" table
ALTER TABLE "cloud_latest_metric" ADD COLUMN "source_site_id" bigint NULL, ADD COLUMN "source_tent_id" bigint NULL, ADD COLUMN "source_zone_id" bigint NULL;
-- Modify "cloud_metric_rollup" table
ALTER TABLE "cloud_metric_rollup" ADD COLUMN "source_site_id" bigint NULL, ADD COLUMN "source_tent_id" bigint NULL;
-- Modify "cloud_plant_location" table
ALTER TABLE "cloud_plant_location" ADD COLUMN "source_tent_id" bigint NULL;
-- Modify "cloud_schedule" table
ALTER TABLE "cloud_schedule" ADD COLUMN "source_site_id" bigint NULL, ADD COLUMN "source_tent_id" bigint NULL, ADD COLUMN "source_zone_id" bigint NULL, ADD COLUMN "source_schedule_id" bigint NULL, ADD CONSTRAINT "uq_cloud_schedule_site_source_schedule" UNIQUE ("site_id", "source_schedule_id");
-- Modify "cloud_site" table
ALTER TABLE "cloud_site" ADD COLUMN "source_site_id" bigint NULL, ADD CONSTRAINT "uq_cloud_site_site_source_site" UNIQUE ("site_id", "source_site_id");
-- Modify "cloud_tent" table
ALTER TABLE "cloud_tent" ADD COLUMN "source_site_id" bigint NULL, ADD COLUMN "source_tent_id" bigint NULL, ADD COLUMN "role" character varying(80) NULL, ADD CONSTRAINT "uq_cloud_tent_site_source_tent" UNIQUE ("site_id", "source_tent_id");
-- Modify "cloud_zone" table
ALTER TABLE "cloud_zone" ADD COLUMN "source_tent_id" bigint NULL, ADD COLUMN "source_zone_id" bigint NULL, ADD CONSTRAINT "uq_cloud_zone_site_source_zone" UNIQUE ("site_id", "source_zone_id");
