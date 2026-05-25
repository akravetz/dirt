-- Seed the breeding tent Shelly drip pump controller.
-- The MAC is the stable identity; hostname and IP are reachability hints.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM "site" AS s
    JOIN "tent" AS t ON t."site_id" = s."id"
    WHERE s."site_id" = 'homebox'
      AND t."tent_id" = 'breeding'
  ) THEN
    RAISE EXCEPTION 'missing scope homebox/breeding';
  END IF;
END $$;

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
breeding AS (
  SELECT t."id"
  FROM "tent" AS t
  JOIN home ON home."id" = t."site_id"
  WHERE t."tent_id" = 'breeding'
)
INSERT INTO "device" (
  "site_id",
  "tent_id",
  "device_id",
  "name",
  "kind",
  "controller",
  "enabled",
  "metadata",
  "ip",
  "hostname",
  "provider_uid_kind",
  "provider_uid"
)
SELECT
  home."id",
  breeding."id",
  'shelly-breeding-drip-pump',
  'Shelly breeding drip pump',
  'actuator',
  'shelly',
  true,
  jsonb_build_object(
    'model', 'S4PL-00116US',
    'app', 'PlugUSG4',
    'generation', 4,
    'rpc_endpoint', '/rpc',
    'switch_id', 0
  ),
  '192.168.1.44'::inet,
  'ShellyPlugUSG4-ACEBE6F59BDC.local',
  'mac',
  'ACEBE6F59BDC'
FROM home, breeding
ON CONFLICT ON CONSTRAINT "uq_device_site_device_id" DO UPDATE SET
  "tent_id" = EXCLUDED."tent_id",
  "name" = EXCLUDED."name",
  "kind" = EXCLUDED."kind",
  "controller" = EXCLUDED."controller",
  "enabled" = EXCLUDED."enabled",
  "metadata" = EXCLUDED."metadata",
  "ip" = EXCLUDED."ip",
  "hostname" = EXCLUDED."hostname",
  "provider_uid_kind" = EXCLUDED."provider_uid_kind",
  "provider_uid" = EXCLUDED."provider_uid",
  "updated_at" = now();

WITH home AS (
  SELECT "id" FROM "site" WHERE "site_id" = 'homebox'
),
drip_pump AS (
  SELECT d."id"
  FROM "device" AS d
  JOIN home ON home."id" = d."site_id"
  WHERE d."device_id" = 'shelly-breeding-drip-pump'
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
  drip_pump."id",
  'pump_power',
  'Drip Pump Power Control',
  'actuator',
  'pump_on',
  'bool',
  'shelly',
  true,
  jsonb_build_object(
    'rpc_method', 'Switch.Set',
    'switch_id', 0,
    'supports_toggle_after', true
  )
FROM drip_pump
ON CONFLICT ON CONSTRAINT "uq_capability_device_capability_id" DO UPDATE SET
  "name" = EXCLUDED."name",
  "kind" = EXCLUDED."kind",
  "metric_name" = EXCLUDED."metric_name",
  "unit" = EXCLUDED."unit",
  "source" = EXCLUDED."source",
  "enabled" = EXCLUDED."enabled",
  "metadata" = EXCLUDED."metadata";
