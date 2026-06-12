-- Enable plant substrate detail history presentation without adding tent current cards.

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
  ('soil_moisture_pct', 'Soil Moisture', '%', 'moisture', 0, 0, 100, false, true, 'plant_water', 'Plant / Water', 30, 100),
  ('substrate_temp_c', 'Substrate Temp', '°F', 'temp', 1, 60, 90, false, true, 'plant_water', 'Plant / Water', 30, 110),
  ('substrate_ec_us_cm', 'Substrate EC', 'mS/cm', 'neutral', 2, 0, 5, false, true, 'plant_water', 'Plant / Water', 30, 120),
  ('substrate_ph', 'Substrate pH', 'pH', 'reservoir', 1, 4, 8, false, true, 'plant_water', 'Plant / Water', 30, 130)
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
