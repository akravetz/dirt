-- Modify "cloud_plant" table
ALTER TABLE "cloud_plant" ADD COLUMN "taken_at" timestamptz NULL;
-- Set comment to column: "rooted_at" on table: "cloud_plant"
COMMENT ON COLUMN "cloud_plant"."rooted_at" IS 'Timestamp when a clone cutting was observed rooted; independent from when the cutting was taken.';
-- Set comment to column: "taken_at" on table: "cloud_plant"
COMMENT ON COLUMN "cloud_plant"."taken_at" IS 'Timestamp when a cutting was taken from its mother plant; clone propagation fact independent from rooting.';
-- Backfill pre-taken_at clones: previous clone projection stored the taken timestamp in rooted_at.
UPDATE "cloud_plant"
SET "taken_at" = "rooted_at",
    "rooted_at" = NULL
WHERE "clone_source_plant_id" IS NOT NULL
  AND "taken_at" IS NULL
  AND "rooted_at" IS NOT NULL;
