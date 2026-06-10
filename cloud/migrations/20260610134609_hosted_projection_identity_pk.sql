-- Modify "cloud_capability" table
ALTER TABLE "cloud_capability" DROP CONSTRAINT "cloud_capability_pkey", DROP COLUMN "capability_key", ADD COLUMN "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY, ADD PRIMARY KEY ("id");
-- Modify "cloud_device" table
ALTER TABLE "cloud_device" DROP CONSTRAINT "cloud_device_pkey", DROP COLUMN "device_key", ADD COLUMN "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY, ADD PRIMARY KEY ("id");
-- Modify "cloud_plant" table
ALTER TABLE "cloud_plant" DROP CONSTRAINT "cloud_plant_pkey", DROP COLUMN "plant_key", ADD COLUMN "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY, ADD PRIMARY KEY ("id");
-- Modify "cloud_schedule" table
ALTER TABLE "cloud_schedule" DROP CONSTRAINT "cloud_schedule_pkey", DROP COLUMN "schedule_key", ADD COLUMN "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY, ADD PRIMARY KEY ("id");
-- Modify "cloud_tent" table
ALTER TABLE "cloud_tent" DROP CONSTRAINT "cloud_tent_pkey", DROP COLUMN "tent_key", ADD COLUMN "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY, ADD PRIMARY KEY ("id");
-- Modify "cloud_wiki_page" table
ALTER TABLE "cloud_wiki_page" DROP CONSTRAINT "cloud_wiki_page_pkey", DROP COLUMN "wiki_key", ADD COLUMN "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY, ADD PRIMARY KEY ("id");
-- Modify "cloud_zone" table
ALTER TABLE "cloud_zone" DROP CONSTRAINT "cloud_zone_pkey", DROP COLUMN "zone_key", ADD COLUMN "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY, ADD PRIMARY KEY ("id");
