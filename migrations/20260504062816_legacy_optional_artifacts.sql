-- Preserve the last growrun photoperiod values in the canonical schedule row
-- before dropping the duplicate growrun columns.
UPDATE "schedule" AS sch
SET
  "starts_local" = gr."lights_on_local",
  "ends_local" = gr."lights_off_local",
  "timezone" = gr."timezone",
  "enabled" = true,
  "updated_at" = now()
FROM "growrun" AS gr
WHERE sch."site_id" = gr."site_id"
  AND sch."tent_id" = gr."tent_id"
  AND sch."kind" = 'lights'
  AND gr."is_current" = true
  AND gr."lights_on_local" IS NOT NULL
  AND gr."lights_off_local" IS NOT NULL;

INSERT INTO "schedule" (
  "site_id",
  "tent_id",
  "schedule_id",
  "kind",
  "starts_local",
  "ends_local",
  "timezone",
  "enabled"
)
SELECT
  gr."site_id",
  gr."tent_id",
  t."tent_id" || '-lights-photoperiod',
  'lights',
  gr."lights_on_local",
  gr."lights_off_local",
  gr."timezone",
  true
FROM "growrun" AS gr
JOIN "tent" AS t ON t."id" = gr."tent_id"
WHERE gr."is_current" = true
  AND gr."lights_on_local" IS NOT NULL
  AND gr."lights_off_local" IS NOT NULL
  AND NOT EXISTS (
    SELECT 1
    FROM "schedule" AS sch
    WHERE sch."site_id" = gr."site_id"
      AND sch."tent_id" = gr."tent_id"
      AND sch."kind" = 'lights'
  );

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM "growrun" AS gr
    WHERE gr."is_current" = true
      AND (
        SELECT count(*)
        FROM "schedule" AS sch
        WHERE sch."site_id" = gr."site_id"
          AND sch."tent_id" = gr."tent_id"
          AND sch."kind" = 'lights'
          AND sch."enabled" = true
          AND sch."starts_local" IS NOT NULL
          AND sch."ends_local" IS NOT NULL
      ) <> 1
  ) THEN
    RAISE EXCEPTION 'current grow runs must have exactly one enabled lights schedule before dropping growrun photoperiod columns';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM "plant"
    WHERE "sensornode_id" IS NOT NULL
      AND "moisture_capability_id" IS NULL
  ) THEN
    RAISE EXCEPTION 'plant.sensornode_id cannot be dropped while a plant lacks moisture_capability_id';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM "sensorcalibration"
    WHERE "capability_id" IS NULL
  ) THEN
    RAISE EXCEPTION 'sensorcalibration.sensornode_id cannot be dropped while a calibration lacks capability_id';
  END IF;
END $$;

-- Modify "growrun" table
ALTER TABLE "growrun" DROP COLUMN "lights_on_local", DROP COLUMN "lights_off_local", DROP COLUMN "location";
-- Modify "plant" table
ALTER TABLE "plant" DROP COLUMN "sensornode_id";
-- Modify "sensorcalibration" table
ALTER TABLE "sensorcalibration" DROP COLUMN "sensornode_id", ALTER COLUMN "capability_id" SET NOT NULL;
