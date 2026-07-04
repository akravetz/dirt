// Seeed XIAO ESP32-C3 RS485 substrate node.
//
// Reads DFRobot SEN0604 substrate sensors over the Seeed RS485 expansion
// board and posts one logical probe payload per responding plant. Runtime
// observability is LAN-first: OTA, GET /health, and GET /status must work
// without USB serial.

#include <Arduino.h>
#include <Preferences.h>
#include <WebServer.h>
#include <WiFi.h>
#include <esp_system.h>
#include <stdarg.h>
#include <stdlib.h>

#include "ingest_client.h"
#include "ota.h"
#include "secrets.h"
#include "wifi_client.h"

// --- Config ---------------------------------------------------------------

#ifndef NODE_DEVICE_ID
#define NODE_DEVICE_ID "plant-a-substrate-node"
#endif
#ifndef NODE_HOSTNAME
#define NODE_HOSTNAME "plant-a-substrate-node"
#endif
#ifndef INGEST_INTERVAL_MS
#define INGEST_INTERVAL_MS 30000
#endif
#ifndef NORMAL_MEASUREMENT_INTERVAL_MS
#define NORMAL_MEASUREMENT_INTERVAL_MS 30000
#endif
#ifndef CALIBRATION_MEASUREMENT_INTERVAL_MS
#define CALIBRATION_MEASUREMENT_INTERVAL_MS 2000
#endif

constexpr int RS485_RX_PIN = 7;
constexpr int RS485_TX_PIN = 6;
constexpr int RS485_ENABLE_PIN = D2;
constexpr uint32_t SENSOR_BAUD = 9600;
constexpr uint32_t RESPONSE_TIMEOUT_MS = 700;
constexpr size_t MODBUS_RESPONSE_MAX = 32;
constexpr size_t MODBUS_MEASUREMENT_LEN = 13;
constexpr size_t MODBUS_WRITE_RESPONSE_LEN = 8;
constexpr uint8_t FACTORY_DEFAULT_ADDRESS = 0x01;
constexpr uint16_t ADDRESS_REGISTER = 0x07D0;
constexpr uint32_t PROVISION_SETTLE_MS = 500;
constexpr uint32_t PROVISION_FAILURE_COOLDOWN_MS = 300000;
constexpr uint32_t PROVISION_SUCCESS_COOLDOWN_MS = 60000;
constexpr uint32_t PROVISION_PREF_SCHEMA_VERSION = 1;
constexpr uint32_t CONFIG_INGEST_INTERVAL_MS = INGEST_INTERVAL_MS;
constexpr uint32_t CONFIG_NORMAL_MEASUREMENT_INTERVAL_MS = NORMAL_MEASUREMENT_INTERVAL_MS;
constexpr uint32_t CONFIG_CALIBRATION_MEASUREMENT_INTERVAL_MS = CALIBRATION_MEASUREMENT_INTERVAL_MS;
constexpr uint32_t CALIBRATION_INTERVAL_MIN_MS = 1000;
constexpr uint32_t CALIBRATION_INTERVAL_MAX_MS = 30000;
constexpr uint32_t CALIBRATION_DURATION_DEFAULT_S = 900;
constexpr uint32_t CALIBRATION_DURATION_MIN_S = 1;
constexpr uint32_t CALIBRATION_DURATION_MAX_S = 3600;
constexpr uint32_t SAMPLES_WINDOW_DEFAULT_S = 120;
constexpr uint32_t SAMPLES_WINDOW_MIN_S = 1;
constexpr uint32_t SAMPLES_WINDOW_MAX_S = 120;
constexpr uint32_t SAMPLE_RING_WINDOW_MS = 5UL * 60UL * 1000UL;
constexpr uint32_t SAMPLE_RING_TARGET_INTERVAL_MS = 2000;
constexpr size_t SAMPLE_RING_CAPACITY =
    (SAMPLE_RING_WINDOW_MS / SAMPLE_RING_TARGET_INTERVAL_MS) + 8;

constexpr const char* CONTROLLER_DEVICE_ID = NODE_DEVICE_ID;
constexpr const char* HOSTNAME = NODE_HOSTNAME;
constexpr const char* PROVISION_PREF_NAMESPACE = "rs485_bus";

// --- State ----------------------------------------------------------------

enum class ModbusStatus {
    Never,
    Ok,
    NoResponse,
    ShortResponse,
    CrcMismatch,
    BadHeader,
    ExtraResponse,
};

enum class ProvisioningResult {
    Never,
    NoTarget,
    NoDefaultResponse,
    InvalidDefaultResponse,
    WriteNoResponse,
    WriteInvalidEcho,
    DefaultStillResponding,
    TargetVerifyFailed,
    Assigned,
};

enum class ProvisioningPhase {
    Idle,
    ProbingDefault,
    WritingAddress,
    Settling,
    VerifyingDefault,
    VerifyingTarget,
};

struct SubstrateSample {
    bool valid = false;
    float moisture_pct = 0.0f;
    float temp_c = 0.0f;
    uint16_t ec_us_cm = 0;
    float ph = 0.0f;
    uint32_t read_ms = 0;
};

struct SampleRingEntry {
    bool used = false;
    bool decoded = false;
    uint32_t seq = 0;
    uint32_t read_ms = 0;
    uint8_t probe_id = 0;
    uint8_t modbus_address = 0;
    float moisture_pct = 0.0f;
    float temp_c = 0.0f;
    uint16_t ec_us_cm = 0;
    float ph = 0.0f;
    ModbusStatus modbus_status = ModbusStatus::Never;
    uint8_t raw_frame[MODBUS_RESPONSE_MAX] = {};
    size_t raw_frame_len = 0;
};

struct ProbeSlot {
    ProbeSlot(const char* label,
              const char* zone,
              const char* device,
              uint8_t address,
              bool slot_enabled,
              bool target,
              bool initial_assigned)
        : plant_label(label),
          zone_id(zone),
          device_id(device),
          modbus_address(address),
          enabled(slot_enabled),
          provisioning_target(target),
          assigned(initial_assigned) {}

    const char* plant_label;
    const char* zone_id;
    const char* device_id;
    uint8_t modbus_address;
    bool enabled;
    bool provisioning_target;
    bool assigned;

    SubstrateSample latest_sample;
    uint8_t last_frame[MODBUS_RESPONSE_MAX] = {};
    size_t last_frame_len = 0;
    ModbusStatus last_modbus_status = ModbusStatus::Never;

    uint32_t modbus_success_count = 0;
    uint32_t modbus_failure_count = 0;
    uint32_t modbus_crc_mismatch_count = 0;
    uint32_t modbus_short_response_count = 0;
    uint32_t modbus_no_response_count = 0;
    uint32_t modbus_bad_header_count = 0;

    uint32_t ingest_ok_count = 0;
    uint32_t ingest_fail_count = 0;
    int last_ingest_code = 0;
    bool sample_pending_ingest = false;

    SampleRingEntry samples[SAMPLE_RING_CAPACITY] = {};
    size_t sample_next = 0;
    size_t sample_count = 0;
};

struct ProvisioningState {
    ProvisioningPhase phase = ProvisioningPhase::Idle;
    ProvisioningResult last_result = ProvisioningResult::Never;
    ModbusStatus last_default_probe_status = ModbusStatus::Never;
    ModbusStatus last_target_verify_status = ModbusStatus::Never;
    int last_target_slot = -1;
    uint8_t last_target_address = 0;
    uint32_t attempt_count = 0;
    uint32_t success_count = 0;
    uint32_t failure_count = 0;
    uint32_t cooldown_skip_count = 0;
    uint32_t last_attempt_ms = 0;
    uint32_t cooldown_until_ms = 0;
};

