// AC Infinity Cloudline LITE 6" fan driver + tent environmental sensor.
// Drives D+ and B5 via two 2N7000 MOSFETs (GPIO 6/7) and reads an Adafruit
// SHT45 (0x44) over I²C on GPIO 4/5.
//
// Network roles:
//   - Posts {temperature_c, humidity_pct, fan_duty_pct} to the dirt ingest
//     endpoint at location=tent at the end of every 60 s cycle.
//   - Exposes a LAN HTTP control surface on :80 — POST /fan {"duty_pct":N}
//     sets the fan; GET /fan returns {"set_duty_pct":N,"reported_duty_pct":N}.
//     `reported_duty_pct` is MOCKED (echoes the last-set value) until the
//     D− tach input is wired; the JSON shape is stable across that
//     transition so host-side callers don't need to change when tach lands.
//   - mDNS hostname fan-controller.local; OTA on port 3232.
//
// Sensor cadence follows Sensirion's creep-mitigation app note: 1 s @ 200 mW
// heater pulse (SHT4X_HIGH_HEATER_1S) → 59 s equilibration → read + post →
// chain the next pulse. 1.67 % heater duty, well under the 10 % lifetime
// cap. The measurement returned by the heat command itself is discarded
// (sensor is still hot; spec is invalid during and right after heating).
//
// Signal inversion on the fan side: MOSFET pulls the line LOW when ESP32
// drives HIGH, so D+ wire duty = 100% − MCU GPIO duty. At reset, MOSFETs
// are off → D+ floats to ~9 V via the fan's internal pull-up → fan runs at
// max. Intentional failsafe: over-ventilation is the safer failure mode.

#include <Arduino.h>
#include <Preferences.h>
#include <WebServer.h>
#include <Wire.h>
#include <Adafruit_SHT4x.h>

#include "ingest_client.h"
#include "ota.h"
#include "secrets.h"
#include "wifi_client.h"

// --- Config ---------------------------------------------------------------

constexpr uint8_t  GPIO_D_PLUS    = 6;
constexpr uint8_t  GPIO_B5        = 7;
constexpr uint8_t  GPIO_I2C_SDA   = 4;
constexpr uint8_t  GPIO_I2C_SCL   = 5;
constexpr uint8_t  LEDC_CH_D_PLUS = 0;
constexpr uint8_t  LEDC_CH_B5     = 1;
constexpr uint32_t PWM_FREQ_HZ    = 5000;
constexpr uint8_t  PWM_RESOLUTION = 10;
constexpr uint32_t PWM_MAX        = (1U << PWM_RESOLUTION) - 1;

constexpr float    B5_MCU_DUTY_PCT  = 1.4f;
constexpr float    D_PLUS_MIN_WIRE  = 22.0f;
constexpr float    D_PLUS_MAX_WIRE  = 100.0f;

// Used only when NVS has no saved value (first-flash, NVS erased). Once
// the host posts a /fan command, the value persists across reboots and
// this default is no longer consulted. See "duty persistence" in
// wiki/hardware/ac-infinity-fan-control.md.
constexpr uint8_t  BOOT_SPEED_PCT   = 15;
constexpr uint32_t EQUILIBRATE_MS   = 59000;
constexpr uint32_t SENSOR_RETRY_MS  = 5000;

constexpr const char* LOCATION = "tent";
constexpr const char* HOSTNAME = "fan-controller";

// NVS-backed duty persistence — survives soft + power-cycle resets.
// Diff-check before writing keeps flash wear bounded if a future host-
// side closed loop writes frequently.
constexpr const char* NVS_NAMESPACE = "fan";
constexpr const char* NVS_KEY_DUTY  = "duty_pct";

// --- State ----------------------------------------------------------------

Adafruit_SHT4x sht;
bool sht_ready = false;

