-- atlas:txmode none

-- Modify "plant" table
ALTER TABLE "plant" ADD COLUMN "moisture_capability_id" bigint NULL, ADD CONSTRAINT "plant_moisture_capability_id_fkey" FOREIGN KEY ("moisture_capability_id") REFERENCES "capability" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT;
-- Backfill current main plants from their legacy moisture node to the
-- canonical plant-node soil_moisture_raw capability.
UPDATE "plant" AS p
SET
  "moisture_capability_id" = c."id",
  "updated_at" = now()
FROM "sensornode" AS sn
JOIN "device" AS d
  ON d."device_id" = CASE sn."location"::text
    WHEN 'plant-a' THEN 'plant-a-node'
    WHEN 'plant-b' THEN 'plant-b-node'
    WHEN 'plant-c' THEN 'plant-c-node'
    WHEN 'plant-d' THEN 'plant-d-node'
    ELSE NULL
  END
JOIN "site" AS s ON s."id" = d."site_id"
JOIN "tent" AS t ON t."id" = d."tent_id"
JOIN "capability" AS c
  ON c."device_id" = d."id"
 AND c."capability_id" = 'soil_moisture_raw'
 AND c."metric_name" = 'soil_moisture_raw'
WHERE p."sensornode_id" = sn."id"
  AND p."moisture_capability_id" IS NULL
  AND s."site_id" = 'homebox'
  AND t."tent_id" = 'main';
-- Create index "ix_plant_moisture_capability_id" to table: "plant"
CREATE INDEX CONCURRENTLY "ix_plant_moisture_capability_id" ON "plant" ("moisture_capability_id");
