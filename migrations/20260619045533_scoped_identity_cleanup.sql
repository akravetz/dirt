ALTER TABLE "site" DROP CONSTRAINT "site_site_id_key";

ALTER TABLE "tent" DROP CONSTRAINT "uq_tent_site_tent_id";

ALTER TABLE "zone" DROP CONSTRAINT "uq_zone_scope_zone_id";

ALTER TABLE "schedule" DROP CONSTRAINT "uq_schedule_tent_schedule_id";

-- atlas:nolint DS103
ALTER TABLE "site" DROP COLUMN "site_id";

-- atlas:nolint DS103
ALTER TABLE "tent" DROP COLUMN "tent_id";

-- atlas:nolint DS103
ALTER TABLE "zone" DROP COLUMN "zone_id";

-- atlas:nolint DS103
ALTER TABLE "schedule" DROP COLUMN "schedule_id";
