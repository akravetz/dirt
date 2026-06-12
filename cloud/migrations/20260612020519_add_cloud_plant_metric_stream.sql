-- Create "cloud_plant_metric_stream" table
CREATE TABLE "cloud_plant_metric_stream" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "site_id" character varying(80) NOT NULL,
  "tent_id" character varying(80) NOT NULL,
  "grow_run_id" character varying(160) NOT NULL,
  "plant_id" character varying(80) NOT NULL,
  "device_id" character varying(120) NOT NULL,
  "capability_id" character varying(160) NOT NULL,
  "metric" character varying(120) NOT NULL,
  "display_order" integer NOT NULL,
  "is_active" boolean NOT NULL,
  "synced_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_cloud_plant_metric_stream_identity" UNIQUE ("site_id", "tent_id", "grow_run_id", "plant_id", "device_id", "capability_id", "metric")
);
-- Create index "ix_cloud_plant_metric_stream_capability_id" to table: "cloud_plant_metric_stream"
CREATE INDEX "ix_cloud_plant_metric_stream_capability_id" ON "cloud_plant_metric_stream" ("capability_id");
-- Create index "ix_cloud_plant_metric_stream_device_id" to table: "cloud_plant_metric_stream"
CREATE INDEX "ix_cloud_plant_metric_stream_device_id" ON "cloud_plant_metric_stream" ("device_id");
-- Create index "ix_cloud_plant_metric_stream_grow_run_id" to table: "cloud_plant_metric_stream"
CREATE INDEX "ix_cloud_plant_metric_stream_grow_run_id" ON "cloud_plant_metric_stream" ("grow_run_id");
-- Create index "ix_cloud_plant_metric_stream_metric" to table: "cloud_plant_metric_stream"
CREATE INDEX "ix_cloud_plant_metric_stream_metric" ON "cloud_plant_metric_stream" ("metric");
-- Create index "ix_cloud_plant_metric_stream_plant_id" to table: "cloud_plant_metric_stream"
CREATE INDEX "ix_cloud_plant_metric_stream_plant_id" ON "cloud_plant_metric_stream" ("plant_id");
-- Create index "ix_cloud_plant_metric_stream_site_id" to table: "cloud_plant_metric_stream"
CREATE INDEX "ix_cloud_plant_metric_stream_site_id" ON "cloud_plant_metric_stream" ("site_id");
-- Create index "ix_cloud_plant_metric_stream_tent_id" to table: "cloud_plant_metric_stream"
CREATE INDEX "ix_cloud_plant_metric_stream_tent_id" ON "cloud_plant_metric_stream" ("tent_id");
