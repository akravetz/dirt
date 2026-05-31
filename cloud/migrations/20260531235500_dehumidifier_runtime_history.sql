-- Model dehumidifier history as runtime percent derived from the binary state.

DELETE FROM "cloud_metric_presentation"
WHERE "metric" = 'dehumidifier_on';

INSERT INTO "cloud_metric_presentation" (
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
  ('dehumidifier_runtime_pct', 'Dehumidifier Runtime', '%', 'humidity', 0, 0, 100, false, true, 'humidity_loop', 'Humidity Loop', 20, 80)
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

UPDATE "cloud_metric_rollup"
SET
  "rollup_key" = "site_id" || ':' || "tent_id" || ':' || "device_id" || ':' || "capability_id" || ':dehumidifier_runtime_pct:' || "bucket" || ':' || to_char("bucket_start_at" AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS') || '+00:00',
  "metric" = 'dehumidifier_runtime_pct',
  "unit" = '%',
  "min_value" = CASE
    WHEN "min_value" IS NULL THEN NULL
    ELSE round(("min_value" * 100.0)::numeric, 4)::double precision
  END,
  "avg_value" = CASE
    WHEN "avg_value" IS NULL THEN NULL
    ELSE round(("avg_value" * 100.0)::numeric, 4)::double precision
  END,
  "max_value" = CASE
    WHEN "max_value" IS NULL THEN NULL
    ELSE round(("max_value" * 100.0)::numeric, 4)::double precision
  END
WHERE "metric" = 'dehumidifier_on';
