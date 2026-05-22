-- Modify "device" table
ALTER TABLE "device" ADD COLUMN "wifi_rssi_dbm" bigint NULL, ADD COLUMN "wifi_reconnect_count" bigint NULL, ADD COLUMN "wifi_driver_reset_count" bigint NULL, ADD COLUMN "wifi_disconnect_reason" bigint NULL, ADD COLUMN "wifi_disconnected_for_ms" bigint NULL;
