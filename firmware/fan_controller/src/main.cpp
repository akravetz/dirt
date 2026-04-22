// AC Infinity Cloudline LITE 6" fan controller — hold + tach feedback.
//
// Drives D+ and B5 via two 2N7000 MOSFETs; reads the fan's D− tach output
// through a voltage divider. Holds the fan at HOLD_SPEED_PCT and prints a
// command-plus-observed log line once per HEARTBEAT_MS, so both the issued
// command and the measured RPM show up on the same line.
//
// Full wiring + protocol: wiki/hardware/ac-infinity-fan-control.md.
//
// Hardware:
//   - ESP32-C3 SuperMini, USB-C powered
//   - GPIO 6  → Q1 gate → fan D+ pad (speed command)
//   - GPIO 7  → Q2 gate → fan B5 pad (keep-alive heartbeat)
//   - GPIO 10 ← tach divider midpoint (D− → 10kΩ → GPIO10 → 4.7kΩ → GND)
//   - 10 kΩ gate-to-GND pull-down on Q1 gate and Q2 gate
//   - ESP32 GND ↔ fan GND tied together at the Treedix breakout
//   - Fan powered separately via its own USB-C brick
//
// Signal inversion: MOSFET pulls the line LOW when ESP32 drives HIGH, so
// D+ wire duty = 100% − MCU GPIO duty. At reset, MOSFETs are off →
// D+ floats to ~9V via the fan's internal pull-up → fan runs at max.
// Intentional failsafe: over-ventilation is the safer failure direction.

#include <Arduino.h>

// --- Config ---------------------------------------------------------------

constexpr uint8_t  GPIO_D_PLUS    = 6;
constexpr uint8_t  GPIO_B5        = 7;
constexpr uint8_t  GPIO_TACH      = 10;
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

// Tach: D− emits a 50%-duty square wave whose frequency tracks RPM.
// Characterized range 45–166 Hz → ~1,350–5,000 RPM at 2 pulses/rev (the
// pulses-per-rev figure is assumed from the wiki — revise the constant if
// observed RPM looks consistently halved or doubled vs fan nameplate).
constexpr uint16_t TACH_PULSES_PER_REV = 2;

// The ISR just counts rising edges. A snapshot routine reads + zeros the
// counter under a brief critical section, recording the window start time
// so the caller can compute "edges per elapsed ms" = Hz.
static volatile uint32_t tach_edge_count = 0;
static volatile uint32_t tach_window_start_ms = 0;
static portMUX_TYPE tach_mux = portMUX_INITIALIZER_UNLOCKED;

static void IRAM_ATTR tach_isr() {
    tach_edge_count++;
}

struct TachSnapshot {
    uint32_t edges;
    uint32_t window_ms;
    uint32_t freq_hz;
    uint32_t rpm;
};

