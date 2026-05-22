-- Standardize scheduled Kasa heat-pad vocabulary to generic heater terms.
-- Device identity remains hardware-specific: kasa-heat-pad-breeding.

WITH breeding_heater_device AS (
  SELECT d."id"
  FROM "device" AS d
  JOIN "site" AS s ON s."id" = d."site_id"
  WHERE s."site_id" = 'homebox'
    AND d."device_id" = 'kasa-heat-pad-breeding'
)
UPDATE "capability" AS c
SET
  "capability_id" = 'power',
  "metric_name" = 'heater_on',
  "name" = 'Heater Power'
FROM breeding_heater_device
WHERE c."device_id" = breeding_heater_device."id"
  AND c."capability_id" = 'heat_pad_power'
  AND c."metric_name" = 'heat_pad_on'
  AND c."name" = 'Heat Pad Power';

WITH breeding AS (
  SELECT t."id"
  FROM "tent" AS t
  JOIN "site" AS s ON s."id" = t."site_id"
  WHERE s."site_id" = 'homebox'
    AND t."tent_id" = 'breeding'
)
UPDATE "schedule" AS sch
SET
  "schedule_id" = 'breeding-heater-night',
  "kind" = 'heater',
  "updated_at" = now()
FROM breeding
WHERE sch."tent_id" = breeding."id"
  AND sch."schedule_id" = 'breeding-heat-pad-night'
  AND sch."kind" = 'heat_pad';
