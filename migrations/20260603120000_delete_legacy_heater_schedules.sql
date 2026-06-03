-- Retire the old schedule-driven heater path. Heater devices and capabilities
-- remain; ClimateControllerService now owns heater targets.
DELETE FROM "schedule"
WHERE "kind" = 'heater';
