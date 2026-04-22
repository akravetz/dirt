#include "ota.h"

#include <ArduinoOTA.h>

namespace ota {

void begin(const char* hostname, const char* password) {
    ArduinoOTA.setHostname(hostname);
    ArduinoOTA.setPassword(password);

    ArduinoOTA.onStart([]() {
        Serial.println("[ota] update starting");
    });
    ArduinoOTA.onEnd([]() {
        Serial.println("\n[ota] update complete, rebooting");
    });
    ArduinoOTA.onProgress([](unsigned int progress, unsigned int total) {
        Serial.printf("[ota] %u%%\r", (progress * 100) / total);
    });
    ArduinoOTA.onError([](ota_error_t error) {
        const char* msg;
        switch (error) {
            case OTA_AUTH_ERROR:    msg = "auth"; break;
            case OTA_BEGIN_ERROR:   msg = "begin"; break;
            case OTA_CONNECT_ERROR: msg = "connect"; break;
            case OTA_RECEIVE_ERROR: msg = "receive"; break;
            case OTA_END_ERROR:     msg = "end"; break;
            default:                msg = "?"; break;
        }
        Serial.printf("[ota] error: %s\n", msg);
    });

    ArduinoOTA.begin();
    Serial.printf("[ota] listening on %s.local:3232\n", hostname);
}

void loop() {
    ArduinoOTA.handle();
}

}  // namespace ota
