-- Seed logical Plant C and Plant D RS485 substrate probe contracts.
--
-- The physical ESP32 remains plant-a-substrate-node.local. Each probe is a
-- logical Dirt device so readings, freshness, hosted sync identity, and plant
-- metric streams stay capability-owned per plant.

WITH probe_devices(
  "device_id",
  "zone_id",
  "name",
  "modbus_address"
) AS (
  VALUES
    ('plant-d-substrate-node', 'plant-d', 'ESP32-C3 Plant D RS485 substrate', '0x03'),
    ('plant-c-substrate-node', 'plant-c', 'ESP32-C3 Plant C RS485 substrate', '0x04')
),
scoped AS (
  SELECT
    s."id" AS site_pk,
    t."id" AS tent_pk,
    z."id" AS zone_pk,
    probe_devices."device_id",
    probe_devices."zone_id",
    probe_devices."name",
    probe_devices."modbus_address"
  FROM probe_devices
  JOIN "site" AS s
    ON s."site_id" = 'homebox'
  JOIN "tent" AS t
    ON t."site_id" = s."id"
   AND t."tent_id" = 'main'
  JOIN "zone" AS z
    ON z."site_id" = s."id"
   AND z."tent_id" = t."id"
   AND z."zone_id" = probe_devices."zone_id"
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
  scoped.site_pk,
  scoped.tent_pk,
  scoped.zone_pk,
  scoped."device_id",
  scoped."name",
  'moisture_node',
  'esp32',
  true,
  jsonb_build_object(
    'sensor_model', 'DFRobot SEN0604',
    'bus_controller_device_id', 'plant-a-substrate-node',
    'bus', 'rs485',
    'modbus_address', scoped."modbus_address",
    'ph_ec_status', 'calibrated'
  ),
  'plant-a-substrate-node.local'
FROM scoped
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

WITH probe_devices(
  "device_id",
  "modbus_address"
) AS (
  VALUES
    ('plant-d-substrate-node', '0x03'),
    ('plant-c-substrate-node', '0x04')
),
home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
nodes AS (
  SELECT
    d."id" AS device_pk,
    probe_devices."modbus_address"
  FROM probe_devices
  JOIN home
    ON true
  JOIN "device" AS d
    ON d."site_id" = home."id"
   AND d."device_id" = probe_devices."device_id"
),
required(
  "capability_id",
  "name",
  "metric_name",
  "unit",
  "calibration_status"
) AS (
  VALUES
    ('soil_moisture_pct', 'Soil Moisture', 'soil_moisture_pct', 'pct', NULL),
    ('substrate_temp_c', 'Substrate Temperature', 'substrate_temp_c', 'degC', NULL),
    ('substrate_ec_us_cm', 'Substrate EC', 'substrate_ec_us_cm', 'us/cm', 'calibrated'),
    ('substrate_ph', 'Substrate pH', 'substrate_ph', 'pH', 'calibrated')
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
  nodes.device_pk,
  required."capability_id",
  required."name",
  'measurement',
  required."metric_name",
  required."unit",
  'esp32',
  true,
  jsonb_strip_nulls(
    jsonb_build_object(
      'expected_wire_metric', true,
      'freshness_required', true,
      'sensor_model', 'DFRobot SEN0604',
      'modbus_address', nodes."modbus_address",
      'calibration_status', required."calibration_status"
    )
  )
FROM nodes
JOIN required
  ON true
ON CONFLICT ON CONSTRAINT "uq_capability_device_capability_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "kind" = EXCLUDED."kind",
  "metric_name" = EXCLUDED."metric_name",
  "unit" = EXCLUDED."unit",
  "source" = EXCLUDED."source",
  "enabled" = EXCLUDED."enabled",
  "metadata" = EXCLUDED."metadata";

DO $$
DECLARE
  missing_plants text[];
  missing_capabilities text[];
BEGIN
  WITH required_plants("plant_id") AS (
    VALUES ('d'), ('c')
  ),
  current_plants AS (
    SELECT
      required_plants."plant_id",
      p."id" AS plant_pk
    FROM required_plants
    LEFT JOIN "site" AS s
      ON s."site_id" = 'homebox'
    LEFT JOIN "tent" AS t
      ON t."site_id" = s."id"
     AND t."tent_id" = 'main'
    LEFT JOIN "growrun" AS gr
      ON gr."site_id" = s."id"
     AND gr."tent_id" = t."id"
     AND gr."is_current" IS TRUE
    LEFT JOIN "plant" AS p
      ON p."site_id" = s."id"
     AND p."tent_id" = t."id"
     AND p."growrun_id" = gr."id"
     AND p."plant_id" = required_plants."plant_id"
  )
  SELECT array_agg("plant_id" ORDER BY "plant_id")
  INTO missing_plants
  FROM current_plants
  WHERE plant_pk IS NULL;

  IF missing_plants IS NOT NULL THEN
    RAISE EXCEPTION 'missing current Plant C/D rows for homebox/main: %',
      array_to_string(missing_plants, ', ');
  END IF;

  WITH required_slots(
    "plant_id",
    "zone_id",
    "device_id",
    "capability_id",
    "metric_name",
    "display_order"
  ) AS (
    VALUES
      ('d', 'plant-d', 'plant-d-substrate-node', 'soil_moisture_pct', 'soil_moisture_pct', 1),
      ('d', 'plant-d', 'plant-d-substrate-node', 'substrate_temp_c', 'substrate_temp_c', 2),
      ('d', 'plant-d', 'plant-d-substrate-node', 'substrate_ec_us_cm', 'substrate_ec_us_cm', 3),
      ('d', 'plant-d', 'plant-d-substrate-node', 'substrate_ph', 'substrate_ph', 4),
      ('c', 'plant-c', 'plant-c-substrate-node', 'soil_moisture_pct', 'soil_moisture_pct', 1),
      ('c', 'plant-c', 'plant-c-substrate-node', 'substrate_temp_c', 'substrate_temp_c', 2),
      ('c', 'plant-c', 'plant-c-substrate-node', 'substrate_ec_us_cm', 'substrate_ec_us_cm', 3),
      ('c', 'plant-c', 'plant-c-substrate-node', 'substrate_ph', 'substrate_ph', 4)
  ),
  expected AS (
    SELECT
      required_slots."plant_id",
      required_slots."metric_name",
      c."id" AS capability_pk
    FROM required_slots
    LEFT JOIN "site" AS s
      ON s."site_id" = 'homebox'
    LEFT JOIN "tent" AS t
      ON t."site_id" = s."id"
     AND t."tent_id" = 'main'
    LEFT JOIN "zone" AS z
      ON z."site_id" = s."id"
     AND z."tent_id" = t."id"
     AND z."zone_id" = required_slots."zone_id"
    LEFT JOIN "device" AS d
      ON d."site_id" = s."id"
     AND d."tent_id" = t."id"
     AND d."zone_id" = z."id"
     AND d."device_id" = required_slots."device_id"
    LEFT JOIN "capability" AS c
      ON c."device_id" = d."id"
     AND c."capability_id" = required_slots."capability_id"
     AND c."metric_name" = required_slots."metric_name"
  )
  SELECT array_agg("plant_id" || ':' || "metric_name" ORDER BY "plant_id", "metric_name")
  INTO missing_capabilities
  FROM expected
  WHERE capability_pk IS NULL;

  IF missing_capabilities IS NOT NULL THEN
    RAISE EXCEPTION 'missing Plant C/D substrate capabilities for homebox/main: %',
      array_to_string(missing_capabilities, ', ');
  END IF;

  WITH required_slots(
    "plant_id",
    "zone_id",
    "device_id",
    "capability_id",
    "metric_name",
    "display_order"
  ) AS (
    VALUES
      ('d', 'plant-d', 'plant-d-substrate-node', 'soil_moisture_pct', 'soil_moisture_pct', 1),
      ('d', 'plant-d', 'plant-d-substrate-node', 'substrate_temp_c', 'substrate_temp_c', 2),
      ('d', 'plant-d', 'plant-d-substrate-node', 'substrate_ec_us_cm', 'substrate_ec_us_cm', 3),
      ('d', 'plant-d', 'plant-d-substrate-node', 'substrate_ph', 'substrate_ph', 4),
      ('c', 'plant-c', 'plant-c-substrate-node', 'soil_moisture_pct', 'soil_moisture_pct', 1),
      ('c', 'plant-c', 'plant-c-substrate-node', 'substrate_temp_c', 'substrate_temp_c', 2),
      ('c', 'plant-c', 'plant-c-substrate-node', 'substrate_ec_us_cm', 'substrate_ec_us_cm', 3),
      ('c', 'plant-c', 'plant-c-substrate-node', 'substrate_ph', 'substrate_ph', 4)
  ),
  stream_capabilities AS (
    SELECT
      p."id" AS plant_pk,
      c."id" AS capability_pk,
      required_slots."display_order"
    FROM required_slots
    JOIN "site" AS s
      ON s."site_id" = 'homebox'
    JOIN "tent" AS t
      ON t."site_id" = s."id"
     AND t."tent_id" = 'main'
    JOIN "growrun" AS gr
      ON gr."site_id" = s."id"
     AND gr."tent_id" = t."id"
     AND gr."is_current" IS TRUE
    JOIN "plant" AS p
      ON p."site_id" = s."id"
     AND p."tent_id" = t."id"
     AND p."growrun_id" = gr."id"
     AND p."plant_id" = required_slots."plant_id"
    JOIN "zone" AS z
      ON z."site_id" = s."id"
     AND z."tent_id" = t."id"
     AND z."zone_id" = required_slots."zone_id"
    JOIN "device" AS d
      ON d."site_id" = s."id"
     AND d."tent_id" = t."id"
     AND d."zone_id" = z."id"
     AND d."device_id" = required_slots."device_id"
    JOIN "capability" AS c
      ON c."device_id" = d."id"
     AND c."capability_id" = required_slots."capability_id"
     AND c."metric_name" = required_slots."metric_name"
  )
  INSERT INTO "plant_metric_stream" (
    "plant_id",
    "capability_id",
    "display_order",
    "is_active"
  )
  SELECT
    stream_capabilities.plant_pk,
    stream_capabilities.capability_pk,
    stream_capabilities."display_order",
    true
  FROM stream_capabilities
  ON CONFLICT ON CONSTRAINT "uq_plant_metric_stream_plant_capability" DO UPDATE SET
    "display_order" = EXCLUDED."display_order",
    "is_active" = EXCLUDED."is_active",
    "updated_at" = now();
END $$;