WebServer http_server(80);
IngestClient ingest(SERVER_URL, SENSOR_INGEST_TOKEN, FIRMWARE_VERSION);
Preferences prefs;

uint8_t  g_set_duty_pct      = BOOT_SPEED_PCT;
uint32_t g_equilibrate_start = 0;
uint32_t g_last_sht_retry    = 0;

// --- SHT45 ----------------------------------------------------------------

bool bring_up_sht() {
    if (!sht.begin(&Wire)) return false;
    sht.setPrecision(SHT4X_HIGH_PRECISION);
    sht.setHeater(SHT4X_NO_HEATER);  // heater driven per-cycle below, not on
    return true;
}

// Blocks ~1.1 s (the heat+measure command holds the I²C bus for the pulse
// duration) — the heater cycle is driven from the main loop so pulse and
// equilibration interleave with ota::loop and http_server.handleClient.
void fire_heater_pulse() {
    sensors_event_t h, t;
    sht.setHeater(SHT4X_HIGH_HEATER_1S);
    sht.getEvent(&h, &t);
    sht.setHeater(SHT4X_NO_HEATER);
}

// --- Fan control ----------------------------------------------------------

// API contract: speed_pct is the host-facing 0..100 control input.
//   speed_pct == 0   → fan off (wire duty 0%)
//   speed_pct == 1   → lowest running speed (wire duty == D_PLUS_MIN_WIRE)
//   speed_pct == 100 → full speed (wire duty 100%)
// The 22% wire-duty stall threshold (D_PLUS_MIN_WIRE) is hidden from the
// host — callers should never need to know about it. There is no API-side
// stall floor; pct=1 is already a useful "barely running" command.
float fan_speed_to_wire_duty(uint8_t speed_pct) {
    if (speed_pct == 0) return 0.0f;
    if (speed_pct > 100) speed_pct = 100;
    return D_PLUS_MIN_WIRE
        + (speed_pct / 100.0f) * (D_PLUS_MAX_WIRE - D_PLUS_MIN_WIRE);
}

uint32_t wire_duty_to_mcu_value(float wire_duty_pct) {
    float mcu_pct = 100.0f - wire_duty_pct;
    if (mcu_pct < 0.0f)   mcu_pct = 0.0f;
    if (mcu_pct > 100.0f) mcu_pct = 100.0f;
    return (uint32_t)(mcu_pct / 100.0f * PWM_MAX + 0.5f);
}

void apply_fan_speed(uint8_t speed_pct) {
    float wire_duty = fan_speed_to_wire_duty(speed_pct);
    uint32_t mcu_value = wire_duty_to_mcu_value(wire_duty);
    ledcWrite(LEDC_CH_D_PLUS, mcu_value);
}

float compute_vpd_kpa(float temp_c, float rh_pct) {
    // VPD = SVP × (1 − RH/100); SVP = 0.6108 × exp(17.27·T / (T + 237.3))
    // (Tetens). Matches the canonical formula used by the host-side loop.
    float svp = 0.6108f * expf(17.27f * temp_c / (temp_c + 237.3f));
    return svp * (1.0f - rh_pct / 100.0f);
}

// --- HTTP control endpoints ----------------------------------------------

// Brittle by design — LAN-only, single caller, minimal flash cost. Body must
// contain `"duty_pct": N` where N is 0..100.
bool parse_duty_body(const String& body, int* out) {
    int idx = body.indexOf("\"duty_pct\"");
    if (idx < 0) return false;
    int colon = body.indexOf(':', idx);
    if (colon < 0) return false;
    const char* p = body.c_str() + colon + 1;
    while (*p == ' ' || *p == '\t') p++;
    char* end = nullptr;
    long v = strtol(p, &end, 10);
    if (end == p) return false;
    if (v < 0 || v > 100) return false;
    *out = (int)v;
    return true;
}

