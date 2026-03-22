#ifndef SENSOR_PROTOCOL_H
#define SENSOR_PROTOCOL_H

#include <math.h>
#include <stdbool.h>
#include <stdint.h>

struct SensorData {
    float temperature_c;
    float humidity_pct;
    int co2_ppm;
    int soil_moisture_raw;
    bool reservoir_has_water;  // true = water detected at low sensor
    bool co2_ready;            // false during MH-Z19B warmup
};

// Convert Celsius to Fahrenheit
float celsius_to_fahrenheit(float celsius);

// Calculate Vapor Pressure Deficit in kPa
// SVP = 0.6108 * exp(17.27 * T / (T + 237.3))  (T in Celsius)
// VPD = SVP * (1 - RH/100)
float calculate_vpd(float temp_c, float humidity_pct);

// Convert raw soil moisture ADC value to percentage
// dry_value = ADC reading in dry air (higher)
// wet_value = ADC reading submerged (lower)
float soil_moisture_to_pct(int raw, int dry_value, int wet_value);

// Validate sensor readings are within plausible ranges
bool validate_temperature(float temp_c);
bool validate_humidity(float humidity_pct);
bool validate_co2(int ppm);

// Encode sensor data as a JSON line into buffer
// Returns number of bytes written, or -1 on error
int encode_json(const SensorData* data, char* buf, int buf_size,
                int dry_value, int wet_value);

#endif
