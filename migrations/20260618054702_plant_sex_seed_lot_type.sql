-- Create "plant_lku_sex" table
CREATE TABLE "plant_lku_sex" (
  "key" text NOT NULL,
  "display_name" text NOT NULL,
  "display_order" integer NOT NULL,
  "is_male" boolean NOT NULL DEFAULT false,
  "is_female" boolean NOT NULL DEFAULT false,
  "is_intersex" boolean NOT NULL DEFAULT false,
  "is_reversed" boolean NOT NULL DEFAULT false,
  PRIMARY KEY ("key")
);
-- Set comment to table: "plant_lku_sex"
COMMENT ON TABLE "plant_lku_sex" IS 'Controlled plant sex values with display and semantic metadata.';
-- Set comment to column: "key" on table: "plant_lku_sex"
COMMENT ON COLUMN "plant_lku_sex"."key" IS 'Controlled plant sex lookup key referenced by plant.sex_key.';
INSERT INTO "plant_lku_sex" (
  "key",
  "display_name",
  "display_order",
  "is_male",
  "is_female",
  "is_intersex",
  "is_reversed"
) VALUES
  ('unknown', 'Unknown', 0, false, false, false, false),
  ('male', 'Male', 10, true, false, false, false),
  ('female', 'Female', 20, false, true, false, false),
  ('herm', 'Intersex / Herm', 30, false, false, true, false),
  ('reversed', 'Reversed', 40, false, false, false, true)
ON CONFLICT ("key") DO UPDATE SET
  "display_name" = EXCLUDED."display_name",
  "display_order" = EXCLUDED."display_order",
  "is_male" = EXCLUDED."is_male",
  "is_female" = EXCLUDED."is_female",
  "is_intersex" = EXCLUDED."is_intersex",
  "is_reversed" = EXCLUDED."is_reversed";
-- Create "seed_lot_lku_sex_type" table
CREATE TABLE "seed_lot_lku_sex_type" (
  "key" text NOT NULL,
  "display_name" text NOT NULL,
  "display_order" integer NOT NULL,
  "is_feminized" boolean NOT NULL DEFAULT false,
  "is_regular" boolean NOT NULL DEFAULT false,
  PRIMARY KEY ("key")
);
-- Set comment to table: "seed_lot_lku_sex_type"
COMMENT ON TABLE "seed_lot_lku_sex_type" IS 'Controlled seed-lot sex type values with display and semantic metadata.';
-- Set comment to column: "key" on table: "seed_lot_lku_sex_type"
COMMENT ON COLUMN "seed_lot_lku_sex_type"."key" IS 'Controlled seed-lot sex type lookup key referenced by seed_lot.sex_type_key.';
INSERT INTO "seed_lot_lku_sex_type" (
  "key",
  "display_name",
  "display_order",
  "is_feminized",
  "is_regular"
) VALUES
  ('unknown', 'Unknown', 0, false, false),
  ('feminized', 'Feminized', 10, true, false),
  ('regular', 'Regular', 20, false, true)
ON CONFLICT ("key") DO UPDATE SET
  "display_name" = EXCLUDED."display_name",
  "display_order" = EXCLUDED."display_order",
  "is_feminized" = EXCLUDED."is_feminized",
  "is_regular" = EXCLUDED."is_regular";
-- Modify "plant" table
ALTER TABLE "plant" ADD COLUMN "sex_key" text NOT NULL DEFAULT 'unknown';
-- Set comment to column: "sex_key" on table: "plant"
COMMENT ON COLUMN "plant"."sex_key" IS 'Lookup-backed controlled plant sex value used for display and semantic branching metadata.';
ALTER TABLE "plant" ADD CONSTRAINT "fk_plant_sex" FOREIGN KEY ("sex_key") REFERENCES "plant_lku_sex" ("key") ON UPDATE NO ACTION ON DELETE RESTRICT NOT VALID;
ALTER TABLE "plant" VALIDATE CONSTRAINT "fk_plant_sex";
-- Modify "seed_lot" table
ALTER TABLE "seed_lot" ADD COLUMN "sex_type_key" text NOT NULL DEFAULT 'unknown';
-- Set comment to column: "sex_type_key" on table: "seed_lot"
COMMENT ON COLUMN "seed_lot"."sex_type_key" IS 'Lookup-backed controlled seed-lot sex type used for display and semantic branching metadata.';
ALTER TABLE "seed_lot" ADD CONSTRAINT "fk_seed_lot_sex_type" FOREIGN KEY ("sex_type_key") REFERENCES "seed_lot_lku_sex_type" ("key") ON UPDATE NO ACTION ON DELETE RESTRICT NOT VALID;
ALTER TABLE "seed_lot" VALIDATE CONSTRAINT "fk_seed_lot_sex_type";
DO $$
DECLARE
  feminized_seed_lot_id bigint;
  regular_line_id bigint;
  regular_seed_lot_id bigint;
