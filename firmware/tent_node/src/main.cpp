// ESP32-C3 SuperMini tent environmental sensor.
//
// Reads an Adafruit SHT45 (product 5665, PTFE-capped) over I2C on GPIO4/5
// and POSTs {temperature_c, humidity_pct} to the dirt ingest endpoint
// every 30s. Replaces the host-wired Arduino Nano + BME280.
//
// I2C pins: SDA=GPIO4, SCL=GPIO5
//   Arduino-ESP32 defaults SDA/SCL to GPIO8/9 on the C3, but on the
//   SuperMini GPIO8 is the onboard LED and a boot strapping pin, and
//   GPIO9 is the BOOT button. GPIO4/5 is the documented alternate I2C
//   path. The JTAG-vs-ADC warning on the plant-node doesn't apply here —
//   I2C actively drives the pins, so there's no passive-read collapse.

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_SHT4x.h>

#include "ingest_client.h"
#include "ota.h"
#include "secrets.h"
#include "wifi_client.h"

// --- Config ---------------------------------------------------------------

constexpr uint8_t  I2C_SDA          = 4;
constexpr uint8_t  I2C_SCL          = 5;
constexpr uint32_t POST_INTERVAL_MS = 30000;  // 30s between POSTs
constexpr uint32_t SENSOR_RETRY_MS  = 5000;   // retry begin() on failure

constexpr const char* LOCATION = "tent";
constexpr const char* HOSTNAME = "tent-node";

// --- State ----------------------------------------------------------------

Adafruit_SHT4x sht;
bool shtReady = false;
uint32_t lastPost = 0;
uint32_t lastSensorRetry = 0;

IngestClient ingest(SERVER_URL, SENSOR_INGEST_TOKEN, FIRMWARE_VERSION);

// --- Sensor bring-up ------------------------------------------------------

bool bringUpSensor() {
    if (!sht.begin(&Wire)) {
        Serial.println("[sht45] begin failed — sensor not detected on I2C");
        return false;
    }
    // High precision: ~10 ms per read, ±0.1°C / ±1.0% RH. At a 30s cadence
    // the extra 8 ms over LOW_PRECISION is free.
    sht.setPrecision(SHT4X_HIGH_PRECISION);
    // Heater off by default. SHT45 has an on-die heater for condensation
    // clearing; at ambient humidity (<95% RH) we don't need it. Future
    // work: pulse SHT4X_MED_HEATER_100MS once/hour if RH pins near 100%.
    sht.setHeater(SHT4X_NO_HEATER);
    Serial.printf("[sht45] ok serial=0x%08X\n", (unsigned int)sht.readSerial());
    return true;
}

// --- Lifecycle ------------------------------------------------------------

void setup() {
    Serial.begin(115200);
    delay(2000);  // give USB-CDC host a moment
    Serial.printf("\n# tent-node fw=%s\n", FIRMWARE_VERSION);

    Wire.begin(I2C_SDA, I2C_SCL);
    shtReady = bringUpSensor();

    wifi_client::connect(WIFI_SSID, WIFI_PASSWORD, HOSTNAME);
    ota::begin(HOSTNAME, OTA_PASSWORD);
}

void loop() {
    ota::loop();
    wifi_client::maintain();

    uint32_t now = millis();

    if (!shtReady && now - lastSensorRetry >= SENSOR_RETRY_MS) {
        lastSensorRetry = now;
        shtReady = bringUpSensor();
    }

    if (shtReady && now - lastPost >= POST_INTERVAL_MS) {
        lastPost = now;

        sensors_event_t humidity, temp;
        if (!sht.getEvent(&humidity, &temp)) {
            Serial.println("[sht45] read failed — dropping sensor, will retry");
            shtReady = false;
            return;
        }

        char metrics[96];
        snprintf(metrics, sizeof(metrics),
                 "{\"temperature_c\":%.2f,\"humidity_pct\":%.2f}",
                 temp.temperature, humidity.relative_humidity);

        int code = ingest.post(LOCATION, metrics);
        if (code > 0) Serial.printf("[post] %s http=%d\n", metrics, code);
    }

    delay(10);  // yield to WiFi/OTA stack
}
