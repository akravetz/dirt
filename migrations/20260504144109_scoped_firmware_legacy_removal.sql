-- Final legacy sensor identity cleanup.
--
-- Historical reservoir_depth_cm readings represent the same physical stream
-- as the canonical reservoir-node reservoir_in capability. Normalize them in
-- storage before dropping sensornode lineage: inches = centimetres / 2.54.
DO $$
DECLARE
  reservoir_capability_id bigint;
  remaining_null_rows bigint;
BEGIN
  SELECT c."id"
  INTO reservoir_capability_id
  FROM "capability" AS c
  JOIN "device" AS d ON d."id" = c."device_id"
  JOIN "site" AS s ON s."id" = d."site_id"
  JOIN "tent" AS t ON t."id" = d."tent_id"
  WHERE s."site_id" = 'homebox'
    AND t."tent_id" = 'main'
    AND d."device_id" = 'reservoir-node'
    AND c."capability_id" = 'reservoir_in'
    AND c."metric_name" = 'reservoir_in';

  IF reservoir_capability_id IS NULL THEN
    RAISE EXCEPTION 'canonical reservoir-node reservoir_in capability is required before legacy sensor cleanup';
  END IF;

  UPDATE "sensorreading" AS sr
  SET "metric" = 'reservoir_in',
      "value" = sr."value" / 2.54,
      "capability_id" = reservoir_capability_id
  FROM "sensornode" AS sn
  WHERE sr."sensornode_id" = sn."id"
    AND sr."capability_id" IS NULL
    AND sn."location"::text = 'reservoir'
    AND sr."metric" = 'reservoir_depth_cm';

  -- Discard known trash historical rows after the normal pre-migration
  -- pg_dump. Do not create archive-only capabilities for these values.
  DELETE FROM "sensorreading" AS sr
  USING "sensornode" AS sn
  WHERE sr."sensornode_id" = sn."id"
    AND sr."capability_id" IS NULL
    AND sn."location"::text = 'tent'
    AND sr."metric" = 'pressure_hpa';

  DELETE FROM "sensorreading" AS sr
  USING "sensornode" AS sn
  WHERE sr."sensornode_id" = sn."id"
    AND sr."capability_id" IS NULL
    AND sn."location"::text = 'plant-a'
    AND sr."metric" = 'humidity_pct';

  SELECT count(*)
  INTO remaining_null_rows
  FROM "sensorreading"
  WHERE "capability_id" IS NULL;

  IF remaining_null_rows <> 0 THEN
    RAISE EXCEPTION 'unexpected null-capability sensorreading rows remain before sensornode cleanup: %', remaining_null_rows;
  END IF;
END $$;

-- Modify "sensorreading" table
ALTER TABLE "sensorreading" DROP COLUMN "sensornode_id", ALTER COLUMN "capability_id" SET NOT NULL;
-- Drop "sensornode" table
DROP TABLE "sensornode";
-- Drop enum type "sensor_location"
DROP TYPE "sensor_location";
