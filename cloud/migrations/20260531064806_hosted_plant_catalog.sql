-- Create "cloud_plant" table
CREATE TABLE "cloud_plant" (
  "plant_key" character varying(480) NOT NULL,
  "site_id" character varying(80) NOT NULL,
  "tent_id" character varying(80) NOT NULL,
  "grow_run_id" character varying(160) NOT NULL,
  "plant_id" character varying(80) NOT NULL,
  "name" character varying(160) NOT NULL,
  "display_order" integer NOT NULL,
  "sticker_color" character varying(40) NULL,
  "status" character varying(40) NOT NULL,
  "purple" boolean NOT NULL,
  "moisture_target_low" double precision NOT NULL,
  "moisture_target_high" double precision NOT NULL,
  "moisture_device_id" character varying(120) NULL,
  "moisture_capability_id" character varying(160) NULL,
  "wiki_path" character varying(500) NULL,
  "is_active" boolean NOT NULL,
  "synced_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("plant_key"),
  CONSTRAINT "cloud_plant_site_id_tent_id_grow_run_id_plant_id_key" UNIQUE ("site_id", "tent_id", "grow_run_id", "plant_id")
);
-- Create index "ix_cloud_plant_grow_run_id" to table: "cloud_plant"
CREATE INDEX "ix_cloud_plant_grow_run_id" ON "cloud_plant" ("grow_run_id");
-- Create index "ix_cloud_plant_moisture_capability_id" to table: "cloud_plant"
CREATE INDEX "ix_cloud_plant_moisture_capability_id" ON "cloud_plant" ("moisture_capability_id");
-- Create index "ix_cloud_plant_moisture_device_id" to table: "cloud_plant"
CREATE INDEX "ix_cloud_plant_moisture_device_id" ON "cloud_plant" ("moisture_device_id");
-- Create index "ix_cloud_plant_plant_id" to table: "cloud_plant"
CREATE INDEX "ix_cloud_plant_plant_id" ON "cloud_plant" ("plant_id");
-- Create index "ix_cloud_plant_site_id" to table: "cloud_plant"
CREATE INDEX "ix_cloud_plant_site_id" ON "cloud_plant" ("site_id");
-- Create index "ix_cloud_plant_tent_id" to table: "cloud_plant"
CREATE INDEX "ix_cloud_plant_tent_id" ON "cloud_plant" ("tent_id");
