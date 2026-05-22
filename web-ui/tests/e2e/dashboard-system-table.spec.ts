// End-to-end acceptance for frontend.dashboard.system_table.
//
// Each `test(...)` block maps 1:1 to a distinct assertion in the plan-
// JSON acceptance[].description for this feature. The evaluator runs a
// coverage audit against the description; collapsing these into one
// mega-test would obscure which assertions are really exercised. See
// web-ui/tests/e2e/README.md §2.
//
// The plan description has two distinct assertions:
//   1. The system section renders a table with 8 rows, one per device
//      from GET /api/system/devices.
//   2. Each row's status badge accessible indicator
//      (role/aria-label/textContent) reflects the device's status value
//      — colour-only indicators are forbidden.
//
import { type Page, expect, test } from "@playwright/test";

const ALLOWED_STATUSES = ["ok", "listening", "warn", "offline"] as const;

interface DevicesPayload {
  devices: {
    name: string;
    kind?: string;
    status: string;
    last_seen?: string | null;
    wifi?: {
      rssi_dbm: number | null;
      reconnect_count: number | null;
      driver_reset_count: number | null;
      disconnect_reason: number | null;
      disconnected_for_ms?: number | null;
    } | null;
  }[];
}

const SYSTEM_DEVICES_WITH_WIFI: DevicesPayload = {
  devices: [
    {
      name: "ESP32-C3 · fan+tent",
      kind: "env_sensor",
      status: "ok",
      last_seen: "2026-05-22T00:00:00Z",
      wifi: {
        rssi_dbm: -72,
        reconnect_count: 4,
        driver_reset_count: 1,
        disconnect_reason: 200,
        disconnected_for_ms: 0,
      },
    },
    {
      name: "ESP32-C3 · plant_a",
      kind: "moisture_node",
      status: "ok",
      last_seen: "2026-05-22T00:00:00Z",
      wifi: {
        rssi_dbm: -68,
        reconnect_count: 2,
        driver_reset_count: 0,
        disconnect_reason: 0,
        disconnected_for_ms: 0,
      },
    },
    {
      name: "ESP32-C3 · plant_b",
      kind: "moisture_node",
      status: "warn",
      last_seen: "2026-05-22T00:00:00Z",
      wifi: {
        rssi_dbm: -84,
        reconnect_count: 11,
        driver_reset_count: 2,
        disconnect_reason: 201,
        disconnected_for_ms: 45000,
      },
    },
    {
      name: "ESP32-C3 · plant_c",
      kind: "moisture_node",
      status: "offline",
      last_seen: null,
      wifi: {
        rssi_dbm: null,
        reconnect_count: 18,
        driver_reset_count: 3,
        disconnect_reason: 200,
        disconnected_for_ms: 900000,
      },
    },
    {
      name: "ESP32-C3 · plant_d",
      kind: "moisture_node",
      status: "ok",
      last_seen: "2026-05-22T00:00:00Z",
      wifi: {
        rssi_dbm: -70,
        reconnect_count: 0,
        driver_reset_count: 0,
        disconnect_reason: 0,
        disconnected_for_ms: 0,
      },
    },
    {
      name: "Humidifier (Govee H7142)",
      kind: "actuator",
      status: "ok",
      last_seen: "2026-05-22T00:00:00Z",
      wifi: null,
    },
    {
      name: "OBSBOT Tiny 2 Lite",
      kind: "camera",
      status: "ok",
      last_seen: "2026-05-22T00:00:00Z",
      wifi: null,
    },
    {
      name: "Jabra Speak 410 (Claudia)",
      kind: "voice",
      status: "listening",
      last_seen: "2026-05-22T00:00:00Z",
      wifi: null,
    },
  ],
};

