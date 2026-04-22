#include "wifi_client.h"

#include <WiFi.h>

namespace wifi_client {

namespace {
constexpr uint32_t CONNECT_BUDGET_MS = 20000;
constexpr uint32_t MAINTAIN_INTERVAL_MS = 5000;

uint32_t last_maintain_ms = 0;
}  // namespace

bool connect(const char* ssid, const char* password, const char* hostname) {
    if (WiFi.status() == WL_CONNECTED) return true;

    Serial.printf("[wifi] connecting to %s ...\n", ssid);
    WiFi.mode(WIFI_STA);
    WiFi.setHostname(hostname);
    WiFi.begin(ssid, password);

    uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < CONNECT_BUDGET_MS) {
        delay(250);
        Serial.print(".");
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("[wifi] ok ip=%s rssi=%d\n",
                      WiFi.localIP().toString().c_str(), WiFi.RSSI());
        return true;
    }
    Serial.println("[wifi] FAILED — will retry");
    return false;
}

void maintain() {
    uint32_t now = millis();
    if (now - last_maintain_ms < MAINTAIN_INTERVAL_MS) return;
    last_maintain_ms = now;
    if (WiFi.status() == WL_CONNECTED) return;

    Serial.println("[wifi] disconnected — reconnecting");
    WiFi.reconnect();
    // Don't block here. If reconnect fails the next tick will retry.
    // Callers that need a confirmed connection should call connect() directly.
}

}  // namespace wifi_client
