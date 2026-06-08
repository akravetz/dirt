#include "ingest_client.h"

#include "wifi_client.h"

#include <HTTPClient.h>
#include <WiFi.h>

namespace {
constexpr uint32_t HTTP_TIMEOUT_MS = 5000;
}

IngestClient::IngestClient(const char* server_url,
                           const char* token,
                           const char* firmware_version)
    : _server_url(server_url),
      _firmware_version(firmware_version),
      _auth_header(String("Bearer ") + token) {}

int IngestClient::post(const char* site_id,
                       const char* tent_id,
                       const char* zone_id,
                       const char* device_id,
                       const char* metrics_json,
                       const char* diagnostics_json) {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[ingest] skipped — wifi not connected");
        return -1;
    }

    HTTPClient http;
    http.setTimeout(HTTP_TIMEOUT_MS);
    http.begin(_server_url);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("Authorization", _auth_header);

    // Hand-build JSON — the shape is stable enough that pulling in
    // ArduinoJson for a handful of fields isn't worth the flash cost.
    // Typical payload ~420 bytes with scoped identity and WiFi telemetry;
    // diagnostics can add ~400 bytes on instrumented nodes.
    wifi_client::Snapshot wifi = wifi_client::snapshot();
    String body;
    body.reserve(diagnostics_json == nullptr ? 512 : 960);
    body += "{\"site_id\":\"";
    body += site_id;
    body += "\",\"tent_id\":\"";
    body += tent_id;
    body += "\"";
    if (zone_id != nullptr) {
        body += ",\"zone_id\":\"";
        body += zone_id;
        body += "\"";
    }
    body += ",\"device_id\":\"";
    body += device_id;
    body += "\",\"source\":\"esp32\",\"firmware_version\":\"";
    body += _firmware_version;
    body += "\",\"ip\":\"";
    body += WiFi.localIP().toString();
    body += "\",\"uptime_ms\":";
    body += String(millis());
    body += ",\"wifi_rssi_dbm\":";
    body += String(wifi.rssi_dbm);
    body += ",\"wifi_reconnect_count\":";
    body += String(wifi.reconnect_count);
    body += ",\"wifi_driver_reset_count\":";
    body += String(wifi.driver_reset_count);
    body += ",\"wifi_disconnect_reason\":";
    body += String(wifi.last_disconnect_reason);
    body += ",\"wifi_disconnected_for_ms\":";
    body += String(wifi.disconnected_for_ms);
    body += ",\"metrics\":";
    body += metrics_json;
    if (diagnostics_json != nullptr) {
        body += ",\"diagnostics\":";
        body += diagnostics_json;
    }
    body += "}";

    int code = http.POST(body);
    if (code <= 0) {
        Serial.printf("[ingest] ERROR=%s\n", http.errorToString(code).c_str());
    }
    http.end();
    return code;
}
