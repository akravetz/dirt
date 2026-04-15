// ESP32-C3 SuperMini plant-node firmware.
//
// Reads a capacitive soil moisture sensor on GPIO4 and POSTs the raw ADC
// value to the dirt ingest endpoint every 30s. Supports WiFi OTA updates
// (password-protected) so the board can be reflashed without disconnecting
// from the pot.
//
// Build-time identity (from platformio.ini):
//   PLANT_ID           "a" | "b" | "c" | "d"
//   FIRMWARE_VERSION   semver string
//
// Secrets (from src/secrets.h, gitignored):
//   WIFI_SSID, WIFI_PASSWORD, SERVER_URL, SENSOR_INGEST_TOKEN, OTA_PASSWORD
//
// mDNS hostname: plant-{PLANT_ID}.local
// OTA port:      3232 (ArduinoOTA default)
//
// Send-only; no response parsing. The server computes the calibrated pct
// from raw via SensorCalibration (auto-tracked extrema per node+metric).

#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoOTA.h>
#include <ESPmDNS.h>
#include <driver/adc.h>

#include "secrets.h"

// --- Config ---------------------------------------------------------------

constexpr int      MOISTURE_PIN      = 3;            // GPIO3 / ADC1_CH3
constexpr adc1_channel_t MOISTURE_ADC_CH = ADC1_CHANNEL_3;
// NOTE: Do NOT use GPIO4 on ESP32-C3. GPIO4-7 are JTAG pins (MTMS/MTDI/MTCK/MTDO)
// and the ADC reads collapse to ~0 when WiFi/BT is active because the JTAG
// peripheral drives the pin. GPIO3 is the nearest safe ADC1 channel.
//
// We read the ADC via the ESP-IDF native driver (adc1_get_raw) instead of
// Arduino's analogRead(). On the ESP32-C3, analogRead() interacts badly with
// WiFi and commonly returns 0 or wildly wrong values. Multiple upstream
// arduino-esp32 issues (#102, #5188, #5502) point at the IDF driver as the
// working path.
constexpr uint32_t POST_INTERVAL_MS  = 30000;        // 30s between POSTs
constexpr uint32_t WIFI_CHECK_MS     = 5000;         // reconnect poll
constexpr uint32_t HTTP_TIMEOUT_MS   = 5000;
constexpr uint16_t ADC_SAMPLES       = 16;           // average N reads

const char* const LOCATION = "plant-" PLANT_ID;      // e.g. "plant-a"
const char* const HOSTNAME = "plant-" PLANT_ID;      // mDNS: plant-a.local

// --- State ----------------------------------------------------------------

uint32_t lastPost       = 0;
uint32_t lastWifiCheck  = 0;

// --- WiFi -----------------------------------------------------------------

void connectWifi() {
    if (WiFi.status() == WL_CONNECTED) return;

    Serial.printf("[wifi] connecting to %s ...\n", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.setHostname(HOSTNAME);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    uint32_t start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < 20000) {
        delay(250);
        Serial.print(".");
    }
    Serial.println();

    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("[wifi] ok ip=%s rssi=%d\n",
                      WiFi.localIP().toString().c_str(), WiFi.RSSI());
    } else {
        Serial.println("[wifi] FAILED — will retry");
    }
}

// --- OTA ------------------------------------------------------------------

void setupOTA() {
    ArduinoOTA.setHostname(HOSTNAME);
    ArduinoOTA.setPassword(OTA_PASSWORD);

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
    Serial.printf("[ota] listening on %s.local:3232\n", HOSTNAME);
}

// --- Sensor ---------------------------------------------------------------

int readMoistureRaw() {
    uint32_t sum = 0;
    for (uint16_t i = 0; i < ADC_SAMPLES; i++) {
        sum += adc1_get_raw(MOISTURE_ADC_CH);
        delay(2);
    }
    return sum / ADC_SAMPLES;
}

// --- POST -----------------------------------------------------------------

void postReading(int raw) {
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("[post] skipped — wifi not connected");
        return;
    }

    HTTPClient http;
    http.setTimeout(HTTP_TIMEOUT_MS);
    http.begin(SERVER_URL);
    http.addHeader("Content-Type", "application/json");
    http.addHeader("Authorization", "Bearer " SENSOR_INGEST_TOKEN);

    // Hand-build JSON — no need for ArduinoJson for this shape.
    String body = String("{\"location\":\"") + LOCATION +
                  "\",\"source\":\"esp32\"" +
                  ",\"firmware_version\":\"" FIRMWARE_VERSION "\"" +
                  ",\"ip\":\"" + WiFi.localIP().toString() + "\"" +
                  ",\"uptime_ms\":" + String(millis()) +
                  ",\"metrics\":{\"soil_moisture_raw\":" + String(raw) + "}}";

    int code = http.POST(body);
    if (code > 0) {
        Serial.printf("[post] raw=%d http=%d\n", raw, code);
    } else {
        Serial.printf("[post] raw=%d ERROR=%s\n",
                      raw, http.errorToString(code).c_str());
    }
    http.end();
}

// --- Lifecycle ------------------------------------------------------------

void setup() {
    Serial.begin(115200);
    delay(2000);  // give USB-CDC host a moment
    Serial.printf("\n# plant-node %s fw=%s\n", LOCATION, FIRMWARE_VERSION);

    // Configure ADC via ESP-IDF driver (see note on MOISTURE_ADC_CH).
    adc1_config_width(ADC_WIDTH_BIT_12);
    adc1_config_channel_atten(MOISTURE_ADC_CH, ADC_ATTEN_DB_11);

    connectWifi();
    setupOTA();
}

void loop() {
    ArduinoOTA.handle();   // must be called frequently

    uint32_t now = millis();

    if (now - lastWifiCheck >= WIFI_CHECK_MS) {
        lastWifiCheck = now;
        if (WiFi.status() != WL_CONNECTED) connectWifi();
    }

    if (now - lastPost >= POST_INTERVAL_MS) {
        lastPost = now;
        postReading(readMoistureRaw());
    }

    delay(10);  // yield to WiFi/OTA stack
}
