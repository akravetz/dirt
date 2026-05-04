// Client for the dirt-hwd /api/ingest/sensors endpoint.
//
// Thin wrapper around HTTPClient that assembles the JSON envelope the
// backend expects: legacy location, scoped identity, source, firmware_version,
// ip, uptime_ms, metrics{…}. Callers hand in a pre-serialized metrics object
// so the client stays sensor-agnostic.

#pragma once

#include <Arduino.h>

class IngestClient {
public:
    // server_url          full POST URL, e.g. "http://homebox.local:8000/api/ingest/sensors"
    // token               bearer token (without "Bearer " prefix)
    // firmware_version    semver string, typically FIRMWARE_VERSION build flag
    //
    // source is hardcoded to "esp32" — every current and foreseeable node
    // using this endpoint is an ESP32. Lift it back into the ctor if that
    // ever changes.
    IngestClient(const char* server_url,
                 const char* token,
                 const char* firmware_version);

    // POST one reading with legacy-only identity. Kept for compatibility with
    // older sketches while the host retires location-scoped ingest.
    int post(const char* location, const char* metrics_json);

    // POST one reading with both legacy location and scoped local identity.
    // metrics_json must be a complete JSON object literal like
    // {"temperature_c":20.12,"humidity_pct":55.3}. IP and uptime_ms are
    // pulled from WiFi.localIP() and millis() respectively.
    //
    // Returns the HTTP status code on success (>0), or the negative
    // HTTPClient error code on transport failure. Failures are logged to
    // Serial internally — callers shouldn't double-log.
    int post(const char* location,
             const char* site_id,
             const char* tent_id,
             const char* zone_id,
             const char* device_id,
             const char* metrics_json);

private:
    const char* _server_url;
    const char* _firmware_version;
    String _auth_header;  // "Bearer <token>" — built once at construction
};
