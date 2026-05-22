// Shared WiFi helper for dirt ESP32-C3 nodes.
//
// begin() configures STA mode, hostname, driver sleep policy, event handlers,
// and starts the first association attempt. maintain() is a cheap per-loop
// state-machine tick that schedules reconnects and escalates stuck offline
// nodes without blocking normal OTA, HTTP, or sensor work.

#pragma once

#include <Arduino.h>

namespace wifi_client {

struct Snapshot {
    bool connected;
    int rssi_dbm;
    uint32_t reconnect_count;
    uint32_t driver_reset_count;
    uint8_t last_disconnect_reason;
    uint32_t disconnected_for_ms;
};

void begin(const char* ssid, const char* password, const char* hostname);
void maintain();
Snapshot snapshot();

}  // namespace wifi_client
