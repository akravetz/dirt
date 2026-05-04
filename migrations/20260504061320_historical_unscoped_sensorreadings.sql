-- Backfill historical sensor readings that have an unambiguous canonical
-- capability, and deliberately leave obsolete/ambiguous metrics unscoped.
--
-- Quarantined historical-unscoped classes after this migration:
--   * tent / pressure_hpa: old atmospheric pressure stream; no current
--     canonical capability or consumer contract.
--   * reservoir / reservoir_depth_cm: old derived centimetre depth; current
--     reservoir depth capability is reservoir_in and the unit conversion
--     would create false lineage.
--   * plant-a / humidity_pct: one-off plant-node payload; humidity is owned
--     by the tent fan-controller, not plant nodes.

WITH legacy_map AS (
  SELECT *
  FROM (VALUES
    ('tent', 'fan-controller'),
    ('plant-a', 'plant-a-node'),
    ('plant-b', 'plant-b-node'),
    ('plant-c', 'plant-c-node'),
    ('plant-d', 'plant-d-node'),
    ('reservoir', 'reservoir-node')
  ) AS v("legacy_location", "device_id")
),
home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
)
UPDATE "sensorreading" sr
SET "capability_id" = c."id"
FROM "sensornode" sn
JOIN legacy_map lm ON lm."legacy_location" = sn."location"::text
JOIN "device" d
  ON d."site_id" = (SELECT "id" FROM home)
 AND d."device_id" = lm."device_id"
JOIN "capability" c
  ON c."device_id" = d."id"
WHERE sr."sensornode_id" = sn."id"
  AND sr."capability_id" IS NULL
  AND c."metric_name" = sr."metric";

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
govee AS (
  SELECT d."id"
  FROM "device" d
  JOIN home ON home."id" = d."site_id"
  WHERE d."device_id" = 'govee-h7142-main'
)
UPDATE "sensorreading" sr
SET "capability_id" = c."id"
FROM "capability" c
JOIN govee ON govee."id" = c."device_id"
WHERE sr."capability_id" IS NULL
  AND sr."metric" IN ('humidifier_on', 'humidifier_mist_level')
  AND c."metric_name" = sr."metric";