struct CalibrationModeState {
    bool active = false;
    uint32_t started_ms = 0;
    uint32_t expires_ms = 0;
    uint32_t interval_ms = CONFIG_CALIBRATION_MEASUREMENT_INTERVAL_MS;
    uint32_t start_count = 0;
    uint32_t stop_count = 0;
    uint32_t auto_expire_count = 0;
    uint32_t measurement_cycle_count = 0;
    uint32_t sample_success_count = 0;
    uint32_t sample_failure_count = 0;
};

HardwareSerial rs485(1);
WebServer http_server(80);
IngestClient ingest(SERVER_URL, SENSOR_INGEST_TOKEN, FIRMWARE_VERSION);

ProbeSlot g_slots[] = {
    {"Plant A", "plant-a", "plant-a-substrate-node", 0x02, true, false, true},
    {"Plant D", "plant-d", "plant-d-substrate-node", 0x03, true, true, false},
    {"Plant C", "plant-c", "plant-c-substrate-node", 0x04, true, true, false},
};
constexpr size_t SLOT_COUNT = sizeof(g_slots) / sizeof(g_slots[0]);

uint32_t g_last_measurement_ms = 0;
uint32_t g_last_ingest_ms = 0;
uint32_t g_last_provisioning_ms = 0;
uint32_t g_loop_last_ms = 0;
uint32_t g_loop_gap_max_ms = 0;
uint32_t g_boot_count = 0;
esp_reset_reason_t g_reset_reason = ESP_RST_UNKNOWN;

size_t g_last_modbus_response_len = 0;
int g_last_ingest_code = 0;
uint32_t g_next_sample_seq = 1;
CalibrationModeState g_calibration;
ProvisioningState g_provisioning;

// --- Modbus ---------------------------------------------------------------

uint16_t crc16_modbus(const uint8_t* data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (uint8_t bit = 0; bit < 8; bit++) {
            if ((crc & 0x0001) != 0) {
                crc >>= 1;
                crc ^= 0xA001;
            } else {
                crc >>= 1;
            }
        }
    }
    return crc;
}

void build_read_command(uint8_t address, uint8_t* command, size_t len) {
    if (len < 8) return;
    command[0] = address;
    command[1] = 0x03;
    command[2] = 0x00;
    command[3] = 0x00;
    command[4] = 0x00;
    command[5] = 0x04;
    uint16_t crc = crc16_modbus(command, 6);
    command[6] = crc & 0xFF;
    command[7] = crc >> 8;
}

void build_write_register_command(uint8_t address,
                                  uint16_t reg,
                                  uint16_t value,
                                  uint8_t* command,
                                  size_t len) {
    if (len < MODBUS_WRITE_RESPONSE_LEN) return;
    command[0] = address;
    command[1] = 0x06;
    command[2] = reg >> 8;
    command[3] = reg & 0xFF;
    command[4] = value >> 8;
    command[5] = value & 0xFF;
    uint16_t crc = crc16_modbus(command, 6);
    command[6] = crc & 0xFF;
    command[7] = crc >> 8;
}

void remember_frame(ProbeSlot& slot, const uint8_t* data, size_t len) {
    slot.last_frame_len = min(len, MODBUS_RESPONSE_MAX);
    memcpy(slot.last_frame, data, slot.last_frame_len);
    g_last_modbus_response_len = slot.last_frame_len;
}

void send_command(const uint8_t* command, size_t len) {
    while (rs485.available() > 0) {
        rs485.read();
    }

    digitalWrite(RS485_ENABLE_PIN, HIGH);
    delayMicroseconds(100);
    rs485.write(command, len);
    rs485.flush();
    delayMicroseconds(200);
    digitalWrite(RS485_ENABLE_PIN, LOW);
}

size_t read_response(uint8_t* response, size_t max_len, bool service_http = true) {
    size_t len = 0;
    uint32_t start_ms = millis();
    while (millis() - start_ms < RESPONSE_TIMEOUT_MS && len < max_len) {
        while (rs485.available() > 0 && len < max_len) {
            response[len++] = static_cast<uint8_t>(rs485.read());
            start_ms = millis();
        }
        ota::loop();
        wifi_client::maintain();
        if (service_http) {
            http_server.handleClient();
        }
        delay(1);
    }
    return len;
}

uint16_t read_u16_be(const uint8_t* data) {
    return (static_cast<uint16_t>(data[0]) << 8) | data[1];
}

const char* modbus_status_name(ModbusStatus status) {
    switch (status) {
        case ModbusStatus::Ok:
            return "ok";
        case ModbusStatus::NoResponse:
            return "no_response";
        case ModbusStatus::ShortResponse:
            return "short_response";
        case ModbusStatus::CrcMismatch:
            return "crc_mismatch";
        case ModbusStatus::BadHeader:
            return "bad_header";
        case ModbusStatus::ExtraResponse:
            return "extra_response";
        case ModbusStatus::Never:
        default:
            return "never";
    }
}

const char* provisioning_result_name(ProvisioningResult result) {
    switch (result) {
        case ProvisioningResult::NoTarget:
            return "no_target";
        case ProvisioningResult::NoDefaultResponse:
            return "no_default_response";
        case ProvisioningResult::InvalidDefaultResponse:
            return "invalid_default_response";
        case ProvisioningResult::WriteNoResponse:
            return "write_no_response";
        case ProvisioningResult::WriteInvalidEcho:
            return "write_invalid_echo";
        case ProvisioningResult::DefaultStillResponding:
            return "default_still_responding";
        case ProvisioningResult::TargetVerifyFailed:
            return "target_verify_failed";
        case ProvisioningResult::Assigned:
            return "assigned";
        case ProvisioningResult::Never:
        default:
            return "never";
    }
}

const char* provisioning_phase_name(ProvisioningPhase phase) {
    switch (phase) {
        case ProvisioningPhase::ProbingDefault:
            return "probing_default";
        case ProvisioningPhase::WritingAddress:
            return "writing_address";
        case ProvisioningPhase::Settling:
            return "settling";
        case ProvisioningPhase::VerifyingDefault:
            return "verifying_default";
        case ProvisioningPhase::VerifyingTarget:
            return "verifying_target";
        case ProvisioningPhase::Idle:
        default:
            return "idle";
    }
}

bool deadline_reached(uint32_t now, uint32_t deadline_ms) {
    return static_cast<int32_t>(now - deadline_ms) >= 0;
}

void expire_calibration_if_due() {
    if (!g_calibration.active) return;
    uint32_t now = millis();
    if (!deadline_reached(now, g_calibration.expires_ms)) return;

    g_calibration.active = false;
    g_calibration.auto_expire_count++;
    Serial.printf("[calibration] auto-expired interval_ms=%lu\n",
                  (unsigned long)g_calibration.interval_ms);
}

uint32_t calibration_remaining_ms() {
    expire_calibration_if_due();
    if (!g_calibration.active) return 0;
    uint32_t now = millis();
    if (deadline_reached(now, g_calibration.expires_ms)) return 0;
    return g_calibration.expires_ms - now;
}

uint32_t current_measurement_interval_ms() {
    expire_calibration_if_due();
    if (g_calibration.active) return g_calibration.interval_ms;
    return CONFIG_NORMAL_MEASUREMENT_INTERVAL_MS;
}