BEGIN
  SELECT source_seed_lot_id
    INTO feminized_seed_lot_id
  FROM plant
  WHERE key IN (
      'SBBS-R1-001',
      'SBBS-R1-002',
      'SBBS-R1-003',
      'SBBS-R1-004'
    )
    AND source_seed_lot_id IS NOT NULL
  GROUP BY source_seed_lot_id
  HAVING count(*) = 4;

  IF feminized_seed_lot_id IS NULL THEN
    RAISE EXCEPTION 'Expected Plants A-D to share one source seed lot';
  END IF;

  UPDATE seed_lot
  SET
    sex_type_key = 'feminized',
    updated_at = now()
  WHERE id = feminized_seed_lot_id;

  SELECT id
    INTO regular_line_id
  FROM plant_line
  WHERE project_code = 'BS01'
    AND generation_label IS NULL
    AND strain = 'BS01'
    AND cultivar = 'Oregon Breeders Group'
  ORDER BY id
  LIMIT 1;

  IF regular_line_id IS NULL THEN
    INSERT INTO plant_line (
      project_code,
      generation_label,
      strain,
      cultivar,
      description,
      source_name
    ) VALUES (
      'BS01',
      NULL,
      'BS01',
      'Oregon Breeders Group',
      'Backfilled purchased regular seed material for Track A R1-R5 / SBBS-R1-005 through SBBS-R1-009.',
      'Purchased regular seed material'
    )
    RETURNING id INTO regular_line_id;
  ELSE
    UPDATE plant_line
    SET
      description =
        'Backfilled purchased regular seed material for Track A R1-R5 / SBBS-R1-005 through SBBS-R1-009.',
      source_name = 'Purchased regular seed material',
      updated_at = now()
    WHERE id = regular_line_id;
  END IF;

  SELECT id
    INTO regular_seed_lot_id
  FROM seed_lot
  WHERE line_id = regular_line_id
    AND is_purchased
    AND vendor_name = 'Unknown vendor'
  ORDER BY id
  LIMIT 1;

  IF regular_seed_lot_id IS NULL THEN
    INSERT INTO seed_lot (
      line_id,
      sex_type_key,
      is_purchased,
      vendor_name,
      notes
    ) VALUES (
      regular_line_id,
      'regular',
      true,
      'Unknown vendor',
      'Backfilled purchased regular seed lot for Track A R1-R5 / SBBS-R1-005 through SBBS-R1-009.'
    )
    RETURNING id INTO regular_seed_lot_id;
  ELSE
    UPDATE seed_lot
    SET
      sex_type_key = 'regular',
      notes =
        'Backfilled purchased regular seed lot for Track A R1-R5 / SBBS-R1-005 through SBBS-R1-009.',
      updated_at = now()
    WHERE id = regular_seed_lot_id;
  END IF;

  UPDATE plant
  SET
    line_id = regular_line_id,
    source_seed_lot_id = regular_seed_lot_id,
    sex_key = 'male',
    updated_at = now()
  WHERE key IN (
      'SBBS-R1-005',
      'SBBS-R1-006',
      'SBBS-R1-007',
      'SBBS-R1-008',
      'SBBS-R1-009'
    );

  IF (
    SELECT count(*)
    FROM plant
    WHERE key IN (
        'SBBS-R1-005',
        'SBBS-R1-006',
        'SBBS-R1-007',
        'SBBS-R1-008',
        'SBBS-R1-009'
      )
      AND line_id = regular_line_id
      AND source_seed_lot_id = regular_seed_lot_id
      AND sex_key = 'male'
  ) <> 5 THEN
    RAISE EXCEPTION 'Track A R1-R5 were not moved to regular male source records';
  END IF;
END $$;
