-- Cut current Plant A moisture over to the validated RS485 substrate probe.
--
-- This intentionally preserves the old capacitive devices, capabilities,
-- calibrations, and readings. B-D only lose their current moisture pointer
-- when that pointer still references the old plant-node soil_moisture_raw
-- capabilities.

DO $$
DECLARE
  rs485_moisture_capability_id bigint;
  plant_a_count bigint;
BEGIN
  SELECT c."id"
  INTO rs485_moisture_capability_id
  FROM "site" AS s
  JOIN "tent" AS t
    ON t."site_id" = s."id"
   AND t."tent_id" = 'main'
  JOIN "zone" AS z
    ON z."site_id" = s."id"
   AND z."tent_id" = t."id"
   AND z."zone_id" = 'plant-a'
  JOIN "device" AS d
    ON d."site_id" = s."id"
   AND d."tent_id" = t."id"
   AND d."zone_id" = z."id"
   AND d."device_id" = 'plant-a-substrate-node'
  JOIN "capability" AS c
    ON c."device_id" = d."id"
   AND c."capability_id" = 'soil_moisture_pct'
   AND c."metric_name" = 'soil_moisture_pct'
  WHERE s."site_id" = 'homebox';

  IF rs485_moisture_capability_id IS NULL THEN
    RAISE EXCEPTION 'missing RS485 plant-a-substrate-node soil_moisture_pct capability for homebox/main/plant-a';
  END IF;

  SELECT count(*)
  INTO plant_a_count
  FROM "plant" AS p
  JOIN "growrun" AS gr
    ON gr."id" = p."growrun_id"
   AND gr."is_current" IS TRUE
  JOIN "site" AS s
    ON s."id" = gr."site_id"
   AND s."id" = p."site_id"
   AND s."site_id" = 'homebox'
  JOIN "tent" AS t
    ON t."id" = gr."tent_id"
   AND t."id" = p."tent_id"
   AND t."tent_id" = 'main'
  WHERE p."plant_id" = 'a';

  IF plant_a_count <> 1 THEN
    RAISE EXCEPTION 'expected exactly one current Plant A row for homebox/main, found %', plant_a_count;
  END IF;

  UPDATE "plant" AS p
  SET
    "moisture_capability_id" = rs485_moisture_capability_id,
    "updated_at" = now()
  FROM "growrun" AS gr,
       "site" AS s,
       "tent" AS t
  WHERE p."growrun_id" = gr."id"
    AND p."site_id" = s."id"
    AND p."tent_id" = t."id"
    AND gr."site_id" = s."id"
    AND gr."tent_id" = t."id"
    AND gr."is_current" IS TRUE
    AND s."site_id" = 'homebox'
    AND t."tent_id" = 'main'
    AND p."plant_id" = 'a'
    AND p."moisture_capability_id" IS DISTINCT FROM rs485_moisture_capability_id;

  UPDATE "plant" AS p
  SET
    "moisture_capability_id" = NULL,
    "updated_at" = now()
  FROM "growrun" AS gr,
       "site" AS s,
       "tent" AS t,
       "capability" AS old_capability,
       "device" AS old_device
  WHERE p."growrun_id" = gr."id"
    AND p."site_id" = s."id"
    AND p."tent_id" = t."id"
    AND gr."site_id" = s."id"
    AND gr."tent_id" = t."id"
    AND old_capability."id" = p."moisture_capability_id"
    AND old_device."id" = old_capability."device_id"
    AND gr."is_current" IS TRUE
    AND s."site_id" = 'homebox'
    AND t."tent_id" = 'main'
    AND p."plant_id" IN ('b', 'c', 'd')
    AND old_device."device_id" IN ('plant-b-node', 'plant-c-node', 'plant-d-node')
    AND old_capability."capability_id" = 'soil_moisture_raw'
    AND old_capability."metric_name" = 'soil_moisture_raw';
END $$;
