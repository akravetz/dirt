-- Add the source-owned metric presentation registry used by gateway rollups.

CREATE TABLE "metric_presentation" (
  "metric" text NOT NULL,
  "display_name" text NOT NULL,
  "unit" text NOT NULL,
  "accent" text NOT NULL,
  "value_precision" integer NOT NULL DEFAULT 1,
  "y_min" double precision NULL,
  "y_max" double precision NULL,
  "current_enabled" boolean NOT NULL DEFAULT false,
  "history_enabled" boolean NOT NULL DEFAULT false,
  "dashboard_group" text NULL,
  "dashboard_group_label" text NULL,
  "dashboard_group_order" integer NULL,
  "display_order" integer NOT NULL DEFAULT 0,
  PRIMARY KEY ("metric")
);

INSERT INTO "metric_presentation" (
  "metric",
  "display_name",
  "unit",
  "accent",
  "value_precision",
  "y_min",
  "y_max",
  "current_enabled",
  "history_enabled",
  "dashboard_group",
  "dashboard_group_label",
  "dashboard_group_order",
  "display_order"
)
VALUES
  ('temperature_f', 'Temperature', '°F', 'temp', 1, 60, 90, true, true, 'temperature_loop', 'Temperature Loop', 10, 10),
  ('humidity_pct', 'Humidity', '%', 'humidity', 0, 20, 90, true, true, 'humidity_loop', 'Humidity Loop', 20, 20),
  ('vpd_kpa', 'VPD', 'kPa', 'vpd', 1, 0, 2, true, true, 'plant_water', 'Plant / Water', 30, 30),
  ('fan_pct', 'Fan', '%', 'neutral', 0, 0, 100, true, true, 'temperature_loop', 'Temperature Loop', 10, 40),
  ('humidifier_intensity_pct', 'Humidifier', '%', 'humidity', 0, 0, 100, true, true, 'humidity_loop', 'Humidity Loop', 20, 50),
  ('reservoir_in', 'Reservoir', 'in', 'reservoir', 0, 0, 30, true, true, 'plant_water', 'Plant / Water', 30, 60),
  ('heater_intensity_pct', 'Heat', '%', 'temp', 0, 0, 100, true, true, 'temperature_loop', 'Temperature Loop', 10, 70),
  ('dehumidifier_on', 'Dehumidifier', '%', 'humidity', 0, 0, 100, false, true, 'humidity_loop', 'Humidity Loop', 20, 80),
  ('reservoir_ph', 'pH', 'pH', 'reservoir', 1, 4, 10, false, true, 'plant_water', 'Plant / Water', 30, 90),
  ('soil_moisture_pct', 'Soil Moisture', '%', 'moisture', 0, 0, 100, false, true, 'plant_water', 'Plant / Water', 30, 100)
ON CONFLICT ("metric") DO UPDATE SET
  "display_name" = EXCLUDED."display_name",
  "unit" = EXCLUDED."unit",
  "accent" = EXCLUDED."accent",
  "value_precision" = EXCLUDED."value_precision",
  "y_min" = EXCLUDED."y_min",
  "y_max" = EXCLUDED."y_max",
  "current_enabled" = EXCLUDED."current_enabled",
  "history_enabled" = EXCLUDED."history_enabled",
  "dashboard_group" = EXCLUDED."dashboard_group",
  "dashboard_group_label" = EXCLUDED."dashboard_group_label",
  "dashboard_group_order" = EXCLUDED."dashboard_group_order",
  "display_order" = EXCLUDED."display_order";
