#include <Arduino.h>
#include <DHT.h>
#include <MHZ19.h>
#include <SoftwareSerial.h>

#include "config.h"
#include "sensor_protocol.h"

DHT dht(DHT_PIN, DHT_TYPE);
SoftwareSerial mhzSerial(MHZ19_RX, MHZ19_TX);
MHZ19 mhz19;

unsigned long lastReadTime = 0;
unsigned long startTime = 0;

void setup() {
    Serial.begin(SERIAL_BAUD);

    dht.begin();

    mhzSerial.begin(9600);
    mhz19.begin(mhzSerial);
    mhz19.autoCalibration(false);

    pinMode(SOIL_MOISTURE_PIN, INPUT);
    pinMode(RESERVOIR_LOW_PIN, INPUT_PULLUP);
    pinMode(RESERVOIR_HALF_PIN, INPUT_PULLUP);
    pinMode(RESERVOIR_FULL_PIN, INPUT_PULLUP);

    startTime = millis();
}

void loop() {
    unsigned long now = millis();
    if (now - lastReadTime < SENSOR_READ_INTERVAL_MS) return;
    lastReadTime = now;

    SensorData data = {};

    // DHT22 — temperature and humidity
    data.temperature_c = dht.readTemperature();
    data.humidity_pct = dht.readHumidity();

    if (isnan(data.temperature_c) || isnan(data.humidity_pct)) {
        data.temperature_c = 0;
        data.humidity_pct = 0;
    }

    // MH-Z19B — CO2 (skip during warmup)
    data.co2_ready = (now - startTime) >= MHZ19_WARMUP_MS;
    if (data.co2_ready) {
        data.co2_ppm = mhz19.getCO2();
    }

    // Soil moisture — analog read
    data.soil_moisture_raw = analogRead(SOIL_MOISTURE_PIN);

    // Reservoir level — non-contact capacitive sensors (active LOW)
    data.reservoir_low = !digitalRead(RESERVOIR_LOW_PIN);
    data.reservoir_half = !digitalRead(RESERVOIR_HALF_PIN);
    data.reservoir_full = !digitalRead(RESERVOIR_FULL_PIN);

    // Encode and send
    char buf[256];
    int len = encode_json(&data, buf, sizeof(buf),
                          SOIL_DRY_VALUE, SOIL_WET_VALUE);
    if (len > 0) {
        Serial.print(buf);
    }
}
