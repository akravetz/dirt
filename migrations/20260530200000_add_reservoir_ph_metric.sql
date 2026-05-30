-- Add the calibrated reservoir pH metric after field calibration.

WITH reservoir AS (
  SELECT d."id"
  FROM "device" AS d
  JOIN "site" AS s ON s."id" = d."site_id"
  WHERE s."site_id" = 'homebox'
    AND d."device_id" = 'reservoir-node'
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
  reservoir."id",
  'reservoir_ph',
  'Reservoir pH',
  'measurement',
  'reservoir_ph',
  'pH',
  'esp32',
  true,
  '{"calibration":{"type":"linear","low":{"ph":4.0,"voltage":2.0313},"high":{"ph":10.0,"voltage":0.9905}}}'::jsonb
FROM reservoir
ON CONFLICT ON CONSTRAINT "uq_capability_device_capability_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "kind" = EXCLUDED."kind",
  "metric_name" = EXCLUDED."metric_name",
  "unit" = EXCLUDED."unit",
  "source" = EXCLUDED."source",
  "enabled" = EXCLUDED."enabled",
  "metadata" = EXCLUDED."metadata";
