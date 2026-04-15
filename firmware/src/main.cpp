#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_BME280.h>

#include "config.h"

Adafruit_BME280 bme;
bool bmeReady = false;
unsigned long lastReadTime = 0;

void setup() {
    Serial.begin(SERIAL_BAUD);
    delay(1000);
    Wire.begin();
    bmeReady = bme.begin(BME280_ADDRESS);
    if (!bmeReady) {
        Serial.println("{\"error\":\"BME280 not found\"}");
    }
}

void loop() {
    unsigned long now = millis();
    if (now - lastReadTime < SENSOR_READ_INTERVAL_MS) return;
    lastReadTime = now;

    if (!bmeReady) {
        bmeReady = bme.begin(BME280_ADDRESS);
        if (!bmeReady) {
            Serial.println("{\"error\":\"BME280 not found\"}");
            return;
        }
    }

    float temp_c = bme.readTemperature();
    float hum = bme.readHumidity();
    float pres_hpa = bme.readPressure() / 100.0f;  // Pa -> hPa

    if (isnan(temp_c) || isnan(hum) || isnan(pres_hpa)) {
        Serial.println("{\"error\":\"BME280 read failed\"}");
        return;
    }

    Serial.print("{\"temperature_c\":");
    Serial.print(temp_c, 2);
    Serial.print(",\"humidity_pct\":");
    Serial.print(hum, 2);
    Serial.print(",\"pressure_hpa\":");
    Serial.print(pres_hpa, 2);
    Serial.println("}");
}
