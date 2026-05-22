#include "wifi_client.h"

#include <Arduino.h>
#include <WiFi.h>
#include <esp_system.h>

namespace wifi_client {

namespace {
constexpr uint32_t RECONNECT_BASE_MS = 5000;
constexpr uint32_t RECONNECT_MAX_MS = 60000;
constexpr uint32_t WIFI_DRIVER_RESET_AFTER_MS = 5UL * 60UL * 1000UL;
constexpr uint32_t MCU_RESTART_AFTER_MS = 15UL * 60UL * 1000UL;

const char* g_ssid = nullptr;
const char* g_password = nullptr;
const char* g_hostname = nullptr;

bool g_started = false;
bool g_event_registered = false;

uint32_t g_last_connected_ms = 0;
uint32_t g_disconnected_since_ms = 0;
uint32_t g_next_reconnect_ms = 0;
uint32_t g_reconnect_delay_ms = RECONNECT_BASE_MS;
uint32_t g_reconnect_count = 0;
uint32_t g_driver_reset_count = 0;
uint32_t g_last_driver_reset_ms = 0;
uint8_t g_last_disconnect_reason = 0;

bool due(uint32_t now, uint32_t scheduled_ms) {
    return (int32_t)(now - scheduled_ms) >= 0;
}

uint32_t disconnected_for_ms(uint32_t now) {
    if (g_disconnected_since_ms == 0) return 0;
    return now - g_disconnected_since_ms;
}

void configure_station() {
    WiFi.mode(WIFI_STA);
    WiFi.setSleep(false);
    if (g_hostname != nullptr) {
        WiFi.setHostname(g_hostname);
    }
}

void reset_driver(uint32_t now, uint32_t offline_for) {
    g_driver_reset_count++;
    g_last_driver_reset_ms = now;
    Serial.printf("[wifi] driver reset #%lu after %lums offline\n",
                  (unsigned long)g_driver_reset_count,
                  (unsigned long)offline_for);

    WiFi.disconnect(true);
    WiFi.mode(WIFI_OFF);
    delay(100);
    configure_station();
}

void on_wifi_event(WiFiEvent_t event, WiFiEventInfo_t info) {
    uint32_t now = millis();

    if (event == ARDUINO_EVENT_WIFI_STA_GOT_IP) {
        g_last_connected_ms = now;
        g_disconnected_since_ms = 0;
        g_reconnect_delay_ms = RECONNECT_BASE_MS;
        Serial.printf("[wifi] connected ip=%s rssi=%d reconnects=%lu resets=%lu\n",
                      WiFi.localIP().toString().c_str(),
                      WiFi.RSSI(),
                      (unsigned long)g_reconnect_count,
                      (unsigned long)g_driver_reset_count);
        return;
    }

    if (event == ARDUINO_EVENT_WIFI_STA_DISCONNECTED) {
        g_last_disconnect_reason = info.wifi_sta_disconnected.reason;
        if (g_disconnected_since_ms == 0) {
            g_disconnected_since_ms = now;
        }
        g_next_reconnect_ms = now;
        Serial.printf("[wifi] disconnected reason=%u offline_for=%lums\n",
                      g_last_disconnect_reason,
                      (unsigned long)disconnected_for_ms(now));
    }
}
}  // namespace

void begin(const char* ssid, const char* password, const char* hostname) {
    g_ssid = ssid;
    g_password = password;
    g_hostname = hostname;
    g_started = true;

    if (!g_event_registered) {
        WiFi.onEvent(on_wifi_event);
        g_event_registered = true;
    }

    configure_station();

    uint32_t now = millis();
    if (WiFi.status() != WL_CONNECTED) {
        g_disconnected_since_ms = now;
        g_next_reconnect_ms = now + RECONNECT_BASE_MS;
    }

    g_reconnect_delay_ms = RECONNECT_BASE_MS;
    Serial.printf("[wifi] begin ssid=%s hostname=%s sleep=off\n",
                  ssid, hostname);
    WiFi.begin(g_ssid, g_password);
}

void maintain() {
    uint32_t now = millis();
    if (!g_started) return;

    if (WiFi.status() == WL_CONNECTED) {
        if (g_disconnected_since_ms != 0) {
            g_disconnected_since_ms = 0;
            g_reconnect_delay_ms = RECONNECT_BASE_MS;
        }
        return;
    }

    if (g_disconnected_since_ms == 0) {
        g_disconnected_since_ms = now;
        g_next_reconnect_ms = now;
    }

    uint32_t offline_for = disconnected_for_ms(now);
    if (offline_for >= MCU_RESTART_AFTER_MS) {
        Serial.printf("[wifi] offline for %lums; restarting MCU\n",
                      (unsigned long)offline_for);
        Serial.flush();
        ESP.restart();
    }

    if (offline_for >= WIFI_DRIVER_RESET_AFTER_MS
        && (g_last_driver_reset_ms == 0
            || now - g_last_driver_reset_ms >= WIFI_DRIVER_RESET_AFTER_MS)) {
        reset_driver(now, offline_for);
    }

    if (!due(now, g_next_reconnect_ms)) return;

    g_reconnect_count++;
    uint32_t delay_ms = g_reconnect_delay_ms;
    Serial.printf("[wifi] reconnect attempt #%lu reason=%u offline_for=%lums next_backoff=%lums\n",
                  (unsigned long)g_reconnect_count,
                  g_last_disconnect_reason,
                  (unsigned long)offline_for,
                  (unsigned long)delay_ms);

    WiFi.begin(g_ssid, g_password);
    g_next_reconnect_ms = now + delay_ms;
    g_reconnect_delay_ms = min(g_reconnect_delay_ms * 2, RECONNECT_MAX_MS);
}

Snapshot snapshot() {
    uint32_t now = millis();
    bool connected = WiFi.status() == WL_CONNECTED;
    return Snapshot{
        connected,
        connected ? WiFi.RSSI() : 0,
        g_reconnect_count,
        g_driver_reset_count,
        g_last_disconnect_reason,
        connected ? 0 : disconnected_for_ms(now),
    };
}

}  // namespace wifi_client
