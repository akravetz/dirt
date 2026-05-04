-- atlas:txmode none

-- Link readings to canonical device capabilities while preserving legacy
-- sensornode_id for transition compatibility.

ALTER TABLE "sensorreading" ADD COLUMN "capability_id" bigint NULL;

-- Historical/test payloads may contain soil_moisture_pct in addition to the
-- firmware's canonical soil_moisture_raw. Keep it linkable during transition.
WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
plant_devices AS (
  SELECT d."id", d."device_id"
  FROM "device" d
  JOIN home ON home."id" = d."site_id"
  WHERE d."device_id" IN (
    'plant-a-node',
    'plant-b-node',
    'plant-c-node',
    'plant-d-node'
  )
)
INSERT INTO "capability" (
  "device_id",
  "capability_id",
  "name",
  "kind",
  "metric_name",
  "unit",
  "source",
  "enabled",
  "metadata"
)
SELECT
  plant_devices."id",
  'soil_moisture_pct',
  'Soil Moisture Percent',
  'measurement',
  'soil_moisture_pct',
  'pct',
  'derived',
  true,
  '{}'::jsonb
FROM plant_devices
ON CONFLICT ON CONSTRAINT "uq_capability_device_capability_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "kind" = EXCLUDED."kind",
  "metric_name" = EXCLUDED."metric_name",
  "unit" = EXCLUDED."unit",
  "source" = EXCLUDED."source",
  "enabled" = EXCLUDED."enabled",
  "metadata" = EXCLUDED."metadata";

WITH legacy_map AS (
  SELECT *
  FROM (VALUES
    ('tent', 'fan-controller'),
    ('plant-a', 'plant-a-node'),
    ('plant-b', 'plant-b-node'),
    ('plant-c', 'plant-c-node'),
    ('plant-d', 'plant-d-node'),
    ('reservoir', 'reservoir-node')
  ) AS v("legacy_location", "device_id")
),
home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
)
UPDATE "sensorreading" sr
SET "capability_id" = c."id"
FROM "sensornode" sn
JOIN legacy_map lm ON lm."legacy_location" = sn."location"::text
JOIN "device" d
  ON d."site_id" = (SELECT "id" FROM home)
  AND d."device_id" = lm."device_id"
JOIN "capability" c
  ON c."device_id" = d."id"
WHERE sr."sensornode_id" = sn."id"
  AND c."metric_name" = sr."metric";

ALTER TABLE "sensorreading"
  ADD CONSTRAINT "sensorreading_capability_id_fkey"
  FOREIGN KEY ("capability_id") REFERENCES "capability" ("id")
  ON UPDATE NO ACTION ON DELETE RESTRICT;

CREATE INDEX CONCURRENTLY "ix_sensorreading_capability_ts"
  ON "sensorreading" ("capability_id", "ts" DESC);
