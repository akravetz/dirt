// ESP32-C3 SuperMini plant-node firmware.
//
// Reads a capacitive soil moisture sensor on GPIO3 and POSTs the raw ADC
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
#include <driver/adc.h>

#include "ingest_client.h"
#include "ota.h"
#include "secrets.h"
#include "wifi_client.h"

// --- Config ---------------------------------------------------------------

constexpr int            MOISTURE_PIN    = 3;  // GPIO3 / ADC1_CH3
constexpr adc1_channel_t MOISTURE_ADC_CH = ADC1_CHANNEL_3;
// NOTE: Do NOT use GPIO4 on ESP32-C3 for ADC. GPIO4-7 are JTAG pins
// (MTMS/MTDI/MTCK/MTDO) and the ADC reads collapse to ~0 when WiFi/BT is
// active because the JTAG peripheral drives the pin. GPIO3 is the nearest
// safe ADC1 channel. (Digital I/O on 4-7 is fine — I2C on the tent node
// uses GPIO4/5 without issue.)
//
// We read the ADC via the ESP-IDF native driver (adc1_get_raw) instead of
// Arduino's analogRead(). On the ESP32-C3, analogRead() interacts badly with
// WiFi and commonly returns 0 or wildly wrong values. Multiple upstream
// arduino-esp32 issues (#102, #5188, #5502) point at the IDF driver as the
// working path.
constexpr uint32_t POST_INTERVAL_MS = 30000;   // 30s between POSTs
constexpr uint32_t HTTP_TIMEOUT_MS  = 5000;
constexpr uint16_t ADC_SAMPLES      = 16;      // average N reads

const char* const LOCATION = "plant-" PLANT_ID;  // e.g. "plant-a"
const char* const HOSTNAME = "plant-" PLANT_ID;  // mDNS: plant-a.local

// --- State ----------------------------------------------------------------

uint32_t lastPost = 0;

IngestClient ingest(SERVER_URL, SENSOR_INGEST_TOKEN, FIRMWARE_VERSION);

// --- Sensor ---------------------------------------------------------------

int readMoistureRaw() {
    uint32_t sum = 0;
    for (uint16_t i = 0; i < ADC_SAMPLES; i++) {
        sum += adc1_get_raw(MOISTURE_ADC_CH);
        delay(2);
    }
    return sum / ADC_SAMPLES;
}

// --- Lifecycle ------------------------------------------------------------

void setup() {
    Serial.begin(115200);
    delay(2000);  // give USB-CDC host a moment
    Serial.printf("\n# plant-node %s fw=%s\n", LOCATION, FIRMWARE_VERSION);

    // Configure ADC via ESP-IDF driver (see note on MOISTURE_ADC_CH).
    adc1_config_width(ADC_WIDTH_BIT_12);
    adc1_config_channel_atten(MOISTURE_ADC_CH, ADC_ATTEN_DB_11);

    wifi_client::connect(WIFI_SSID, WIFI_PASSWORD, HOSTNAME);
    ota::begin(HOSTNAME, OTA_PASSWORD);
}

void loop() {
    ota::loop();
    wifi_client::maintain();

    uint32_t now = millis();
    if (now - lastPost >= POST_INTERVAL_MS) {
        lastPost = now;
        int raw = readMoistureRaw();
        char metrics[48];
        snprintf(metrics, sizeof(metrics),
                 "{\"soil_moisture_raw\":%d}", raw);
        int code = ingest.post(LOCATION, metrics);
        if (code > 0) Serial.printf("[post] raw=%d http=%d\n", raw, code);
    }

    delay(10);  // yield to WiFi/OTA stack
}
