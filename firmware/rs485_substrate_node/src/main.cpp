// Seeed XIAO ESP32-C3 RS485 substrate node.
//
// Reads a DFRobot SEN0604 substrate sensor over the Seeed RS485 expansion
// board and posts direct Plant A substrate metrics. Runtime observability is
// LAN-first: OTA, GET /health, and GET /status must work without USB serial.

#include <Arduino.h>
#include <Preferences.h>
#include <WebServer.h>
#include <WiFi.h>
#include <esp_system.h>

#include "ingest_client.h"
#include "ota.h"
#include "secrets.h"
#include "wifi_client.h"

// --- Config ---------------------------------------------------------------

#ifndef NODE_SITE_ID
#define NODE_SITE_ID "homebox"
#endif
#ifndef NODE_TENT_ID
#define NODE_TENT_ID "main"
#endif
#ifndef NODE_ZONE_ID
#define NODE_ZONE_ID "plant-a"
#endif
#ifndef NODE_DEVICE_ID
#define NODE_DEVICE_ID "plant-a-substrate-node"
#endif
#ifndef NODE_HOSTNAME
#define NODE_HOSTNAME "plant-a-substrate-node"
#endif
#ifndef MODBUS_ADDRESS
#define MODBUS_ADDRESS 0x02
#endif
#ifndef POST_INTERVAL_MS
#define POST_INTERVAL_MS 30000
#endif

constexpr int RS485_RX_PIN = 7;
constexpr int RS485_TX_PIN = 6;
constexpr int RS485_ENABLE_PIN = D2;
constexpr uint32_t SENSOR_BAUD = 9600;
constexpr uint32_t RESPONSE_TIMEOUT_MS = 700;
constexpr size_t MODBUS_RESPONSE_MAX = 32;
constexpr size_t MODBUS_MEASUREMENT_LEN = 13;

constexpr const char* SITE_ID = NODE_SITE_ID;
constexpr const char* TENT_ID = NODE_TENT_ID;
constexpr const char* ZONE_ID = NODE_ZONE_ID;
constexpr const char* DEVICE_ID = NODE_DEVICE_ID;
constexpr const char* HOSTNAME = NODE_HOSTNAME;
constexpr uint8_t SENSOR_ADDRESS = MODBUS_ADDRESS;
constexpr uint32_t POLL_INTERVAL_MS = POST_INTERVAL_MS;

// --- State ----------------------------------------------------------------

enum class ModbusStatus {
    Never,
    Ok,
    NoResponse,
    ShortResponse,
    CrcMismatch,
    BadHeader,
};

struct SubstrateSample {
    bool valid = false;
    float moisture_pct = 0.0f;
    float temp_c = 0.0f;
    uint16_t ec_us_cm = 0;
    float ph = 0.0f;
    uint32_t read_ms = 0;
};

HardwareSerial rs485(1);
WebServer http_server(80);
IngestClient ingest(SERVER_URL, SENSOR_INGEST_TOKEN, FIRMWARE_VERSION);

SubstrateSample g_latest_sample;
uint8_t g_last_frame[MODBUS_RESPONSE_MAX] = {};
size_t g_last_frame_len = 0;
ModbusStatus g_last_modbus_status = ModbusStatus::Never;

uint32_t g_last_poll_ms = 0;
uint32_t g_loop_last_ms = 0;
uint32_t g_loop_gap_max_ms = 0;
uint32_t g_boot_count = 0;
esp_reset_reason_t g_reset_reason = ESP_RST_UNKNOWN;

uint32_t g_modbus_success_count = 0;
uint32_t g_modbus_failure_count = 0;
uint32_t g_modbus_crc_mismatch_count = 0;
uint32_t g_modbus_short_response_count = 0;
uint32_t g_modbus_no_response_count = 0;

uint32_t g_ingest_ok_count = 0;
uint32_t g_ingest_fail_count = 0;
int g_last_ingest_code = 0;

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

void build_read_command(uint8_t* command, size_t len) {
    if (len < 8) return;
    command[0] = SENSOR_ADDRESS;
    command[1] = 0x03;
    command[2] = 0x00;
    command[3] = 0x00;
    command[4] = 0x00;
    command[5] = 0x04;
    uint16_t crc = crc16_modbus(command, 6);
    command[6] = crc & 0xFF;
    command[7] = crc >> 8;
}

