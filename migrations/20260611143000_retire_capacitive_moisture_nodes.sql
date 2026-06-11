-- Retire the old capacitive plant moisture nodes from active inventory.
--
-- Historical device rows, raw readings, and calibration rows are preserved.
-- Current plant moisture ownership was already moved by
-- 20260611120000_plant_a_moisture_cutover.sql.

WITH retired_devices AS (
  UPDATE "device" AS d
  SET
    "enabled" = false,
    "metadata" = coalesce(d."metadata", '{}'::jsonb) || jsonb_build_object(
      'retired_at', '2026-06-11',
      'retirement_reason', 'capacitive moisture nodes retired after Plant A RS485 substrate cutover',
      'retired_by', '20260611143000_retire_capacitive_moisture_nodes'
    ),
    "updated_at" = now()
  WHERE d."device_id" IN (
    'plant-a-node',
    'plant-b-node',
    'plant-c-node',
    'plant-d-node'
  )
  RETURNING d."id"
)
UPDATE "capability" AS c
SET
  "enabled" = false,
  "metadata" = coalesce(c."metadata", '{}'::jsonb) || jsonb_build_object(
    'retired_at', '2026-06-11',
    'retirement_reason', 'capacitive raw moisture retired from current operations',
    'retired_by', '20260611143000_retire_capacitive_moisture_nodes'
  )
FROM retired_devices AS d
WHERE c."device_id" = d."id"
  AND c."capability_id" = 'soil_moisture_raw'
  AND c."metric_name" = 'soil_moisture_raw';
