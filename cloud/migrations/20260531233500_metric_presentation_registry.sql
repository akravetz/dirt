-- Add the source-owned metric presentation registry used by browser routes.

CREATE TABLE "cloud_metric_presentation" (
  "metric" character varying(120) NOT NULL,
  "display_name" character varying(160) NOT NULL,
  "unit" character varying(40) NOT NULL,
  "accent" character varying(40) NOT NULL,
  "value_precision" integer NOT NULL,
  "y_min" double precision NULL,
  "y_max" double precision NULL,
  "current_enabled" boolean NOT NULL,
  "history_enabled" boolean NOT NULL,
  "dashboard_group" character varying(80) NULL,
  "dashboard_group_label" character varying(160) NULL,
  "dashboard_group_order" integer NULL,
  "display_order" integer NOT NULL,
  PRIMARY KEY ("metric")
);

INSERT INTO "cloud_metric_presentation" (
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
