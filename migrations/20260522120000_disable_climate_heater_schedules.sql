-- Retire schedule-driven climate heater ownership before climate dispatch cutover.
-- Heater devices and capabilities remain available for ClimateControllerService.

UPDATE "schedule" AS sch
SET
  "enabled" = false,
  "updated_at" = now()
FROM "device" AS d
WHERE sch."device_id" = d."id"
  AND sch."kind" = 'heater'
  AND sch."enabled" IS true
  AND d."kind" = 'actuator'
  AND d."controller" IN ('kasa', 'ac_infinity_ble');
