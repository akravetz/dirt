DO $$
DECLARE
  feminized_line_id bigint;
  regular_line_id bigint;
  regular_seed_lot_id bigint;
BEGIN
  SELECT line_id
    INTO feminized_line_id
  FROM seed_lot
  WHERE id = 1;

  IF feminized_line_id IS NULL THEN
    RAISE EXCEPTION 'Expected seed_lot id 1 to exist';
  END IF;

  IF (
    SELECT count(*)
    FROM plant_line
    WHERE id = feminized_line_id
      AND project_code = 'SBBS'
      AND generation_label = 'R1'
      AND strain = 'Sirius Black x BS01'
      AND cultivar = 'SBxBS01 regular'
  ) <> 1 THEN
    RAISE EXCEPTION
      'Seed lot 1 plant line does not match the expected pre-correction identity';
  END IF;

  IF (
    SELECT count(*)
    FROM plant
    WHERE key IN (
        'SBBS-R1-001',
        'SBBS-R1-002',
        'SBBS-R1-003',
        'SBBS-R1-004'
      )
      AND line_id = feminized_line_id
      AND source_seed_lot_id = 1
  ) <> 4 THEN
    RAISE EXCEPTION
      'Expected Plants A-D to still point at seed lot 1 before source correction';
  END IF;

  IF (
    SELECT count(*)
    FROM plant
    WHERE key = 'SBBS-R1-006'
      AND line_id = feminized_line_id
      AND source_seed_lot_id = 1
  ) <> 1 THEN
    RAISE EXCEPTION
      'Expected SBBS-R1-006 to still point at seed lot 1 before source correction';
  END IF;

  UPDATE plant_line
  SET
    cultivar = 'Oregon Breeders Group',
    strain = 'Sirius Black (Reversed) x BS01 Feminized',
    description = 'Corrected purchased feminized seed material for main-tent Plants A-D.',
    source_name = 'Purchased feminized seed material',
    updated_at = now()
  WHERE id = feminized_line_id;

  UPDATE seed_lot
  SET
    notes = 'Corrected purchased feminized seed lot for main-tent Plants A-D.',
    updated_at = now()
  WHERE id = 1;

  SELECT id
    INTO regular_line_id
  FROM plant_line
  WHERE project_code = 'BS01'
    AND generation_label IS NULL
    AND strain = 'BS01'
    AND cultivar = 'Oregon Breeders Group';

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
      'Backfilled purchased regular seed material for Track A R2 / SBBS-R1-006.',
      'Purchased regular seed material'
    )
    RETURNING id INTO regular_line_id;
  ELSE
    UPDATE plant_line
    SET
      description =
        'Backfilled purchased regular seed material for Track A R2 / SBBS-R1-006.',
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
    AND notes = 'Backfilled purchased regular seed lot for Track A R2 / SBBS-R1-006.'
  ORDER BY id
  LIMIT 1;

  IF regular_seed_lot_id IS NULL THEN
    INSERT INTO seed_lot (
      line_id,
      is_purchased,
      vendor_name,
      notes
    ) VALUES (
      regular_line_id,
      true,
      'Unknown vendor',
      'Backfilled purchased regular seed lot for Track A R2 / SBBS-R1-006.'
    )
    RETURNING id INTO regular_seed_lot_id;
  END IF;

  UPDATE plant
  SET
    line_id = regular_line_id,
    source_seed_lot_id = regular_seed_lot_id,
    updated_at = now()
  WHERE key = 'SBBS-R1-006';

  IF (
    SELECT count(*)
    FROM plant
    WHERE key IN (
        'SBBS-R1-001',
        'SBBS-R1-002',
        'SBBS-R1-003',
        'SBBS-R1-004'
      )
      AND line_id = feminized_line_id
      AND source_seed_lot_id = 1
  ) <> 4 THEN
    RAISE EXCEPTION 'Plants A-D were not left on corrected seed lot 1';
  END IF;

  IF (
    SELECT count(*)
    FROM plant
    WHERE key = 'SBBS-R1-006'
      AND line_id = regular_line_id
      AND source_seed_lot_id = regular_seed_lot_id
  ) <> 1 THEN
    RAISE EXCEPTION 'SBBS-R1-006 was not moved to the corrected BS01 seed lot';
  END IF;
END $$;
