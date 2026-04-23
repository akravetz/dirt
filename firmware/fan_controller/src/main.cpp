// AC Infinity Cloudline LITE 6" fan driver + tent environmental sensor.
//
// Drives D+ and B5 via two 2N7000 MOSFETs and reads an Adafruit SHT45
// (product 5665, PTFE-capped) over I²C. Holds the fan at HOLD_SPEED_PCT
// and emits a combined heartbeat line every HEARTBEAT_MS showing both the
// commanded fan state and the most recent tent temp / RH / VPD.
//
// Full wiring + protocol:
//   wiki/hardware/ac-infinity-fan-control.md
//   wiki/decisions/2026-04-22-sht45-tent-node-esp32.md
//
// Hardware:
//   - ESP32-C3 SuperMini, USB-C powered
//   - GPIO 6  → Q1 gate → fan D+ pad (speed command)
//   - GPIO 7  → Q2 gate → fan B5 pad (keep-alive heartbeat)
//   - GPIO 4  → SHT45 SDA (I²C data)
//   - GPIO 5  → SHT45 SCL (I²C clock)
//   - 10 kΩ gate-to-GND pull-down on each MOSFET gate
//   - ESP32 GND ↔ fan GND tied together at the Treedix breakout
//   - Fan powered separately via its own USB-C brick
//   - SHT45 VIN from ESP32 3V3, GND on the common rail
//
// Signal inversion on the fan side: MOSFET pulls the line LOW when ESP32
// drives HIGH, so D+ wire duty = 100% − MCU GPIO duty. At reset, MOSFETs
// are off → D+ floats to ~9V via the fan's internal pull-up → fan runs at
// max. Intentional failsafe: over-ventilation is the safer failure mode.
//
// Tach (D−) path is deliberately not implemented yet. See the fan-control
// hardware page for the plan to revisit.

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_SHT4x.h>

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

constexpr float    B5_MCU_DUTY_PCT = 1.4f;
constexpr float    D_PLUS_MIN_WIRE = 22.0f;
constexpr float    D_PLUS_MAX_WIRE = 100.0f;

constexpr uint8_t  HOLD_SPEED_PCT = 30;
constexpr uint32_t HEARTBEAT_MS   = 60000;

// --- SHT45 ----------------------------------------------------------------

Adafruit_SHT4x sht;
bool sht_ready = false;

bool bring_up_sht() {
    if (!sht.begin(&Wire)) return false;
    sht.setPrecision(SHT4X_HIGH_PRECISION);
    sht.setHeater(SHT4X_NO_HEATER);
    return true;
}

// --- Fan control helpers --------------------------------------------------

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

void set_fan_speed(uint8_t speed_pct) {
    float wire_duty = fan_speed_to_wire_duty(speed_pct);
    uint32_t mcu_value = wire_duty_to_mcu_value(wire_duty);
    ledcWrite(LEDC_CH_D_PLUS, mcu_value);
}

// --- Combined heartbeat ---------------------------------------------------

// VPD = SVP × (1 − RH/100); SVP = 0.6108 × exp(17.27·T / (T + 237.3))
// (Tetens). T in °C, RH in %, returns kPa. Matches the canonical
// formula used by the host-side control loop.
float compute_vpd_kpa(float temp_c, float rh_pct) {
    float svp = 0.6108f * expf(17.27f * temp_c / (temp_c + 237.3f));
    return svp * (1.0f - rh_pct / 100.0f);
}

void log_heartbeat() {
    unsigned long now = millis();
    float wire_duty = fan_speed_to_wire_duty(HOLD_SPEED_PCT);

    Serial.printf("[%8lu ms] fan=%u%% (D+ wire=%.1f%%)",
                  now, HOLD_SPEED_PCT, wire_duty);

    if (!sht_ready) {
        sht_ready = bring_up_sht();
    }

    if (!sht_ready) {
        Serial.println("  |  sht45: offline (begin failed — check SDA/SCL/VIN/GND)");
        return;
    }

    sensors_event_t humidity, temp;
    if (!sht.getEvent(&humidity, &temp)) {
        Serial.println("  |  sht45: read FAILED — dropping sensor, will retry");
        sht_ready = false;
        return;
    }

    float temp_f = temp.temperature * 9.0f / 5.0f + 32.0f;
    float vpd = compute_vpd_kpa(temp.temperature, humidity.relative_humidity);
    Serial.printf("  |  tent: %.2f°C (%.1f°F)  RH %.1f%%  VPD %.2f kPa\n",
                  temp.temperature, temp_f, humidity.relative_humidity, vpd);
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
    Serial.println("# Inversion: MCU HIGH → MOSFET on → fan line LOW");
    Serial.printf ("# Hold:     fan=%u%%  heartbeat every %lus\n",
                   HOLD_SPEED_PCT, (unsigned long)(HEARTBEAT_MS / 1000));
    Serial.println("# ========================================================");
    Serial.println();

    // LEDC PWM for D+ and B5
    ledcSetup(LEDC_CH_D_PLUS, PWM_FREQ_HZ, PWM_RESOLUTION);
    ledcAttachPin(GPIO_D_PLUS, LEDC_CH_D_PLUS);
    ledcSetup(LEDC_CH_B5, PWM_FREQ_HZ, PWM_RESOLUTION);
    ledcAttachPin(GPIO_B5, LEDC_CH_B5);

    uint32_t b5_value = (uint32_t)(B5_MCU_DUTY_PCT / 100.0f * PWM_MAX + 0.5f);
    ledcWrite(LEDC_CH_B5, b5_value);
    Serial.printf("[boot] B5 heartbeat: MCU duty=%.1f%%  wire=%.1f%%  ledc=%u/%u\n",
                  B5_MCU_DUTY_PCT, 100.0f - B5_MCU_DUTY_PCT, b5_value, PWM_MAX);

    // I²C for SHT45
    Wire.begin(GPIO_I2C_SDA, GPIO_I2C_SCL);
    sht_ready = bring_up_sht();
    if (sht_ready) {
        Serial.printf("[boot] SHT45 ok, serial=0x%08X\n",
                      (unsigned int)sht.readSerial());
    } else {
        Serial.println("[boot] SHT45 begin failed — will retry each heartbeat");
    }

    // Hold D+ at wire=100% (MCU 0%) for a couple seconds so you can hear
    // the failsafe-max blast before settling to the hold speed.
    ledcWrite(LEDC_CH_D_PLUS, 0);
    Serial.println("[boot] D+ initial:  MCU duty=0.0%  wire=100.0%  (fan at max)");
    delay(2000);

    Serial.println();
    Serial.println("# --- entering hold mode ---");
    set_fan_speed(HOLD_SPEED_PCT);
    delay(3000);  // let the fan settle to hold speed before first reading
    log_heartbeat();
}

void loop() {
    delay(HEARTBEAT_MS);
    set_fan_speed(HOLD_SPEED_PCT);
    log_heartbeat();
}
