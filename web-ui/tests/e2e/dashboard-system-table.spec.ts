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
// Fixture values come from the MSW handler for /api/system/devices in
// web-ui/src/mocks/handlers.ts (eight devices covering the full
// DeviceStatusKind enum).
import { type Page, expect, test } from "@playwright/test";

const ALLOWED_STATUSES = ["ok", "listening", "warn", "offline"] as const;

interface DevicesPayload {
  devices: { name: string; status: string }[];
}

// Install the response listener BEFORE navigation so the fetch the
// component fires can't race past us; returns the parsed body so each
// test can anchor its assertions to exactly what the server returned.
async function loadDashboardAndCapture(page: Page): Promise<DevicesPayload> {
  const responsePromise = page.waitForResponse(
    (resp) => new URL(resp.url()).pathname === "/api/system/devices" && resp.ok(),
  );
  await page.goto("/");
  const resp = await responsePromise;
  return (await resp.json()) as DevicesPayload;
}

test.describe("dashboard system table", () => {
  test("system section renders a table with 8 rows, one per device from GET /api/system/devices", async ({
    page,
  }) => {
    const payload = await loadDashboardAndCapture(page);
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
    const payload = await loadDashboardAndCapture(page);
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
});
