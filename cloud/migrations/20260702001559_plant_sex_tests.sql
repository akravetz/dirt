-- Create "cloud_plant_sex_test" table
CREATE TABLE "cloud_plant_sex_test" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "site_id" character varying(80) NOT NULL,
  "source_sex_test_id" bigint NOT NULL,
  "source_plant_id" bigint NOT NULL,
  "vendor_name" character varying(160) NOT NULL,
  "assay_name" character varying(160) NULL,
  "vendor_test_code" character varying(160) NOT NULL,
  "sample_collected_at" timestamptz NOT NULL,
  "sample_sent_at" timestamptz NULL,
  "result_received_at" timestamptz NULL,
  "result_sex_key" character varying(40) NULL,
  "is_inconclusive" boolean NOT NULL,
  "notes" text NULL,
  "synced_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "ck_cloud_plant_sex_test_result_sex_key_lab_result" CHECK ((result_sex_key IS NULL) OR ((result_sex_key)::text IN ('male'::text, 'female'::text))),
  CONSTRAINT "uq_cloud_plant_sex_test_site_source_test" UNIQUE ("site_id", "source_sex_test_id"),
  CONSTRAINT "uq_cloud_plant_sex_test_site_vendor_code" UNIQUE ("site_id", "vendor_name", "vendor_test_code")
);
-- Create index "ix_cloud_plant_sex_test_site_id" to table: "cloud_plant_sex_test"
CREATE INDEX "ix_cloud_plant_sex_test_site_id" ON "cloud_plant_sex_test" ("site_id");
-- Create index "ix_cloud_plant_sex_test_site_result_received" to table: "cloud_plant_sex_test"
CREATE INDEX "ix_cloud_plant_sex_test_site_result_received" ON "cloud_plant_sex_test" ("site_id", "result_received_at");
-- Create index "ix_cloud_plant_sex_test_site_source_plant" to table: "cloud_plant_sex_test"
CREATE INDEX "ix_cloud_plant_sex_test_site_source_plant" ON "cloud_plant_sex_test" ("site_id", "source_plant_id");
