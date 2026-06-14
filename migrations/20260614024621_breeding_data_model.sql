CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE _breeding_plant_migration_map (
  plant_row_id bigint PRIMARY KEY,
  old_plant_id text NOT NULL,
  new_key text NOT NULL,
  grid_position text NOT NULL
);

INSERT INTO _breeding_plant_migration_map (
  plant_row_id,
  old_plant_id,
  new_key,
  grid_position
) VALUES
  (1, 'a', 'SBBS-R1-001', 'A1'),
  (2, 'b', 'SBBS-R1-002', 'B1'),
  (3, 'c', 'SBBS-R1-003', 'C1'),
  (4, 'd', 'SBBS-R1-004', 'D1'),
  (5, 'r1', 'SBBS-R1-005', 'A1'),
  (6, 'r2', 'SBBS-R1-006', 'B1'),
  (7, 'r3', 'SBBS-R1-007', 'C1'),
  (8, 'r4', 'SBBS-R1-008', 'D1'),
  (9, 'r5', 'SBBS-R1-009', 'E1');

DO $$
BEGIN
  IF (
    SELECT count(*)
    FROM growrun
    WHERE grow_run_id IN (
      'main-2026-03-15',
      'breeding-track-a-2026-04-28'
    )
  ) <> 2 THEN
    RAISE EXCEPTION
      'Expected current main and breeding growrun rows are missing';
  END IF;

  IF (
    SELECT count(*)
    FROM growrun
    WHERE grow_run_id = 'main-2026-03-15'
      AND strain = 'Sirius Black × BS01'
      AND germination_date = DATE '2026-03-15'
  ) <> 1 THEN
    RAISE EXCEPTION
      'Expected main growrun identity facts do not match migration assumptions';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM growrun
    WHERE grow_run_id = 'main-2026-03-15'
      AND flower_start_date IS NOT NULL
      AND flower_start_date <> DATE '2026-05-03'
  ) THEN
    RAISE EXCEPTION
      'Main growrun flower_start_date conflicts with expected 2026-05-03';
  END IF;

  IF (
    SELECT count(*)
    FROM growrun
    WHERE grow_run_id = 'breeding-track-a-2026-04-28'
      AND strain = 'SBxBS01 regular'
      AND germination_date = DATE '2026-04-28'
      AND flower_start_date = DATE '2026-05-24'
  ) <> 1 THEN
    RAISE EXCEPTION
      'Expected breeding growrun facts do not match migration assumptions';
  END IF;

  IF (SELECT count(*) FROM plant) <> 9 THEN
    RAISE EXCEPTION 'Expected exactly 9 local plant rows';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM plant AS p
    LEFT JOIN _breeding_plant_migration_map AS m
      ON m.plant_row_id = p.id
     AND m.old_plant_id = p.plant_id
    WHERE m.plant_row_id IS NULL
  ) THEN
    RAISE EXCEPTION
      'Existing plant rows do not match the explicit id/plant_id mapping';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM _breeding_plant_migration_map AS m
    LEFT JOIN plant AS p
      ON p.id = m.plant_row_id
     AND p.plant_id = m.old_plant_id
    WHERE p.id IS NULL
  ) THEN
    RAISE EXCEPTION
      'One or more explicit plant mappings did not match an existing row';
  END IF;

  IF (SELECT count(*) FROM plant_metric_stream) <> 12 THEN
    RAISE EXCEPTION
      'Expected 12 plant_metric_stream rows before plant identity migration';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM plant_metric_stream AS pms
    LEFT JOIN _breeding_plant_migration_map AS m
      ON m.plant_row_id = pms.plant_id
    WHERE m.plant_row_id IS NULL
  ) THEN
    RAISE EXCEPTION
      'plant_metric_stream references a plant outside the explicit mapping';
  END IF;
END $$;

UPDATE growrun
SET
  flower_start_date = DATE '2026-05-03',
  updated_at = now()
WHERE grow_run_id = 'main-2026-03-15'
  AND flower_start_date IS NULL;

