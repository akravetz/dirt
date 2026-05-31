-- Canonicalize hosted product telemetry rows after the local producer cutover.

UPDATE "cloud_capability"
SET
  "capability_id" = 'fan_pct',
  "capability_key" = "site_id" || ':' || "tent_id" || ':' || "device_id" || ':fan_pct',
  "metric_name" = 'fan_pct',
  "unit" = '%'
WHERE "device_id" = 'fan-controller'
  AND (
    "capability_id" = 'fan_duty_pct'
    OR "metric_name" = 'fan_duty_pct'
  );

UPDATE "cloud_latest_metric"
SET
  "capability_id" = 'fan_pct',
  "metric" = 'fan_pct',
  "unit" = '%',
  "metric_key" = "site_id" || ':' || "tent_id" || ':' || "device_id" || ':fan_pct:fan_pct'
WHERE "device_id" = 'fan-controller'
  AND (
    "capability_id" = 'fan_duty_pct'
    OR "metric" = 'fan_duty_pct'
  );

UPDATE "cloud_metric_rollup"
SET
  "capability_id" = 'fan_pct',
  "metric" = 'fan_pct',
  "unit" = '%',
  "rollup_key" = "site_id" || ':' || "tent_id" || ':' || "device_id" || ':fan_pct:fan_pct:' || "bucket" || ':' || to_char("bucket_start_at" AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS') || '+00:00'
WHERE "device_id" = 'fan-controller'
  AND (
    "capability_id" = 'fan_duty_pct'
    OR "metric" = 'fan_duty_pct'
  );

UPDATE "cloud_capability"
SET
  "capability_id" = 'humidifier_intensity_pct',
  "capability_key" = "site_id" || ':' || "tent_id" || ':' || "device_id" || ':humidifier_intensity_pct',
  "metric_name" = 'humidifier_intensity_pct',
  "unit" = '%'
WHERE "device_id" = 'govee-h7142-main'
  AND (
    "capability_id" = 'humidifier_mist_level'
    OR "metric_name" = 'humidifier_mist_level'
  );

UPDATE "cloud_latest_metric"
SET
  "capability_id" = 'humidifier_intensity_pct',
  "metric" = 'humidifier_intensity_pct',
  "value" = "value" * 100.0 / 9.0,
  "unit" = '%',
  "metric_key" = "site_id" || ':' || "tent_id" || ':' || "device_id" || ':humidifier_intensity_pct:humidifier_intensity_pct'
WHERE "device_id" = 'govee-h7142-main'
  AND (
    "capability_id" = 'humidifier_mist_level'
    OR "metric" = 'humidifier_mist_level'
  );

UPDATE "cloud_metric_rollup"
SET
  "capability_id" = 'humidifier_intensity_pct',
  "metric" = 'humidifier_intensity_pct',
  "min_value" = "min_value" * 100.0 / 9.0,
  "avg_value" = "avg_value" * 100.0 / 9.0,
  "max_value" = "max_value" * 100.0 / 9.0,
  "unit" = '%',
  "rollup_key" = "site_id" || ':' || "tent_id" || ':' || "device_id" || ':humidifier_intensity_pct:humidifier_intensity_pct:' || "bucket" || ':' || to_char("bucket_start_at" AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS') || '+00:00'
WHERE "device_id" = 'govee-h7142-main'
  AND (
    "capability_id" = 'humidifier_mist_level'
    OR "metric" = 'humidifier_mist_level'
  );

UPDATE "cloud_capability"
SET
  "metric_name" = 'heater_intensity_pct',
  "unit" = '%'
WHERE "device_id" = 'ac-infinity-thermoforge-main'
  AND "metric_name" = 'heater_heat_level';

UPDATE "cloud_latest_metric"
SET
  "metric" = 'heater_intensity_pct',
  "value" = "value" * 10.0,
  "unit" = '%',
  "metric_key" = "site_id" || ':' || "tent_id" || ':' || "device_id" || ':' || "capability_id" || ':heater_intensity_pct'
WHERE "device_id" = 'ac-infinity-thermoforge-main'
  AND "metric" = 'heater_heat_level';

UPDATE "cloud_metric_rollup"
SET
  "metric" = 'heater_intensity_pct',
  "min_value" = "min_value" * 10.0,
  "avg_value" = "avg_value" * 10.0,
  "max_value" = "max_value" * 10.0,
  "unit" = '%',
  "rollup_key" = "site_id" || ':' || "tent_id" || ':' || "device_id" || ':' || "capability_id" || ':heater_intensity_pct:' || "bucket" || ':' || to_char("bucket_start_at" AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS') || '+00:00'
WHERE "device_id" = 'ac-infinity-thermoforge-main'
  AND "metric" = 'heater_heat_level';