// Read the counter + window start, then reset both atomically so the next
// snapshot measures a clean, non-overlapping window. Integer math only —
// avoid float in the ISR path and keep this routine trivially predictable.
TachSnapshot snapshot_tach() {
    TachSnapshot s = {};
    uint32_t now = millis();
    portENTER_CRITICAL(&tach_mux);
    s.edges = tach_edge_count;
    s.window_ms = now - tach_window_start_ms;
    tach_edge_count = 0;
    tach_window_start_ms = now;
    portEXIT_CRITICAL(&tach_mux);

    if (s.window_ms > 0 && s.edges > 0) {
        // Hz = edges * 1000 / window_ms. Order the multiply first to avoid
        // integer truncation when edges < window_ms (common at low RPM).
        s.freq_hz = (s.edges * 1000UL) / s.window_ms;
        s.rpm = (s.freq_hz * 60UL) / TACH_PULSES_PER_REV;
    }
    return s;
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

void log_state(uint8_t commanded_pct) {
    TachSnapshot t = snapshot_tach();
    float wire_duty = fan_speed_to_wire_duty(commanded_pct);
    if (t.edges == 0) {
        Serial.printf(
            "[%8lu ms] cmd=%u%% (D+ wire=%.1f%%)  tach: SILENT "
            "(no edges in %lums window — fan stopped or tach wiring open)\n",
            (unsigned long)millis(), commanded_pct, wire_duty,
            (unsigned long)t.window_ms);
    } else {
        Serial.printf(
            "[%8lu ms] cmd=%u%% (D+ wire=%.1f%%)  tach: %lu Hz  %lu RPM  "
            "(%lu edges over %lums)\n",
            (unsigned long)millis(), commanded_pct, wire_duty,
            (unsigned long)t.freq_hz, (unsigned long)t.rpm,
            (unsigned long)t.edges, (unsigned long)t.window_ms);
    }
}

// --- Lifecycle ------------------------------------------------------------

void setup() {
    Serial.begin(115200);
    delay(2000);

    Serial.println();
    Serial.println("# ========================================================");
    Serial.printf ("# fan-controller fw=%s — hold + tach feedback\n", FIRMWARE_VERSION);
    Serial.println("# ========================================================");
    Serial.printf ("# D+ gate:  GPIO %u  (Q1 → fan D+ pad)\n", GPIO_D_PLUS);
    Serial.printf ("# B5 gate:  GPIO %u  (Q2 → fan B5 pad)\n", GPIO_B5);
    Serial.printf ("# D- tach:  GPIO %u  (via 10k/4.7k divider, RISING edges)\n", GPIO_TACH);
    Serial.printf ("# PWM:      %u Hz, %u-bit (ledc 0..%u)\n",
                   PWM_FREQ_HZ, PWM_RESOLUTION, PWM_MAX);
    Serial.println("# Inversion: MCU HIGH → MOSFET on → fan line LOW");
    Serial.printf ("# Hold:     fan=%u%%  heartbeat every %lus\n",
                   HOLD_SPEED_PCT, (unsigned long)(HEARTBEAT_MS / 1000));
    Serial.printf ("# Tach:     assumes %u pulses/rev; RPM = Hz × 60 / pulses-per-rev\n",
                   TACH_PULSES_PER_REV);
    Serial.println("# ========================================================");
    Serial.println();

    ledcSetup(LEDC_CH_D_PLUS, PWM_FREQ_HZ, PWM_RESOLUTION);
    ledcAttachPin(GPIO_D_PLUS, LEDC_CH_D_PLUS);
    ledcSetup(LEDC_CH_B5, PWM_FREQ_HZ, PWM_RESOLUTION);
    ledcAttachPin(GPIO_B5, LEDC_CH_B5);

    uint32_t b5_value = (uint32_t)(B5_MCU_DUTY_PCT / 100.0f * PWM_MAX + 0.5f);
    ledcWrite(LEDC_CH_B5, b5_value);
    Serial.printf("[boot] B5 heartbeat: MCU duty=%.1f%%  wire=%.1f%%  ledc=%u/%u\n",
                  B5_MCU_DUTY_PCT, 100.0f - B5_MCU_DUTY_PCT, b5_value, PWM_MAX);

    pinMode(GPIO_TACH, INPUT);
    tach_window_start_ms = millis();
    attachInterrupt(digitalPinToInterrupt(GPIO_TACH), tach_isr, RISING);

    // Hold D+ at "fan-max" (MCU 0% → wire 100%) for a 3s boot blast; then
    // sample the tach so we get a max-speed reading before settling down.
    ledcWrite(LEDC_CH_D_PLUS, 0);
    Serial.println("[boot] D+ initial:  MCU duty=0.0%  wire=100.0%  (fan at max)");
    (void)snapshot_tach();  // reset the counter — discard the "just booted" window
    delay(3000);
    log_state(100);  // commanded 100% (really: D+ floating; same-speed)

    Serial.println();
    Serial.println("# --- entering hold mode ---");
    set_fan_speed(HOLD_SPEED_PCT);
    (void)snapshot_tach();  // reset so the 3s settle window is clean
    delay(3000);             // let the motor settle to the new speed
    log_state(HOLD_SPEED_PCT);
}

void loop() {
    delay(HEARTBEAT_MS);
    set_fan_speed(HOLD_SPEED_PCT);
    log_state(HOLD_SPEED_PCT);
}