uint8_t probe_id_for_slot(size_t slot_index) {
    return static_cast<uint8_t>(slot_index + 1);
}

ModbusStatus parse_measurement_response(uint8_t address,
                                        const uint8_t* response,
                                        size_t len,
                                        bool require_single_frame,
                                        SubstrateSample& sample) {
    if (len == 0) return ModbusStatus::NoResponse;
    if (len < MODBUS_MEASUREMENT_LEN) return ModbusStatus::ShortResponse;
    if (require_single_frame && len != MODBUS_MEASUREMENT_LEN) return ModbusStatus::ExtraResponse;

    if (response[0] != address || response[1] != 0x03 || response[2] != 0x08) {
        return ModbusStatus::BadHeader;
    }

    uint16_t expected_crc = crc16_modbus(response, MODBUS_MEASUREMENT_LEN - 2);
    uint16_t received_crc = static_cast<uint16_t>(response[11]) |
                            (static_cast<uint16_t>(response[12]) << 8);
    if (expected_crc != received_crc) return ModbusStatus::CrcMismatch;

    uint16_t moisture_raw = read_u16_be(response + 3);
    int16_t temp_raw = static_cast<int16_t>(read_u16_be(response + 5));
    uint16_t ec_raw = read_u16_be(response + 7);
    uint16_t ph_raw = read_u16_be(response + 9);

    sample.valid = true;
    sample.moisture_pct = moisture_raw / 10.0f;
    sample.temp_c = temp_raw / 10.0f;
    sample.ec_us_cm = ec_raw;
    sample.ph = ph_raw / 10.0f;
    sample.read_ms = millis();
    return ModbusStatus::Ok;
}

ModbusStatus read_measurement(uint8_t address,
                              bool require_single_frame,
                              SubstrateSample& sample,
                              uint8_t* response,
                              size_t max_len,
                              size_t& len,
                              bool service_http = true) {
    uint8_t command[8] = {};
    build_read_command(address, command, sizeof(command));
    send_command(command, sizeof(command));
    len = read_response(response, max_len, service_http);
    return parse_measurement_response(address, response, len, require_single_frame, sample);
}

void record_slot_modbus_failure(ProbeSlot& slot, ModbusStatus status) {
    slot.last_modbus_status = status;
    slot.modbus_failure_count++;
    switch (status) {
        case ModbusStatus::NoResponse:
            slot.modbus_no_response_count++;
            break;
        case ModbusStatus::ShortResponse:
            slot.modbus_short_response_count++;
            break;
        case ModbusStatus::CrcMismatch:
            slot.modbus_crc_mismatch_count++;
            break;
        case ModbusStatus::BadHeader:
        case ModbusStatus::ExtraResponse:
            slot.modbus_bad_header_count++;
            break;
        case ModbusStatus::Never:
        case ModbusStatus::Ok:
        default:
            break;
    }
}

void record_sample_ring_entry(ProbeSlot& slot,
                              size_t slot_index,
                              const SubstrateSample& sample,
                              ModbusStatus status,
                              const uint8_t* frame,
                              size_t frame_len) {
    SampleRingEntry& entry = slot.samples[slot.sample_next];
    slot.sample_next = (slot.sample_next + 1) % SAMPLE_RING_CAPACITY;
    if (slot.sample_count < SAMPLE_RING_CAPACITY) {
        slot.sample_count++;
    }

    entry.used = true;
    entry.decoded = status == ModbusStatus::Ok && sample.valid;
    entry.seq = g_next_sample_seq++;
    entry.read_ms = entry.decoded ? sample.read_ms : millis();
    entry.probe_id = probe_id_for_slot(slot_index);
    entry.modbus_address = slot.modbus_address;
    entry.moisture_pct = entry.decoded ? sample.moisture_pct : 0.0f;
    entry.temp_c = entry.decoded ? sample.temp_c : 0.0f;
    entry.ec_us_cm = entry.decoded ? sample.ec_us_cm : 0;
    entry.ph = entry.decoded ? sample.ph : 0.0f;
    entry.modbus_status = status;
    entry.raw_frame_len = min(frame_len, MODBUS_RESPONSE_MAX);
    memcpy(entry.raw_frame, frame, entry.raw_frame_len);

    if (g_calibration.active) {
        if (entry.decoded) {
            g_calibration.sample_success_count++;
        } else {
            g_calibration.sample_failure_count++;
        }
    }
}

bool read_substrate_sample(ProbeSlot& slot, size_t slot_index) {
    uint8_t response[MODBUS_RESPONSE_MAX] = {};
    size_t len = 0;
    SubstrateSample sample;
    ModbusStatus status =
        read_measurement(slot.modbus_address, false, sample, response, sizeof(response), len);
    remember_frame(slot, response, len);
    record_sample_ring_entry(slot, slot_index, sample, status, response, len);

    if (status != ModbusStatus::Ok) {
        record_slot_modbus_failure(slot, status);
        Serial.printf("[modbus] %s addr=0x%02X status=%s len=%u\n",
                      slot.device_id,
                      slot.modbus_address,
                      modbus_status_name(status),
                      static_cast<unsigned>(len));
        return false;
    }

    slot.latest_sample = sample;
    slot.last_modbus_status = ModbusStatus::Ok;
    slot.modbus_success_count++;
    slot.sample_pending_ingest = true;
    Serial.printf("[modbus] %s addr=0x%02X moisture=%.1f%% temp=%.1fC ec=%u ph=%.1f\n",
                  slot.device_id,
                  slot.modbus_address,
                  slot.latest_sample.moisture_pct,
                  slot.latest_sample.temp_c,
                  slot.latest_sample.ec_us_cm,
                  slot.latest_sample.ph);
    return true;
}

// --- Provisioning ---------------------------------------------------------

void slot_pref_keys(size_t slot_index,
                    char* assigned_key,
                    size_t assigned_len,
                    char* addr_key,
                    size_t addr_len) {
    snprintf(assigned_key, assigned_len, "slot%u_assigned", static_cast<unsigned>(slot_index));
    snprintf(addr_key, addr_len, "slot%u_addr", static_cast<unsigned>(slot_index));
}

void load_slot_assignments() {
    Preferences prefs;
    prefs.begin(PROVISION_PREF_NAMESPACE, /*readOnly=*/false);
    uint32_t schema = prefs.getUInt("schema", 0);
    if (schema != PROVISION_PREF_SCHEMA_VERSION) {
        prefs.putUInt("schema", PROVISION_PREF_SCHEMA_VERSION);
    }

    for (size_t i = 0; i < SLOT_COUNT; i++) {
        ProbeSlot& slot = g_slots[i];
        if (!slot.provisioning_target) {
            slot.assigned = true;
            continue;
        }

        char assigned_key[16];
        char addr_key[16];
        slot_pref_keys(i, assigned_key, sizeof(assigned_key), addr_key, sizeof(addr_key));
        uint32_t stored_addr = prefs.getUInt(addr_key, slot.modbus_address);
        bool stored_assigned = prefs.getBool(assigned_key, false);
        slot.assigned = stored_assigned && stored_addr == slot.modbus_address;
    }
    prefs.end();
}

