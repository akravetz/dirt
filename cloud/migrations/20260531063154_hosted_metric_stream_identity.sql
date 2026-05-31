-- atlas:txmode none

-- Modify "cloud_capability" table
ALTER TABLE "cloud_capability" ALTER COLUMN "capability_key" TYPE character varying(480);
UPDATE "cloud_capability"
SET "capability_key" = "site_id" || ':' || "tent_id" || ':' || "device_id" || ':' || "capability_id"
WHERE "capability_key" != "site_id" || ':' || "tent_id" || ':' || "device_id" || ':' || "capability_id";
ALTER TABLE "cloud_capability" DROP CONSTRAINT "cloud_capability_site_id_tent_id_capability_id_key", ADD CONSTRAINT "cloud_capability_site_id_tent_id_device_id_capability_id_key" UNIQUE ("site_id", "tent_id", "device_id", "capability_id");
-- Modify "cloud_latest_metric" table
ALTER TABLE "cloud_latest_metric" ALTER COLUMN "metric_key" TYPE character varying(700);
DELETE FROM "cloud_latest_metric" WHERE "device_id" IS NULL;
UPDATE "cloud_latest_metric"
SET "metric_key" = "site_id" || ':' || "tent_id" || ':' || "device_id" || ':' || "capability_id" || ':' || "metric"
WHERE "metric_key" != "site_id" || ':' || "tent_id" || ':' || "device_id" || ':' || "capability_id" || ':' || "metric";
ALTER TABLE "cloud_latest_metric" DROP CONSTRAINT "cloud_latest_metric_site_id_tent_id_capability_id_metric_key", ALTER COLUMN "device_id" SET NOT NULL, ADD CONSTRAINT "cloud_latest_metric_site_id_tent_id_device_id_capability_id_key" UNIQUE ("site_id", "tent_id", "device_id", "capability_id", "metric");
-- Modify "cloud_metric_rollup" table
DELETE FROM "cloud_metric_rollup";
ALTER TABLE "cloud_metric_rollup" ALTER COLUMN "rollup_key" TYPE character varying(700);
ALTER TABLE "cloud_metric_rollup" DROP CONSTRAINT "cloud_metric_rollup_site_id_tent_id_capability_id_metric_bu_key", ADD COLUMN "device_id" character varying(120);
ALTER TABLE "cloud_metric_rollup" ALTER COLUMN "device_id" SET NOT NULL, ADD CONSTRAINT "cloud_metric_rollup_site_id_tent_id_device_id_capability_id_key" UNIQUE ("site_id", "tent_id", "device_id", "capability_id", "metric", "bucket", "bucket_start_at");
-- Create index "ix_cloud_metric_rollup_device_id" to table: "cloud_metric_rollup"
CREATE INDEX CONCURRENTLY "ix_cloud_metric_rollup_device_id" ON "cloud_metric_rollup" ("device_id");
