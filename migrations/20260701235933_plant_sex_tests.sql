-- Create "plant_sex_test" table
CREATE TABLE "plant_sex_test" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "plant_id" bigint NOT NULL,
  "vendor_name" text NOT NULL,
  "assay_name" text NULL,
  "vendor_test_code" text NOT NULL,
  "sample_collected_at" timestamptz NOT NULL,
  "sample_sent_at" timestamptz NULL,
  "result_received_at" timestamptz NULL,
  "result_sex_key" text NULL,
  "is_inconclusive" boolean NOT NULL DEFAULT false,
  "notes" text NULL,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  "updated_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_plant_sex_test_vendor_code" UNIQUE ("vendor_name", "vendor_test_code"),
  CONSTRAINT "fk_plant_sex_test_plant" FOREIGN KEY ("plant_id") REFERENCES "plant" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "fk_plant_sex_test_result_sex" FOREIGN KEY ("result_sex_key") REFERENCES "plant_lku_sex" ("key") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "ck_plant_sex_test_assay_name_not_blank" CHECK ((assay_name IS NULL) OR (btrim(assay_name) <> ''::text)),
  CONSTRAINT "ck_plant_sex_test_notes_not_blank" CHECK ((notes IS NULL) OR (btrim(notes) <> ''::text)),
  CONSTRAINT "ck_plant_sex_test_result_state" CHECK (((result_received_at IS NULL) AND (result_sex_key IS NULL) AND (NOT is_inconclusive)) OR ((result_received_at IS NOT NULL) AND ((
CASE
    WHEN (result_sex_key IS NOT NULL) THEN 1
    ELSE 0
END +
CASE
    WHEN is_inconclusive THEN 1
    ELSE 0
END) = 1))),
  CONSTRAINT "ck_plant_sex_test_timestamp_order" CHECK (((sample_sent_at IS NULL) OR (sample_sent_at >= sample_collected_at)) AND ((result_received_at IS NULL) OR (result_received_at >= sample_collected_at)) AND ((result_received_at IS NULL) OR (sample_sent_at IS NULL) OR (result_received_at >= sample_sent_at))),
  CONSTRAINT "ck_plant_sex_test_vendor_name_not_blank" CHECK (btrim(vendor_name) <> ''::text),
  CONSTRAINT "ck_plant_sex_test_vendor_test_code_not_blank" CHECK (btrim(vendor_test_code) <> ''::text)
);
-- Create index "ix_plant_sex_test_plant_sample_collected" to table: "plant_sex_test"
CREATE INDEX "ix_plant_sex_test_plant_sample_collected" ON "plant_sex_test" ("plant_id", "sample_collected_at" DESC);
-- Create index "ux_plant_sex_test_one_pending_per_plant" to table: "plant_sex_test"
CREATE UNIQUE INDEX "ux_plant_sex_test_one_pending_per_plant" ON "plant_sex_test" ("plant_id") WHERE (result_received_at IS NULL);