void mark_slot_assigned(size_t slot_index) {
    if (slot_index >= SLOT_COUNT) return;
    ProbeSlot& slot = g_slots[slot_index];
    Preferences prefs;
    prefs.begin(PROVISION_PREF_NAMESPACE, /*readOnly=*/false);
    char assigned_key[16];
    char addr_key[16];
    slot_pref_keys(slot_index, assigned_key, sizeof(assigned_key), addr_key, sizeof(addr_key));
    prefs.putUInt("schema", PROVISION_PREF_SCHEMA_VERSION);
    prefs.putUInt(addr_key, slot.modbus_address);
    prefs.putBool(assigned_key, true);
    prefs.end();
    slot.assigned = true;
}

bool cooldown_active(uint32_t now, uint32_t until_ms) {
    return until_ms != 0 && static_cast<int32_t>(until_ms - now) > 0;
}

uint32_t provisioning_cooldown_remaining_ms() {
    uint32_t now = millis();
    if (!cooldown_active(now, g_provisioning.cooldown_until_ms)) return 0;
    return g_provisioning.cooldown_until_ms - now;
}

int next_provisioning_target_index() {
    for (size_t i = 0; i < SLOT_COUNT; i++) {
        ProbeSlot& slot = g_slots[i];
        if (!slot.enabled || !slot.provisioning_target) continue;
        if (!slot.assigned && slot.modbus_success_count == 0) return static_cast<int>(i);
    }
    return -1;
}

bool validate_write_register_echo(const uint8_t* response,
                                  size_t len,
                                  uint8_t address,
                                  uint16_t reg,
                                  uint16_t value) {
    if (len != MODBUS_WRITE_RESPONSE_LEN) return false;
    if (response[0] != address || response[1] != 0x06) return false;
    if (read_u16_be(response + 2) != reg || read_u16_be(response + 4) != value) return false;
    uint16_t expected_crc = crc16_modbus(response, MODBUS_WRITE_RESPONSE_LEN - 2);
    uint16_t received_crc = static_cast<uint16_t>(response[6]) |
                            (static_cast<uint16_t>(response[7]) << 8);
    return expected_crc == received_crc;
}

bool write_factory_address(uint8_t target_address, size_t& len) {
    uint8_t command[MODBUS_WRITE_RESPONSE_LEN] = {};
    uint8_t response[MODBUS_RESPONSE_MAX] = {};
    build_write_register_command(
        FACTORY_DEFAULT_ADDRESS, ADDRESS_REGISTER, target_address, command, sizeof(command));
    send_command(command, sizeof(command));
    len = read_response(response, sizeof(response));
    return validate_write_register_echo(
        response, len, FACTORY_DEFAULT_ADDRESS, ADDRESS_REGISTER, target_address);
}

void service_delay(uint32_t delay_ms) {
    uint32_t start_ms = millis();
    while (millis() - start_ms < delay_ms) {
        ota::loop();
        wifi_client::maintain();
        http_server.handleClient();
        delay(5);
    }
}

void record_provisioning_failure(ProvisioningResult result) {
    g_provisioning.phase = ProvisioningPhase::Idle;
    g_provisioning.last_result = result;
    g_provisioning.failure_count++;
    g_provisioning.cooldown_until_ms = millis() + PROVISION_FAILURE_COOLDOWN_MS;
    Serial.printf("[provision] failed result=%s target=0x%02X cooldown_ms=%lu\n",
                  provisioning_result_name(result),
                  g_provisioning.last_target_address,
                  (unsigned long)PROVISION_FAILURE_COOLDOWN_MS);
}

void record_provisioning_success(size_t slot_index) {
    mark_slot_assigned(slot_index);
    g_provisioning.phase = ProvisioningPhase::Idle;
    g_provisioning.last_result = ProvisioningResult::Assigned;
    g_provisioning.success_count++;
    g_provisioning.cooldown_until_ms = millis() + PROVISION_SUCCESS_COOLDOWN_MS;
    Serial.printf("[provision] assigned %s addr=0x%02X\n",
                  g_slots[slot_index].device_id,
                  g_slots[slot_index].modbus_address);
}

void attempt_factory_provisioning() {
    uint32_t now = millis();
    if (cooldown_active(now, g_provisioning.cooldown_until_ms)) {
        g_provisioning.cooldown_skip_count++;
        return;
    }

    int target_index = next_provisioning_target_index();
    if (target_index < 0) {
        g_provisioning.last_result = ProvisioningResult::NoTarget;
        return;
    }

    ProbeSlot& target = g_slots[target_index];
    g_provisioning.attempt_count++;
    g_provisioning.last_attempt_ms = now;
    g_provisioning.last_target_slot = target_index;
    g_provisioning.last_target_address = target.modbus_address;
    g_provisioning.last_default_probe_status = ModbusStatus::Never;
    g_provisioning.last_target_verify_status = ModbusStatus::Never;

    uint8_t response[MODBUS_RESPONSE_MAX] = {};
    size_t len = 0;
    SubstrateSample default_sample;
    g_provisioning.phase = ProvisioningPhase::ProbingDefault;
    ModbusStatus default_status = read_measurement(
        FACTORY_DEFAULT_ADDRESS, true, default_sample, response, sizeof(response), len);
    g_provisioning.last_default_probe_status = default_status;
    if (default_status == ModbusStatus::NoResponse) {
        record_provisioning_failure(ProvisioningResult::NoDefaultResponse);
        return;
    }
    if (default_status != ModbusStatus::Ok) {
        record_provisioning_failure(ProvisioningResult::InvalidDefaultResponse);
        return;
    }

    size_t write_len = 0;
    g_provisioning.phase = ProvisioningPhase::WritingAddress;
    if (!write_factory_address(target.modbus_address, write_len)) {
        record_provisioning_failure(write_len == 0 ? ProvisioningResult::WriteNoResponse
                                                  : ProvisioningResult::WriteInvalidEcho);
        return;
    }

    g_provisioning.phase = ProvisioningPhase::Settling;
    service_delay(PROVISION_SETTLE_MS);

    SubstrateSample after_write_default_sample;
    g_provisioning.phase = ProvisioningPhase::VerifyingDefault;
    default_status = read_measurement(
        FACTORY_DEFAULT_ADDRESS, true, after_write_default_sample, response, sizeof(response), len);
    g_provisioning.last_default_probe_status = default_status;
    if (default_status == ModbusStatus::Ok) {
        record_provisioning_failure(ProvisioningResult::DefaultStillResponding);
        return;
    }

    SubstrateSample target_sample;
    g_provisioning.phase = ProvisioningPhase::VerifyingTarget;
    ModbusStatus target_status =
        read_measurement(target.modbus_address, true, target_sample, response, sizeof(response), len);
    remember_frame(target, response, len);
    g_provisioning.last_target_verify_status = target_status;
    if (target_status != ModbusStatus::Ok) {
        record_slot_modbus_failure(target, target_status);
        record_provisioning_failure(ProvisioningResult::TargetVerifyFailed);
        return;
    }

    target.latest_sample = target_sample;
    target.last_modbus_status = ModbusStatus::Ok;
    target.modbus_success_count++;
    record_provisioning_success(static_cast<size_t>(target_index));
}

// --- JSON helpers ---------------------------------------------------------

bool appendf(char* out, size_t out_len, size_t& pos, const char* fmt, ...) {
    if (pos >= out_len) return false;

    va_list args;
    va_start(args, fmt);
    int written = vsnprintf(out + pos, out_len - pos, fmt, args);
    va_end(args);

    if (written < 0) return false;
    if (static_cast<size_t>(written) >= out_len - pos) {
        pos = out_len;
        return false;
    }
    pos += static_cast<size_t>(written);
    return true;
}

