#include <sensor_protocol.h>
#include <unity.h>

#include <cmath>
#include <cstring>

void test_celsius_to_fahrenheit() {
    TEST_ASSERT_FLOAT_WITHIN(0.01, 32.0, celsius_to_fahrenheit(0.0));
    TEST_ASSERT_FLOAT_WITHIN(0.01, 212.0, celsius_to_fahrenheit(100.0));
    TEST_ASSERT_FLOAT_WITHIN(0.01, 77.0, celsius_to_fahrenheit(25.0));
}

void test_vpd_calculation() {
    // At 25°C, 50% RH: SVP ≈ 3.167 kPa, VPD ≈ 1.584 kPa
    float vpd = calculate_vpd(25.0, 50.0);
    TEST_ASSERT_FLOAT_WITHIN(0.05, 1.58, vpd);

    // At 100% RH, VPD should be ~0
    vpd = calculate_vpd(25.0, 100.0);
    TEST_ASSERT_FLOAT_WITHIN(0.01, 0.0, vpd);

    // Invalid humidity returns -1
    vpd = calculate_vpd(25.0, 150.0);
    TEST_ASSERT_FLOAT_WITHIN(0.01, -1.0, vpd);
}

void test_soil_moisture_to_pct() {
    // Dry air reading (800) should be 0%
    TEST_ASSERT_FLOAT_WITHIN(0.1, 0.0, soil_moisture_to_pct(800, 800, 400));

    // Submerged reading (400) should be 100%
    TEST_ASSERT_FLOAT_WITHIN(0.1, 100.0, soil_moisture_to_pct(400, 800, 400));

    // Midpoint (600) should be 50%
    TEST_ASSERT_FLOAT_WITHIN(0.1, 50.0, soil_moisture_to_pct(600, 800, 400));

    // Clamped above 100%
    TEST_ASSERT_FLOAT_WITHIN(0.1, 100.0, soil_moisture_to_pct(300, 800, 400));

    // Clamped below 0%
    TEST_ASSERT_FLOAT_WITHIN(0.1, 0.0, soil_moisture_to_pct(900, 800, 400));
}

void test_reservoir_low_logic() {
    // reservoir_has_water=true means sensor detects water → not low
    // reservoir_has_water=false means no water at sensor → reservoir is low
    SensorData data = {};
    data.temperature_c = 25.0;
    data.humidity_pct = 50.0;
    data.co2_ready = false;
    data.soil_moisture_raw = 600;

    char buf[256];

    // Water present → reservoir_low: false
    data.reservoir_has_water = true;
    encode_json(&data, buf, sizeof(buf), 800, 400);
    TEST_ASSERT_NOT_NULL(strstr(buf, "\"reservoir_low\":false"));

    // No water → reservoir_low: true
    data.reservoir_has_water = false;
    encode_json(&data, buf, sizeof(buf), 800, 400);
    TEST_ASSERT_NOT_NULL(strstr(buf, "\"reservoir_low\":true"));
}

void test_validate_temperature() {
    TEST_ASSERT_TRUE(validate_temperature(25.0));
    TEST_ASSERT_TRUE(validate_temperature(-40.0));
    TEST_ASSERT_TRUE(validate_temperature(80.0));
    TEST_ASSERT_FALSE(validate_temperature(-41.0));
    TEST_ASSERT_FALSE(validate_temperature(81.0));
}

void test_validate_humidity() {
    TEST_ASSERT_TRUE(validate_humidity(50.0));
    TEST_ASSERT_TRUE(validate_humidity(0.0));
    TEST_ASSERT_TRUE(validate_humidity(100.0));
    TEST_ASSERT_FALSE(validate_humidity(-1.0));
    TEST_ASSERT_FALSE(validate_humidity(101.0));
}

void test_validate_co2() {
    TEST_ASSERT_TRUE(validate_co2(400));
    TEST_ASSERT_TRUE(validate_co2(0));
    TEST_ASSERT_TRUE(validate_co2(5000));
    TEST_ASSERT_FALSE(validate_co2(-1));
    TEST_ASSERT_FALSE(validate_co2(5001));
}

void test_encode_json() {
    SensorData data = {};
    data.temperature_c = 25.0;
    data.humidity_pct = 52.0;
    data.co2_ppm = 812;
    data.co2_ready = true;
    data.soil_moisture_raw = 600;
    data.reservoir_has_water = true;

    char buf[256];
    int len = encode_json(&data, buf, sizeof(buf), 800, 400);

    TEST_ASSERT_GREATER_THAN(0, len);
    TEST_ASSERT_NOT_NULL(strstr(buf, "\"temperature_f\""));
    TEST_ASSERT_NOT_NULL(strstr(buf, "\"humidity_pct\""));
    TEST_ASSERT_NOT_NULL(strstr(buf, "\"co2_ppm\""));
    TEST_ASSERT_NOT_NULL(strstr(buf, "\"soil_moisture_pct\""));
    TEST_ASSERT_NOT_NULL(strstr(buf, "\"reservoir_low\""));
    TEST_ASSERT_NOT_NULL(strstr(buf, "\"vpd\""));
    // Ends with newline
    TEST_ASSERT_EQUAL('\n', buf[len - 1]);
}

void test_encode_json_without_co2() {
    SensorData data = {};
    data.temperature_c = 25.0;
    data.humidity_pct = 52.0;
    data.co2_ready = false;  // Warming up
    data.soil_moisture_raw = 600;

    char buf[256];
    int len = encode_json(&data, buf, sizeof(buf), 800, 400);

    TEST_ASSERT_GREATER_THAN(0, len);
    // co2_ppm should not appear during warmup
    TEST_ASSERT_NULL(strstr(buf, "\"co2_ppm\""));
}

void test_encode_json_buffer_too_small() {
    SensorData data = {};
    data.temperature_c = 25.0;
    data.humidity_pct = 52.0;
    data.co2_ready = true;
    data.co2_ppm = 812;
    data.soil_moisture_raw = 600;

    char buf[10];  // Way too small
    int len = encode_json(&data, buf, sizeof(buf), 800, 400);
    TEST_ASSERT_EQUAL(-1, len);
}

int main() {
    UNITY_BEGIN();

    RUN_TEST(test_celsius_to_fahrenheit);
    RUN_TEST(test_vpd_calculation);
    RUN_TEST(test_soil_moisture_to_pct);
    RUN_TEST(test_reservoir_low_logic);
    RUN_TEST(test_validate_temperature);
    RUN_TEST(test_validate_humidity);
    RUN_TEST(test_validate_co2);
    RUN_TEST(test_encode_json);
    RUN_TEST(test_encode_json_without_co2);
    RUN_TEST(test_encode_json_buffer_too_small);

    return UNITY_END();
}
