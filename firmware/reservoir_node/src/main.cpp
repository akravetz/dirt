// Seeed XIAO ESP32-C3 reservoir canary firmware.
//
// Reads the DFRobot KIT0139 hydrostatic pressure transducer through a
// SEN0262 4-20mA->0-5V converter on an ADS1115 (I2C 0x48), converts raw
// counts to water depth in inches using compiled-in two-point cal +
// density correction, and POSTs both the raw count and the depth to
// the dirt ingest endpoint every 30s. WiFi OTA enabled.
//
// Build-time identity (from platformio.ini): FIRMWARE_VERSION
//
// Secrets (from src/secrets.h, gitignored):
//   WIFI_SSID, WIFI_PASSWORD, SERVER_URL, SENSOR_INGEST_TOKEN, OTA_PASSWORD
//
// mDNS hostname: dirt-reservoir-xiao.local
// OTA port:      3232 (ArduinoOTA default)
//
// Calibration lives in firmware (mirroring the tent SHT45 pattern: device
// ships already-calibrated values; server stores them as-is). Recalibrate
// by editing the constants below and OTA-reflashing. The raw count is also
// POSTed so history can be recomputed against new constants if cal changes.
// Posts as homebox/main/reservoir/reservoir-xiao.
// Full rationale: wiki/hardware/reservoir-level.md "Where the calibration lives".

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_ADS1X15.h>

#include "ingest_client.h"
#include "ota.h"
#include "secrets.h"
#include "wifi_client.h"

// --- Config ---------------------------------------------------------------

constexpr uint8_t  GPIO_I2C_SDA = 4;
constexpr uint8_t  GPIO_I2C_SCL = 5;
constexpr uint8_t  ADS_ADDR     = 0x48;

constexpr uint32_t POST_INTERVAL_MS = 30000;  // 30s; matches plant nodes
constexpr uint16_t SAMPLE_COUNT     = 32;     // ~9 mV jitter at GAIN_FOUR

const char* const SITE_ID = "homebox";
const char* const TENT_ID = "main";
const char* const ZONE_ID = "reservoir";
const char* const DEVICE_ID = "reservoir-xiao";
const char* const HOSTNAME = "dirt-reservoir-xiao";

// --- Calibration ----------------------------------------------------------
//
// Two-point linear cal in final mounted position 2026-05-12 (supersedes
// the 2026-04-26 final-mount cal after the reservoir reading was found
// biased during refill). Re-take per the cal procedure in
// wiki/hardware/reservoir-level.md whenever the probe is remounted or the
// recipe changes substantially. When updating, also update the cal table
// in the wiki — the firmware ships whatever is here, so a desync silently
// drifts the depth values.
//
//   raw_count(22.130 cm head) = 20015  (tape depth 9.5 in)
//   raw_count(66.263 cm head) = 25448  (settled top refill average,
//     tape depth 26.875 in)
//   inferred raw_count(0 cm head) = 17291
//   slope = 122.24 counts/cm with DENSITY_REL applied in rawToDepthIn().
//
// PROBE_OFFSET_CM lets the published value represent water depth from
// the tank floor (what "Reservoir: X in" means to a human) rather than
// water column above the diaphragm. The probe physically can't see the
// bottom 2 cm, so the published depth bottoms out at PROBE_OFFSET_CM /
// CM_PER_INCH ≈ 0.79 in when the diaphragm is in air.
//
// Internal math is cm because the cal procedure measures cm with a tape;
// we convert to inches at the publish boundary because the contract +
// dashboard speak inches.
//
// Density correction: hydroponic nutrient solution runs ~1.005-1.010 g/mL,
// which biases hydrostatic depth high by ~0.7-1.0%. Divide by this constant
// before adding the geometric probe offset. Recalibrate the slope rather
// than tweaking the constant if the recipe changes substantially.

constexpr float CAL_RAW_AT_ZERO_CM = 17291.0f;
constexpr float CAL_COUNTS_PER_CM  = 122.24f;
constexpr float DENSITY_REL        = 1.007f;
constexpr float PROBE_OFFSET_CM    = 2.0f;
constexpr float CM_PER_INCH        = 2.54f;
constexpr float ADS_GAIN_TWOTHIRDS_LSB_V = 0.00018750f;
constexpr float ADS_GAIN_ONE_LSB_V       = 0.00012500f;
constexpr float ADS_GAIN_TWO_LSB_V       = 0.00006250f;
constexpr float ADS_GAIN_FOUR_LSB_V = 0.00003125f;

// --- State ----------------------------------------------------------------

Adafruit_ADS1115 ads;
IngestClient     ingest(SERVER_URL, SENSOR_INGEST_TOKEN, FIRMWARE_VERSION);
uint32_t         lastPost = 0;

// --- Sensor ---------------------------------------------------------------

int16_t readAdsRaw(uint8_t channel) {
    int32_t sum = 0;
    for (uint16_t i = 0; i < SAMPLE_COUNT; i++) {
        sum += ads.readADC_SingleEnded(channel);
    }
    return (int16_t)(sum / SAMPLE_COUNT);
}

int16_t readAdsRawAtGain(uint8_t channel, adsGain_t gain) {
    ads.setGain(gain);
    delay(5);
    return readAdsRaw(channel);
}

int32_t gainTwoRawToCalibrationRaw(int16_t raw) {
    return (int32_t)raw * 2;
}

