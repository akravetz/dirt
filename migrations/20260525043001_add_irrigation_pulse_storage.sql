-- Create "irrigation_schedule_item" table
CREATE TABLE "irrigation_schedule_item" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "schedule_id" bigint NOT NULL,
  "starts_local" time NOT NULL,
  "duration_s" integer NOT NULL,
  "enabled" boolean NOT NULL DEFAULT true,
  "label" text NULL,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  "updated_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_irrigation_schedule_item_schedule_start" UNIQUE ("schedule_id", "starts_local"),
  CONSTRAINT "irrigation_schedule_item_schedule_id_fkey" FOREIGN KEY ("schedule_id") REFERENCES "schedule" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "ck_irrigation_schedule_item_duration_positive" CHECK (duration_s > 0)
);
-- Create index "ix_irrigation_schedule_item_schedule_id" to table: "irrigation_schedule_item"
CREATE INDEX "ix_irrigation_schedule_item_schedule_id" ON "irrigation_schedule_item" ("schedule_id");
-- Create "irrigation_run" table
CREATE TABLE "irrigation_run" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "schedule_id" bigint NOT NULL,
  "schedule_item_id" bigint NOT NULL,
  "device_id" bigint NOT NULL,
  "capability_id" bigint NOT NULL,
  "intended_start_at" timestamptz NOT NULL,
  "started_at" timestamptz NULL,
  "finished_at" timestamptz NULL,
  "duration_s" integer NOT NULL,
  "status" text NOT NULL,
  "error" text NULL,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  "updated_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_irrigation_run_schedule_item_intended_start" UNIQUE ("schedule_item_id", "intended_start_at"),
  CONSTRAINT "irrigation_run_capability_id_fkey" FOREIGN KEY ("capability_id") REFERENCES "capability" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "irrigation_run_device_id_fkey" FOREIGN KEY ("device_id") REFERENCES "device" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "irrigation_run_schedule_id_fkey" FOREIGN KEY ("schedule_id") REFERENCES "schedule" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "irrigation_run_schedule_item_id_fkey" FOREIGN KEY ("schedule_item_id") REFERENCES "irrigation_schedule_item" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "ck_irrigation_run_duration_positive" CHECK (duration_s > 0),
  CONSTRAINT "ck_irrigation_run_status" CHECK (status = ANY (ARRAY['pending'::text, 'dispatched'::text, 'failed'::text, 'skipped'::text]))
);
-- Create index "ix_irrigation_run_capability_id" to table: "irrigation_run"
CREATE INDEX "ix_irrigation_run_capability_id" ON "irrigation_run" ("capability_id");
-- Create index "ix_irrigation_run_device_id" to table: "irrigation_run"
CREATE INDEX "ix_irrigation_run_device_id" ON "irrigation_run" ("device_id");
-- Create index "ix_irrigation_run_schedule_id" to table: "irrigation_run"
CREATE INDEX "ix_irrigation_run_schedule_id" ON "irrigation_run" ("schedule_id");
-- Create index "ix_irrigation_run_schedule_item_id" to table: "irrigation_run"
CREATE INDEX "ix_irrigation_run_schedule_item_id" ON "irrigation_run" ("schedule_item_id");

-- Seed the disabled breeding tent irrigation schedule and calibration pulse.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM "site" AS s
    JOIN "tent" AS t ON t."site_id" = s."id"
    JOIN "device" AS d ON d."site_id" = s."id" AND d."tent_id" = t."id"
    JOIN "capability" AS c ON c."device_id" = d."id"
    WHERE s."site_id" = 'homebox'
      AND t."tent_id" = 'breeding'
      AND d."device_id" = 'shelly-breeding-drip-pump'
      AND c."capability_id" = 'pump_power'
  ) THEN
    RAISE EXCEPTION 'missing Shelly breeding drip pump capability';
  END IF;
END $$;

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
breeding AS (
  SELECT t."id"
  FROM "tent" AS t
  JOIN home ON home."id" = t."site_id"
  WHERE t."tent_id" = 'breeding'
),
drip_pump AS (
  SELECT d."id"
  FROM "device" AS d
  JOIN home ON home."id" = d."site_id"
  JOIN breeding ON breeding."id" = d."tent_id"
  WHERE d."device_id" = 'shelly-breeding-drip-pump'
),
pump_power AS (
  SELECT c."id"
  FROM "capability" AS c
  JOIN drip_pump ON drip_pump."id" = c."device_id"
  WHERE c."capability_id" = 'pump_power'
)
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
  home."id",
  breeding."id",
  drip_pump."id",
  pump_power."id",
  'breeding-drip-pump-irrigation',
  'irrigation',
  NULL,
  NULL,
  'America/Denver',
  false
FROM home, breeding, drip_pump, pump_power
ON CONFLICT ON CONSTRAINT "uq_schedule_tent_schedule_id" DO UPDATE SET
  "device_id" = EXCLUDED."device_id",
  "capability_id" = EXCLUDED."capability_id",
  "kind" = EXCLUDED."kind",
  "starts_local" = EXCLUDED."starts_local",
  "ends_local" = EXCLUDED."ends_local",
  "timezone" = EXCLUDED."timezone",
  "enabled" = EXCLUDED."enabled",
  "updated_at" = now();

WITH irrigation_schedule AS (
  SELECT sch."id"
  FROM "schedule" AS sch
  JOIN "site" AS s ON s."id" = sch."site_id"
  JOIN "tent" AS t ON t."id" = sch."tent_id"
  WHERE s."site_id" = 'homebox'
    AND t."tent_id" = 'breeding'
    AND sch."schedule_id" = 'breeding-drip-pump-irrigation'
)
INSERT INTO "irrigation_schedule_item" (
  "schedule_id",
  "starts_local",
  "duration_s",
  "enabled",
  "label"
)
SELECT
  irrigation_schedule."id",
  '11:00:00'::time,
  5,
  false,
  'Calibration pulse'
FROM irrigation_schedule
ON CONFLICT ON CONSTRAINT "uq_irrigation_schedule_item_schedule_start" DO UPDATE SET
  "duration_s" = EXCLUDED."duration_s",
  "enabled" = EXCLUDED."enabled",
  "label" = EXCLUDED."label",
  "updated_at" = now();