void append_bytes_hex(const uint8_t* data, size_t len, char* out, size_t out_len) {
    size_t pos = 0;
    for (size_t i = 0; i < len && pos + 3 <= out_len; i++) {
        int written = snprintf(out + pos, out_len - pos, "%02X", data[i]);
        if (written <= 0) break;
        pos += static_cast<size_t>(written);
    }
    if (out_len > 0) {
        out[min(pos, out_len - 1)] = '\0';
    }
}

void append_frame_hex(const ProbeSlot& slot, char* out, size_t out_len) {
    append_bytes_hex(slot.last_frame, slot.last_frame_len, out, out_len);
}

void send_contentf(const char* fmt, ...) {
    char chunk[1024];
    va_list args;
    va_start(args, fmt);
    vsnprintf(chunk, sizeof(chunk), fmt, args);
    va_end(args);
    http_server.sendContent(chunk);
}

void build_diagnostics(char* out, size_t out_len) {
    uint32_t modbus_success_count = 0;
    uint32_t modbus_failure_count = 0;
    uint32_t modbus_crc_mismatch_count = 0;
    uint32_t modbus_short_response_count = 0;
    uint32_t modbus_no_response_count = 0;
    uint32_t ingest_ok_count = 0;
    uint32_t ingest_fail_count = 0;

    for (size_t i = 0; i < SLOT_COUNT; i++) {
        const ProbeSlot& slot = g_slots[i];
        modbus_success_count += slot.modbus_success_count;
        modbus_failure_count += slot.modbus_failure_count;
        modbus_crc_mismatch_count += slot.modbus_crc_mismatch_count;
        modbus_short_response_count += slot.modbus_short_response_count;
        modbus_no_response_count += slot.modbus_no_response_count;
        ingest_ok_count += slot.ingest_ok_count;
        ingest_fail_count += slot.ingest_fail_count;
    }

    snprintf(out, out_len,
             "{\"boot_count\":%lu,"
             "\"reset_reason\":%u,"
             "\"modbus_success_count\":%lu,"
             "\"modbus_failure_count\":%lu,"
             "\"modbus_crc_mismatch_count\":%lu,"
             "\"modbus_short_response_count\":%lu,"
             "\"modbus_no_response_count\":%lu,"
             "\"last_modbus_response_len\":%u,"
             "\"last_ingest_code\":%d,"
             "\"ingest_ok_count\":%lu,"
             "\"ingest_fail_count\":%lu,"
             "\"free_heap_bytes\":%lu,"
             "\"min_free_heap_bytes\":%lu,"
             "\"loop_gap_max_ms\":%lu}",
             (unsigned long)g_boot_count,
             (unsigned int)g_reset_reason,
             (unsigned long)modbus_success_count,
             (unsigned long)modbus_failure_count,
             (unsigned long)modbus_crc_mismatch_count,
             (unsigned long)modbus_short_response_count,
             (unsigned long)modbus_no_response_count,
             static_cast<unsigned>(g_last_modbus_response_len),
             g_last_ingest_code,
             (unsigned long)ingest_ok_count,
             (unsigned long)ingest_fail_count,
             (unsigned long)ESP.getFreeHeap(),
             (unsigned long)ESP.getMinFreeHeap(),
             (unsigned long)g_loop_gap_max_ms);
}

bool build_calibration_mode_json(char* out, size_t out_len) {
    uint32_t remaining_ms = calibration_remaining_ms();
    size_t pos = 0;
    return appendf(out, out_len, pos,
                   "{\"active\":%s,"
                   "\"started_ms\":%lu,"
                   "\"expires_ms\":%lu,"
                   "\"remaining_ms\":%lu,"
                   "\"interval_ms\":%lu,"
                   "\"normal_measurement_interval_ms\":%lu,"
                   "\"ingest_interval_ms\":%lu,"
                   "\"counters\":{"
                   "\"start_count\":%lu,"
                   "\"stop_count\":%lu,"
                   "\"auto_expire_count\":%lu,"
                   "\"measurement_cycle_count\":%lu,"
                   "\"sample_success_count\":%lu,"
                   "\"sample_failure_count\":%lu"
                   "}}",
                   g_calibration.active ? "true" : "false",
                   (unsigned long)g_calibration.started_ms,
                   (unsigned long)g_calibration.expires_ms,
                   (unsigned long)remaining_ms,
                   (unsigned long)g_calibration.interval_ms,
                   (unsigned long)CONFIG_NORMAL_MEASUREMENT_INTERVAL_MS,
                   (unsigned long)CONFIG_INGEST_INTERVAL_MS,
                   (unsigned long)g_calibration.start_count,
                   (unsigned long)g_calibration.stop_count,
                   (unsigned long)g_calibration.auto_expire_count,
                   (unsigned long)g_calibration.measurement_cycle_count,
                   (unsigned long)g_calibration.sample_success_count,
                   (unsigned long)g_calibration.sample_failure_count);
}

void build_sample_json(const ProbeSlot& slot, char* out, size_t out_len) {
    if (!slot.latest_sample.valid) {
        snprintf(out, out_len, "null");
        return;
    }
    snprintf(out, out_len,
             "{\"soil_moisture_pct\":%.1f,"
             "\"substrate_temp_c\":%.1f,"
             "\"substrate_ec_us_cm\":%u,"
             "\"substrate_ph\":%.1f,"
             "\"age_ms\":%lu}",
             slot.latest_sample.moisture_pct,
             slot.latest_sample.temp_c,
             slot.latest_sample.ec_us_cm,
             slot.latest_sample.ph,
             (unsigned long)(millis() - slot.latest_sample.read_ms));
}

const char* provisioning_state_name() {
    if (provisioning_cooldown_remaining_ms() > 0) return "cooldown";
    return provisioning_phase_name(g_provisioning.phase);
}

bool build_provisioning_json(char* out, size_t out_len) {
    uint32_t cooldown_ms = provisioning_cooldown_remaining_ms();
    size_t pos = 0;
    if (!appendf(
            out, out_len, pos,
            "{\"state\":\"%s\","
            "\"schema_version\":%lu,"
            "\"factory_default_address\":\"0x%02X\","
            "\"address_register\":\"0x%04X\","
            "\"last_result\":\"%s\","
            "\"cooldown_ms_remaining\":%lu,"
            "\"attempt_count\":%lu,"
            "\"success_count\":%lu,"
            "\"failure_count\":%lu,"
            "\"cooldown_skip_count\":%lu,"
            "\"last_default_probe_status\":\"%s\","
            "\"last_target_verify_status\":\"%s\","
            "\"last_target\":",
            provisioning_state_name(),
            (unsigned long)PROVISION_PREF_SCHEMA_VERSION,
            FACTORY_DEFAULT_ADDRESS,
            ADDRESS_REGISTER,
            provisioning_result_name(g_provisioning.last_result),
            (unsigned long)cooldown_ms,
            (unsigned long)g_provisioning.attempt_count,
            (unsigned long)g_provisioning.success_count,
            (unsigned long)g_provisioning.failure_count,
            (unsigned long)g_provisioning.cooldown_skip_count,
            modbus_status_name(g_provisioning.last_default_probe_status),
            modbus_status_name(g_provisioning.last_target_verify_status))) {
        return false;
    }

    if (g_provisioning.last_target_slot >= 0 &&
        static_cast<size_t>(g_provisioning.last_target_slot) < SLOT_COUNT) {
        const ProbeSlot& target = g_slots[g_provisioning.last_target_slot];
        if (!appendf(out, out_len, pos,
                     "{\"plant_label\":\"%s\","
                     "\"device_id\":\"%s\","
                     "\"address\":\"0x%02X\"}",
                     target.plant_label,
                     target.device_id,
                     target.modbus_address)) {
            return false;
        }
    } else {
        if (!appendf(out, out_len, pos, "null")) return false;
    }
    return appendf(out, out_len, pos, "}");
}

