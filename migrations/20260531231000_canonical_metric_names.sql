-- Canonicalize product telemetry names at the producer/storage boundary.

UPDATE "sensorreading"
SET "metric" = 'fan_pct'
WHERE "metric" = 'fan_duty_pct';

UPDATE "capability" AS c
SET
  "capability_id" = 'fan_pct',
  "name" = 'Fan',
  "metric_name" = 'fan_pct',
  "unit" = '%'
FROM "device" AS d
WHERE c."device_id" = d."id"
  AND d."device_id" = 'fan-controller'
  AND (
    c."capability_id" = 'fan_duty_pct'
    OR c."metric_name" = 'fan_duty_pct'
  );

UPDATE "sensorreading"
SET
  "metric" = 'humidifier_intensity_pct',
  "value" = "value" * 100.0 / 9.0
WHERE "metric" = 'humidifier_mist_level';

UPDATE "capability" AS c
SET
  "capability_id" = 'humidifier_intensity_pct',
  "name" = 'Humidifier Intensity',
  "metric_name" = 'humidifier_intensity_pct',
  "unit" = '%'
FROM "device" AS d
WHERE c."device_id" = d."id"
  AND d."device_id" = 'govee-h7142-main'
  AND (
    c."capability_id" = 'humidifier_mist_level'
    OR c."metric_name" = 'humidifier_mist_level'
  );

UPDATE "sensorreading"
SET
  "metric" = 'heater_intensity_pct',
  "value" = "value" * 10.0
WHERE "metric" = 'heater_heat_level';

UPDATE "capability" AS c
SET
  "name" = 'Heater Intensity',
  "metric_name" = 'heater_intensity_pct',
  "unit" = '%'
FROM "device" AS d
WHERE c."device_id" = d."id"
  AND d."device_id" = 'ac-infinity-thermoforge-main'
  AND c."metric_name" = 'heater_heat_level';
