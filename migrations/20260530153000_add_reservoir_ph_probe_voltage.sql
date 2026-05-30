-- Add calibration capture metrics for the reservoir pH probe.
--
-- The first rollout intentionally persists raw ADS1115 counts and measured
-- volts only. Calibrated pH needs a real two-point field calibration before it
-- becomes a canonical metric.

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
  v."capability_id",
  v."name",
  'measurement',
  v."metric_name",
  v."unit",
  'esp32',
  true,
  '{}'::jsonb
FROM reservoir
JOIN (VALUES
  ('reservoir_ph_raw', 'Reservoir pH Raw', 'reservoir_ph_raw', 'raw'),
  ('reservoir_ph_voltage', 'Reservoir pH Voltage', 'reservoir_ph_voltage', 'V')
) AS v("capability_id", "name", "metric_name", "unit") ON true
ON CONFLICT ON CONSTRAINT "uq_capability_device_capability_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "kind" = EXCLUDED."kind",
  "metric_name" = EXCLUDED."metric_name",
  "unit" = EXCLUDED."unit",
  "source" = EXCLUDED."source",
  "enabled" = EXCLUDED."enabled",
  "metadata" = EXCLUDED."metadata";