CREATE TABLE plant_line (
  id bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  project_code text NULL,
  generation_label text NULL,
  strain text NOT NULL,
  cultivar text NOT NULL,
  description text NULL,
  source_name text NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (id),
  CONSTRAINT uq_plant_line_identity UNIQUE NULLS NOT DISTINCT (
    project_code,
    generation_label,
    strain,
    cultivar
  ),
  CONSTRAINT ck_plant_line_project_code_not_blank
    CHECK (project_code IS NULL OR btrim(project_code) <> ''),
  CONSTRAINT ck_plant_line_generation_label_not_blank
    CHECK (generation_label IS NULL OR btrim(generation_label) <> ''),
  CONSTRAINT ck_plant_line_strain_not_blank CHECK (btrim(strain) <> ''),
  CONSTRAINT ck_plant_line_cultivar_not_blank CHECK (btrim(cultivar) <> ''),
  CONSTRAINT ck_plant_line_description_not_blank
    CHECK (description IS NULL OR btrim(description) <> ''),
  CONSTRAINT ck_plant_line_source_name_not_blank
    CHECK (source_name IS NULL OR btrim(source_name) <> '')
);

CREATE TABLE cross_event (
  id bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  resulting_line_id bigint NOT NULL,
  seed_parent_plant_id bigint NOT NULL,
  pollen_parent_plant_id bigint NOT NULL,
  pollinated_at timestamptz NOT NULL,
  pollen_parent_is_reversed boolean NULL,
  notes text NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (id),
  CONSTRAINT fk_cross_event_resulting_line
    FOREIGN KEY (resulting_line_id) REFERENCES plant_line (id)
    ON DELETE RESTRICT,
  CONSTRAINT ck_cross_event_distinct_parents
    CHECK (seed_parent_plant_id <> pollen_parent_plant_id),
  CONSTRAINT ck_cross_event_notes_not_blank
    CHECK (notes IS NULL OR btrim(notes) <> '')
);

CREATE TABLE seed_lot (
  id bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  line_id bigint NOT NULL,
  is_purchased boolean NOT NULL DEFAULT false,
  vendor_name text NULL,
  acquired_at timestamptz NULL,
  produced_by_cross_event_id bigint NULL,
  is_produced boolean NOT NULL
    GENERATED ALWAYS AS (produced_by_cross_event_id IS NOT NULL) STORED,
  seed_count integer NULL,
  notes text NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (id),
  CONSTRAINT fk_seed_lot_line
    FOREIGN KEY (line_id) REFERENCES plant_line (id) ON DELETE RESTRICT,
  CONSTRAINT ck_seed_lot_not_purchased_and_produced
    CHECK (NOT (is_purchased AND produced_by_cross_event_id IS NOT NULL)),
  CONSTRAINT ck_seed_lot_vendor_for_purchased
    CHECK (
      NOT is_purchased
      OR (vendor_name IS NOT NULL AND btrim(vendor_name) <> '')
    ),
  CONSTRAINT ck_seed_lot_vendor_only_when_purchased
    CHECK (is_purchased OR vendor_name IS NULL),
  CONSTRAINT ck_seed_lot_seed_count_positive
    CHECK (seed_count IS NULL OR seed_count >= 0),
  CONSTRAINT ck_seed_lot_notes_not_blank
    CHECK (notes IS NULL OR btrim(notes) <> '')
);

INSERT INTO plant_line (
  project_code,
  generation_label,
  strain,
  cultivar,
  description,
  source_name
) VALUES (
  'SBBS',
  'R1',
  'Sirius Black x BS01',
  'SBxBS01 regular',
  'Backfilled purchased material for existing main growrun '
    || 'Sirius Black × BS01 and breeding growrun SBxBS01 regular.',
  'Purchased seed material'
);

INSERT INTO seed_lot (
  line_id,
  is_purchased,
  vendor_name,
  notes
)
SELECT
  pl.id,
  true,
  'Unknown vendor',
  'Backfilled purchased seed lot for current Sirius Black x BS01 material; '
    || 'the original vendor was not recorded in growrun data.'
