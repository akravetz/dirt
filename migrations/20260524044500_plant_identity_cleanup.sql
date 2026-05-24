-- atlas:txmode none

ALTER TYPE "plant_sticker" ADD VALUE IF NOT EXISTS 'brown' BEFORE 'blue';

ALTER TABLE "plant"
  ADD COLUMN "display_order" integer NOT NULL DEFAULT 0;

UPDATE "plant" AS p
SET
  "display_order" = v."display_order",
  "updated_at" = now()
FROM "site" AS s
JOIN "tent" AS t
  ON t."site_id" = s."id"
JOIN (VALUES
  ('a', 1),
  ('b', 2),
  ('c', 3),
  ('d', 4)
) AS v("plant_id", "display_order")
  ON true
WHERE s."site_id" = 'homebox'
  AND t."tent_id" = 'main'
  AND p."site_id" = s."id"
  AND p."tent_id" = t."id"
  AND p."plant_id" = v."plant_id";

ALTER TABLE "plant" DROP CONSTRAINT "ck_plant_code_lowercase_letter";

ALTER TABLE "plant"
  DROP COLUMN "code",
  DROP COLUMN "label",
  ALTER COLUMN "sticker_color" DROP NOT NULL;

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
breeding AS (
  SELECT "id" FROM "tent"
  WHERE "site_id" = (SELECT "id" FROM home)
    AND "tent_id" = 'breeding'
)
INSERT INTO "growrun" (
  "site_id",
  "tent_id",
  "grow_run_id",
  "name",
  "purpose",
  "germination_date",
  "flower_start_date",
  "strain",
  "timezone",
  "plant_count",
  "is_current",
  "started_at"
)
SELECT
  home."id",
  breeding."id",
  'breeding-track-a-2026-04-28',
  'Track A pollen run',
  'pollen',
  '2026-04-28'::date,
  NULL::date,
  'SBxBS01 regular',
  'America/Denver',
  5,
  true,
  '2026-04-28'::timestamp AT TIME ZONE 'America/Denver'
FROM home, breeding
ON CONFLICT ON CONSTRAINT "uq_growrun_tent_grow_run_id" DO UPDATE SET
  "site_id" = EXCLUDED."site_id",
  "name" = EXCLUDED."name",
  "purpose" = EXCLUDED."purpose",
  "germination_date" = EXCLUDED."germination_date",
  "flower_start_date" = EXCLUDED."flower_start_date",
  "strain" = EXCLUDED."strain",
  "timezone" = EXCLUDED."timezone",
  "plant_count" = EXCLUDED."plant_count",
  "is_current" = EXCLUDED."is_current",
  "started_at" = EXCLUDED."started_at",
  "ended_at" = NULL,
  "updated_at" = now();

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
breeding AS (
  SELECT "id" FROM "tent"
  WHERE "site_id" = (SELECT "id" FROM home)
    AND "tent_id" = 'breeding'
),
track_a AS (
  SELECT "id" FROM "growrun"
  WHERE "tent_id" = (SELECT "id" FROM breeding)
    AND "grow_run_id" = 'breeding-track-a-2026-04-28'
)
INSERT INTO "plant" (
  "site_id",
  "tent_id",
  "growrun_id",
  "plant_id",
  "name",
  "display_order",
  "sticker_color",
  "status",
  "purple"
)
SELECT
  home."id",
  breeding."id",
  track_a."id",
  v."plant_id",
  v."name",
  v."display_order",
  v."sticker_color"::"plant_sticker",
  'secondary'::"plant_status",
  false
FROM home, breeding, track_a
JOIN (VALUES
  ('r1', 'Track A R1', 1, 'pink'),
  ('r2', 'Track A R2', 2, 'yellow'),
  ('r3', 'Track A R3', 3, 'brown'),
  ('r4', 'Track A R4', 4, 'blue'),
  ('r5', 'Track A R5', 5, 'orange')
) AS v("plant_id", "name", "display_order", "sticker_color")
  ON true
ON CONFLICT ON CONSTRAINT "uq_plant_growrun_plant_id" DO UPDATE SET
  "site_id" = EXCLUDED."site_id",
  "tent_id" = EXCLUDED."tent_id",
  "name" = EXCLUDED."name",
  "display_order" = EXCLUDED."display_order",
  "sticker_color" = EXCLUDED."sticker_color",
  "status" = EXCLUDED."status",
  "purple" = EXCLUDED."purple",
  "updated_at" = now();