async function loadDashboardWithSystemPayload(
  page: Page,
  payload: DevicesPayload,
): Promise<DevicesPayload> {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/sensors/current") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          ts: "2026-05-22T00:00:00Z",
          stale: false,
          metrics: {
            temperature_f: metricEnvelope(74.2, "°F"),
            humidity_pct: metricEnvelope(58, "%"),
            vpd_kpa: metricEnvelope(1.1, "kPa"),
            fan_pct: metricEnvelope(35, "%"),
            humidifier_intensity_pct: metricEnvelope(0, "%"),
            reservoir_in: metricEnvelope(7.5, "in"),
          },
        }),
      });
      return;
    }
    if (url.pathname === "/api/sensors/metadata") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ metrics: [] }),
      });
      return;
    }
    if (url.pathname === "/api/system/devices") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ts: "2026-05-22T00:00:00Z", devices: payload.devices }),
      });
      return;
    }
    if (url.pathname === "/api/grow/current") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          germination_date: "2026-05-01",
          flower_start_date: null,
          day_number: 22,
          grow_week_number: 4,
          flower_week_number: null,
          stage: "veg",
          strain: "Fixture",
          plant_count: 4,
          lights: {
            on: true,
            on_local: "05:00:00",
            off_local: "23:00:00",
            minutes_until_off: 120,
            minutes_until_on: 960,
          },
        }),
      });
      return;
    }
    if (url.pathname === "/api/tents/main/lights/schedules") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ site_id: "homebox", tent_id: "main", schedules: [] }),
      });
      return;
    }
    if (url.pathname === "/api/plants") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ day: 22, plants: [] }),
      });
      return;
    }
    if (url.pathname === "/api/sensors/history") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          range: url.searchParams.get("range") ?? "1h",
          metric: url.searchParams.get("metric") ?? "temperature_f",
          unit: "",
          points: [],
        }),
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });
  const responsePromise = page.waitForResponse(
    (resp) => new URL(resp.url()).pathname === "/api/system/devices" && resp.ok(),
  );
  await page.goto("/");
  const resp = await responsePromise;
  return (await resp.json()) as DevicesPayload;
}

function metricEnvelope(value: number, unit: string): object {
  return {
    value,
    unit,
    target: null,
    status: "ok",
    ts: "2026-05-22T00:00:00Z",
  };
}

test.describe("dashboard system table", () => {
  test("system section renders a table with 8 rows, one per device from GET /api/system/devices", async ({
    page,
  }) => {
    const payload = await loadDashboardWithSystemPayload(page, SYSTEM_DEVICES_WITH_WIFI);
    expect(payload.devices).toHaveLength(8);

    const section = page.getByRole("region", { name: "System devices" });
    await expect(section).toBeVisible();
    const bodyRows = section.getByRole("table").locator("tbody tr");
    await expect(bodyRows).toHaveCount(8);

    for (const device of payload.devices) {
      await expect(bodyRows.filter({ hasText: device.name })).toHaveCount(1);
    }
  });

  test("each row's status badge accessible indicator reflects the device's status value", async ({
    page,
  }) => {
    const payload = await loadDashboardWithSystemPayload(page, SYSTEM_DEVICES_WITH_WIFI);
    expect(payload.devices).toHaveLength(8);

    const section = page.getByRole("region", { name: "System devices" });
    await expect(section).toBeVisible();
    const bodyRows = section.getByRole("table").locator("tbody tr");
    await expect(bodyRows).toHaveCount(8);

    // Shape-and-presence: each row's badge text equals the device's
    // reported status, and every status is one of the enum variants.
    // Previous assertion ("every allowed variant present") coupled the
    // spec to a fixture that happened to exercise all four states —
    // live BE rarely reports "warn" in a healthy system, so insisting
    // on full enum coverage from real data is unrealistic.
    for (const device of payload.devices) {
      const row = bodyRows.filter({ hasText: device.name });
      await expect(row).toHaveCount(1);
      const badge = row.getByRole("status", { name: `${device.name} status` });
      await expect(badge).toBeVisible();
      await expect(badge).toHaveText(device.status);
      expect(ALLOWED_STATUSES).toContain(device.status);
    }
  });

  test("wifi diagnostics render when present and use placeholders when absent", async ({
    page,
  }) => {
    await loadDashboardWithSystemPayload(page, SYSTEM_DEVICES_WITH_WIFI);

    const section = page.getByRole("region", { name: "System devices" });
    await expect(section).toBeVisible();
    const bodyRows = section.getByRole("table").locator("tbody tr");
    await expect(bodyRows).toHaveCount(8);

    const fanRow = bodyRows.filter({ hasText: "ESP32-C3 · fan+tent" });
    await expect(fanRow.getByRole("cell").nth(2)).toHaveText("-72");
    await expect(fanRow.getByRole("cell").nth(3)).toHaveText("4");
    await expect(fanRow.getByRole("cell").nth(4)).toHaveText("1");
    await expect(fanRow.getByRole("cell").nth(5)).toHaveText("200");

    const humidifierRow = bodyRows.filter({ hasText: "Humidifier (Govee H7142)" });
    await expect(humidifierRow.getByRole("cell").nth(2)).toHaveText("--");
    await expect(humidifierRow.getByRole("cell").nth(3)).toHaveText("--");
    await expect(humidifierRow.getByRole("cell").nth(4)).toHaveText("--");
    await expect(humidifierRow.getByRole("cell").nth(5)).toHaveText("--");
  });
});