void remember_frame(const uint8_t* data, size_t len) {
    g_last_frame_len = min(len, MODBUS_RESPONSE_MAX);
    memcpy(g_last_frame, data, g_last_frame_len);
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

size_t read_response(uint8_t* response, size_t max_len) {
    size_t len = 0;
    uint32_t start_ms = millis();
    while (millis() - start_ms < RESPONSE_TIMEOUT_MS && len < max_len) {
        while (rs485.available() > 0 && len < max_len) {
            response[len++] = static_cast<uint8_t>(rs485.read());
            start_ms = millis();
        }
        ota::loop();
        wifi_client::maintain();
        http_server.handleClient();
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
        case ModbusStatus::Never:
        default:
            return "never";
    }
}

bool read_substrate_sample() {
    uint8_t command[8] = {};
    build_read_command(command, sizeof(command));
    send_command(command, sizeof(command));

    uint8_t response[MODBUS_RESPONSE_MAX] = {};
    size_t len = read_response(response, sizeof(response));
    remember_frame(response, len);

    if (len == 0) {
        g_last_modbus_status = ModbusStatus::NoResponse;
        g_modbus_no_response_count++;
        g_modbus_failure_count++;
        Serial.println("[modbus] no response");
        return false;
    }

    if (len < MODBUS_MEASUREMENT_LEN) {
        g_last_modbus_status = ModbusStatus::ShortResponse;
        g_modbus_short_response_count++;
        g_modbus_failure_count++;
        Serial.printf("[modbus] short response len=%u\n", static_cast<unsigned>(len));
        return false;
    }

    if (response[0] != SENSOR_ADDRESS || response[1] != 0x03 || response[2] != 0x08) {
        g_last_modbus_status = ModbusStatus::BadHeader;
        g_modbus_failure_count++;
        Serial.printf("[modbus] bad header addr=0x%02X fn=0x%02X bytes=%u\n",
                      response[0], response[1], response[2]);
        return false;
    }

    uint16_t expected_crc = crc16_modbus(response, MODBUS_MEASUREMENT_LEN - 2);
    uint16_t received_crc = static_cast<uint16_t>(response[11]) |
                            (static_cast<uint16_t>(response[12]) << 8);
    if (expected_crc != received_crc) {
        g_last_modbus_status = ModbusStatus::CrcMismatch;
        g_modbus_crc_mismatch_count++;
        g_modbus_failure_count++;
        Serial.printf("[modbus] crc mismatch expected=%04X received=%04X\n",
                      expected_crc, received_crc);
        return false;
    }

    uint16_t moisture_raw = read_u16_be(response + 3);
    int16_t temp_raw = static_cast<int16_t>(read_u16_be(response + 5));
    uint16_t ec_raw = read_u16_be(response + 7);
    uint16_t ph_raw = read_u16_be(response + 9);

    g_latest_sample.valid = true;
    g_latest_sample.moisture_pct = moisture_raw / 10.0f;
    g_latest_sample.temp_c = temp_raw / 10.0f;
    g_latest_sample.ec_us_cm = ec_raw;
    g_latest_sample.ph = ph_raw / 10.0f;
    g_latest_sample.read_ms = millis();

    g_last_modbus_status = ModbusStatus::Ok;
    g_modbus_success_count++;
    Serial.printf("[modbus] moisture=%.1f%% temp=%.1fC ec=%u ph=%.1f\n",
                  g_latest_sample.moisture_pct,
                  g_latest_sample.temp_c,
                  g_latest_sample.ec_us_cm,
                  g_latest_sample.ph);
    return true;
}

// --- JSON helpers ---------------------------------------------------------

void append_frame_hex(char* out, size_t out_len) {
    size_t pos = 0;
    for (size_t i = 0; i < g_last_frame_len && pos + 3 <= out_len; i++) {
        int written = snprintf(out + pos, out_len - pos, "%02X", g_last_frame[i]);
        if (written <= 0) break;
        pos += static_cast<size_t>(written);
    }
    if (out_len > 0) {
        out[min(pos, out_len - 1)] = '\0';
    }
}

void build_diagnostics(char* out, size_t out_len) {
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
             (unsigned long)g_modbus_success_count,
             (unsigned long)g_modbus_failure_count,
             (unsigned long)g_modbus_crc_mismatch_count,
             (unsigned long)g_modbus_short_response_count,
             (unsigned long)g_modbus_no_response_count,
             static_cast<unsigned>(g_last_frame_len),
             g_last_ingest_code,
             (unsigned long)g_ingest_ok_count,
             (unsigned long)g_ingest_fail_count,
             (unsigned long)ESP.getFreeHeap(),
             (unsigned long)ESP.getMinFreeHeap(),
             (unsigned long)g_loop_gap_max_ms);
}

void build_sample_json(char* out, size_t out_len) {
    if (!g_latest_sample.valid) {
        snprintf(out, out_len, "null");
        return;
    }
    snprintf(out, out_len,
             "{\"soil_moisture_pct\":%.1f,"
             "\"substrate_temp_c\":%.1f,"
             "\"substrate_ec_us_cm\":%u,"
             "\"substrate_ph\":%.1f,"
             "\"age_ms\":%lu}",
             g_latest_sample.moisture_pct,
             g_latest_sample.temp_c,
             g_latest_sample.ec_us_cm,
             g_latest_sample.ph,
             (unsigned long)(millis() - g_latest_sample.read_ms));
}

