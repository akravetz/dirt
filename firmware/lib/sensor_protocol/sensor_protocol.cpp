#include "sensor_protocol.h"

#include <ArduinoJson.h>
#include <math.h>
#include <stdio.h>

float celsius_to_fahrenheit(float celsius) {
    return celsius * 9.0f / 5.0f + 32.0f;
}

float calculate_vpd(float temp_c, float humidity_pct) {
    if (humidity_pct < 0 || humidity_pct > 100) return -1.0f;
    float svp = 0.6108f * expf(17.27f * temp_c / (temp_c + 237.3f));
    return svp * (1.0f - humidity_pct / 100.0f);
}

float soil_moisture_to_pct(int raw, int dry_value, int wet_value) {
    if (dry_value == wet_value) return 0.0f;
    float pct = (float)(dry_value - raw) / (float)(dry_value - wet_value) * 100.0f;
    if (pct < 0.0f) pct = 0.0f;
    if (pct > 100.0f) pct = 100.0f;
    return pct;
}

const char* reservoir_level_str(bool low, bool half, bool full) {
    if (full) return "full";
    if (half) return "half";
    if (low) return "low";
    return "empty";
}

bool validate_temperature(float temp_c) {
    return temp_c >= -40.0f && temp_c <= 80.0f;
}

bool validate_humidity(float humidity_pct) {
    return humidity_pct >= 0.0f && humidity_pct <= 100.0f;
}

bool validate_co2(int ppm) {
    return ppm >= 0 && ppm <= 5000;
}

static float round1(float v) { return roundf(v * 10.0f) / 10.0f; }
static float round2(float v) { return roundf(v * 100.0f) / 100.0f; }

int encode_json(const SensorData* data, char* buf, int buf_size,
                int dry_value, int wet_value) {
    JsonDocument doc;

    float temp_f = celsius_to_fahrenheit(data->temperature_c);
    doc["temperature_f"] = round1(temp_f);
    doc["humidity_pct"] = round1(data->humidity_pct);

    if (data->co2_ready) {
        doc["co2_ppm"] = data->co2_ppm;
    }

    float soil_pct = soil_moisture_to_pct(
        data->soil_moisture_raw, dry_value, wet_value);
    doc["soil_moisture_pct"] = round1(soil_pct);

    doc["reservoir_level"] = reservoir_level_str(
        data->reservoir_low, data->reservoir_half, data->reservoir_full);

    float vpd = calculate_vpd(data->temperature_c, data->humidity_pct);
    if (vpd >= 0) {
        doc["vpd"] = round2(vpd);
    }

    int len = serializeJson(doc, buf, buf_size);
    if (len <= 0 || len >= buf_size - 1) return -1;

    buf[len] = '\n';
    buf[len + 1] = '\0';
    return len + 1;
}