void handle_post_fan() {
    String body = http_server.arg("plain");
    int duty = 0;
    if (!parse_duty_body(body, &duty)) {
        http_server.send(400, "application/json",
                         "{\"error\":\"expected {\\\"duty_pct\\\":0..100}\"}");
        return;
    }
    g_set_duty_pct = (uint8_t)duty;
    apply_fan_speed(g_set_duty_pct);
    if (prefs.getUChar(NVS_KEY_DUTY, 255) != g_set_duty_pct) {
        prefs.putUChar(NVS_KEY_DUTY, g_set_duty_pct);
    }
    char resp[48];
    snprintf(resp, sizeof(resp), "{\"duty_pct\":%u}", g_set_duty_pct);
    http_server.send(200, "application/json", resp);
    Serial.printf("[http] POST /fan duty_pct=%u\n", g_set_duty_pct);
}

void handle_get_fan() {
    char resp[80];
    snprintf(resp, sizeof(resp),
             "{\"set_duty_pct\":%u,\"reported_duty_pct\":%u}",
             g_set_duty_pct, g_set_duty_pct);
    http_server.send(200, "application/json", resp);
}

void handle_not_found() {
    http_server.send(404, "application/json", "{\"error\":\"not found\"}");
}

// --- Sensor cycle ---------------------------------------------------------

// Read the sensor (normal precision, no heater), post to ingest, kick off
// the next heater pulse, and reset the equilibration timer. Bail cleanly if
// the I²C read fails — the next loop iteration will re-bring-up the sensor.
void complete_cycle() {
    sensors_event_t humidity, temp;
    if (!sht.getEvent(&humidity, &temp)) {
        Serial.println("[sht45] read FAILED — dropping sensor, will retry");
        sht_ready = false;
        return;
    }
    float temp_f = temp.temperature * 9.0f / 5.0f + 32.0f;
    float vpd = compute_vpd_kpa(temp.temperature, humidity.relative_humidity);
    Serial.printf("[cycle] %.2f°C (%.1f°F) RH %.1f%% VPD %.2f kPa | fan=%u%%\n",
                  temp.temperature, temp_f,
                  humidity.relative_humidity, vpd, g_set_duty_pct);

    char metrics[96];
    snprintf(metrics, sizeof(metrics),
             "{\"temperature_c\":%.2f,\"humidity_pct\":%.2f,\"fan_duty_pct\":%u}",
             temp.temperature, humidity.relative_humidity, g_set_duty_pct);
    int code = ingest.post(LOCATION, metrics);
    if (code > 0) Serial.printf("[ingest] http=%d\n", code);

    // Chain straight into the next pulse per Sensirion AN §3.
    fire_heater_pulse();
    g_equilibrate_start = millis();
}

// Called every loop iteration; cheap when nothing is due. Drives the
// heater-pulse / equilibrate / read cycle and handles sensor re-bring-up.
void pump_sensor_cycle() {
    uint32_t now = millis();

    if (!sht_ready) {
        if (now - g_last_sht_retry < SENSOR_RETRY_MS) return;
        g_last_sht_retry = now;
        sht_ready = bring_up_sht();
        if (!sht_ready) return;
        Serial.printf("[sht45] ok serial=0x%08X — starting heater cycle\n",
                      (unsigned int)sht.readSerial());
        fire_heater_pulse();
        g_equilibrate_start = millis();
        return;
    }

    if (now - g_equilibrate_start >= EQUILIBRATE_MS) {
        complete_cycle();
    }
}

// --- Lifecycle ------------------------------------------------------------