bool build_status_json(char* out, size_t out_len) {
    wifi_client::Snapshot wifi = wifi_client::snapshot();
    char diagnostics[512];
    char sample[192];
    char frame_hex[MODBUS_RESPONSE_MAX * 2 + 1];
    build_diagnostics(diagnostics, sizeof(diagnostics));
    build_sample_json(sample, sizeof(sample));
    append_frame_hex(frame_hex, sizeof(frame_hex));

    int written = snprintf(
        out, out_len,
        "{\"identity\":{"
        "\"site_id\":\"%s\","
        "\"tent_id\":\"%s\","
        "\"zone_id\":\"%s\","
        "\"device_id\":\"%s\","
        "\"hostname\":\"%s\""
        "},"
        "\"firmware_version\":\"%s\","
        "\"latest_sample\":%s,"
        "\"latest_raw_modbus_frame_hex\":\"%s\","
        "\"last_modbus_status\":\"%s\","
        "\"last_ingest_status\":{"
        "\"code\":%d,"
        "\"ok_count\":%lu,"
        "\"fail_count\":%lu"
        "},"
        "\"wifi\":{"
        "\"connected\":%s,"
        "\"ip\":\"%s\","
        "\"rssi_dbm\":%d,"
        "\"reconnect_count\":%lu,"
        "\"driver_reset_count\":%lu,"
        "\"last_disconnect_reason\":%u,"
        "\"disconnected_for_ms\":%lu"
        "},"
        "\"diagnostics\":%s}",
        SITE_ID,
        TENT_ID,
        ZONE_ID,
        DEVICE_ID,
        HOSTNAME,
        FIRMWARE_VERSION,
        sample,
        frame_hex,
        modbus_status_name(g_last_modbus_status),
        g_last_ingest_code,
        (unsigned long)g_ingest_ok_count,
        (unsigned long)g_ingest_fail_count,
        wifi.connected ? "true" : "false",
        WiFi.localIP().toString().c_str(),
        wifi.rssi_dbm,
        (unsigned long)wifi.reconnect_count,
        (unsigned long)wifi.driver_reset_count,
        wifi.last_disconnect_reason,
        (unsigned long)wifi.disconnected_for_ms,
        diagnostics);
    return written > 0 && static_cast<size_t>(written) < out_len;
}

// --- HTTP -----------------------------------------------------------------

void handle_health() {
    char resp[96];
    snprintf(resp, sizeof(resp),
             "{\"ok\":true,\"modbus\":\"%s\",\"ingest_code\":%d}",
             modbus_status_name(g_last_modbus_status),
             g_last_ingest_code);
    http_server.send(200, "application/json", resp);
}

void handle_status() {
    char resp[1536];
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

void post_latest_sample() {
    char metrics[160];
    snprintf(metrics, sizeof(metrics),
             "{\"soil_moisture_pct\":%.1f,"
             "\"substrate_temp_c\":%.1f,"
             "\"substrate_ec_us_cm\":%u,"
             "\"substrate_ph\":%.1f}",
             g_latest_sample.moisture_pct,
             g_latest_sample.temp_c,
             g_latest_sample.ec_us_cm,
             g_latest_sample.ph);

    char diagnostics[512];
    build_diagnostics(diagnostics, sizeof(diagnostics));
    int code = ingest.post(SITE_ID, TENT_ID, ZONE_ID, DEVICE_ID, metrics, diagnostics);
    g_last_ingest_code = code;
    if (code > 0) {
        g_ingest_ok_count++;
    } else {
        g_ingest_fail_count++;
    }
    Serial.printf("[ingest] http=%d ok=%lu fail=%lu\n",
                  code,
                  (unsigned long)g_ingest_ok_count,
                  (unsigned long)g_ingest_fail_count);
}

void poll_sensor_if_due() {
    uint32_t now = millis();
    if (g_last_poll_ms != 0 && now - g_last_poll_ms < POLL_INTERVAL_MS) {
        return;
    }
    g_last_poll_ms = now;

    if (read_substrate_sample()) {
        post_latest_sample();
    }
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

    pinMode(RS485_ENABLE_PIN, OUTPUT);
    digitalWrite(RS485_ENABLE_PIN, LOW);
    rs485.begin(SENSOR_BAUD, SERIAL_8N1, RS485_RX_PIN, RS485_TX_PIN);

    Serial.println();
    Serial.println("# rs485-substrate-node");
    Serial.printf("# fw=%s device=%s host=%s address=0x%02X interval=%lums\n",
                  FIRMWARE_VERSION,
                  DEVICE_ID,
                  HOSTNAME,
                  SENSOR_ADDRESS,
                  (unsigned long)POLL_INTERVAL_MS);
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
    http_server.onNotFound(handle_not_found);
    http_server.begin();
    Serial.println("[boot] http status surface up on :80 (GET /health, GET /status)");
}

void loop() {
    record_loop_gap();
    ota::loop();
    wifi_client::maintain();
    http_server.handleClient();
    poll_sensor_if_due();
    delay(10);
}
