-- Create "site" table
CREATE TABLE "site" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "site_id" text NOT NULL,
  "name" text NOT NULL,
  "location" text NULL,
  "timezone" text NOT NULL DEFAULT 'America/Denver',
  "is_default" boolean NOT NULL DEFAULT false,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  "updated_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("id"),
  CONSTRAINT "site_site_id_key" UNIQUE ("site_id")
);
-- Create index "ux_site_is_default" to table: "site"
CREATE UNIQUE INDEX "ux_site_is_default" ON "site" ("is_default") WHERE (is_default = true);
-- Create "tent" table
CREATE TABLE "tent" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "site_id" bigint NOT NULL,
  "tent_id" text NOT NULL,
  "name" text NOT NULL,
  "role" text NOT NULL,
  "is_default" boolean NOT NULL DEFAULT false,
  "active" boolean NOT NULL DEFAULT true,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  "updated_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_tent_site_tent_id" UNIQUE ("site_id", "tent_id"),
  CONSTRAINT "tent_site_id_fkey" FOREIGN KEY ("site_id") REFERENCES "site" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT
);
-- Create index "ix_tent_site_id" to table: "tent"
CREATE INDEX "ix_tent_site_id" ON "tent" ("site_id");
-- Create index "ux_tent_default_per_site" to table: "tent"
CREATE UNIQUE INDEX "ux_tent_default_per_site" ON "tent" ("site_id") WHERE (is_default = true);
-- Create "zone" table
CREATE TABLE "zone" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "site_id" bigint NOT NULL,
  "tent_id" bigint NULL,
  "zone_id" text NOT NULL,
  "name" text NOT NULL,
  "zone_type" text NOT NULL,
  "active" boolean NOT NULL DEFAULT true,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  "updated_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_zone_scope_zone_id" UNIQUE ("site_id", "tent_id", "zone_id"),
  CONSTRAINT "zone_site_id_fkey" FOREIGN KEY ("site_id") REFERENCES "site" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "zone_tent_id_fkey" FOREIGN KEY ("tent_id") REFERENCES "tent" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT
);
-- Create index "ix_zone_site_id" to table: "zone"
CREATE INDEX "ix_zone_site_id" ON "zone" ("site_id");
-- Create index "ix_zone_tent_id" to table: "zone"
CREATE INDEX "ix_zone_tent_id" ON "zone" ("tent_id");
-- Create "device" table
CREATE TABLE "device" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "site_id" bigint NOT NULL,
  "tent_id" bigint NULL,
  "zone_id" bigint NULL,
  "device_id" text NOT NULL,
  "name" text NOT NULL,
  "kind" text NOT NULL,
  "controller" text NOT NULL,
  "enabled" boolean NOT NULL DEFAULT true,
  "metadata" jsonb NOT NULL DEFAULT '{}',
  "created_at" timestamptz NOT NULL DEFAULT now(),
  "updated_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_device_site_device_id" UNIQUE ("site_id", "device_id"),
  CONSTRAINT "device_site_id_fkey" FOREIGN KEY ("site_id") REFERENCES "site" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "device_tent_id_fkey" FOREIGN KEY ("tent_id") REFERENCES "tent" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "device_zone_id_fkey" FOREIGN KEY ("zone_id") REFERENCES "zone" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT
);
-- Create index "ix_device_site_id" to table: "device"
CREATE INDEX "ix_device_site_id" ON "device" ("site_id");
-- Create index "ix_device_tent_id" to table: "device"
CREATE INDEX "ix_device_tent_id" ON "device" ("tent_id");
-- Create index "ix_device_zone_id" to table: "device"
CREATE INDEX "ix_device_zone_id" ON "device" ("zone_id");
-- Create "capability" table
CREATE TABLE "capability" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "device_id" bigint NOT NULL,
  "capability_id" text NOT NULL,
  "name" text NOT NULL,
  "kind" text NOT NULL,
  "metric_name" text NULL,
  "unit" text NULL,
  "source" text NULL,
  "enabled" boolean NOT NULL DEFAULT true,
  "metadata" jsonb NOT NULL DEFAULT '{}',
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_capability_device_capability_id" UNIQUE ("device_id", "capability_id"),
  CONSTRAINT "capability_device_id_fkey" FOREIGN KEY ("device_id") REFERENCES "device" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT
);
-- Create index "ix_capability_device_id" to table: "capability"
CREATE INDEX "ix_capability_device_id" ON "capability" ("device_id");
-- Create index "ix_capability_metric_name" to table: "capability"
CREATE INDEX "ix_capability_metric_name" ON "capability" ("metric_name");
-- Create "command" table
CREATE TABLE "command" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "command_id" text NOT NULL,
  "idempotency_key" text NOT NULL,
  "site_id" bigint NOT NULL,
  "tent_id" bigint NULL,
  "zone_id" bigint NULL,
  "device_id" bigint NULL,
  "capability_id" bigint NULL,
  "command_type" text NOT NULL,
  "payload" jsonb NOT NULL DEFAULT '{}',
  "requested_by" text NOT NULL,
  "source" text NOT NULL,
  "status" text NOT NULL DEFAULT 'queued',
  "queued_at" timestamptz NOT NULL DEFAULT now(),
  "started_at" timestamptz NULL,
  "succeeded_at" timestamptz NULL,
  "failed_at" timestamptz NULL,
  "cancelled_at" timestamptz NULL,
  "result" jsonb NULL,
  "error" jsonb NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_command_command_id" UNIQUE ("command_id"),
  CONSTRAINT "uq_command_idempotency_key" UNIQUE ("idempotency_key"),
  CONSTRAINT "command_capability_id_fkey" FOREIGN KEY ("capability_id") REFERENCES "capability" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "command_device_id_fkey" FOREIGN KEY ("device_id") REFERENCES "device" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "command_site_id_fkey" FOREIGN KEY ("site_id") REFERENCES "site" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "command_tent_id_fkey" FOREIGN KEY ("tent_id") REFERENCES "tent" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "command_zone_id_fkey" FOREIGN KEY ("zone_id") REFERENCES "zone" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT
);
-- Create index "ix_command_queued_at" to table: "command"
CREATE INDEX "ix_command_queued_at" ON "command" ("queued_at" DESC);
-- Create index "ix_command_site_id" to table: "command"
CREATE INDEX "ix_command_site_id" ON "command" ("site_id");
-- Create index "ix_command_status" to table: "command"
CREATE INDEX "ix_command_status" ON "command" ("status");
-- Create index "ix_command_tent_id" to table: "command"
CREATE INDEX "ix_command_tent_id" ON "command" ("tent_id");
-- Create "growrun" table
CREATE TABLE "growrun" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "site_id" bigint NOT NULL,
  "tent_id" bigint NOT NULL,
  "grow_run_id" text NOT NULL,
  "name" text NOT NULL,
  "purpose" text NOT NULL,
  "germination_date" date NULL,
  "flower_start_date" date NULL,
  "lights_on_local" time NULL,
  "lights_off_local" time NULL,
  "strain" text NULL,
  "timezone" text NOT NULL DEFAULT 'America/Denver',
  "plant_count" smallint NOT NULL DEFAULT 0,
  "is_current" boolean NOT NULL DEFAULT false,
  "started_at" timestamptz NULL,
  "ended_at" timestamptz NULL,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  "updated_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_growrun_tent_grow_run_id" UNIQUE ("tent_id", "grow_run_id"),
  CONSTRAINT "growrun_site_id_fkey" FOREIGN KEY ("site_id") REFERENCES "site" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "growrun_tent_id_fkey" FOREIGN KEY ("tent_id") REFERENCES "tent" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "ck_growrun_plant_count" CHECK ((plant_count >= 0) AND (plant_count <= 64))
);
-- Create index "ix_growrun_site_id" to table: "growrun"
CREATE INDEX "ix_growrun_site_id" ON "growrun" ("site_id");
-- Create index "ix_growrun_tent_id" to table: "growrun"
CREATE INDEX "ix_growrun_tent_id" ON "growrun" ("tent_id");
-- Create index "ux_growrun_current_per_tent" to table: "growrun"
CREATE UNIQUE INDEX "ux_growrun_current_per_tent" ON "growrun" ("tent_id") WHERE (is_current = true);
-- Create "schedule" table
CREATE TABLE "schedule" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "site_id" bigint NOT NULL,
  "tent_id" bigint NOT NULL,
  "device_id" bigint NULL,
  "capability_id" bigint NULL,
  "schedule_id" text NOT NULL,
  "kind" text NOT NULL,
  "starts_local" time NULL,
  "ends_local" time NULL,
  "timezone" text NOT NULL DEFAULT 'America/Denver',
  "enabled" boolean NOT NULL DEFAULT true,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  "updated_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_schedule_tent_schedule_id" UNIQUE ("tent_id", "schedule_id"),
  CONSTRAINT "schedule_capability_id_fkey" FOREIGN KEY ("capability_id") REFERENCES "capability" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "schedule_device_id_fkey" FOREIGN KEY ("device_id") REFERENCES "device" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "schedule_site_id_fkey" FOREIGN KEY ("site_id") REFERENCES "site" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "schedule_tent_id_fkey" FOREIGN KEY ("tent_id") REFERENCES "tent" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT
);
-- Create index "ix_schedule_capability_id" to table: "schedule"
CREATE INDEX "ix_schedule_capability_id" ON "schedule" ("capability_id");
-- Create index "ix_schedule_device_id" to table: "schedule"
CREATE INDEX "ix_schedule_device_id" ON "schedule" ("device_id");
-- Create index "ix_schedule_site_id" to table: "schedule"
CREATE INDEX "ix_schedule_site_id" ON "schedule" ("site_id");
-- Create index "ix_schedule_tent_id" to table: "schedule"
CREATE INDEX "ix_schedule_tent_id" ON "schedule" ("tent_id");

