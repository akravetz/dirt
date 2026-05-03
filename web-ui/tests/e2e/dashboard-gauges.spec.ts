// End-to-end acceptance for frontend.dashboard.gauges.
//
// Each `test(...)` block maps 1:1 to a distinct assertion in the plan-
// JSON acceptance[].description for this feature. The evaluator runs a
// coverage audit against the description; collapsing these into one
// mega-test would obscure which assertions are really exercised. See
// web-ui/tests/e2e/README.md §2.
//
// Fixture values come from the MSW handlers in
// web-ui/src/mocks/handlers.ts (/api/sensors/current and
// /api/grow/current). MSW intercepts these endpoints in dev AND in the
// Vite build Playwright runs against, so the spec is independent of
// the backend stack.
import { expect, test } from "@playwright/test";

test.describe("dashboard gauges", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    // Wait for the dashboard's sensors query to settle — the metric
    // tiles are rendered only after /api/sensors/current resolves, so
    // every assertion below needs to wait past the "Loading sensors…"
    // placeholder. One deterministic landmark to wait on.
    await expect(
      page.getByRole("region", { name: "Environment gauges" }),
    ).toBeVisible();
  });

  test("six gauge tiles render with the expected metric headings", async ({
    page,
  }) => {
    // The <article aria-label={name}> per-tile contract is the spec's
    // handle onto each metric. Six dashboard metrics expected, one per
    // SensorsCurrent.metrics. `exact: true` prevents substring matches
    // against the sparkline strip below, whose tiles are labelled
    // "{Metric} sparkline" (frontend.dashboard.sparklines).
    await expect(
      page.getByRole("article", { name: "Temperature", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("article", { name: "Humidity", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("article", { name: "VPD", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("article", { name: "Fan", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("article", { name: "Humidifier", exact: true }),
    ).toBeVisible();
    await expect(
      page.getByRole("article", { name: "Reservoir", exact: true }),
    ).toBeVisible();

    // Each tile renders its metric name as a heading (h2). Sparklines
    // render their metric name in an <h3>, so getByRole('heading', ...)
    // without a level filter would also see those — scope on level=2.
    await expect(
      page.getByRole("heading", { level: 2, name: "Temperature" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { level: 2, name: "Humidity" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { level: 2, name: "VPD" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { level: 2, name: "Fan" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { level: 2, name: "Humidifier" }),
    ).toBeVisible();
    await expect(
      page.getByRole("heading", { level: 2, name: "Reservoir" }),
    ).toBeVisible();

    // Guard against stray tiles in the gauges section specifically.
    // Count is scoped to the Environment gauges landmark so the
    // sparkline strip's own articles don't inflate the total.
    const gaugesArticles = page
      .getByRole("region", { name: "Environment gauges" })
      .locator("article[aria-label]");
    await expect(gaugesArticles).toHaveCount(6);
  });

  test("each tile renders a numeric reading and the expected unit", async ({
    page,
  }) => {
    // Shape+presence assertion: each tile surfaces *some* numeric value
    // plus the metric's unit suffix. Values come from live BE captures
    // (refreshed via scripts/capture-fixtures), so the specific number
    // drifts between runs; asserting an exact literal coupled the spec
    // to the MSW fixture and broke on every recapture.
    const TILES: Array<[string, string]> = [
      ["Temperature", "°F"],
      ["Humidity", "%"],
      ["VPD", "kPa"],
      ["Fan", "%"],
      ["Humidifier", "%"],
      ["Reservoir", "in"],
    ];
    for (const [name, unit] of TILES) {
      const tile = page.getByRole("article", { name, exact: true });
      await expect(tile).toContainText(/\d/);
      await expect(tile).toContainText(unit);
    }
  });

  test("target-band arcs render only on temperature / humidity / VPD", async ({
    page,
  }) => {
    // <svg aria-label="target band"> is the Gauge component's accessible
    // marker for the arc. Present on metrics whose envelope has a
    // non-null `target`; absent on fan_pct + reservoir_in (which the
    // BE returns with target=null).
    await expect(
      page
        .getByRole("article", { name: "Temperature", exact: true })
        .getByLabel("target band"),
    ).toHaveCount(1);
    await expect(
      page
        .getByRole("article", { name: "Humidity", exact: true })
        .getByLabel("target band"),
    ).toHaveCount(1);
    await expect(
      page
        .getByRole("article", { name: "VPD", exact: true })
        .getByLabel("target band"),
    ).toHaveCount(1);

    // No arc on the band-less tiles.
    await expect(
      page
        .getByRole("article", { name: "Fan", exact: true })
        .getByLabel("target band"),
    ).toHaveCount(0);
    await expect(
      page
        .getByRole("article", { name: "Humidifier", exact: true })
        .getByLabel("target band"),
    ).toHaveCount(0);
    await expect(
      page
        .getByRole("article", { name: "Reservoir", exact: true })
        .getByLabel("target band"),
    ).toHaveCount(0);

    // Total count: exactly three banded tiles.
    await expect(page.getByLabel("target band")).toHaveCount(3);
  });

  test("each tile surfaces a band-status value from the SensorMetric envelope", async ({
    page,
  }) => {
    // The Gauge component mirrors the envelope's status field verbatim
    // into a role="status" element whose text is "ok" | "warn" | "crit",
    // plus a data-status attribute. Real BE values drift into warn/crit
    // whenever a metric leaves its target band, so asserting a specific
    // status couples the spec to live sensor state; here we assert the
    // contract — status text is one of the enum values and matches the
    // data attribute.
    const STATUS_PATTERN = /^(ok|warn|crit)$/;
    for (const name of [
      "Temperature",
      "Humidity",
      "VPD",
      "Fan",
      "Humidifier",
      "Reservoir",
    ]) {
      const tile = page.getByRole("article", { name, exact: true });
      const status = tile.getByRole("status");
      await expect(status).toHaveText(STATUS_PATTERN);
      const text = (await status.textContent())?.trim() ?? "";
      await expect(status).toHaveAttribute("data-status", text);
    }
  });

  test("top bar shows grow stage, lights, and strain from /api/grow/current", async ({
    page,
  }) => {
    // Shape+presence: banner renders "Day N" for some positive integer
    // N (day_number advances daily, so hard-coding the literal coupled
    // the spec to the MSW fixture) plus stage, lights, and strain.
    const banner = page.getByRole("banner");
    await expect(banner).toContainText(/Day \d+/);
    await expect(banner).toContainText("Veg");
    await expect(banner).toContainText("05:00-23:00");
    await expect(banner).toContainText("Sirius Black × BS01");
    // Middle-dot separator is visible (U+00B7 or the ASCII " · " we
    // rendered): the exact literal from TopBar is " · ".
    await expect(banner).toContainText("·");
  });
});
