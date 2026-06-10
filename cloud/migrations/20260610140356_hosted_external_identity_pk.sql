-- Modify "cloud_asset" table
ALTER TABLE "cloud_asset" DROP CONSTRAINT "cloud_asset_pkey", ADD COLUMN "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY, ADD PRIMARY KEY ("id"), ADD CONSTRAINT "cloud_asset_asset_id_key" UNIQUE ("asset_id");
-- Modify "cloud_audit_event" table
ALTER TABLE "cloud_audit_event" DROP CONSTRAINT "cloud_audit_event_pkey", ADD COLUMN "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY, ADD PRIMARY KEY ("id"), ADD CONSTRAINT "cloud_audit_event_event_id_key" UNIQUE ("event_id");
-- Modify "cloud_command" table
ALTER TABLE "cloud_command" DROP CONSTRAINT "cloud_command_pkey", ADD COLUMN "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY, ADD PRIMARY KEY ("id"), ADD CONSTRAINT "cloud_command_command_id_key" UNIQUE ("command_id");
-- Modify "cloud_site" table
ALTER TABLE "cloud_site" DROP CONSTRAINT "cloud_site_pkey", ADD COLUMN "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY, ADD PRIMARY KEY ("id"), ADD CONSTRAINT "cloud_site_site_id_key" UNIQUE ("site_id");
-- Modify "gateway_credential" table
ALTER TABLE "gateway_credential" DROP CONSTRAINT "gateway_credential_pkey", ADD COLUMN "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY, ADD PRIMARY KEY ("id"), ADD CONSTRAINT "gateway_credential_credential_id_key" UNIQUE ("credential_id");
