#ifndef DIRT_CONFIG_H
#define DIRT_CONFIG_H

// --- Sensor Feature Flags ---
// Comment out a line to disable that sensor.
#define ENABLE_DHT22
// #define ENABLE_MHZ19B
// #define ENABLE_SOIL_MOISTURE
// #define ENABLE_RESERVOIR

// --- Pin Definitions ---
#define DHT_PIN 6
#define DHT_TYPE DHT22

#define MHZ19_RX 2
#define MHZ19_TX 3

#define SOIL_MOISTURE_PIN A0

#define RESERVOIR_LOW_PIN 7

// --- Timing ---
#define SENSOR_READ_INTERVAL_MS 10000  // 10 seconds
#define MHZ19_WARMUP_MS 180000         // 3 minutes

// --- Soil Moisture Calibration ---
// Calibrate these with your sensor:
// DRY_VALUE = reading in dry air
// WET_VALUE = reading submerged in water
#define SOIL_DRY_VALUE 800
#define SOIL_WET_VALUE 400

// --- Serial ---
#define SERIAL_BAUD 9600

#endif