FROM plant_line AS pl
WHERE pl.project_code = 'SBBS'
  AND pl.generation_label = 'R1'
  AND pl.strain = 'Sirius Black x BS01'
  AND pl.cultivar = 'SBxBS01 regular';

CREATE TABLE plant_location_history (
  id bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  plant_id bigint NOT NULL,
  site_id bigint NOT NULL,
  tent_id bigint NOT NULL,
  grid_position text NOT NULL,
  start_at timestamptz NOT NULL,
  end_at timestamptz NULL,
  is_current boolean NOT NULL GENERATED ALWAYS AS (end_at IS NULL) STORED,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (id),
  CONSTRAINT fk_plant_location_plant
    FOREIGN KEY (plant_id) REFERENCES plant (id) ON DELETE RESTRICT,
  CONSTRAINT fk_plant_location_site
    FOREIGN KEY (site_id) REFERENCES site (id) ON DELETE RESTRICT,
  CONSTRAINT fk_plant_location_tent
    FOREIGN KEY (tent_id) REFERENCES tent (id) ON DELETE RESTRICT,
  CONSTRAINT ck_plant_location_grid_position_not_blank
    CHECK (btrim(grid_position) <> ''),
  CONSTRAINT ck_plant_location_time_order
    CHECK (end_at IS NULL OR end_at > start_at),
  CONSTRAINT ex_plant_location_no_overlap_per_plant
    EXCLUDE USING gist (
      plant_id WITH =,
      tstzrange(start_at, COALESCE(end_at, 'infinity'::timestamptz), '[)')
        WITH &&
    ),
  CONSTRAINT ex_plant_location_no_overlap_per_tent_grid_position
    EXCLUDE USING gist (
      tent_id WITH =,
      grid_position WITH =,
      tstzrange(start_at, COALESCE(end_at, 'infinity'::timestamptz), '[)')
        WITH &&
    )
);

INSERT INTO plant_location_history (
  plant_id,
  site_id,
  tent_id,
  grid_position,
  start_at
)
SELECT
  p.id,
  p.site_id,
  p.tent_id,
  m.grid_position,
  COALESCE(
    g.started_at,
    g.germination_date::timestamp AT TIME ZONE g.timezone,
    p.created_at
  )
FROM plant AS p
JOIN growrun AS g ON g.id = p.growrun_id
JOIN _breeding_plant_migration_map AS m ON m.plant_row_id = p.id;

CREATE INDEX ix_plant_location_current_tent
  ON plant_location_history (tent_id, grid_position, plant_id)
  WHERE end_at IS NULL;

CREATE INDEX ix_plant_location_plant_start
  ON plant_location_history (plant_id, start_at DESC);

CREATE UNIQUE INDEX ux_plant_location_current_grid_position_per_tent
  ON plant_location_history (tent_id, grid_position)
  WHERE end_at IS NULL;

CREATE UNIQUE INDEX ux_plant_location_current_per_plant
  ON plant_location_history (plant_id)
  WHERE end_at IS NULL;

CREATE TABLE plant_note (
  id bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  plant_id bigint NOT NULL,
  observed_at timestamptz NOT NULL,
  body text NOT NULL,
  created_by text NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (id),
  CONSTRAINT fk_plant_note_plant
    FOREIGN KEY (plant_id) REFERENCES plant (id) ON DELETE RESTRICT,
  CONSTRAINT ck_plant_note_body_not_blank CHECK (btrim(body) <> ''),
  CONSTRAINT ck_plant_note_created_by_not_blank
    CHECK (created_by IS NULL OR btrim(created_by) <> '')
);

CREATE INDEX ix_plant_note_plant_observed_at
  ON plant_note (plant_id, observed_at DESC);

