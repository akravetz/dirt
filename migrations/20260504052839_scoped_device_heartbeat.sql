-- Modify "device" table
ALTER TABLE "device" ADD COLUMN "last_seen" timestamptz NULL, ADD COLUMN "ip" inet NULL, ADD COLUMN "firmware_version" text NULL, ADD COLUMN "uptime_ms" bigint NULL;

-- Backfill canonical ESP32/device heartbeat from legacy sensornode rows.
UPDATE "device" AS d
SET
  "last_seen" = sn."last_seen",
  "ip" = sn."ip",
  "firmware_version" = sn."firmware_version",
  "uptime_ms" = sn."uptime_ms",
  "updated_at" = now()
FROM "sensornode" AS sn
WHERE d."metadata"->>'legacy_location' = sn."location"::text;

-- Backfill non-legacy scoped devices, such as the Govee humidifier, from
-- their latest recorded capability reading when no explicit heartbeat exists.
WITH latest_reading AS (
  SELECT c."device_id", max(sr."ts") AS "last_seen"
  FROM "sensorreading" AS sr
  JOIN "capability" AS c ON c."id" = sr."capability_id"
  GROUP BY c."device_id"
)
UPDATE "device" AS d
SET
  "last_seen" = latest_reading."last_seen",
  "updated_at" = now()
FROM latest_reading
WHERE d."id" = latest_reading."device_id"
  AND d."last_seen" IS NULL;
