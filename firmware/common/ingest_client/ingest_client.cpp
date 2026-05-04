#include "ingest_client.h"

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

int IngestClient::post(const char* location, const char* metrics_json) {
    return post(location, nullptr, nullptr, nullptr, nullptr, metrics_json);
}

int IngestClient::post(const char* location,
                       const char* site_id,
                       const char* tent_id,
                       const char* zone_id,
                       const char* device_id,
                       const char* metrics_json) {
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
    // Typical payload ~300 bytes with scoped identity; reserve 384 to avoid
    // realloc while keeping RAM use predictable.
    String body;
    body.reserve(384);
    body += "{\"location\":\"";
    body += location;
    body += "\"";
    if (site_id != nullptr) {
        body += ",\"site_id\":\"";
        body += site_id;
        body += "\"";
    }
    if (tent_id != nullptr) {
        body += ",\"tent_id\":\"";
        body += tent_id;
        body += "\"";
    }
    if (zone_id != nullptr) {
        body += ",\"zone_id\":\"";
        body += zone_id;
        body += "\"";
    }
    if (device_id != nullptr) {
        body += ",\"device_id\":\"";
        body += device_id;
        body += "\"";
    }
    body += ",\"source\":\"esp32\",\"firmware_version\":\"";
    body += _firmware_version;
    body += "\",\"ip\":\"";
    body += WiFi.localIP().toString();
    body += "\",\"uptime_ms\":";
    body += String(millis());
    body += ",\"metrics\":";
    body += metrics_json;
    body += "}";

    int code = http.POST(body);
    if (code <= 0) {
        Serial.printf("[ingest] ERROR=%s\n", http.errorToString(code).c_str());
    }
    http.end();
    return code;
}