CREATE TABLE plant_event (
  id bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  plant_id bigint NOT NULL,
  is_pollen_collection boolean NOT NULL DEFAULT false,
  is_seed_production boolean NOT NULL DEFAULT false,
  is_clone_taken boolean NOT NULL DEFAULT false,
  is_sex_observation boolean NOT NULL DEFAULT false,
  is_reversal boolean NOT NULL DEFAULT false,
  is_transplant boolean NOT NULL DEFAULT false,
  is_selection_for_breeding boolean NOT NULL DEFAULT false,
  occurred_at timestamptz NOT NULL,
  reason text NULL,
  notes text NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (id),
  CONSTRAINT fk_plant_event_plant
    FOREIGN KEY (plant_id) REFERENCES plant (id) ON DELETE RESTRICT,
  CONSTRAINT ck_plant_event_one_kind CHECK (
    (CASE WHEN is_pollen_collection THEN 1 ELSE 0 END) +
    (CASE WHEN is_seed_production THEN 1 ELSE 0 END) +
    (CASE WHEN is_clone_taken THEN 1 ELSE 0 END) +
    (CASE WHEN is_sex_observation THEN 1 ELSE 0 END) +
    (CASE WHEN is_reversal THEN 1 ELSE 0 END) +
    (CASE WHEN is_transplant THEN 1 ELSE 0 END) +
    (CASE WHEN is_selection_for_breeding THEN 1 ELSE 0 END) = 1
  ),
  CONSTRAINT ck_plant_event_reason_not_blank
    CHECK (reason IS NULL OR btrim(reason) <> ''),
  CONSTRAINT ck_plant_event_notes_not_blank
    CHECK (notes IS NULL OR btrim(notes) <> ''),
  CONSTRAINT ck_plant_event_metadata_object
    CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX ix_plant_event_plant_occurred_at
  ON plant_event (plant_id, occurred_at DESC);

-- atlas:nolint BC102
ALTER TABLE plant RENAME COLUMN plant_id TO key;

UPDATE plant AS p
SET key = m.new_key
FROM _breeding_plant_migration_map AS m
WHERE m.plant_row_id = p.id;

ALTER TABLE plant
  ADD COLUMN line_id bigint NULL,
  ADD COLUMN source_seed_lot_id bigint NULL,
  ADD COLUMN clone_source_plant_id bigint NULL,
  ADD COLUMN germinated_at timestamptz NULL,
  ADD COLUMN rooted_at timestamptz NULL,
  ADD COLUMN veg_started_at timestamptz NULL,
  ADD COLUMN flower_started_at timestamptz NULL,
  ADD COLUMN culled_at timestamptz NULL,
  ADD COLUMN culled_reason text NULL,
  ADD COLUMN harvested_at timestamptz NULL,
  ADD COLUMN selected_for_breeding_at timestamptz NULL,
  ADD COLUMN selected_for_breeding_reason text NULL;

UPDATE plant AS p
SET
  line_id = pl.id,
  source_seed_lot_id = sl.id,
  germinated_at = g.germination_date::timestamp AT TIME ZONE g.timezone,
  flower_started_at = g.flower_start_date::timestamp AT TIME ZONE g.timezone
FROM growrun AS g
JOIN plant_line AS pl
  ON pl.project_code = 'SBBS'
 AND pl.generation_label = 'R1'
 AND pl.strain = 'Sirius Black x BS01'
 AND pl.cultivar = 'SBxBS01 regular'
JOIN seed_lot AS sl ON sl.line_id = pl.id
WHERE g.id = p.growrun_id;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM plant
    WHERE line_id IS NULL
       OR source_seed_lot_id IS NULL
       OR germinated_at IS NULL
       OR flower_started_at IS NULL
  ) THEN
    RAISE EXCEPTION
      'Plant line, seed lot, or lifecycle timestamp backfill was incomplete';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM plant_metric_stream AS pms
    LEFT JOIN plant AS p ON p.id = pms.plant_id
    WHERE p.id IS NULL
  ) THEN
    RAISE EXCEPTION
      'plant_metric_stream plant_id references were not preserved';
  END IF;
END $$;

-- atlas:nolint MF104 PG303
ALTER TABLE plant ALTER COLUMN line_id SET NOT NULL;

ALTER TABLE plant
  ADD COLUMN is_seed_grown boolean NOT NULL
    GENERATED ALWAYS AS (source_seed_lot_id IS NOT NULL) STORED,
  ADD COLUMN is_clone boolean NOT NULL
    GENERATED ALWAYS AS (clone_source_plant_id IS NOT NULL) STORED;