-- ============================================================
-- Seed data — canonical local scope and current hardware map.
-- ============================================================

INSERT INTO "site" ("site_id", "name", "location", "timezone", "is_default")
VALUES ('homebox', 'Homebox', 'Denver, MT', 'America/Denver', true)
ON CONFLICT ("site_id") DO UPDATE SET
  "name" = EXCLUDED."name",
  "location" = EXCLUDED."location",
  "timezone" = EXCLUDED."timezone",
  "is_default" = EXCLUDED."is_default",
  "updated_at" = now();

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
)
INSERT INTO "tent" ("site_id", "tent_id", "name", "role", "is_default", "active")
SELECT home."id", v."tent_id", v."name", v."role", v."is_default", v."active"
FROM home
JOIN (VALUES
  ('main', 'Main Tent', 'flower', true, true),
  ('breeding', 'Breeding Tent', 'breeding', false, true)
) AS v("tent_id", "name", "role", "is_default", "active") ON true
ON CONFLICT ON CONSTRAINT "uq_tent_site_tent_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "role" = EXCLUDED."role",
  "is_default" = EXCLUDED."is_default",
  "active" = EXCLUDED."active",
  "updated_at" = now();

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
main AS (
  SELECT "id" FROM "tent"
  WHERE "site_id" = (SELECT "id" FROM home) AND "tent_id" = 'main'
)
INSERT INTO "zone" ("site_id", "tent_id", "zone_id", "name", "zone_type", "active")
SELECT home."id", main."id", v."zone_id", v."name", v."zone_type", true
FROM home, main
JOIN (VALUES
  ('canopy', 'Canopy', 'canopy'),
  ('reservoir', 'Reservoir', 'reservoir'),
  ('plant-a', 'Plant A', 'plant'),
  ('plant-b', 'Plant B', 'plant'),
  ('plant-c', 'Plant C', 'plant'),
  ('plant-d', 'Plant D', 'plant'),
  ('exhaust', 'Exhaust', 'airflow'),
  ('lights', 'Lights', 'fixture')
) AS v("zone_id", "name", "zone_type") ON true
ON CONFLICT ON CONSTRAINT "uq_zone_scope_zone_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "zone_type" = EXCLUDED."zone_type",
  "active" = EXCLUDED."active",
  "updated_at" = now();

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
main AS (
  SELECT "id" FROM "tent"
  WHERE "site_id" = (SELECT "id" FROM home) AND "tent_id" = 'main'
),
main_zones AS (
  SELECT "zone_id", "id" FROM "zone" WHERE "tent_id" = (SELECT "id" FROM main)
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
  "metadata"
)
SELECT
  home."id",
  CASE WHEN v."tent_scoped" THEN main."id" ELSE NULL END,
  main_zones."id",
  v."device_id",
  v."name",
  v."kind",
  v."controller",
  true,
  v."metadata"::jsonb
