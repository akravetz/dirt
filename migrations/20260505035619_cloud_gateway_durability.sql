-- Create "cloud_outbox" table
CREATE TABLE "cloud_outbox" (
  "id" bigint NOT NULL GENERATED ALWAYS AS IDENTITY,
  "event_type" text NOT NULL,
  "idempotency_key" text NOT NULL,
  "payload" jsonb NOT NULL DEFAULT '{}',
  "status" text NOT NULL DEFAULT 'pending',
  "attempt_count" bigint NOT NULL DEFAULT 0,
  "next_retry_at" timestamptz NOT NULL DEFAULT now(),
  "last_error" text NULL,
  "delivered_at" timestamptz NULL,
  "created_at" timestamptz NOT NULL DEFAULT now(),
  "updated_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("id"),
  CONSTRAINT "uq_cloud_outbox_idempotency_key" UNIQUE ("idempotency_key")
);
-- Create index "ix_cloud_outbox_event_type" to table: "cloud_outbox"
CREATE INDEX "ix_cloud_outbox_event_type" ON "cloud_outbox" ("event_type");
-- Create index "ix_cloud_outbox_status_next_retry" to table: "cloud_outbox"
CREATE INDEX "ix_cloud_outbox_status_next_retry" ON "cloud_outbox" ("status", "next_retry_at");
-- Create "cloud_sync_cursor" table
CREATE TABLE "cloud_sync_cursor" (
  "cursor_key" text NOT NULL,
  "cursor_value" jsonb NOT NULL DEFAULT '{}',
  "updated_at" timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY ("cursor_key")
);
