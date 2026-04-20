-- Create enum type "plant_sticker"
CREATE TYPE "plant_sticker" AS ENUM ('yellow', 'orange', 'pink', 'blue');
-- Create enum type "plant_status"
CREATE TYPE "plant_status" AS ENUM ('primary', 'secondary', 'retired');
-- Create enum type "sensor_location"
CREATE TYPE "sensor_location" AS ENUM ('tent', 'plant-a', 'plant-b', 'plant-c', 'plant-d', 'reservoir');
-- Create enum type "sensor_source"
CREATE TYPE "sensor_source" AS ENUM ('arduino', 'esp32', 'kasa', 'mock');
-- Create "growstate" table
CREATE TABLE "growstate" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "germination_date" date NOT NULL,
  "flower_start_date" date NULL,
  "lights_on_local" time NOT NULL DEFAULT '05:00:00',
  "lights_off_local" time NOT NULL DEFAULT '23:00:00',
  "strain" text NOT NULL DEFAULT 'Sirius Black × BS01',
  "location" text NOT NULL DEFAULT 'Denver, MT · closet tent',
  "plant_count" smallint NOT NULL DEFAULT 4,
  "is_current" boolean NOT NULL DEFAULT false,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("id"),
  CONSTRAINT "ck_growstate_plant_count" CHECK ((plant_count >= 1) AND (plant_count <= 16))
);
-- Create index "ux_growstate_is_current" to table: "growstate"
CREATE UNIQUE INDEX "ux_growstate_is_current" ON "growstate" ("is_current") WHERE (is_current = true);
-- Create "snapshot" table
CREATE TABLE "snapshot" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "ts" timestamptz NOT NULL DEFAULT now(),
  "file_path" text NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "snapshot_file_path_key" UNIQUE ("file_path")
);
-- Create index "ix_snapshot_ts" to table: "snapshot"
CREATE INDEX "ix_snapshot_ts" ON "snapshot" ("ts" DESC);
-- Create "sensornode" table
CREATE TABLE "sensornode" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "location" "sensor_location" NOT NULL,
  "ip" inet NULL,
  "firmware_version" text NULL,
  "uptime_ms" bigint NULL,
  "last_seen" timestamptz NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "sensornode_location_key" UNIQUE ("location")
);
-- Create index "ix_sensornode_last_seen" to table: "sensornode"
CREATE INDEX "ix_sensornode_last_seen" ON "sensornode" ("last_seen" DESC);
-- Create "plant" table
CREATE TABLE "plant" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "growstate_id" bigint NOT NULL,
  "sensornode_id" bigint NOT NULL,
  "code" text NOT NULL,
  "name" text NOT NULL,
  "sticker_color" "plant_sticker" NOT NULL,
  "status" "plant_status" NOT NULL DEFAULT 'secondary',
  "purple" boolean NOT NULL DEFAULT false,
  "label" text NULL,
  "moisture_target_low" double precision NOT NULL DEFAULT 55,
  "moisture_target_high" double precision NOT NULL DEFAULT 70,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  "updated_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("id"),
  CONSTRAINT "plant_sensornode_id_key" UNIQUE ("sensornode_id"),
  CONSTRAINT "uq_plant_grow_code" UNIQUE ("growstate_id", "code"),
  CONSTRAINT "plant_growstate_id_fkey" FOREIGN KEY ("growstate_id") REFERENCES "growstate" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "plant_sensornode_id_fkey" FOREIGN KEY ("sensornode_id") REFERENCES "sensornode" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT,
  CONSTRAINT "ck_plant_code_lowercase_letter" CHECK (code ~ '^[a-z]$'::text),
  CONSTRAINT "ck_plant_moisture_high_bounds" CHECK (moisture_target_high <= (100)::double precision),
  CONSTRAINT "ck_plant_moisture_low_bounds" CHECK ((moisture_target_low >= (0)::double precision) AND (moisture_target_low < moisture_target_high))
);
-- Create index "ix_plant_growstate_id" to table: "plant"
CREATE INDEX "ix_plant_growstate_id" ON "plant" ("growstate_id");
-- Create index "ix_plant_status" to table: "plant"
CREATE INDEX "ix_plant_status" ON "plant" ("status");
-- Create "sensorcalibration" table
CREATE TABLE "sensorcalibration" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "sensornode_id" bigint NOT NULL,
  "metric" text NOT NULL,
  "raw_low" double precision NOT NULL,
  "raw_high" double precision NOT NULL,
  "updated_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_sensorcalibration_node_metric" UNIQUE ("sensornode_id", "metric"),
  CONSTRAINT "sensorcalibration_sensornode_id_fkey" FOREIGN KEY ("sensornode_id") REFERENCES "sensornode" ("id") ON UPDATE NO ACTION ON DELETE CASCADE,
  CONSTRAINT "ck_sensorcalibration_range" CHECK (raw_high >= raw_low)
);
-- Create "sensorreading" table
CREATE TABLE "sensorreading" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "ts" timestamptz NOT NULL DEFAULT now(),
  "sensornode_id" bigint NOT NULL,
  "metric" text NOT NULL,
  "value" double precision NOT NULL,
  "source" "sensor_source" NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "sensorreading_sensornode_id_fkey" FOREIGN KEY ("sensornode_id") REFERENCES "sensornode" ("id") ON UPDATE NO ACTION ON DELETE RESTRICT
);
-- Create index "ix_sensorreading_metric_ts" to table: "sensorreading"
CREATE INDEX "ix_sensorreading_metric_ts" ON "sensorreading" ("metric", "ts" DESC);
-- Create index "ix_sensorreading_node_ts" to table: "sensorreading"
CREATE INDEX "ix_sensorreading_node_ts" ON "sensorreading" ("sensornode_id", "ts" DESC);
-- Create index "ix_sensorreading_ts" to table: "sensorreading"
CREATE INDEX "ix_sensorreading_ts" ON "sensorreading" USING BRIN ("ts");

