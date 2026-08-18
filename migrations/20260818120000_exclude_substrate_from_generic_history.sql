-- Keep mapped substrate history while excluding it from anonymous tent aggregates.

UPDATE "metric_presentation"
SET
  "history_enabled" = true,
  "dashboard_group" = NULL,
  "dashboard_group_label" = NULL,
  "dashboard_group_order" = NULL
WHERE "metric" IN (
  'soil_moisture_pct',
  'substrate_temp_c',
  'substrate_ec_us_cm',
  'substrate_ph'
);
