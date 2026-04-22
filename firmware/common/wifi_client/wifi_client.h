// Shared WiFi helpers for dirt ESP32-C3 nodes.
//
// Two entry points:
//   connect()  — blocking initial connect with a 20s budget; call from setup()
//   maintain() — cheap per-loop poll; reconnects if the station dropped,
//                rate-limited internally so it's safe to call every iteration

#pragma once

#include <Arduino.h>

namespace wifi_client {

// Blocking initial connect. Sets STA mode + hostname, begins association, and
// waits up to 20s for WL_CONNECTED. Returns true iff connected on return.
// Safe to call again later — treated as a retry.
bool connect(const char* ssid, const char* password, const char* hostname);

// Rate-limited reconnect check. Call every loop; at most one reconnect
// attempt per WIFI_CHECK_MS. No-op if already connected. Uses cached
// creds from the prior connect() call — WiFi.reconnect() restarts
// association with the same SSID/password the driver already has.
void maintain();

}  // namespace wifi_client