FROM home, main
JOIN (VALUES
  ('fan-controller', 'ESP32-C3 · fan+tent', 'env_sensor', 'esp32', true, 'canopy', '{"legacy_location":"tent"}'),
  ('plant-a-node', 'ESP32-C3 · plant_a', 'moisture_node', 'esp32', true, 'plant-a', '{"legacy_location":"plant-a"}'),
  ('plant-b-node', 'ESP32-C3 · plant_b', 'moisture_node', 'esp32', true, 'plant-b', '{"legacy_location":"plant-b"}'),
  ('plant-c-node', 'ESP32-C3 · plant_c', 'moisture_node', 'esp32', true, 'plant-c', '{"legacy_location":"plant-c"}'),
  ('plant-d-node', 'ESP32-C3 · plant_d', 'moisture_node', 'esp32', true, 'plant-d', '{"legacy_location":"plant-d"}'),
  ('reservoir-node', 'ESP32-C3 · reservoir', 'level_sensor', 'esp32', true, 'reservoir', '{"legacy_location":"reservoir"}'),
  ('govee-h7142-main', 'Humidifier (Govee H7142)', 'actuator', 'govee', true, 'canopy', '{"sku":"H7142"}'),
  ('kasa-lights-main', 'Kasa grow lights', 'actuator', 'kasa', true, 'lights', '{}'),
  ('obsbot-main', 'OBSBOT Tiny 2 Lite', 'camera', 'dirt-camera', true, 'canopy', '{}'),
  ('jabra-claudia', 'Jabra Speak 410 (Claudia)', 'voice', 'systemd', false, NULL, '{}')
) AS v("device_id", "name", "kind", "controller", "tent_scoped", "zone_key", "metadata") ON true
LEFT JOIN main_zones ON main_zones."zone_id" = v."zone_key"
ON CONFLICT ON CONSTRAINT "uq_device_site_device_id" DO UPDATE SET
  "tent_id" = EXCLUDED."tent_id",
  "zone_id" = EXCLUDED."zone_id",
  "name" = EXCLUDED."name",
  "kind" = EXCLUDED."kind",
  "controller" = EXCLUDED."controller",
  "enabled" = EXCLUDED."enabled",
  "metadata" = EXCLUDED."metadata",
  "updated_at" = now();

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
devices AS (
  SELECT "device_id", "id" FROM "device" WHERE "site_id" = (SELECT "id" FROM home)
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
  devices."id",
  v."capability_id",
  v."name",
  v."kind",
  v."metric_name",
  v."unit",
  v."source",
  true,
  '{}'::jsonb
FROM devices
JOIN (VALUES
  ('fan-controller', 'temperature_c', 'Temperature C', 'measurement', 'temperature_c', 'degC', 'esp32'),
  ('fan-controller', 'temperature_f', 'Temperature F', 'measurement', 'temperature_f', 'degF', 'derived'),
  ('fan-controller', 'humidity_pct', 'Humidity', 'measurement', 'humidity_pct', 'pct', 'esp32'),
  ('fan-controller', 'vpd_kpa', 'VPD', 'measurement', 'vpd_kpa', 'kPa', 'derived'),
  ('fan-controller', 'dew_point_f', 'Dew Point', 'measurement', 'dew_point_f', 'degF', 'derived'),
  ('fan-controller', 'fan_duty_pct', 'Fan Duty', 'measurement', 'fan_duty_pct', 'pct', 'esp32'),
  ('plant-a-node', 'soil_moisture_raw', 'Soil Moisture Raw', 'measurement', 'soil_moisture_raw', 'raw', 'esp32'),
  ('plant-b-node', 'soil_moisture_raw', 'Soil Moisture Raw', 'measurement', 'soil_moisture_raw', 'raw', 'esp32'),
  ('plant-c-node', 'soil_moisture_raw', 'Soil Moisture Raw', 'measurement', 'soil_moisture_raw', 'raw', 'esp32'),
  ('plant-d-node', 'soil_moisture_raw', 'Soil Moisture Raw', 'measurement', 'soil_moisture_raw', 'raw', 'esp32'),
  ('reservoir-node', 'reservoir_pressure_raw', 'Reservoir Pressure Raw', 'measurement', 'reservoir_pressure_raw', 'raw', 'esp32'),
  ('reservoir-node', 'reservoir_in', 'Reservoir Depth', 'measurement', 'reservoir_in', 'in', 'esp32'),
  ('govee-h7142-main', 'humidifier_on', 'Humidifier Power State', 'actuator_state', 'humidifier_on', 'bool', 'govee'),
  ('govee-h7142-main', 'humidifier_mist_level', 'Humidifier Mist Level', 'actuator_state', 'humidifier_mist_level', 'level', 'govee'),
  ('govee-h7142-main', 'power', 'Humidifier Power Control', 'actuator', NULL, NULL, 'govee'),
  ('govee-h7142-main', 'mist_level', 'Humidifier Mist Control', 'actuator', NULL, 'level', 'govee'),
  ('kasa-lights-main', 'lights_power', 'Lights Power Control', 'actuator', NULL, NULL, 'kasa'),
  ('obsbot-main', 'camera_capture', 'Camera Capture', 'camera_action', NULL, NULL, 'dirt-camera'),
  ('obsbot-main', 'ptz_move', 'PTZ Move', 'camera_action', NULL, NULL, 'dirt-camera'),
  ('jabra-claudia', 'voice_session', 'Voice Session', 'voice', NULL, NULL, 'systemd')
) AS v("device_key", "capability_id", "name", "kind", "metric_name", "unit", "source")
  ON devices."device_id" = v."device_key"
ON CONFLICT ON CONSTRAINT "uq_capability_device_capability_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "kind" = EXCLUDED."kind",
  "metric_name" = EXCLUDED."metric_name",
  "unit" = EXCLUDED."unit",
  "source" = EXCLUDED."source",
  "enabled" = EXCLUDED."enabled",
  "metadata" = EXCLUDED."metadata";
