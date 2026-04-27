// ESP32-C3 SuperMini reservoir-node firmware.
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
// mDNS hostname: dirt-reservoir.local
// OTA port:      3232 (ArduinoOTA default)
//
// Calibration lives in firmware (mirroring the tent SHT45 pattern: device
// ships already-calibrated values; server stores them as-is). Recalibrate
// by editing the constants below and OTA-reflashing. The raw count is also
// POSTed so history can be recomputed against new constants if cal changes.
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

const char* const LOCATION = "reservoir";
const char* const HOSTNAME = "dirt-reservoir";

// --- Calibration ----------------------------------------------------------
//
// Two-point linear cal in final mounted position 2026-04-26 (supersedes
// the bench-bring-up cal of the same date). Re-take per the cal
// procedure in wiki/hardware/reservoir-level.md whenever the probe is
// remounted or the recipe changes substantially. When updating, also
// update the cal table in the wiki — the firmware ships whatever is
// here, so a desync silently drifts the depth values.
//
//   raw_count(0 cm head)    = 18540  (4 mA loop floor, probe in air)
//   raw_count(63.532 cm head) = 25471 (mean of 15 settled readings,
//     probe suspended 2 cm above tank floor, water at 25.8 in / 65.532 cm)
//   slope = (25471 - 18540) / 63.532 = 109.10 counts/cm
//   (assumes cal fluid ≈ water; for nutrient at 1.007, slope = 108.34)
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

constexpr float CAL_RAW_AT_ZERO_CM = 18540.0f;
constexpr float CAL_COUNTS_PER_CM  = 109.10f;
constexpr float DENSITY_REL        = 1.007f;
constexpr float PROBE_OFFSET_CM    = 2.0f;
constexpr float CM_PER_INCH        = 2.54f;

// --- State ----------------------------------------------------------------

Adafruit_ADS1115 ads;
IngestClient     ingest(SERVER_URL, SENSOR_INGEST_TOKEN, FIRMWARE_VERSION);
uint32_t         lastPost = 0;

// --- Sensor ---------------------------------------------------------------

// Read and average SAMPLE_COUNT consecutive ADS1115 samples on A0.
// Per-sample read takes ~7.5 ms at the ADS1115's 128 SPS default, so 32
// samples is ~240 ms — well under our 30 s post interval.
int16_t readPressureRaw() {
    int32_t sum = 0;
    for (uint16_t i = 0; i < SAMPLE_COUNT; i++) {
        sum += ads.readADC_SingleEnded(0);
    }
    return (int16_t)(sum / SAMPLE_COUNT);
}

// Convert raw ADS counts to water depth (from the tank floor) in inches:
// two-point cal → density correction → add probe offset → cm→in.
float rawToDepthIn(int16_t raw) {
    float column_cm = (raw - CAL_RAW_AT_ZERO_CM) / CAL_COUNTS_PER_CM / DENSITY_REL;
    float tank_cm  = column_cm + PROBE_OFFSET_CM;
    return tank_cm / CM_PER_INCH;
}

// --- Lifecycle ------------------------------------------------------------

void setup() {
    Serial.begin(115200);
    delay(2000);  // give USB-CDC host a moment
    Serial.printf("\n# reservoir-node fw=%s\n", FIRMWARE_VERSION);

    Wire.begin(GPIO_I2C_SDA, GPIO_I2C_SCL);
    if (!ads.begin(ADS_ADDR, &Wire)) {
        Serial.printf("# ERROR: ADS1115 not responding at 0x%02X — halting\n",
                      ADS_ADDR);
        while (true) delay(1000);
    }
    ads.setGain(GAIN_FOUR);  // +/- 1.024V FS, 31.25 uV/count

    wifi_client::connect(WIFI_SSID, WIFI_PASSWORD, HOSTNAME);
    ota::begin(HOSTNAME, OTA_PASSWORD);
}

void loop() {
    ota::loop();
    wifi_client::maintain();

    uint32_t now = millis();
    if (now - lastPost >= POST_INTERVAL_MS) {
        lastPost = now;
        int16_t raw      = readPressureRaw();
        float   depth_in = rawToDepthIn(raw);
        char    metrics[80];
        snprintf(metrics, sizeof(metrics),
                 "{\"reservoir_pressure_raw\":%d,\"reservoir_in\":%.2f}",
                 raw, depth_in);
        int code = ingest.post(LOCATION, metrics);
        if (code > 0) {
            Serial.printf("[post] raw=%d depth_in=%.2f http=%d\n",
                          raw, depth_in, code);
        }
    }

    delay(10);  // yield to WiFi/OTA stack
}
