-- Create "plant_metric_stream" table
CREATE TABLE "plant_metric_stream" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "plant_id" bigint NOT NULL,
  "capability_id" bigint NOT NULL,
  "display_order" integer NOT NULL DEFAULT 0,
  "is_active" boolean NOT NULL DEFAULT true,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  "updated_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_plant_metric_stream_plant_capability" UNIQUE ("plant_id", "capability_id"),
  CONSTRAINT "plant_metric_stream_capability_id_fkey" FOREIGN KEY ("capability_id") REFERENCES "capability" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "plant_metric_stream_plant_id_fkey" FOREIGN KEY ("plant_id") REFERENCES "plant" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT
);
-- Create index "ix_plant_metric_stream_capability_id" to table: "plant_metric_stream"
CREATE INDEX "ix_plant_metric_stream_capability_id" ON "plant_metric_stream" ("capability_id");
-- Create index "ix_plant_metric_stream_is_active" to table: "plant_metric_stream"
CREATE INDEX "ix_plant_metric_stream_is_active" ON "plant_metric_stream" ("is_active");
-- Create index "ix_plant_metric_stream_plant_id" to table: "plant_metric_stream"
CREATE INDEX "ix_plant_metric_stream_plant_id" ON "plant_metric_stream" ("plant_id");

-- Seed Plant A's canonical active metric streams for the current grow.
DO $$
DECLARE
  plant_a_pk bigint;
  plant_a_count bigint;
  missing_metrics text[];
BEGIN
  SELECT count(*), min(p."id")
  INTO plant_a_count, plant_a_pk
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

  WITH required("capability_id", "metric_name", "display_order") AS (
    VALUES
      ('soil_moisture_pct', 'soil_moisture_pct', 1),
      ('substrate_temp_c', 'substrate_temp_c', 2),
      ('substrate_ec_us_cm', 'substrate_ec_us_cm', 3),
      ('substrate_ph', 'substrate_ph', 4)
  )
  SELECT array_agg(required."metric_name" ORDER BY required."display_order")
  INTO missing_metrics
  FROM required
  WHERE NOT EXISTS (
    SELECT 1
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
     AND c."capability_id" = required."capability_id"
     AND c."metric_name" = required."metric_name"
    WHERE s."site_id" = 'homebox'
  );

  IF missing_metrics IS NOT NULL THEN
    RAISE EXCEPTION 'missing Plant A substrate capabilities for homebox/main: %', array_to_string(missing_metrics, ', ');
  END IF;

  WITH required("capability_id", "metric_name", "display_order") AS (
    VALUES
      ('soil_moisture_pct', 'soil_moisture_pct', 1),
      ('substrate_temp_c', 'substrate_temp_c', 2),
      ('substrate_ec_us_cm', 'substrate_ec_us_cm', 3),
      ('substrate_ph', 'substrate_ph', 4)
  ),
  stream_capabilities AS (
    SELECT c."id" AS capability_pk, required."display_order"
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
  INSERT INTO "plant_metric_stream" (
    "plant_id",
    "capability_id",
    "display_order",
    "is_active"
  )
  SELECT
    plant_a_pk,
    stream_capabilities.capability_pk,
    stream_capabilities."display_order",
    true
  FROM stream_capabilities
  ON CONFLICT ON CONSTRAINT "uq_plant_metric_stream_plant_capability" DO UPDATE SET
    "display_order" = EXCLUDED."display_order",
    "is_active" = EXCLUDED."is_active",
    "updated_at" = now();
END $$;