bool is_slot_failing(const ProbeSlot& slot) {
    if (!slot.enabled) return false;
    return slot.last_modbus_status != ModbusStatus::Never &&
           slot.last_modbus_status != ModbusStatus::Ok;
}

bool any_enabled_slot_failing() {
    for (size_t i = 0; i < SLOT_COUNT; i++) {
        if (is_slot_failing(g_slots[i])) return true;
    }
    return false;
}

size_t enabled_slot_count() {
    size_t count = 0;
    for (size_t i = 0; i < SLOT_COUNT; i++) {
        if (g_slots[i].enabled) count++;
    }
    return count;
}

bool append_slots_json(char* out, size_t out_len, size_t& pos) {
    if (!appendf(out, out_len, pos, "[")) return false;
    for (size_t i = 0; i < SLOT_COUNT; i++) {
        const ProbeSlot& slot = g_slots[i];
        char sample[192];
        char frame_hex[MODBUS_RESPONSE_MAX * 2 + 1];
        build_sample_json(slot, sample, sizeof(sample));
        append_frame_hex(slot, frame_hex, sizeof(frame_hex));

        if (i > 0 && !appendf(out, out_len, pos, ",")) return false;
        if (!appendf(
                out, out_len, pos,
                "{\"plant_label\":\"%s\","
                "\"probe_id\":%u,"
                "\"device_id\":\"%s\","
                "\"modbus_address\":\"0x%02X\","
                "\"enabled\":%s,"
                "\"assigned\":%s,"
                "\"provisioning_target\":%s,"
                "\"sample_ring_count\":%u,"
                "\"latest_sample\":%s,"
                "\"latest_raw_modbus_frame_hex\":\"%s\","
                "\"last_modbus_status\":\"%s\","
                "\"last_ingest_status\":{"
                "\"code\":%d,"
                "\"ok_count\":%lu,"
                "\"fail_count\":%lu"
                "},"
                "\"modbus_counters\":{"
                "\"success_count\":%lu,"
                "\"failure_count\":%lu,"
                "\"crc_mismatch_count\":%lu,"
                "\"short_response_count\":%lu,"
                "\"no_response_count\":%lu,"
                "\"bad_header_count\":%lu"
                "}}",
                slot.plant_label,
                probe_id_for_slot(i),
                slot.device_id,
                slot.modbus_address,
                slot.enabled ? "true" : "false",
                slot.assigned ? "true" : "false",
                slot.provisioning_target ? "true" : "false",
                static_cast<unsigned>(slot.sample_count),
                sample,
                frame_hex,
                modbus_status_name(slot.last_modbus_status),
                slot.last_ingest_code,
                (unsigned long)slot.ingest_ok_count,
                (unsigned long)slot.ingest_fail_count,
                (unsigned long)slot.modbus_success_count,
                (unsigned long)slot.modbus_failure_count,
                (unsigned long)slot.modbus_crc_mismatch_count,
                (unsigned long)slot.modbus_short_response_count,
                (unsigned long)slot.modbus_no_response_count,
                (unsigned long)slot.modbus_bad_header_count)) {
            return false;
        }
    }
    return appendf(out, out_len, pos, "]");
}

bool build_status_json(char* out, size_t out_len) {
    wifi_client::Snapshot wifi = wifi_client::snapshot();
    char diagnostics[512];
    char calibration[640];
    char provisioning[768];
    build_diagnostics(diagnostics, sizeof(diagnostics));
    if (!build_calibration_mode_json(calibration, sizeof(calibration))) return false;
    if (!build_provisioning_json(provisioning, sizeof(provisioning))) return false;

    size_t pos = 0;
    if (!appendf(
            out, out_len, pos,
            "{\"controller\":{"
            "\"device_id\":\"%s\","
            "\"hostname\":\"%s\","
            "\"slot_count\":%u,"
            "\"enabled_slot_count\":%u,"
            "\"any_enabled_slot_failing\":%s,"
            "\"normal_measurement_interval_ms\":%lu,"
            "\"ingest_interval_ms\":%lu"
            "},"
            "\"firmware_version\":\"%s\","
            "\"calibration_mode\":%s,"
            "\"wifi\":{"
            "\"connected\":%s,"
            "\"ip\":\"%s\","
            "\"rssi_dbm\":%d,"
            "\"reconnect_count\":%lu,"
            "\"driver_reset_count\":%lu,"
            "\"last_disconnect_reason\":%u,"
            "\"disconnected_for_ms\":%lu"
            "},"
            "\"diagnostics\":%s,"
            "\"provisioning\":%s,"
            "\"slots\":",
            CONTROLLER_DEVICE_ID,
            HOSTNAME,
            static_cast<unsigned>(SLOT_COUNT),
            static_cast<unsigned>(enabled_slot_count()),
            any_enabled_slot_failing() ? "true" : "false",
            (unsigned long)CONFIG_NORMAL_MEASUREMENT_INTERVAL_MS,
            (unsigned long)CONFIG_INGEST_INTERVAL_MS,
            FIRMWARE_VERSION,
            calibration,
            wifi.connected ? "true" : "false",
            WiFi.localIP().toString().c_str(),
            wifi.rssi_dbm,
            (unsigned long)wifi.reconnect_count,
            (unsigned long)wifi.driver_reset_count,
            wifi.last_disconnect_reason,
            (unsigned long)wifi.disconnected_for_ms,
            diagnostics,
            provisioning)) {
        return false;
    }
    if (!append_slots_json(out, out_len, pos)) return false;
    return appendf(out, out_len, pos, "}");
}

// --- HTTP -----------------------------------------------------------------

void send_json_error(int status_code, const char* message) {
    char resp[160];
    snprintf(resp, sizeof(resp), "{\"error\":\"%s\"}", message);
    http_server.send(status_code, "application/json", resp);
}

bool parse_uint_query_arg(const char* name,
                          uint32_t default_value,
                          uint32_t min_value,
                          uint32_t max_value,
                          uint32_t& value,
                          char* error,
                          size_t error_len) {
    if (!http_server.hasArg(name)) {
        value = default_value;
        return true;
    }

    String raw = http_server.arg(name);
    if (raw.length() == 0) {
        snprintf(error, error_len, "%s is required", name);
        return false;
    }
    for (unsigned int i = 0; i < raw.length(); i++) {
        char ch = raw.charAt(i);
        if (ch < '0' || ch > '9') {
            snprintf(error, error_len, "%s must be an integer", name);
            return false;
        }
    }

    uint32_t parsed = static_cast<uint32_t>(strtoul(raw.c_str(), nullptr, 10));
    if (parsed < min_value || parsed > max_value) {
        snprintf(error,
                 error_len,
                 "%s must be between %lu and %lu",
                 name,
                 (unsigned long)min_value,
                 (unsigned long)max_value);
        return false;
    }
    value = parsed;
    return true;
}

