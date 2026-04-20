#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_BME280.h>

#include "config.h"

Adafruit_BME280 bme;
bool bmeReady = false;
unsigned long lastReadTime = 0;

// Raw register reads used once at boot for diagnostic telemetry. We emit the
// factory calibration coefficients + control registers so the host can diff
// them across boots: if a post-reset sensor drifts but these bytes are
// identical across boots, the issue is downstream of the library's static
// state; if they differ, the coefficient read at begin() is unreliable.
// See `apps/hwd/src/dirt_hwd/services/serial_reader.py` boot-event handling.

static uint8_t readReg8(uint8_t addr, uint8_t reg) {
    Wire.beginTransmission(addr);
    Wire.write(reg);
    Wire.endTransmission();
    Wire.requestFrom((int)addr, 1);
    return Wire.available() ? Wire.read() : 0xFF;
}

static void readRegBlock(uint8_t addr, uint8_t reg, uint8_t *buf, uint8_t len) {
    Wire.beginTransmission(addr);
    Wire.write(reg);
    Wire.endTransmission();
    Wire.requestFrom((int)addr, (int)len);
    for (uint8_t i = 0; i < len && Wire.available(); i++) {
        buf[i] = Wire.read();
    }
}

static void printHexByte(uint8_t b) {
    if (b < 0x10) Serial.print('0');
    Serial.print(b, HEX);
}

static void printHexBlock(const uint8_t *buf, uint8_t len) {
    for (uint8_t i = 0; i < len; i++) printHexByte(buf[i]);
}

static void emitBootDiagnostics() {
    uint8_t chipId   = readReg8(BME280_ADDRESS, 0xD0);
    uint8_t calibTP[24];   // 0x88..0x9F — dig_T1..dig_P9
    uint8_t calibH[7];     // 0xE1..0xE7 — dig_H2..dig_H6 (packed)
    readRegBlock(BME280_ADDRESS, 0x88, calibTP, 24);
    uint8_t digH1    = readReg8(BME280_ADDRESS, 0xA1);
    readRegBlock(BME280_ADDRESS, 0xE1, calibH, 7);
    uint8_t ctrlHum  = readReg8(BME280_ADDRESS, 0xF2);
    uint8_t ctrlMeas = readReg8(BME280_ADDRESS, 0xF4);
    uint8_t config   = readReg8(BME280_ADDRESS, 0xF5);

    Serial.print(F("{\"event\":\"boot\",\"chip_id\":"));
    Serial.print(chipId);
    Serial.print(F(",\"calib_tp\":\""));
    printHexBlock(calibTP, 24);
    Serial.print(F("\",\"dig_H1\":"));
    Serial.print(digH1);
    Serial.print(F(",\"calib_h\":\""));
    printHexBlock(calibH, 7);
    Serial.print(F("\",\"ctrl_hum\":"));
    Serial.print(ctrlHum);
    Serial.print(F(",\"ctrl_meas\":"));
    Serial.print(ctrlMeas);
    Serial.print(F(",\"config\":"));
    Serial.print(config);
    Serial.println(F("}"));
}

void setup() {
    Serial.begin(SERIAL_BAUD);
    delay(1000);
    Wire.begin();
    bmeReady = bme.begin(BME280_ADDRESS);
    if (!bmeReady) {
        Serial.println("{\"error\":\"BME280 not found\"}");
        return;
    }
    emitBootDiagnostics();
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
        emitBootDiagnostics();
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
