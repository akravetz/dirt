-- Add AC Infinity as an owned reading source for ThermoForge actuator metrics.
ALTER TYPE "sensor_source" ADD VALUE IF NOT EXISTS 'ac_infinity' BEFORE 'arduino';
