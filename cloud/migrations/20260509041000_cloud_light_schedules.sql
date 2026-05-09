-- Create "cloud_schedule" table
CREATE TABLE "cloud_schedule" (
  "schedule_key" character varying(320) NOT NULL,
  "site_id" character varying(80) NOT NULL,
  "tent_id" character varying(80) NOT NULL,
  "zone_id" character varying(80) NULL,
  "device_id" character varying(120) NULL,
  "capability_id" character varying(160) NULL,
  "schedule_id" character varying(160) NOT NULL,
  "kind" character varying(80) NOT NULL,
  "starts_local" time NOT NULL,
  "ends_local" time NOT NULL,
  "timezone" character varying(80) NOT NULL,
  "is_enabled" boolean NOT NULL,
  "synced_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("schedule_key"),
  CONSTRAINT "cloud_schedule_site_id_tent_id_schedule_id_key" UNIQUE ("site_id", "tent_id", "schedule_id")
);
-- Create index "ix_cloud_schedule_capability_id" to table: "cloud_schedule"
CREATE INDEX "ix_cloud_schedule_capability_id" ON "cloud_schedule" ("capability_id");
-- Create index "ix_cloud_schedule_device_id" to table: "cloud_schedule"
CREATE INDEX "ix_cloud_schedule_device_id" ON "cloud_schedule" ("device_id");
-- Create index "ix_cloud_schedule_schedule_id" to table: "cloud_schedule"
CREATE INDEX "ix_cloud_schedule_schedule_id" ON "cloud_schedule" ("schedule_id");
-- Create index "ix_cloud_schedule_site_id" to table: "cloud_schedule"
CREATE INDEX "ix_cloud_schedule_site_id" ON "cloud_schedule" ("site_id");
-- Create index "ix_cloud_schedule_tent_id" to table: "cloud_schedule"
CREATE INDEX "ix_cloud_schedule_tent_id" ON "cloud_schedule" ("tent_id");
-- Create index "ix_cloud_schedule_zone_id" to table: "cloud_schedule"
CREATE INDEX "ix_cloud_schedule_zone_id" ON "cloud_schedule" ("zone_id");
