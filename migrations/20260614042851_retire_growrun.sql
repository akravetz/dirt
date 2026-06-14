-- Modify "snapshot" table
-- atlas:nolint DS103
ALTER TABLE "snapshot" DROP COLUMN "growrun_id";
-- Drop "growrun" table
-- atlas:nolint DS102
DROP TABLE "growrun";
