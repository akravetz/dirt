-- Modify "cloud_plant_location" table
ALTER TABLE "cloud_plant_location" ALTER COLUMN "grid_position" DROP NOT NULL;
-- Create "cloud_cross_event" table
CREATE TABLE "cloud_cross_event" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "site_id" character varying(80) NOT NULL,
  "source_cross_event_id" bigint NOT NULL,
  "resulting_line_source_id" bigint NOT NULL,
  "seed_parent_source_plant_id" bigint NOT NULL,
  "pollen_parent_source_plant_id" bigint NOT NULL,
  "pollinated_at" timestamptz NOT NULL,
  "pollen_parent_is_reversed" boolean NULL,
  "notes" text NULL,
  "synced_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_cloud_cross_event_site_source_cross_event" UNIQUE ("site_id", "source_cross_event_id")
);
-- Create index "ix_cloud_cross_event_site_id" to table: "cloud_cross_event"
CREATE INDEX "ix_cloud_cross_event_site_id" ON "cloud_cross_event" ("site_id");
-- Create "cloud_plant_event" table
CREATE TABLE "cloud_plant_event" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "site_id" character varying(80) NOT NULL,
  "source_event_id" bigint NOT NULL,
  "source_plant_id" bigint NOT NULL,
  "is_pollen_collection" boolean NOT NULL,
  "is_seed_production" boolean NOT NULL,
  "is_clone_taken" boolean NOT NULL,
  "is_sex_observation" boolean NOT NULL,
  "is_reversal" boolean NOT NULL,
  "is_transplant" boolean NOT NULL,
  "is_selection_for_breeding" boolean NOT NULL,
  "occurred_at" timestamptz NOT NULL,
  "reason" text NULL,
  "notes" text NULL,
  "metadata" json NOT NULL,
  "synced_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_cloud_plant_event_site_source_event" UNIQUE ("site_id", "source_event_id")
);
-- Create index "ix_cloud_plant_event_plant_occurred_at" to table: "cloud_plant_event"
CREATE INDEX "ix_cloud_plant_event_plant_occurred_at" ON "cloud_plant_event" ("site_id", "source_plant_id", "occurred_at");
-- Create index "ix_cloud_plant_event_site_id" to table: "cloud_plant_event"
CREATE INDEX "ix_cloud_plant_event_site_id" ON "cloud_plant_event" ("site_id");
-- Create "cloud_plant_note" table
CREATE TABLE "cloud_plant_note" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "site_id" character varying(80) NOT NULL,
  "source_note_id" bigint NOT NULL,
  "source_plant_id" bigint NOT NULL,
  "observed_at" timestamptz NOT NULL,
  "body" text NOT NULL,
  "created_by" character varying(160) NULL,
  "synced_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_cloud_plant_note_site_source_note" UNIQUE ("site_id", "source_note_id")
);
-- Create index "ix_cloud_plant_note_plant_observed_at" to table: "cloud_plant_note"
CREATE INDEX "ix_cloud_plant_note_plant_observed_at" ON "cloud_plant_note" ("site_id", "source_plant_id", "observed_at");
-- Create index "ix_cloud_plant_note_site_id" to table: "cloud_plant_note"
CREATE INDEX "ix_cloud_plant_note_site_id" ON "cloud_plant_note" ("site_id");