// Convert raw ADS counts to water depth (from the tank floor) in inches:
// two-point cal → density correction → add probe offset → cm→in.
float rawToDepthIn(int32_t raw) {
    float column_cm = (raw - CAL_RAW_AT_ZERO_CM) / CAL_COUNTS_PER_CM / DENSITY_REL;
    float tank_cm  = column_cm + PROBE_OFFSET_CM;
    return tank_cm / CM_PER_INCH;
}

// --- Lifecycle ------------------------------------------------------------

void setup() {
    Serial.begin(115200);
    delay(2000);  // give USB-CDC host a moment
    Serial.printf("\n# reservoir-xiao fw=%s\n", FIRMWARE_VERSION);

    Wire.begin(GPIO_I2C_SDA, GPIO_I2C_SCL);
    if (!ads.begin(ADS_ADDR, &Wire)) {
        Serial.printf("# ERROR: ADS1115 not responding at 0x%02X — halting\n",
                      ADS_ADDR);
        while (true) delay(1000);
    }
    ads.setGain(GAIN_TWO);  // +/- 2.048V FS, 62.5 uV/count
    Serial.printf("# ADS1115 addr=0x%02X gain=%d lsb_v=%.8f\n",
                  ADS_ADDR, (int)ads.getGain(), ADS_GAIN_TWO_LSB_V);

    wifi_client::begin(WIFI_SSID, WIFI_PASSWORD, HOSTNAME);
    ota::begin(HOSTNAME, OTA_PASSWORD);
}

void loop() {
    ota::loop();
    wifi_client::maintain();

    uint32_t now = millis();
    if (now - lastPost >= POST_INTERVAL_MS) {
        lastPost = now;
        int16_t raw0_gain_two = readAdsRawAtGain(0, GAIN_TWO);
        int32_t raw0          = gainTwoRawToCalibrationRaw(raw0_gain_two);
        int16_t raw1          = readAdsRaw(1);
        int16_t raw2          = readAdsRaw(2);
        int16_t raw3          = readAdsRaw(3);
        int16_t a0_gain_twothirds = readAdsRawAtGain(0, GAIN_TWOTHIRDS);
        int16_t a0_gain_one       = readAdsRawAtGain(0, GAIN_ONE);
        int16_t a0_gain_two       = readAdsRawAtGain(0, GAIN_TWO);
        int16_t a0_gain_four      = readAdsRawAtGain(0, GAIN_FOUR);
        float   depth_in = rawToDepthIn(raw0);
        char    metrics[768];
        snprintf(metrics, sizeof(metrics),
                 "{"
                 "\"reservoir_pressure_raw\":%ld,"
                 "\"reservoir_in\":%.2f,"
                 "\"reservoir_diag_ads_gain\":%d,"
                 "\"reservoir_diag_a0_raw\":%ld,"
                 "\"reservoir_diag_a1_raw\":%d,"
                 "\"reservoir_diag_a2_raw\":%d,"
                 "\"reservoir_diag_a3_raw\":%d,"
                 "\"reservoir_diag_a0_v\":%.3f,"
                 "\"reservoir_diag_a1_v\":%.3f,"
                 "\"reservoir_diag_a2_v\":%.3f,"
                 "\"reservoir_diag_a3_v\":%.3f,"
                 "\"reservoir_diag_a0_gain_two_canonical_raw\":%ld,"
                 "\"reservoir_diag_a0_gain_twothirds_raw\":%d,"
                 "\"reservoir_diag_a0_gain_one_raw\":%d,"
                 "\"reservoir_diag_a0_gain_two_raw\":%d,"
                 "\"reservoir_diag_a0_gain_four_raw\":%d,"
                 "\"reservoir_diag_a0_gain_twothirds_v\":%.3f,"
                 "\"reservoir_diag_a0_gain_one_v\":%.3f,"
                 "\"reservoir_diag_a0_gain_two_v\":%.3f,"
                 "\"reservoir_diag_a0_gain_four_v\":%.3f"
                 "}",
                 (long)raw0,
                 depth_in,
                 (int)GAIN_TWO,
                 (long)raw0,
                 raw1,
                 raw2,
                 raw3,
                 raw0 * ADS_GAIN_FOUR_LSB_V,
                 raw1 * ADS_GAIN_TWO_LSB_V,
                 raw2 * ADS_GAIN_TWO_LSB_V,
                 raw3 * ADS_GAIN_TWO_LSB_V,
                 (long)gainTwoRawToCalibrationRaw(a0_gain_two),
                 a0_gain_twothirds,
                 a0_gain_one,
                 a0_gain_two,
                 a0_gain_four,
                 a0_gain_twothirds * ADS_GAIN_TWOTHIRDS_LSB_V,
                 a0_gain_one * ADS_GAIN_ONE_LSB_V,
                 a0_gain_two * ADS_GAIN_TWO_LSB_V,
                 a0_gain_four * ADS_GAIN_FOUR_LSB_V);
        int code = ingest.post(SITE_ID, TENT_ID, ZONE_ID, DEVICE_ID, metrics);
        if (code > 0) {
            Serial.printf("[post] a0_cal=%ld a0_gain_two=%d gain_v=[%.3f %.3f %.3f %.3f] depth_in=%.2f http=%d\n",
                          (long)raw0,
                          raw0_gain_two,
                          a0_gain_twothirds * ADS_GAIN_TWOTHIRDS_LSB_V,
                          a0_gain_one * ADS_GAIN_ONE_LSB_V,
                          a0_gain_two * ADS_GAIN_TWO_LSB_V,
                          a0_gain_four * ADS_GAIN_FOUR_LSB_V,
                          depth_in,
                          code);
        }
    }

    delay(10);  // yield to WiFi/OTA stack
}
