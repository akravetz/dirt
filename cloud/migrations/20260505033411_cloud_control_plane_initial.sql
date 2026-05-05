-- Create "cloud_asset" table
CREATE TABLE "cloud_asset" (
  "asset_id" character varying(160) NOT NULL,
  "site_id" character varying(80) NOT NULL,
  "tent_id" character varying(80) NOT NULL,
  "zone_id" character varying(80) NULL,
  "device_id" character varying(120) NULL,
  "kind" character varying(40) NOT NULL,
  "object_key" character varying(500) NOT NULL,
  "content_type" character varying(120) NOT NULL,
  "byte_size" integer NOT NULL,
  "sha256" character varying(64) NULL,
  "captured_at" timestamptz NOT NULL,
  "uploaded_at" timestamptz NOT NULL,
  "signed_url_expires_at" timestamptz NULL,
  PRIMARY KEY ("asset_id"),
  CONSTRAINT "cloud_asset_site_id_tent_id_object_key_key" UNIQUE ("site_id", "tent_id", "object_key")
);
-- Create index "ix_cloud_asset_device_id" to table: "cloud_asset"
CREATE INDEX "ix_cloud_asset_device_id" ON "cloud_asset" ("device_id");
-- Create index "ix_cloud_asset_object_key" to table: "cloud_asset"
CREATE INDEX "ix_cloud_asset_object_key" ON "cloud_asset" ("object_key");
-- Create index "ix_cloud_asset_site_id" to table: "cloud_asset"
CREATE INDEX "ix_cloud_asset_site_id" ON "cloud_asset" ("site_id");
-- Create index "ix_cloud_asset_tent_id" to table: "cloud_asset"
CREATE INDEX "ix_cloud_asset_tent_id" ON "cloud_asset" ("tent_id");
-- Create index "ix_cloud_asset_zone_id" to table: "cloud_asset"
CREATE INDEX "ix_cloud_asset_zone_id" ON "cloud_asset" ("zone_id");
-- Create "cloud_audit_event" table
CREATE TABLE "cloud_audit_event" (
  "event_id" character varying(80) NOT NULL,
  "site_id" character varying(80) NULL,
  "actor_type" character varying(40) NOT NULL,
  "actor_id" character varying(160) NULL,
  "event_type" character varying(120) NOT NULL,
  "subject_type" character varying(80) NULL,
  "subject_id" character varying(160) NULL,
  "metadata" json NOT NULL,
  "created_at" timestamptz NOT NULL,
  PRIMARY KEY ("event_id")
);
-- Create index "ix_cloud_audit_event_event_type" to table: "cloud_audit_event"
CREATE INDEX "ix_cloud_audit_event_event_type" ON "cloud_audit_event" ("event_type");
-- Create index "ix_cloud_audit_event_site_id" to table: "cloud_audit_event"
CREATE INDEX "ix_cloud_audit_event_site_id" ON "cloud_audit_event" ("site_id");
-- Create "cloud_capability" table
CREATE TABLE "cloud_capability" (
  "capability_key" character varying(320) NOT NULL,
  "site_id" character varying(80) NOT NULL,
  "tent_id" character varying(80) NOT NULL,
  "device_id" character varying(120) NOT NULL,
  "capability_id" character varying(160) NOT NULL,
  "metric_name" character varying(120) NULL,
  "kind" character varying(80) NOT NULL,
  "unit" character varying(40) NULL,
  "is_enabled" boolean NOT NULL,
  "synced_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("capability_key"),
  CONSTRAINT "cloud_capability_site_id_tent_id_capability_id_key" UNIQUE ("site_id", "tent_id", "capability_id")
);
-- Create index "ix_cloud_capability_capability_id" to table: "cloud_capability"
CREATE INDEX "ix_cloud_capability_capability_id" ON "cloud_capability" ("capability_id");
-- Create index "ix_cloud_capability_device_id" to table: "cloud_capability"
CREATE INDEX "ix_cloud_capability_device_id" ON "cloud_capability" ("device_id");
-- Create index "ix_cloud_capability_site_id" to table: "cloud_capability"
CREATE INDEX "ix_cloud_capability_site_id" ON "cloud_capability" ("site_id");
-- Create index "ix_cloud_capability_tent_id" to table: "cloud_capability"
CREATE INDEX "ix_cloud_capability_tent_id" ON "cloud_capability" ("tent_id");
-- Create "cloud_command" table
CREATE TABLE "cloud_command" (
  "command_id" character varying(80) NOT NULL,
  "idempotency_key" character varying(160) NOT NULL,
  "site_id" character varying(80) NOT NULL,
  "tent_id" character varying(80) NOT NULL,
  "device_id" character varying(120) NULL,
  "capability_id" character varying(160) NULL,
  "command_type" character varying(80) NOT NULL,
  "payload" json NOT NULL,
  "requested_by" character varying(160) NOT NULL,
  "status" character varying(40) NOT NULL,
  "queued_at" timestamptz NOT NULL,
  "expires_at" timestamptz NOT NULL,
  "claimed_by" character varying(120) NULL,
  "claimed_at" timestamptz NULL,
  "started_at" timestamptz NULL,
  "finished_at" timestamptz NULL,
  "result" json NULL,
  "error" character varying(500) NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("command_id"),
  CONSTRAINT "cloud_command_requested_by_idempotency_key_key" UNIQUE ("requested_by", "idempotency_key")
);
-- Create index "ix_cloud_command_claimable" to table: "cloud_command"
CREATE INDEX "ix_cloud_command_claimable" ON "cloud_command" ("site_id", "status", "expires_at");
-- Create index "ix_cloud_command_command_type" to table: "cloud_command"
CREATE INDEX "ix_cloud_command_command_type" ON "cloud_command" ("command_type");
-- Create index "ix_cloud_command_idempotency_key" to table: "cloud_command"
CREATE INDEX "ix_cloud_command_idempotency_key" ON "cloud_command" ("idempotency_key");
-- Create index "ix_cloud_command_requested_by" to table: "cloud_command"
CREATE INDEX "ix_cloud_command_requested_by" ON "cloud_command" ("requested_by");
-- Create index "ix_cloud_command_site_id" to table: "cloud_command"
CREATE INDEX "ix_cloud_command_site_id" ON "cloud_command" ("site_id");
-- Create index "ix_cloud_command_status" to table: "cloud_command"
CREATE INDEX "ix_cloud_command_status" ON "cloud_command" ("status");
-- Create index "ix_cloud_command_tent_id" to table: "cloud_command"
CREATE INDEX "ix_cloud_command_tent_id" ON "cloud_command" ("tent_id");
-- Create "cloud_device" table
CREATE TABLE "cloud_device" (
  "device_key" character varying(260) NOT NULL,
  "site_id" character varying(80) NOT NULL,
  "tent_id" character varying(80) NOT NULL,
  "zone_id" character varying(80) NULL,
  "device_id" character varying(120) NOT NULL,
  "name" character varying(160) NOT NULL,
  "kind" character varying(80) NOT NULL,
  "controller" character varying(80) NULL,
  "is_active" boolean NOT NULL,
  "last_seen_at" timestamptz NULL,
  "synced_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("device_key"),
  CONSTRAINT "cloud_device_site_id_tent_id_device_id_key" UNIQUE ("site_id", "tent_id", "device_id")
);
-- Create index "ix_cloud_device_device_id" to table: "cloud_device"
CREATE INDEX "ix_cloud_device_device_id" ON "cloud_device" ("device_id");
-- Create index "ix_cloud_device_site_id" to table: "cloud_device"
CREATE INDEX "ix_cloud_device_site_id" ON "cloud_device" ("site_id");
-- Create index "ix_cloud_device_tent_id" to table: "cloud_device"
CREATE INDEX "ix_cloud_device_tent_id" ON "cloud_device" ("tent_id");
-- Create index "ix_cloud_device_zone_id" to table: "cloud_device"
CREATE INDEX "ix_cloud_device_zone_id" ON "cloud_device" ("zone_id");
-- Create "cloud_latest_metric" table
CREATE TABLE "cloud_latest_metric" (
  "metric_key" character varying(360) NOT NULL,
  "site_id" character varying(80) NOT NULL,
  "tent_id" character varying(80) NOT NULL,
  "zone_id" character varying(80) NULL,
  "device_id" character varying(120) NULL,
  "capability_id" character varying(160) NOT NULL,
  "metric" character varying(120) NOT NULL,
  "value" double precision NOT NULL,
  "unit" character varying(40) NULL,
  "source_updated_at" timestamptz NOT NULL,
  "received_at" timestamptz NOT NULL,
  "stale_after_s" integer NOT NULL,
  PRIMARY KEY ("metric_key"),
  CONSTRAINT "cloud_latest_metric_site_id_tent_id_capability_id_metric_key" UNIQUE ("site_id", "tent_id", "capability_id", "metric")
);
-- Create index "ix_cloud_latest_metric_capability_id" to table: "cloud_latest_metric"
CREATE INDEX "ix_cloud_latest_metric_capability_id" ON "cloud_latest_metric" ("capability_id");
-- Create index "ix_cloud_latest_metric_device_id" to table: "cloud_latest_metric"
CREATE INDEX "ix_cloud_latest_metric_device_id" ON "cloud_latest_metric" ("device_id");
-- Create index "ix_cloud_latest_metric_metric" to table: "cloud_latest_metric"
CREATE INDEX "ix_cloud_latest_metric_metric" ON "cloud_latest_metric" ("metric");
-- Create index "ix_cloud_latest_metric_site_id" to table: "cloud_latest_metric"
CREATE INDEX "ix_cloud_latest_metric_site_id" ON "cloud_latest_metric" ("site_id");
-- Create index "ix_cloud_latest_metric_tent_id" to table: "cloud_latest_metric"
CREATE INDEX "ix_cloud_latest_metric_tent_id" ON "cloud_latest_metric" ("tent_id");
-- Create index "ix_cloud_latest_metric_zone_id" to table: "cloud_latest_metric"
CREATE INDEX "ix_cloud_latest_metric_zone_id" ON "cloud_latest_metric" ("zone_id");
-- Create "cloud_metric_rollup" table
CREATE TABLE "cloud_metric_rollup" (
  "rollup_key" character varying(480) NOT NULL,
  "site_id" character varying(80) NOT NULL,
  "tent_id" character varying(80) NOT NULL,
  "capability_id" character varying(160) NOT NULL,
  "metric" character varying(120) NOT NULL,
  "bucket" character varying(40) NOT NULL,
  "bucket_start_at" timestamptz NOT NULL,
  "bucket_end_at" timestamptz NOT NULL,
  "min_value" double precision NULL,
  "avg_value" double precision NULL,
  "max_value" double precision NULL,
  "sample_count" integer NOT NULL,
  "unit" character varying(40) NULL,
  "received_at" timestamptz NOT NULL,
  PRIMARY KEY ("rollup_key"),
  CONSTRAINT "cloud_metric_rollup_site_id_tent_id_capability_id_metric_bu_key" UNIQUE ("site_id", "tent_id", "capability_id", "metric", "bucket", "bucket_start_at")
);
-- Create index "ix_cloud_metric_rollup_bucket" to table: "cloud_metric_rollup"
CREATE INDEX "ix_cloud_metric_rollup_bucket" ON "cloud_metric_rollup" ("bucket");
-- Create index "ix_cloud_metric_rollup_capability_id" to table: "cloud_metric_rollup"
CREATE INDEX "ix_cloud_metric_rollup_capability_id" ON "cloud_metric_rollup" ("capability_id");
-- Create index "ix_cloud_metric_rollup_metric" to table: "cloud_metric_rollup"
CREATE INDEX "ix_cloud_metric_rollup_metric" ON "cloud_metric_rollup" ("metric");
-- Create index "ix_cloud_metric_rollup_site_id" to table: "cloud_metric_rollup"
CREATE INDEX "ix_cloud_metric_rollup_site_id" ON "cloud_metric_rollup" ("site_id");
-- Create index "ix_cloud_metric_rollup_tent_id" to table: "cloud_metric_rollup"
CREATE INDEX "ix_cloud_metric_rollup_tent_id" ON "cloud_metric_rollup" ("tent_id");
-- Create "cloud_site" table
CREATE TABLE "cloud_site" (
  "site_id" character varying(80) NOT NULL,
  "name" character varying(160) NOT NULL,
  "timezone" character varying(80) NOT NULL,
  "is_active" boolean NOT NULL,
  "gateway_last_seen_at" timestamptz NULL,
  "last_catalog_sync_at" timestamptz NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("site_id")
);
-- Create "cloud_tent" table
CREATE TABLE "cloud_tent" (
  "tent_key" character varying(180) NOT NULL,
  "site_id" character varying(80) NOT NULL,
  "tent_id" character varying(80) NOT NULL,
  "name" character varying(160) NOT NULL,
  "is_active" boolean NOT NULL,
  "synced_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("tent_key"),
  CONSTRAINT "cloud_tent_site_id_tent_id_key" UNIQUE ("site_id", "tent_id")
);
-- Create index "ix_cloud_tent_site_id" to table: "cloud_tent"
CREATE INDEX "ix_cloud_tent_site_id" ON "cloud_tent" ("site_id");
-- Create index "ix_cloud_tent_tent_id" to table: "cloud_tent"
CREATE INDEX "ix_cloud_tent_tent_id" ON "cloud_tent" ("tent_id");
-- Create "cloud_zone" table
CREATE TABLE "cloud_zone" (
  "zone_key" character varying(260) NOT NULL,
  "site_id" character varying(80) NOT NULL,
  "tent_id" character varying(80) NOT NULL,
  "zone_id" character varying(80) NOT NULL,
  "name" character varying(160) NOT NULL,
  "kind" character varying(80) NOT NULL,
  "is_active" boolean NOT NULL,
  "synced_at" timestamptz NOT NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("zone_key"),
  CONSTRAINT "cloud_zone_site_id_tent_id_zone_id_key" UNIQUE ("site_id", "tent_id", "zone_id")
);
-- Create index "ix_cloud_zone_site_id" to table: "cloud_zone"
CREATE INDEX "ix_cloud_zone_site_id" ON "cloud_zone" ("site_id");
-- Create index "ix_cloud_zone_tent_id" to table: "cloud_zone"
CREATE INDEX "ix_cloud_zone_tent_id" ON "cloud_zone" ("tent_id");
-- Create index "ix_cloud_zone_zone_id" to table: "cloud_zone"
CREATE INDEX "ix_cloud_zone_zone_id" ON "cloud_zone" ("zone_id");
-- Create "gateway_credential" table
CREATE TABLE "gateway_credential" (
  "credential_id" character varying(120) NOT NULL,
  "gateway_id" character varying(120) NOT NULL,
  "token_sha256" character varying(64) NOT NULL,
  "allowed_site_id" character varying(80) NOT NULL,
  "is_active" boolean NOT NULL,
  "last_used_at" timestamptz NULL,
  "rotated_at" timestamptz NULL,
  "revoked_at" timestamptz NULL,
  "created_at" timestamptz NOT NULL,
  "updated_at" timestamptz NOT NULL,
  PRIMARY KEY ("credential_id")
);
-- Create index "ix_gateway_credential_allowed_site_id" to table: "gateway_credential"
CREATE INDEX "ix_gateway_credential_allowed_site_id" ON "gateway_credential" ("allowed_site_id");
-- Create index "ix_gateway_credential_gateway_id" to table: "gateway_credential"
CREATE INDEX "ix_gateway_credential_gateway_id" ON "gateway_credential" ("gateway_id");
-- Create index "ix_gateway_credential_token_sha256" to table: "gateway_credential"
CREATE INDEX "ix_gateway_credential_token_sha256" ON "gateway_credential" ("token_sha256");
