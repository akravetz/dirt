-- Correct swapped Kasa physical identities for clone and breeding lights.
--
-- Logical schedules were already correct:
--   clones:   06:00-00:00 local (18/6)
--   breeding: 09:00-21:00 local (12/12)
-- The physical MACs were assigned to the opposite logical device rows.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM "site" AS s
    JOIN "device" AS d ON d."site_id" = s."id"
    WHERE s."site_id" = 'homebox'
      AND d."device_id" = 'kasa-lights-clones'
  ) THEN
    RAISE EXCEPTION 'missing device homebox/kasa-lights-clones';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM "site" AS s
    JOIN "device" AS d ON d."site_id" = s."id"
    WHERE s."site_id" = 'homebox'
      AND d."device_id" = 'kasa-lights-breeding'
  ) THEN
    RAISE EXCEPTION 'missing device homebox/kasa-lights-breeding';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM "site" AS s
    JOIN "device" AS d ON d."site_id" = s."id"
    WHERE s."site_id" = 'homebox'
      AND d."device_id" NOT IN ('kasa-lights-clones', 'kasa-lights-breeding')
      AND d."provider_uid" IN ('10:5A:95:8B:E6:76', '10:5A:95:8B:E8:B7')
  ) THEN
    RAISE EXCEPTION 'clone/breeding Kasa MAC is assigned to an unexpected device';
  END IF;
END $$;

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
target_devices AS (
  SELECT d."id"
  FROM "device" AS d
  JOIN home ON home."id" = d."site_id"
  WHERE d."device_id" IN ('kasa-lights-clones', 'kasa-lights-breeding')
)
UPDATE "device" AS d
SET
  "provider_uid" = NULL,
  "updated_at" = now()
FROM target_devices
WHERE d."id" = target_devices."id";

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
desired AS (
  SELECT *
  FROM (VALUES
    ('kasa-lights-clones', '10:5A:95:8B:E6:76', '192.168.1.180'::inet),
    ('kasa-lights-breeding', '10:5A:95:8B:E8:B7', '192.168.1.220'::inet)
  ) AS v("device_id", "provider_uid", "ip")
)
UPDATE "device" AS d
SET
  "provider_uid_kind" = 'mac',
  "provider_uid" = desired."provider_uid",
  "ip" = desired."ip",
  "updated_at" = now()
FROM home
JOIN desired ON true
WHERE d."site_id" = home."id"
  AND d."device_id" = desired."device_id";

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
desired AS (
  SELECT *
  FROM (VALUES
    ('clones', 'clones-lights-photoperiod', 'kasa-lights-clones', '06:00'::time, '00:00'::time),
    ('breeding', 'breeding-lights-photoperiod', 'kasa-lights-breeding', '09:00'::time, '21:00'::time)
  ) AS v("tent_id", "schedule_id", "device_id", "starts_local", "ends_local")
),
resolved AS (
  SELECT
    home."id" AS "site_pk",
    t."id" AS "tent_pk",
    d."id" AS "device_pk",
    c."id" AS "capability_pk",
    desired."schedule_id",
    desired."starts_local",
    desired."ends_local"
  FROM home
  JOIN desired ON true
  JOIN "tent" AS t
    ON t."site_id" = home."id"
   AND t."tent_id" = desired."tent_id"
  JOIN "device" AS d
    ON d."site_id" = home."id"
   AND d."device_id" = desired."device_id"
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
  resolved."schedule_id",
  'lights',
  resolved."starts_local",
  resolved."ends_local",
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
