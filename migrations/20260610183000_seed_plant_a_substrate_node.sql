-- Seed the Plant A RS485 substrate node contract.
--
-- This is only the side-by-side device/capability inventory. Plant A's
-- canonical moisture_capability_id is intentionally left unchanged until the
-- live node has proven stable.

WITH scope AS (
  SELECT
    s."id" AS site_pk,
    t."id" AS tent_pk,
    z."id" AS zone_pk
  FROM "site" AS s
  JOIN "tent" AS t
    ON t."site_id" = s."id"
   AND t."tent_id" = 'main'
  JOIN "zone" AS z
    ON z."site_id" = s."id"
   AND z."tent_id" = t."id"
   AND z."zone_id" = 'plant-a'
  WHERE s."site_id" = 'homebox'
)
INSERT INTO "device" (
  "site_id",
  "tent_id",
  "zone_id",
  "device_id",
  "name",
  "kind",
  "controller",
  "enabled",
  "metadata",
  "hostname"
)
SELECT
  scope.site_pk,
  scope.tent_pk,
  scope.zone_pk,
  'plant-a-substrate-node',
  'ESP32-C3 · Plant A RS485 substrate',
  'moisture_node',
  'esp32',
  true,
  jsonb_build_object(
    'sensor_model', 'DFRobot SEN0604',
    'modbus_address', '0x02',
    'bus', 'rs485',
    'ph_ec_status', 'experimental'
  ),
  'plant-a-substrate-node.local'
FROM scope
ON CONFLICT ON CONSTRAINT "uq_device_site_device_id" DO UPDATE SET
  "tent_id" = EXCLUDED."tent_id",
  "zone_id" = EXCLUDED."zone_id",
  "name" = EXCLUDED."name",
  "kind" = EXCLUDED."kind",
  "controller" = EXCLUDED."controller",
  "enabled" = EXCLUDED."enabled",
  "metadata" = EXCLUDED."metadata",
  "hostname" = EXCLUDED."hostname",
  "updated_at" = now();

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
node AS (
  SELECT d."id"
  FROM "device" AS d
  JOIN home ON home."id" = d."site_id"
  WHERE d."device_id" = 'plant-a-substrate-node'
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
  node."id",
  v."capability_id",
  v."name",
  'measurement',
  v."metric_name",
  v."unit",
  'esp32',
  true,
  jsonb_build_object(
    'expected_wire_metric', true,
    'freshness_required', true,
    'sensor_model', 'DFRobot SEN0604',
    'modbus_address', '0x02',
    'experimental', v."experimental",
    'experimental_note', v."experimental_note"
  )
FROM node
JOIN (VALUES
  ('soil_moisture_pct', 'Soil Moisture', 'soil_moisture_pct', 'pct', false, NULL),
  ('substrate_temp_c', 'Substrate Temperature', 'substrate_temp_c', 'degC', false, NULL),
  ('substrate_ec_us_cm', 'Substrate EC', 'substrate_ec_us_cm', 'us/cm', true, 'pH/EC readings are experimental trend/reference values until field-calibrated.'),
  ('substrate_ph', 'Substrate pH', 'substrate_ph', 'pH', true, 'pH/EC readings are experimental trend/reference values until field-calibrated.')
) AS v(
  "capability_id",
  "name",
  "metric_name",
  "unit",
  "experimental",
  "experimental_note"
) ON true
ON CONFLICT ON CONSTRAINT "uq_capability_device_capability_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "kind" = EXCLUDED."kind",
  "metric_name" = EXCLUDED."metric_name",
  "unit" = EXCLUDED."unit",
  "source" = EXCLUDED."source",
  "enabled" = EXCLUDED."enabled",
  "metadata" = EXCLUDED."metadata";
