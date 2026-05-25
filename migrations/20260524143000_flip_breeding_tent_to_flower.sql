-- Flip the breeding tent Track A pollen run to flower.
-- Match the breeding tent flower schedule to the main tent: 09:00-21:00 local.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM "site" AS s
    JOIN "tent" AS t ON t."site_id" = s."id"
    WHERE s."site_id" = 'homebox'
      AND t."tent_id" = 'breeding'
  ) THEN
    RAISE EXCEPTION 'missing scope homebox/breeding';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM "growrun" AS gr
    JOIN "site" AS s ON s."id" = gr."site_id"
    JOIN "tent" AS t ON t."id" = gr."tent_id"
    WHERE s."site_id" = 'homebox'
      AND t."tent_id" = 'breeding'
      AND gr."is_current" = true
  ) THEN
    RAISE EXCEPTION 'missing current growrun for homebox/breeding';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM "growrun" AS gr
    JOIN "site" AS s ON s."id" = gr."site_id"
    JOIN "tent" AS t ON t."id" = gr."tent_id"
    WHERE s."site_id" = 'homebox'
      AND t."tent_id" = 'breeding'
      AND gr."is_current" = true
      AND gr."flower_start_date" IS NOT NULL
      AND gr."flower_start_date" <> DATE '2026-05-24'
  ) THEN
    RAISE EXCEPTION 'breeding flower_start_date is already set to a different date';
  END IF;
END $$;

WITH breeding_current AS (
  SELECT gr."id"
  FROM "growrun" AS gr
  JOIN "site" AS s ON s."id" = gr."site_id"
  JOIN "tent" AS t ON t."id" = gr."tent_id"
  WHERE s."site_id" = 'homebox'
    AND t."tent_id" = 'breeding'
    AND gr."is_current" = true
)
UPDATE "growrun" AS gr
SET
  "flower_start_date" = DATE '2026-05-24',
  "updated_at" = now()
FROM breeding_current
WHERE gr."id" = breeding_current."id"
  AND gr."flower_start_date" IS DISTINCT FROM DATE '2026-05-24';

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
resolved AS (
  SELECT
    home."id" AS "site_pk",
    t."id" AS "tent_pk",
    d."id" AS "device_pk",
    c."id" AS "capability_pk"
  FROM home
  JOIN "tent" AS t
    ON t."site_id" = home."id"
   AND t."tent_id" = 'breeding'
  JOIN "device" AS d
    ON d."site_id" = home."id"
   AND d."device_id" = 'kasa-lights-breeding'
  JOIN "capability" AS c
    ON c."device_id" = d."id"
   AND c."capability_id" = 'lights_power'
)
INSERT INTO "schedule" (
  "site_id",
  "tent_id",
  "device_id",
  "capability_id",
  "schedule_id",
  "kind",
  "starts_local",
  "ends_local",
  "timezone",
  "enabled"
)
SELECT
  resolved."site_pk",
  resolved."tent_pk",
  resolved."device_pk",
  resolved."capability_pk",
  'breeding-lights-photoperiod',
  'lights',
  '09:00'::time,
  '21:00'::time,
  'America/Denver',
  true
FROM resolved
ON CONFLICT ON CONSTRAINT "uq_schedule_tent_schedule_id" DO UPDATE SET
  "device_id" = EXCLUDED."device_id",
  "capability_id" = EXCLUDED."capability_id",
  "kind" = EXCLUDED."kind",
  "starts_local" = EXCLUDED."starts_local",
  "ends_local" = EXCLUDED."ends_local",
  "timezone" = EXCLUDED."timezone",
  "enabled" = EXCLUDED."enabled",
  "updated_at" = now();
