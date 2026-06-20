-- atlas:txmode none

-- Create index "ix_cloud_asset_site_source_tent_captured" to table: "cloud_asset"
CREATE INDEX CONCURRENTLY "ix_cloud_asset_site_source_tent_captured" ON "cloud_asset" ("site_id", "source_tent_id", "captured_at");
-- Create index "ix_cloud_asset_site_source_zone_captured" to table: "cloud_asset"
CREATE INDEX CONCURRENTLY "ix_cloud_asset_site_source_zone_captured" ON "cloud_asset" ("site_id", "source_zone_id", "captured_at");
-- Create index "ux_cloud_asset_site_source_tent_object_key" to table: "cloud_asset"
CREATE UNIQUE INDEX CONCURRENTLY "ux_cloud_asset_site_source_tent_object_key" ON "cloud_asset" ("site_id", "source_tent_id", "object_key");
-- Create index "ux_cloud_capability_site_source_tent_device_cap" to table: "cloud_capability"
CREATE UNIQUE INDEX CONCURRENTLY "ux_cloud_capability_site_source_tent_device_cap" ON "cloud_capability" ("site_id", "source_tent_id", "device_id", "capability_id");
-- Create index "ix_cloud_device_site_source_zone" to table: "cloud_device"
CREATE INDEX CONCURRENTLY "ix_cloud_device_site_source_zone" ON "cloud_device" ("site_id", "source_zone_id");
-- Create index "ux_cloud_device_site_source_tent_device" to table: "cloud_device"
CREATE UNIQUE INDEX CONCURRENTLY "ux_cloud_device_site_source_tent_device" ON "cloud_device" ("site_id", "source_tent_id", "device_id");
-- Create index "ux_cloud_latest_metric_site_source_stream" to table: "cloud_latest_metric"
CREATE UNIQUE INDEX CONCURRENTLY "ux_cloud_latest_metric_site_source_stream" ON "cloud_latest_metric" ("site_id", "source_tent_id", "device_id", "capability_id", "metric");
-- Create index "ix_cloud_metric_rollup_site_source_metric_bucket" to table: "cloud_metric_rollup"
CREATE INDEX CONCURRENTLY "ix_cloud_metric_rollup_site_source_metric_bucket" ON "cloud_metric_rollup" ("site_id", "source_tent_id", "metric", "bucket", "bucket_start_at");
-- Create index "ux_cloud_metric_rollup_site_source_stream_bucket" to table: "cloud_metric_rollup"
CREATE UNIQUE INDEX CONCURRENTLY "ux_cloud_metric_rollup_site_source_stream_bucket" ON "cloud_metric_rollup" ("site_id", "source_tent_id", "device_id", "capability_id", "metric", "bucket", "bucket_start_at");
-- Create index "ix_cloud_schedule_site_source_tent_kind" to table: "cloud_schedule"
CREATE INDEX CONCURRENTLY "ix_cloud_schedule_site_source_tent_kind" ON "cloud_schedule" ("site_id", "source_tent_id", "kind");
-- Create index "ix_cloud_schedule_site_source_zone" to table: "cloud_schedule"
CREATE INDEX CONCURRENTLY "ix_cloud_schedule_site_source_zone" ON "cloud_schedule" ("site_id", "source_zone_id");
-- Create index "ix_cloud_zone_site_source_tent" to table: "cloud_zone"
CREATE INDEX CONCURRENTLY "ix_cloud_zone_site_source_tent" ON "cloud_zone" ("site_id", "source_tent_id");
