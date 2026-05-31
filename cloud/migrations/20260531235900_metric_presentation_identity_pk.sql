-- Use a surrogate row identity while preserving metric as the business key.

ALTER TABLE "cloud_metric_presentation"
  DROP CONSTRAINT "cloud_metric_presentation_pkey";

ALTER TABLE "cloud_metric_presentation"
  ADD COLUMN "id" bigint GENERATED ALWAYS AS IDENTITY;

ALTER TABLE "cloud_metric_presentation"
  ADD CONSTRAINT "cloud_metric_presentation_pkey" PRIMARY KEY ("id");

ALTER TABLE "cloud_metric_presentation"
  ADD CONSTRAINT "uq_cloud_metric_presentation_metric" UNIQUE ("metric");
