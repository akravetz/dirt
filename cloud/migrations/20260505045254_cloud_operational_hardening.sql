-- Modify "cloud_site" table
ALTER TABLE "cloud_site" ADD COLUMN "gateway_backlog_depth" integer NOT NULL DEFAULT 0;
