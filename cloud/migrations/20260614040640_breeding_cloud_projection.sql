-- atlas:nolint DS102

-- The cloud plant tables are gateway-reseeded mirrors. The local source identity
-- changed from grow-run scoped text IDs to integer plant IDs, so preserving rows
-- through ALTER/backfill would keep misleading projection data.
DROP TABLE "cloud_plant_metric_stream";
DROP TABLE "cloud_plant";

-- Create "cloud_plant_line" table
CREATE TABLE "cloud_plant_line" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "site_id" character varying(80) NOT NULL,
  "source_line_id" bigint NOT NULL,
  "project_code" character varying(80) NULL,
  "generation_label" character varying(80) NULL,
  "strain" character varying(160) NOT NULL,
  "cultivar" character varying(160) NOT NULL,
  "description" text NULL,
  "source_name" character varying(160) NULL,
  "synced_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_cloud_plant_line_site_source_line" UNIQUE ("site_id", "source_line_id")
);
-- Create index "ix_cloud_plant_line_site_id" to table: "cloud_plant_line"
CREATE INDEX "ix_cloud_plant_line_site_id" ON "cloud_plant_line" ("site_id");

-- Create "cloud_seed_lot" table
CREATE TABLE "cloud_seed_lot" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "site_id" character varying(80) NOT NULL,
  "source_seed_lot_id" bigint NOT NULL,
  "line_source_id" bigint NOT NULL,
  "is_purchased" boolean NOT NULL,
  "vendor_name" character varying(160) NULL,
  "acquired_at" timestamptz NULL,
  "produced_by_cross_event_source_id" bigint NULL,
  "seed_count" integer NULL,
  "notes" text NULL,
  "synced_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_cloud_seed_lot_site_source_seed_lot" UNIQUE ("site_id", "source_seed_lot_id")
);
-- Create index "ix_cloud_seed_lot_site_id" to table: "cloud_seed_lot"
CREATE INDEX "ix_cloud_seed_lot_site_id" ON "cloud_seed_lot" ("site_id");

-- Create "cloud_plant" table
CREATE TABLE "cloud_plant" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "site_id" character varying(80) NOT NULL,
  "source_plant_id" bigint NOT NULL,
  "line_source_id" bigint NOT NULL,
  "source_seed_lot_id" bigint NULL,
  "clone_source_plant_id" bigint NULL,
  "key" character varying(120) NOT NULL,
  "name" character varying(160) NOT NULL,
  "germinated_at" timestamptz NULL,
  "rooted_at" timestamptz NULL,
  "veg_started_at" timestamptz NULL,
  "flower_started_at" timestamptz NULL,
  "culled_at" timestamptz NULL,
  "culled_reason" text NULL,
  "harvested_at" timestamptz NULL,
  "selected_for_breeding_at" timestamptz NULL,
  "selected_for_breeding_reason" text NULL,
  "is_active" boolean NOT NULL,
  "synced_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_cloud_plant_site_source_plant" UNIQUE ("site_id", "source_plant_id")
);
-- Create index "ix_cloud_plant_key" to table: "cloud_plant"
CREATE INDEX "ix_cloud_plant_key" ON "cloud_plant" ("key");
-- Create index "ix_cloud_plant_site_id" to table: "cloud_plant"
CREATE INDEX "ix_cloud_plant_site_id" ON "cloud_plant" ("site_id");

-- Create "cloud_plant_location" table
CREATE TABLE "cloud_plant_location" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "site_id" character varying(80) NOT NULL,
  "source_location_id" bigint NOT NULL,
  "source_plant_id" bigint NOT NULL,
  "tent_id" character varying(80) NOT NULL,
  "grid_position" character varying(80) NOT NULL,
  "start_at" timestamptz NOT NULL,
  "end_at" timestamptz NULL,
  "synced_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_cloud_plant_location_site_source_location" UNIQUE ("site_id", "source_location_id")
);
-- Create index "ix_cloud_plant_location_current_tent" to table: "cloud_plant_location"
CREATE INDEX "ix_cloud_plant_location_current_tent" ON "cloud_plant_location" ("site_id", "tent_id", "grid_position", "source_plant_id");
-- Create index "ix_cloud_plant_location_site_id" to table: "cloud_plant_location"
CREATE INDEX "ix_cloud_plant_location_site_id" ON "cloud_plant_location" ("site_id");
-- Create index "ix_cloud_plant_location_tent_id" to table: "cloud_plant_location"
CREATE INDEX "ix_cloud_plant_location_tent_id" ON "cloud_plant_location" ("tent_id");

-- Create "cloud_plant_metric_stream" table
CREATE TABLE "cloud_plant_metric_stream" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "site_id" character varying(80) NOT NULL,
  "source_plant_id" bigint NOT NULL,
  "device_id" character varying(120) NOT NULL,
  "capability_id" character varying(160) NOT NULL,
  "metric" character varying(120) NOT NULL,
  "display_order" integer NOT NULL,
  "is_active" boolean NOT NULL,
  "synced_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_cloud_plant_metric_stream_identity" UNIQUE ("site_id", "source_plant_id", "device_id", "capability_id", "metric")
);
-- Create index "ix_cloud_plant_metric_stream_capability_id" to table: "cloud_plant_metric_stream"
CREATE INDEX "ix_cloud_plant_metric_stream_capability_id" ON "cloud_plant_metric_stream" ("capability_id");
-- Create index "ix_cloud_plant_metric_stream_device_id" to table: "cloud_plant_metric_stream"
CREATE INDEX "ix_cloud_plant_metric_stream_device_id" ON "cloud_plant_metric_stream" ("device_id");
-- Create index "ix_cloud_plant_metric_stream_metric" to table: "cloud_plant_metric_stream"
CREATE INDEX "ix_cloud_plant_metric_stream_metric" ON "cloud_plant_metric_stream" ("metric");
-- Create index "ix_cloud_plant_metric_stream_site_id" to table: "cloud_plant_metric_stream"
CREATE INDEX "ix_cloud_plant_metric_stream_site_id" ON "cloud_plant_metric_stream" ("site_id");
