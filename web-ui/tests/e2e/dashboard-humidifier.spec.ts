// End-to-end acceptance for frontend.dashboard.humidifier.
//
// Each `test(...)` block maps 1:1 to a distinct assertion in the plan-
// JSON acceptance[].description for this feature. The evaluator runs a
// coverage audit against the description; collapsing these into one
// mega-test would obscure which assertions are really exercised. See
// web-ui/tests/e2e/README.md §2.
//
// Fixtures come from the MSW handlers for /api/humidifier/state and
// /api/humidifier/history in web-ui/src/mocks/handlers.ts:
//   - state: on=true, duration_s=7200 (2h), cycles_24h=8
//   - history transitions per range: 1h→4, 24h→12, 7d→28
//     (alternating on/off, first transition on=true)
// MSW intercepts in dev AND in the Vite build Playwright runs against,
// so the spec is independent of the backend stack.
import { expect, test } from "@playwright/test";

test.describe("dashboard humidifier", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    // Wait for the dashboard's sensors query to settle so the gauges
    // and humidifier sections are mounted.
    await expect(
      page.getByRole("region", { name: "Environment gauges" }),
    ).toBeVisible();
    // Wait until the humidifier state query has resolved — the tile
    // only mounts after /api/humidifier/state returns.
    await expect(
      page.getByRole("article", { name: "Humidifier", exact: true }),
    ).toBeVisible();
  });

  test("humidifier tile renders with the ON/OFF state from /api/humidifier/state", async ({
    page,
  }) => {
    // Fixture state.on === true → status word = "ON".
    const tile = page.getByRole("article", { name: "Humidifier", exact: true });
    const stateWord = tile.getByRole("status", { name: "Humidifier state" });
    await expect(stateWord).toBeVisible();
    await expect(stateWord).toHaveText("ON");
    // data-on mirrors the boolean so the evaluator can grep the DOM
    // for the contract value directly.
    await expect(stateWord).toHaveAttribute("data-on", "true");
  });

  test("humidifier tile shows duration since last transition", async ({ page }) => {
    // Fixture duration_s = 7200 (2 hours). The tile formats this as
    // "2h" (coarse breakdown — see HumidifierTile.formatDuration).
    const tile = page.getByRole("article", { name: "Humidifier", exact: true });
    const duration = tile.getByRole("group", {
      name: "Duration since last transition",
    });
    await expect(duration).toBeVisible();
    await expect(duration).toContainText("2h");
  });

  test("humidifier tile shows the cycles-per-24h count", async ({ page }) => {
    // Fixture cycles_24h = 8.
    const tile = page.getByRole("article", { name: "Humidifier", exact: true });
    const cycles = tile.getByRole("group", { name: "Cycles in last 24 hours" });
    await expect(cycles).toBeVisible();
    await expect(cycles).toContainText("8");
  });

  test("duty-cycle strip renders below the sparklines with one rectangle per transition", async ({
    page,
  }) => {
    // Default range is 24h → fixture history length = 12 transitions.
    const strip = page.getByRole("article", { name: "Humidifier duty cycle" });
    await expect(strip).toBeVisible();
    await expect(strip.getByLabel("humidifier segment")).toHaveCount(12);

    // Strip is anchored below the sparklines region.
    const sparklinesBottom = await page
      .getByRole("region", { name: "Environment sparklines" })
      .evaluate((el) => el.getBoundingClientRect().bottom);
    const stripTop = await strip.evaluate(
      (el) => el.getBoundingClientRect().top,
    );
    expect(stripTop).toBeGreaterThanOrEqual(sparklinesBottom);
  });

  test("changing the range triggers a fresh GET /api/humidifier/history and re-renders the strip", async ({
    page,
  }) => {
    // Track every /api/humidifier/history request the browser dispatches.
    const requests: { range: string | null }[] = [];
    page.on("request", (req) => {
      const u = new URL(req.url());
      if (u.pathname === "/api/humidifier/history") {
        requests.push({ range: u.searchParams.get("range") });
      }
    });

    // Fresh reload so we observe the initial baseline fetch + each
    // subsequent range switch deterministically.
    await page.goto("/");
    const strip = page.getByRole("article", { name: "Humidifier duty cycle" });
    await expect(strip).toBeVisible();
    // Initial baseline: one history fetch at the default 24h range →
    // 12 segments rendered.
    await expect
      .poll(() => requests.filter((r) => r.range === "24h").length, {
        timeout: 5000,
      })
      .toBe(1);
    await expect(strip.getByLabel("humidifier segment")).toHaveCount(12);

    const rangeGroup = page.getByRole("group", { name: "Sparkline range" });

    // Switch to 1h → fresh history fetch at range=1h → 4 segments.
    await rangeGroup.getByRole("button", { name: "1h" }).click();
    await expect
      .poll(() => requests.filter((r) => r.range === "1h").length, {
        timeout: 5000,
      })
      .toBe(1);
    await expect(strip.getByLabel("humidifier segment")).toHaveCount(4);

    // Switch to 7d → fresh history fetch at range=7d → 28 segments.
    await rangeGroup.getByRole("button", { name: "7d" }).click();
    await expect
      .poll(() => requests.filter((r) => r.range === "7d").length, {
        timeout: 5000,
      })
      .toBe(1);
    await expect(strip.getByLabel("humidifier segment")).toHaveCount(28);
  });
});