void send_calibration_mode_response(const char* state) {
    char calibration[640];
    char resp[768];
    if (!build_calibration_mode_json(calibration, sizeof(calibration))) {
        send_json_error(500, "calibration response too large");
        return;
    }
    snprintf(resp,
             sizeof(resp),
             "{\"ok\":true,\"state\":\"%s\",\"calibration_mode\":%s}",
             state,
             calibration);
    http_server.send(200, "application/json", resp);
}

void handle_calibration_start() {
    uint32_t duration_s = CALIBRATION_DURATION_DEFAULT_S;
    uint32_t interval_ms = CONFIG_CALIBRATION_MEASUREMENT_INTERVAL_MS;
    char error[120];
    if (!parse_uint_query_arg("duration_s",
                              CALIBRATION_DURATION_DEFAULT_S,
                              CALIBRATION_DURATION_MIN_S,
                              CALIBRATION_DURATION_MAX_S,
                              duration_s,
                              error,
                              sizeof(error)) ||
        !parse_uint_query_arg("interval_ms",
                              CONFIG_CALIBRATION_MEASUREMENT_INTERVAL_MS,
                              CALIBRATION_INTERVAL_MIN_MS,
                              CALIBRATION_INTERVAL_MAX_MS,
                              interval_ms,
                              error,
                              sizeof(error))) {
        send_json_error(400, error);
        return;
    }

    uint32_t now = millis();
    g_calibration.active = true;
    g_calibration.started_ms = now;
    g_calibration.expires_ms = now + (duration_s * 1000UL);
    g_calibration.interval_ms = interval_ms;
    g_calibration.start_count++;
    g_last_measurement_ms = 0;

    Serial.printf("[calibration] started duration_s=%lu interval_ms=%lu\n",
                  (unsigned long)duration_s,
                  (unsigned long)interval_ms);
    send_calibration_mode_response("started");
}

void handle_calibration_stop() {
    g_calibration.active = false;
    g_calibration.stop_count++;
    Serial.println("[calibration] stopped");
    send_calibration_mode_response("stopped");
}

size_t ring_start_index(const ProbeSlot& slot) {
    if (slot.sample_count < SAMPLE_RING_CAPACITY) return 0;
    return slot.sample_next;
}

bool sample_within_window(const SampleRingEntry& entry, uint32_t now, uint32_t window_ms) {
    if (!entry.used) return false;
    return now - entry.read_ms <= window_ms;
}

size_t count_recent_samples(const ProbeSlot& slot, uint32_t now, uint32_t window_ms) {
    size_t count = 0;
    size_t start = ring_start_index(slot);
    for (size_t i = 0; i < slot.sample_count; i++) {
        size_t index = (start + i) % SAMPLE_RING_CAPACITY;
        if (sample_within_window(slot.samples[index], now, window_ms)) {
            count++;
        }
    }
    return count;
}

void send_ring_entry_json(const SampleRingEntry& entry) {
    char frame_hex[MODBUS_RESPONSE_MAX * 2 + 1];
    append_bytes_hex(entry.raw_frame, entry.raw_frame_len, frame_hex, sizeof(frame_hex));

    if (entry.decoded) {
        send_contentf("{\"seq\":%lu,"
                      "\"read_ms\":%lu,"
                      "\"probe_id\":%u,"
                      "\"modbus_address\":\"0x%02X\","
                      "\"modbus_status\":\"%s\","
                      "\"valid\":true,"
                      "\"soil_moisture_pct\":%.1f,"
                      "\"substrate_temp_c\":%.1f,"
                      "\"substrate_ec_us_cm\":%u,"
                      "\"substrate_ph\":%.1f,"
                      "\"raw_modbus_frame_hex\":\"%s\"}",
                      (unsigned long)entry.seq,
                      (unsigned long)entry.read_ms,
                      entry.probe_id,
                      entry.modbus_address,
                      modbus_status_name(entry.modbus_status),
                      entry.moisture_pct,
                      entry.temp_c,
                      entry.ec_us_cm,
                      entry.ph,
                      frame_hex);
        return;
    }

    send_contentf("{\"seq\":%lu,"
                  "\"read_ms\":%lu,"
                  "\"probe_id\":%u,"
                  "\"modbus_address\":\"0x%02X\","
                  "\"modbus_status\":\"%s\","
                  "\"valid\":false,"
                  "\"soil_moisture_pct\":null,"
                  "\"substrate_temp_c\":null,"
                  "\"substrate_ec_us_cm\":null,"
                  "\"substrate_ph\":null,"
                  "\"raw_modbus_frame_hex\":\"%s\"}",
                  (unsigned long)entry.seq,
                  (unsigned long)entry.read_ms,
                  entry.probe_id,
                  entry.modbus_address,
                  modbus_status_name(entry.modbus_status),
                  frame_hex);
}

void send_slot_samples_json(const ProbeSlot& slot,
                            size_t slot_index,
                            uint32_t now,
                            uint32_t window_ms) {
    size_t returned_count = count_recent_samples(slot, now, window_ms);
    send_contentf("{\"probe_id\":%u,"
                  "\"device_id\":\"%s\","
                  "\"modbus_address\":\"0x%02X\","
                  "\"enabled\":%s,"
                  "\"ring_capacity\":%u,"
                  "\"ring_sample_count\":%u,"
                  "\"returned_sample_count\":%u,"
                  "\"samples\":[",
                  probe_id_for_slot(slot_index),
                  slot.device_id,
                  slot.modbus_address,
                  slot.enabled ? "true" : "false",
                  static_cast<unsigned>(SAMPLE_RING_CAPACITY),
                  static_cast<unsigned>(slot.sample_count),
                  static_cast<unsigned>(returned_count));

    bool first = true;
    size_t start = ring_start_index(slot);
    for (size_t i = 0; i < slot.sample_count; i++) {
        size_t index = (start + i) % SAMPLE_RING_CAPACITY;
        const SampleRingEntry& entry = slot.samples[index];
        if (!sample_within_window(entry, now, window_ms)) continue;
        if (!first) {
            http_server.sendContent(",");
        }
        send_ring_entry_json(entry);
        first = false;
    }
    http_server.sendContent("]}");
}

void handle_samples() {
    uint32_t window_s = SAMPLES_WINDOW_DEFAULT_S;
    char error[120];
    if (!parse_uint_query_arg("window_s",
                              SAMPLES_WINDOW_DEFAULT_S,
                              SAMPLES_WINDOW_MIN_S,
                              SAMPLES_WINDOW_MAX_S,
                              window_s,
                              error,
                              sizeof(error))) {
        send_json_error(400, error);
        return;
    }

    char calibration[640];
    if (!build_calibration_mode_json(calibration, sizeof(calibration))) {
        send_json_error(500, "samples response too large");
        return;
    }

    uint32_t now = millis();
    uint32_t window_ms = window_s * 1000UL;
    http_server.setContentLength(CONTENT_LENGTH_UNKNOWN);
    http_server.send(200, "application/json", "");
    send_contentf("{\"controller\":{"
                  "\"device_id\":\"%s\","
                  "\"hostname\":\"%s\","
                  "\"firmware_version\":\"%s\","
                  "\"read_ms\":%lu,"
                  "\"window_s\":%lu,"
                  "\"calibration_mode\":%s"
                  "},"
                  "\"slots\":[",
                  CONTROLLER_DEVICE_ID,
                  HOSTNAME,
                  FIRMWARE_VERSION,
                  (unsigned long)now,
                  (unsigned long)window_s,
                  calibration);

    for (size_t i = 0; i < SLOT_COUNT; i++) {
        if (i > 0) {
            http_server.sendContent(",");
        }
        send_slot_samples_json(g_slots[i], i, now, window_ms);
    }
    http_server.sendContent("]}");
    http_server.sendContent("");
}