-- atlas:nolint CD101 CD102 DS103
ALTER TABLE plant
  DROP CONSTRAINT plant_growrun_id_fkey,
  DROP CONSTRAINT plant_site_id_fkey,
  DROP CONSTRAINT plant_tent_id_fkey,
  DROP CONSTRAINT uq_plant_growrun_plant_id,
  DROP CONSTRAINT ck_plant_moisture_high_bounds,
  DROP CONSTRAINT ck_plant_moisture_low_bounds,
  DROP COLUMN sticker_color,
  DROP COLUMN status,
  DROP COLUMN purple,
  DROP COLUMN moisture_target_low,
  DROP COLUMN moisture_target_high,
  DROP COLUMN site_id,
  DROP COLUMN tent_id,
  DROP COLUMN growrun_id,
  DROP COLUMN display_order;

-- atlas:nolint MF101 PG105 PG306 PG305
ALTER TABLE plant
  ADD CONSTRAINT uq_plant_key UNIQUE (key),
  ADD CONSTRAINT fk_plant_line
    FOREIGN KEY (line_id) REFERENCES plant_line (id) ON DELETE RESTRICT,
  ADD CONSTRAINT fk_plant_source_seed_lot
    FOREIGN KEY (source_seed_lot_id) REFERENCES seed_lot (id)
    ON DELETE RESTRICT,
  ADD CONSTRAINT fk_plant_clone_source
    FOREIGN KEY (clone_source_plant_id) REFERENCES plant (id)
    ON DELETE RESTRICT,
  ADD CONSTRAINT ck_plant_key_not_blank CHECK (btrim(key) <> ''),
  ADD CONSTRAINT ck_plant_name_not_blank CHECK (btrim(name) <> ''),
  ADD CONSTRAINT ck_plant_seed_or_clone_not_both
    CHECK (source_seed_lot_id IS NULL OR clone_source_plant_id IS NULL),
  ADD CONSTRAINT ck_plant_not_self_clone
    CHECK (clone_source_plant_id IS NULL OR clone_source_plant_id <> id),
  ADD CONSTRAINT ck_plant_seed_not_rooted_as_clone
    CHECK (source_seed_lot_id IS NULL OR rooted_at IS NULL),
  ADD CONSTRAINT ck_plant_clone_not_germinated
    CHECK (clone_source_plant_id IS NULL OR germinated_at IS NULL),
  ADD CONSTRAINT ck_plant_culled_reason_required CHECK (
    (culled_at IS NULL AND culled_reason IS NULL)
    OR (
      culled_at IS NOT NULL
      AND culled_reason IS NOT NULL
      AND btrim(culled_reason) <> ''
    )
  ),
  ADD CONSTRAINT ck_plant_culled_or_harvested_not_both
    CHECK (culled_at IS NULL OR harvested_at IS NULL),
  ADD CONSTRAINT ck_plant_selection_reason_not_blank
    CHECK (
      selected_for_breeding_reason IS NULL
      OR btrim(selected_for_breeding_reason) <> ''
    );

COMMENT ON COLUMN plant.key IS
  'Unique human-readable plant identifier printed on tags and used in notes/photos, e.g. SBBS-R1-001.';

-- atlas:nolint PG306
ALTER TABLE cross_event
  ADD CONSTRAINT fk_cross_event_seed_parent
    FOREIGN KEY (seed_parent_plant_id) REFERENCES plant (id)
    ON DELETE RESTRICT,
  ADD CONSTRAINT fk_cross_event_pollen_parent
    FOREIGN KEY (pollen_parent_plant_id) REFERENCES plant (id)
    ON DELETE RESTRICT;

-- atlas:nolint PG306
ALTER TABLE seed_lot
  ADD CONSTRAINT fk_seed_lot_cross_event
    FOREIGN KEY (produced_by_cross_event_id) REFERENCES cross_event (id)
    ON DELETE RESTRICT;

-- atlas:nolint DS102
DROP TYPE plant_sticker;

-- atlas:nolint DS102
DROP TYPE plant_status;

DROP TABLE _breeding_plant_migration_map;