void setup() {
    Serial.begin(115200);
    delay(2000);

    Serial.println();
    Serial.println("# ========================================================");
    Serial.printf ("# fan+tent dual-role node fw=%s\n", FIRMWARE_VERSION);
    Serial.println("# ========================================================");
    Serial.printf ("# D+ gate:  GPIO %u  (Q1 → fan D+ pad)\n", GPIO_D_PLUS);
    Serial.printf ("# B5 gate:  GPIO %u  (Q2 → fan B5 pad)\n", GPIO_B5);
    Serial.printf ("# SHT45:    GPIO %u SDA, GPIO %u SCL (Adafruit 5665, 0x44)\n",
                   GPIO_I2C_SDA, GPIO_I2C_SCL);
    Serial.printf ("# PWM:      %u Hz, %u-bit (ledc 0..%u)\n",
                   PWM_FREQ_HZ, PWM_RESOLUTION, PWM_MAX);
    Serial.printf ("# Heater:   200mW/1s pulse every %lus (Sensirion AN §3)\n",
                   (unsigned long)((EQUILIBRATE_MS + 1000) / 1000));
    Serial.println("# ========================================================");
    Serial.println();

    // LEDC PWM for D+ and B5
    ledcSetup(LEDC_CH_D_PLUS, PWM_FREQ_HZ, PWM_RESOLUTION);
    ledcAttachPin(GPIO_D_PLUS, LEDC_CH_D_PLUS);
    ledcSetup(LEDC_CH_B5, PWM_FREQ_HZ, PWM_RESOLUTION);
    ledcAttachPin(GPIO_B5, LEDC_CH_B5);

    uint32_t b5_value = (uint32_t)(B5_MCU_DUTY_PCT / 100.0f * PWM_MAX + 0.5f);
    ledcWrite(LEDC_CH_B5, b5_value);
    Serial.printf("[boot] B5 keep-alive: MCU duty=%.1f%%  wire=%.1f%%\n",
                  B5_MCU_DUTY_PCT, 100.0f - B5_MCU_DUTY_PCT);

    // I²C for SHT45
    Wire.begin(GPIO_I2C_SDA, GPIO_I2C_SCL);
    sht_ready = bring_up_sht();
    if (sht_ready) {
        Serial.printf("[boot] SHT45 ok, serial=0x%08X\n",
                      (unsigned int)sht.readSerial());
    } else {
        Serial.println("[boot] SHT45 begin failed — will retry in main loop");
    }

    // Hold D+ at wire=100% (MCU 0%) for a couple seconds so you can hear
    // the failsafe-max blast before settling to the hold speed.
    ledcWrite(LEDC_CH_D_PLUS, 0);
    Serial.println("[boot] D+ initial:  MCU duty=0.0%  wire=100.0%  (fan at max)");
    delay(2000);

    // Restore last commanded duty from NVS — survives reboots.
    // Falls back to BOOT_SPEED_PCT on first-flash or after `nvs_flash_erase`.
    prefs.begin(NVS_NAMESPACE, /*readOnly=*/false);
    uint8_t saved = prefs.getUChar(NVS_KEY_DUTY, BOOT_SPEED_PCT);
    if (saved > 100) saved = BOOT_SPEED_PCT;  // corrupt → fall back
    g_set_duty_pct = saved;
    apply_fan_speed(g_set_duty_pct);
    Serial.printf("[boot] fan -> %u%% (restored from NVS)\n", g_set_duty_pct);

    // WiFi + OTA + HTTP control surface
    wifi_client::connect(WIFI_SSID, WIFI_PASSWORD, HOSTNAME);
    ota::begin(HOSTNAME, OTA_PASSWORD);
    http_server.on("/fan", HTTP_GET, handle_get_fan);
    http_server.on("/fan", HTTP_POST, handle_post_fan);
    http_server.onNotFound(handle_not_found);
    http_server.begin();
    Serial.println("[boot] http control surface up on :80 (GET/POST /fan)");

    // Kick off the sensor cycle immediately if the sensor is already up.
    if (sht_ready) {
        fire_heater_pulse();
        g_equilibrate_start = millis();
    }
}

void loop() {
    ota::loop();
    wifi_client::maintain();
    http_server.handleClient();
    pump_sensor_cycle();
    delay(10);  // yield to WiFi/OTA stack
}
