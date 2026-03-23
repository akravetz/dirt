#include <Arduino.h>

#include "config.h"
#include "sensor_protocol.h"

#ifdef ENABLE_DHT22
#include <DHT.h>
DHT dht(DHT_PIN, DHT_TYPE);
#endif

#ifdef ENABLE_MHZ19B
#include <MHZ19.h>
#include <SoftwareSerial.h>
SoftwareSerial mhzSerial(MHZ19_RX, MHZ19_TX);
MHZ19 mhz19;
#endif

unsigned long lastReadTime = 0;
unsigned long startTime = 0;

void setup() {
    Serial.begin(SERIAL_BAUD);

#ifdef ENABLE_DHT22
    dht.begin();
#endif

#ifdef ENABLE_MHZ19B
    mhzSerial.begin(9600);
    mhz19.begin(mhzSerial);
    mhz19.autoCalibration(false);
#endif

#ifdef ENABLE_SOIL_MOISTURE
    pinMode(SOIL_MOISTURE_PIN, INPUT);
#endif

#ifdef ENABLE_RESERVOIR
    pinMode(RESERVOIR_LOW_PIN, INPUT_PULLUP);
#endif

    startTime = millis();
}

void loop() {
    unsigned long now = millis();
    if (now - lastReadTime < SENSOR_READ_INTERVAL_MS) return;
    lastReadTime = now;

    SensorData data = {};

#ifdef ENABLE_DHT22
    data.temperature_c = dht.readTemperature();
    data.humidity_pct = dht.readHumidity();
    if (isnan(data.temperature_c) || isnan(data.humidity_pct)) {
        data.temperature_c = 0;
        data.humidity_pct = 0;
    }
#endif

#ifdef ENABLE_MHZ19B
    data.co2_ready = (now - startTime) >= MHZ19_WARMUP_MS;
    if (data.co2_ready) {
        data.co2_ppm = mhz19.getCO2();
    }
#endif

#ifdef ENABLE_SOIL_MOISTURE
    data.soil_moisture_raw = analogRead(SOIL_MOISTURE_PIN);
#endif

#ifdef ENABLE_RESERVOIR
    data.reservoir_has_water = !digitalRead(RESERVOIR_LOW_PIN);
#endif

    char buf[256];
    int len = encode_json(&data, buf, sizeof(buf),
                          SOIL_DRY_VALUE, SOIL_WET_VALUE);
    if (len > 0) {
        Serial.print(buf);
    }
}