-- ============================================================
-- Seed data — makes all FK targets exist from day one.
-- ============================================================

-- growstate: one row, flagged current. germination_date + strain + location
-- come from the wiki / current config; the sqlite→postgres data move
-- overwrites germination_date + flower_start_date + lights_on/off with the
-- actual values from var/dirt.db.pre-pg-cutover.
INSERT INTO "growstate" ("germination_date", "strain", "location", "plant_count", "is_current")
VALUES ('2026-03-15', 'Sirius Black × BS01', 'Denver, MT · closet tent', 4, true);

-- sensornode: one row per sensor_location enum value. The ESP32 plant nodes
-- self-populate ip/firmware/uptime/last_seen on their first POST. The 'tent'
-- and 'reservoir' rows stay minimally populated until real hardware owns them.
INSERT INTO "sensornode" ("location") VALUES
  ('tent'),
  ('plant-a'),
  ('plant-b'),
  ('plant-c'),
  ('plant-d'),
  ('reservoir');

-- plant: 4 rows for the current grow, each FK'd to its sensornode by location.
-- Sticker/status/purple/label come from the mockup's initial values and current
-- wiki (plant-a.md / plant-d.md both tagged Primary keeper + confirmed purple).
INSERT INTO "plant" ("growstate_id", "sensornode_id", "code", "name", "sticker_color", "status", "purple", "label")
SELECT g."id", n."id", v.code, v.name, v.sticker::"plant_sticker", v.status::"plant_status", v.purple, v.label
FROM "growstate" g
  CROSS JOIN "sensornode" n
  JOIN (VALUES
    ('a', 'Plant A', 'yellow', 'primary',   true,  'Purple Keeper Candidate', 'plant-a'),
    ('b', 'Plant B', 'orange', 'secondary', false, NULL,                      'plant-b'),
    ('c', 'Plant C', 'pink',   'secondary', false, NULL,                      'plant-c'),
    ('d', 'Plant D', 'blue',   'primary',   true,  'Purple Keeper Candidate', 'plant-d')
  ) AS v(code, name, sticker, status, purple, label, node_location)
    ON n."location"::text = v.node_location
WHERE g."is_current" = true;
