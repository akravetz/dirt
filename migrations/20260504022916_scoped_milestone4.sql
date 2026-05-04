-- atlas:txmode none

-- Modify "sensorcalibration" table
ALTER TABLE "sensorcalibration" ALTER COLUMN "sensornode_id" DROP NOT NULL, ADD COLUMN "capability_id" bigint NULL, ADD CONSTRAINT "uq_sensorcalibration_capability_metric" UNIQUE ("capability_id", "metric"), ADD CONSTRAINT "sensorcalibration_capability_id_fkey" FOREIGN KEY ("capability_id") REFERENCES "capability" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT;
-- Backfill legacy per-(sensornode, metric) calibration rows onto canonical
-- default-main capabilities. The legacy sensornode mapping mirrors the
-- firmware location compatibility layer in ReadingsService.
UPDATE "sensorcalibration" AS sc
SET "capability_id" = c."id"
FROM "sensornode" AS sn
JOIN "device" AS d
  ON d."device_id" = CASE sn."location"::text
    WHEN 'tent' THEN 'fan-controller'
    WHEN 'reservoir' THEN 'reservoir-node'
    WHEN 'plant-a' THEN 'plant-a-node'
    WHEN 'plant-b' THEN 'plant-b-node'
    WHEN 'plant-c' THEN 'plant-c-node'
    WHEN 'plant-d' THEN 'plant-d-node'
    ELSE NULL
  END
JOIN "site" AS s ON s."id" = d."site_id"
JOIN "tent" AS t ON t."id" = d."tent_id"
JOIN "capability" AS c ON c."device_id" = d."id"
WHERE sc."sensornode_id" = sn."id"
  AND sc."capability_id" IS NULL
  AND c."metric_name" = sc."metric"
  AND s."site_id" = 'homebox'
  AND t."tent_id" = 'main';
-- Create index "ix_sensorcalibration_capability_id" to table: "sensorcalibration"
CREATE INDEX CONCURRENTLY "ix_sensorcalibration_capability_id" ON "sensorcalibration" ("capability_id");
-- Modify "snapshot" table
ALTER TABLE "snapshot" ADD COLUMN "site_id" bigint NULL, ADD COLUMN "tent_id" bigint NULL, ADD COLUMN "zone_id" bigint NULL, ADD COLUMN "device_id" bigint NULL, ADD COLUMN "growrun_id" bigint NULL, ADD COLUMN "view_id" text NOT NULL DEFAULT 'periodic', ADD COLUMN "kind" text NOT NULL DEFAULT 'periodic', ADD CONSTRAINT "snapshot_device_id_fkey" FOREIGN KEY ("device_id") REFERENCES "device" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT, ADD CONSTRAINT "snapshot_growrun_id_fkey" FOREIGN KEY ("growrun_id") REFERENCES "growrun" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT, ADD CONSTRAINT "snapshot_site_id_fkey" FOREIGN KEY ("site_id") REFERENCES "site" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT, ADD CONSTRAINT "snapshot_tent_id_fkey" FOREIGN KEY ("tent_id") REFERENCES "tent" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT, ADD CONSTRAINT "snapshot_zone_id_fkey" FOREIGN KEY ("zone_id") REFERENCES "zone" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT;
-- Backfill existing periodic snapshots to the current main tent and camera.
UPDATE "snapshot" AS snap
SET
  "site_id" = s."id",
  "tent_id" = t."id",
  "zone_id" = d."zone_id",
  "device_id" = d."id",
  "growrun_id" = gr."id",
  "view_id" = 'periodic',
  "kind" = 'periodic'
FROM "site" AS s
JOIN "tent" AS t ON t."site_id" = s."id"
JOIN "device" AS d ON d."site_id" = s."id" AND d."device_id" = 'obsbot-main'
LEFT JOIN "growrun" AS gr
  ON gr."site_id" = s."id"
 AND gr."tent_id" = t."id"
 AND gr."is_current" = true
WHERE s."site_id" = 'homebox'
  AND t."tent_id" = 'main'
  AND snap."site_id" IS NULL
  AND snap."tent_id" IS NULL;
-- Create index "ix_snapshot_device_id" to table: "snapshot"
CREATE INDEX CONCURRENTLY "ix_snapshot_device_id" ON "snapshot" ("device_id");
-- Create index "ix_snapshot_growrun_id" to table: "snapshot"
CREATE INDEX CONCURRENTLY "ix_snapshot_growrun_id" ON "snapshot" ("growrun_id");
-- Create index "ix_snapshot_scope_ts" to table: "snapshot"
CREATE INDEX CONCURRENTLY "ix_snapshot_scope_ts" ON "snapshot" ("site_id", "tent_id", "ts" DESC);
-- Materialize the main photoperiod as a scoped schedule row while growrun keeps
-- the user-facing photoperiod columns during this phase.
INSERT INTO "schedule" (
  "site_id",
  "tent_id",
  "device_id",
  "capability_id",
  "schedule_id",
  "kind",
  "starts_local",
  "ends_local",
  "timezone",
  "enabled"
)
SELECT
  s."id",
  t."id",
  d."id",
  c."id",
  'main-lights-photoperiod',
  'lights',
  gr."lights_on_local",
  gr."lights_off_local",
  gr."timezone",
  true
FROM "site" AS s
JOIN "tent" AS t ON t."site_id" = s."id"
JOIN "growrun" AS gr
  ON gr."site_id" = s."id"
 AND gr."tent_id" = t."id"
 AND gr."is_current" = true
LEFT JOIN "device" AS d
  ON d."site_id" = s."id"
 AND d."device_id" = 'kasa-lights-main'
LEFT JOIN "capability" AS c
  ON c."device_id" = d."id"
 AND c."capability_id" = 'lights_power'
WHERE s."site_id" = 'homebox'
  AND t."tent_id" = 'main'
ON CONFLICT ("tent_id", "schedule_id") DO UPDATE SET
  "device_id" = EXCLUDED."device_id",
  "capability_id" = EXCLUDED."capability_id",
  "starts_local" = EXCLUDED."starts_local",
  "ends_local" = EXCLUDED."ends_local",
  "timezone" = EXCLUDED."timezone",
  "enabled" = EXCLUDED."enabled",
  "updated_at" = now();
