-- Use a surrogate row identity while preserving metric as the business key.

ALTER TABLE "metric_presentation"
  DROP CONSTRAINT "metric_presentation_pkey";

ALTER TABLE "metric_presentation"
  ADD COLUMN "id" bigint GENERATED ALWAYS AS IDENTITY;

ALTER TABLE "metric_presentation"
  ADD CONSTRAINT "metric_presentation_pkey" PRIMARY KEY ("id");

ALTER TABLE "metric_presentation"
  ADD CONSTRAINT "uq_metric_presentation_metric" UNIQUE ("metric");
