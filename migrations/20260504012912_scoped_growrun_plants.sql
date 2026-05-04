-- atlas:txmode none

-- Move current singleton grow semantics into the scoped growrun table.

ALTER TABLE "growrun"
  ADD COLUMN "location" text NOT NULL DEFAULT 'Denver, MT · closet tent';

INSERT INTO "growrun" (
  "site_id",
  "tent_id",
  "grow_run_id",
  "name",
  "purpose",
  "germination_date",
  "flower_start_date",
  "lights_on_local",
  "lights_off_local",
  "strain",
  "location",
  "timezone",
  "plant_count",
  "is_current",
  "started_at"
)
SELECT
  s."id",
  t."id",
  t."tent_id" || '-' || g."germination_date"::text,
  'Main grow ' || g."germination_date"::text,
  'flower',
  g."germination_date",
  g."flower_start_date",
  g."lights_on_local",
  g."lights_off_local",
  g."strain",
  g."location",
  g."timezone",
  g."plant_count",
  g."is_current",
  g."germination_date"::timestamp AT TIME ZONE g."timezone"
FROM "growstate" g
JOIN "site" s ON s."site_id" = 'homebox'
JOIN "tent" t ON t."site_id" = s."id" AND t."tent_id" = 'main'
WHERE g."is_current" = true
ON CONFLICT ON CONSTRAINT "uq_growrun_tent_grow_run_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "purpose" = EXCLUDED."purpose",
  "germination_date" = EXCLUDED."germination_date",
  "flower_start_date" = EXCLUDED."flower_start_date",
  "lights_on_local" = EXCLUDED."lights_on_local",
  "lights_off_local" = EXCLUDED."lights_off_local",
  "strain" = EXCLUDED."strain",
  "location" = EXCLUDED."location",
  "timezone" = EXCLUDED."timezone",
  "plant_count" = EXCLUDED."plant_count",
  "is_current" = EXCLUDED."is_current",
  "started_at" = EXCLUDED."started_at",
  "updated_at" = now();

ALTER TABLE "plant"
  ADD COLUMN "site_id" bigint NULL,
  ADD COLUMN "tent_id" bigint NULL,
  ADD COLUMN "growrun_id" bigint NULL,
  ADD COLUMN "plant_id" text NULL;

WITH scope AS (
  SELECT s."id" AS site_pk, t."id" AS tent_pk
  FROM "site" s
  JOIN "tent" t ON t."site_id" = s."id"
  WHERE s."site_id" = 'homebox' AND t."tent_id" = 'main'
),
current_main AS (
  SELECT gr."id" AS growrun_pk, gr."site_id", gr."tent_id"
  FROM "growrun" gr
  JOIN scope sc ON sc.site_pk = gr."site_id" AND sc.tent_pk = gr."tent_id"
  WHERE gr."is_current" = true
  LIMIT 1
)
UPDATE "plant" p
SET
  "site_id" = current_main."site_id",
  "tent_id" = current_main."tent_id",
  "growrun_id" = current_main.growrun_pk,
  "plant_id" = p."code"
FROM current_main
WHERE p."growstate_id" IS NOT NULL;

ALTER TABLE "plant"
  ALTER COLUMN "site_id" SET NOT NULL,
  ALTER COLUMN "tent_id" SET NOT NULL,
  ALTER COLUMN "growrun_id" SET NOT NULL,
  ALTER COLUMN "plant_id" SET NOT NULL;

ALTER TABLE "plant" DROP CONSTRAINT "plant_growstate_id_fkey";
ALTER TABLE "plant" DROP CONSTRAINT "uq_plant_grow_code";
DROP INDEX "ix_plant_growstate_id";

ALTER TABLE "plant"
  ADD CONSTRAINT "uq_plant_growrun_plant_id" UNIQUE ("growrun_id", "plant_id"),
  ADD CONSTRAINT "plant_growrun_id_fkey" FOREIGN KEY ("growrun_id") REFERENCES "growrun" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  ADD CONSTRAINT "plant_site_id_fkey" FOREIGN KEY ("site_id") REFERENCES "site" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  ADD CONSTRAINT "plant_tent_id_fkey" FOREIGN KEY ("tent_id") REFERENCES "tent" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT;

ALTER TABLE "plant" DROP COLUMN "growstate_id";

CREATE INDEX CONCURRENTLY "ix_plant_growrun_id" ON "plant" ("growrun_id");
CREATE INDEX CONCURRENTLY "ix_plant_site_id" ON "plant" ("site_id");
CREATE INDEX CONCURRENTLY "ix_plant_tent_id" ON "plant" ("tent_id");

DROP TABLE "growstate";
