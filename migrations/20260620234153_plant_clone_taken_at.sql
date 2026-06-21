-- Modify "plant" table
ALTER TABLE "plant" ADD COLUMN "taken_at" timestamptz NULL;
-- Set comment to column: "rooted_at" on table: "plant"
COMMENT ON COLUMN "plant"."rooted_at" IS 'Timestamp when a clone cutting was observed rooted; independent from when the cutting was taken.';
-- Set comment to column: "taken_at" on table: "plant"
COMMENT ON COLUMN "plant"."taken_at" IS 'Timestamp when a cutting was taken from its mother plant; clone propagation fact independent from rooting.';
-- Backfill pre-taken_at clones: previous clone creation stored the taken timestamp in rooted_at.
UPDATE "plant"
SET "taken_at" = "rooted_at",
    "rooted_at" = NULL
WHERE "clone_source_plant_id" IS NOT NULL
  AND "taken_at" IS NULL
  AND "rooted_at" IS NOT NULL;
-- Add seed-grown propagation guard after backfill.
ALTER TABLE "plant" ADD CONSTRAINT "ck_plant_seed_not_taken_as_clone" CHECK ("source_seed_lot_id" IS NULL OR "taken_at" IS NULL) NOT VALID;
ALTER TABLE "plant" VALIDATE CONSTRAINT "ck_plant_seed_not_taken_as_clone";
