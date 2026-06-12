-- Mark Plant A RS485 substrate pH/EC capabilities as calibrated.
--
-- Keep the existing capability metadata contract intact while removing the
-- old experimental flags from the two pH/EC streams.

DO $$
DECLARE
  missing_metrics text[];
BEGIN
  WITH required("capability_id", "metric_name") AS (
    VALUES
      ('substrate_ec_us_cm', 'substrate_ec_us_cm'),
      ('substrate_ph', 'substrate_ph')
  ),
  expected AS (
    SELECT
      required."capability_id",
      required."metric_name",
      c."id" AS capability_pk
    FROM required
    LEFT JOIN "site" AS s
      ON s."site_id" = 'homebox'
    LEFT JOIN "tent" AS t
      ON t."site_id" = s."id"
     AND t."tent_id" = 'main'
    LEFT JOIN "zone" AS z
      ON z."site_id" = s."id"
     AND z."tent_id" = t."id"
     AND z."zone_id" = 'plant-a'
    LEFT JOIN "device" AS d
      ON d."site_id" = s."id"
     AND d."tent_id" = t."id"
     AND d."zone_id" = z."id"
     AND d."device_id" = 'plant-a-substrate-node'
    LEFT JOIN "capability" AS c
      ON c."device_id" = d."id"
     AND c."capability_id" = required."capability_id"
     AND c."metric_name" = required."metric_name"
  )
  SELECT array_agg(expected."metric_name" ORDER BY expected."metric_name")
  INTO missing_metrics
  FROM expected
  WHERE expected.capability_pk IS NULL;

  IF missing_metrics IS NOT NULL THEN
    RAISE EXCEPTION 'missing Plant A substrate pH/EC capabilities for homebox/main: %',
      array_to_string(missing_metrics, ', ');
  END IF;

  WITH required("capability_id", "metric_name") AS (
    VALUES
      ('substrate_ec_us_cm', 'substrate_ec_us_cm'),
      ('substrate_ph', 'substrate_ph')
  ),
  target_capabilities AS (
    SELECT c."id" AS capability_pk
    FROM required
    JOIN "site" AS s
      ON s."site_id" = 'homebox'
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
     AND c."capability_id" = required."capability_id"
     AND c."metric_name" = required."metric_name"
  )
  UPDATE "capability" AS c
  SET
    "metadata" = (
      (coalesce(c."metadata", '{}'::jsonb) - 'experimental' - 'experimental_note')
      || jsonb_build_object('calibration_status', 'calibrated')
    )
  FROM target_capabilities AS target
  WHERE c."id" = target.capability_pk
    AND (
      c."metadata" ? 'experimental'
      OR c."metadata" ? 'experimental_note'
      OR c."metadata"->>'calibration_status' IS DISTINCT FROM 'calibrated'
    );

  UPDATE "device" AS d
  SET
    "metadata" = (
      coalesce(d."metadata", '{}'::jsonb)
      || jsonb_build_object('ph_ec_status', 'calibrated')
    ),
    "updated_at" = now()
  FROM "site" AS s
  JOIN "tent" AS t
    ON t."site_id" = s."id"
   AND t."tent_id" = 'main'
  JOIN "zone" AS z
    ON z."site_id" = s."id"
   AND z."tent_id" = t."id"
   AND z."zone_id" = 'plant-a'
  WHERE s."site_id" = 'homebox'
    AND d."site_id" = s."id"
    AND d."tent_id" = t."id"
    AND d."zone_id" = z."id"
    AND d."device_id" = 'plant-a-substrate-node'
    AND d."metadata"->>'ph_ec_status' IS DISTINCT FROM 'calibrated';
END $$;