void handle_health() {
    bool failing = any_enabled_slot_failing();
    char resp[128];
    snprintf(resp, sizeof(resp),
             "{\"ok\":%s,\"any_enabled_slot_failing\":%s,\"last_ingest_code\":%d}",
             failing ? "false" : "true",
             failing ? "true" : "false",
             g_last_ingest_code);
    http_server.send(200, "application/json", resp);
}

void handle_status() {
    static char resp[6144];
    if (!build_status_json(resp, sizeof(resp))) {
        http_server.send(500, "application/json", "{\"error\":\"status too large\"}");
        return;
    }
    http_server.send(200, "application/json", resp);
}

void handle_not_found() {
    http_server.send(404, "application/json", "{\"error\":\"not found\"}");
}

// --- Sensor cycle ---------------------------------------------------------

void post_latest_sample(ProbeSlot& slot) {
    char metrics[160];
    snprintf(metrics, sizeof(metrics),
             "{\"soil_moisture_pct\":%.1f,"
             "\"substrate_temp_c\":%.1f,"
             "\"substrate_ec_us_cm\":%u,"
             "\"substrate_ph\":%.1f}",
             slot.latest_sample.moisture_pct,
             slot.latest_sample.temp_c,
             slot.latest_sample.ec_us_cm,
             slot.latest_sample.ph);

    char diagnostics[512];
    build_diagnostics(diagnostics, sizeof(diagnostics));
    int code = ingest.post(slot.device_id, metrics, diagnostics);
    slot.last_ingest_code = code;
    g_last_ingest_code = code;
    if (code > 0) {
        slot.ingest_ok_count++;
    } else {
        slot.ingest_fail_count++;
    }
    Serial.printf("[ingest] %s http=%d ok=%lu fail=%lu\n",
                  slot.device_id,
                  code,
                  (unsigned long)slot.ingest_ok_count,
                  (unsigned long)slot.ingest_fail_count);
}

void measure_sensors_if_due() {
    uint32_t now = millis();
    uint32_t interval_ms = current_measurement_interval_ms();
    if (g_last_measurement_ms != 0 && now - g_last_measurement_ms < interval_ms) {
        return;
    }
    g_last_measurement_ms = now;
    bool calibration_active = g_calibration.active;
    if (calibration_active) {
        g_calibration.measurement_cycle_count++;
    }

    for (size_t i = 0; i < SLOT_COUNT; i++) {
        ProbeSlot& slot = g_slots[i];
        if (!slot.enabled) continue;
        if (read_substrate_sample(slot, i)) {
            if (slot.provisioning_target && !slot.assigned) {
                mark_slot_assigned(i);
            }
        }
    }
}

void ingest_latest_samples_if_due() {
    uint32_t now = millis();
    if (g_last_ingest_ms != 0 && now - g_last_ingest_ms < CONFIG_INGEST_INTERVAL_MS) {
        return;
    }
    g_last_ingest_ms = now;

    for (size_t i = 0; i < SLOT_COUNT; i++) {
        ProbeSlot& slot = g_slots[i];
        if (!slot.enabled || !slot.sample_pending_ingest || !slot.latest_sample.valid) continue;
        post_latest_sample(slot);
        slot.sample_pending_ingest = false;
    }
}

void attempt_factory_provisioning_if_due() {
    uint32_t now = millis();
    if (g_last_provisioning_ms != 0 &&
        now - g_last_provisioning_ms < CONFIG_NORMAL_MEASUREMENT_INTERVAL_MS) {
        return;
    }
    g_last_provisioning_ms = now;
    attempt_factory_provisioning();
}

void record_loop_gap() {
    uint32_t now = millis();
    if (g_loop_last_ms != 0) {
        uint32_t gap = now - g_loop_last_ms;
        if (gap > g_loop_gap_max_ms) {
            g_loop_gap_max_ms = gap;
        }
    }
    g_loop_last_ms = now;
}

// --- Lifecycle ------------------------------------------------------------

void setup() {
    Serial.begin(115200);
    delay(200);

    g_reset_reason = esp_reset_reason();
    Preferences diag_prefs;
    diag_prefs.begin("node_diag", /*readOnly=*/false);
    g_boot_count = diag_prefs.getUInt("boot_count", 0) + 1;
    diag_prefs.putUInt("boot_count", g_boot_count);
    diag_prefs.end();
    load_slot_assignments();

    pinMode(RS485_ENABLE_PIN, OUTPUT);
    digitalWrite(RS485_ENABLE_PIN, LOW);
    rs485.begin(SENSOR_BAUD, SERIAL_8N1, RS485_RX_PIN, RS485_TX_PIN);

    Serial.println();
    Serial.println("# rs485-substrate-node");
    Serial.printf("# fw=%s controller=%s host=%s slots=%u normal_measurement_interval=%lums "
                  "calibration_measurement_interval=%lums ingest_interval=%lums\n",
                  FIRMWARE_VERSION,
                  CONTROLLER_DEVICE_ID,
                  HOSTNAME,
                  static_cast<unsigned>(SLOT_COUNT),
                  (unsigned long)CONFIG_NORMAL_MEASUREMENT_INTERVAL_MS,
                  (unsigned long)CONFIG_CALIBRATION_MEASUREMENT_INTERVAL_MS,
                  (unsigned long)CONFIG_INGEST_INTERVAL_MS);
    for (size_t i = 0; i < SLOT_COUNT; i++) {
        const ProbeSlot& slot = g_slots[i];
        Serial.printf("# slot %s zone=%s device=%s address=0x%02X enabled=%s assigned=%s target=%s\n",
                      slot.plant_label,
                      slot.zone_id,
                      slot.device_id,
                      slot.modbus_address,
                      slot.enabled ? "true" : "false",
                      slot.assigned ? "true" : "false",
                      slot.provisioning_target ? "true" : "false");
    }
    Serial.printf("# uart=%lu 8N1 rx_gpio=%d tx_gpio=%d enable_pin=D2\n",
                  (unsigned long)SENSOR_BAUD,
                  RS485_RX_PIN,
                  RS485_TX_PIN);
    Serial.printf("# boot count=%lu reset_reason=%u free_heap=%lu\n",
                  (unsigned long)g_boot_count,
                  (unsigned int)g_reset_reason,
                  (unsigned long)ESP.getFreeHeap());

    wifi_client::begin(WIFI_SSID, WIFI_PASSWORD, HOSTNAME);
    ota::begin(HOSTNAME, OTA_PASSWORD);

    http_server.on("/health", HTTP_GET, handle_health);
    http_server.on("/status", HTTP_GET, handle_status);
    http_server.on("/calibration/start", HTTP_POST, handle_calibration_start);
    http_server.on("/calibration/stop", HTTP_POST, handle_calibration_stop);
    http_server.on("/samples", HTTP_GET, handle_samples);
    http_server.onNotFound(handle_not_found);
    http_server.begin();
    Serial.println("[boot] http status surface up on :80 "
                   "(GET /health, GET /status, GET /samples, POST /calibration/start, "
                   "POST /calibration/stop)");
}

void loop() {
    record_loop_gap();
    ota::loop();
    wifi_client::maintain();
    http_server.handleClient();
    measure_sensors_if_due();
    ingest_latest_samples_if_due();
    attempt_factory_provisioning_if_due();
    delay(10);
}
