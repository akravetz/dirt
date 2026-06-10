-- Modify "cloud_latest_metric" table
ALTER TABLE "cloud_latest_metric" DROP CONSTRAINT "cloud_latest_metric_pkey", DROP COLUMN "metric_key", ADD COLUMN "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY, ADD PRIMARY KEY ("id");
-- Modify "cloud_metric_rollup" table
ALTER TABLE "cloud_metric_rollup" DROP CONSTRAINT "cloud_metric_rollup_pkey", DROP COLUMN "rollup_key", ADD COLUMN "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY, ADD PRIMARY KEY ("id");
