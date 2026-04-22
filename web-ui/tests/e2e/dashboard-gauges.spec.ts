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
    // Wait for the dashboard's sensors query to settle — the five
    // tiles are rendered only after /api/sensors/current resolves, so
    // every assertion below needs to wait past the "Loading sensors…"
    // placeholder. One deterministic landmark to wait on.
    await expect(
      page.getByRole("region", { name: "Environment gauges" }),
    ).toBeVisible();
  });

  test("five gauge tiles render with the expected metric headings", async ({
    page,
  }) => {
    // The <article aria-label={name}> per-tile contract is the spec's
    // handle onto each metric. Five metrics expected, one per key in
    // SensorsCurrent.metrics.
    await expect(
      page.getByRole("article", { name: "Temperature" }),
    ).toBeVisible();
    await expect(page.getByRole("article", { name: "Humidity" })).toBeVisible();
    await expect(page.getByRole("article", { name: "VPD" })).toBeVisible();
    await expect(page.getByRole("article", { name: "Fan" })).toBeVisible();
    await expect(page.getByRole("article", { name: "Reservoir" })).toBeVisible();

    // Each tile renders its metric name as a heading (h2).
    await expect(
      page.getByRole("heading", { name: "Temperature" }),
    ).toBeVisible();
    await expect(page.getByRole("heading", { name: "Humidity" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "VPD" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Fan" })).toBeVisible();
    await expect(page.getByRole("heading", { name: "Reservoir" })).toBeVisible();

    // Guard against stray tiles (a sixth article would still satisfy
    // the five containsText assertions above but would indicate drift).
    const articles = page.locator("article[aria-label]");
    await expect(articles).toHaveCount(5);
  });

  test("each tile's displayed value matches the MSW-fixture reading", async ({
    page,
  }) => {
    // Values + units come straight from web-ui/src/mocks/handlers.ts.
    // Formatter is one-decimal by default; fan/humidity/reservoir use
    // integer format per routes/index.tsx GAUGE_TILES config.
    //   temperature_f: 76   → "76.0" + "°F"
    //   humidity_pct : 50   → "50"   + "%"   (integer)
    //   vpd_kpa      : 1.0  → "1.0"  + "kPa"
    //   fan_pct      : 48   → "48"   + "%"   (integer)
    //   reservoir_in : 9.2  → "9.2"  + "in"
    const temp = page.getByRole("article", { name: "Temperature" });
    await expect(temp).toContainText("76.0");
    await expect(temp).toContainText("°F");

    const humidity = page.getByRole("article", { name: "Humidity" });
    await expect(humidity).toContainText("50");
    await expect(humidity).toContainText("%");

    const vpd = page.getByRole("article", { name: "VPD" });
    await expect(vpd).toContainText("1.0");
    await expect(vpd).toContainText("kPa");

    const fan = page.getByRole("article", { name: "Fan" });
    await expect(fan).toContainText("48");
    await expect(fan).toContainText("%");

    const reservoir = page.getByRole("article", { name: "Reservoir" });
    await expect(reservoir).toContainText("9.2");
    await expect(reservoir).toContainText("in");
  });

  test("target-band arcs render only on temperature / humidity / VPD", async ({
    page,
  }) => {
    // <svg aria-label="target band"> is the Gauge component's accessible
    // marker for the arc. Present on metrics whose envelope has a
    // non-null `target`; absent on fan_pct + reservoir_in (which the
    // BE returns with target=null).
    await expect(
      page.getByRole("article", { name: "Temperature" }).getByLabel("target band"),
    ).toHaveCount(1);
    await expect(
      page.getByRole("article", { name: "Humidity" }).getByLabel("target band"),
    ).toHaveCount(1);
    await expect(
      page.getByRole("article", { name: "VPD" }).getByLabel("target band"),
    ).toHaveCount(1);

    // No arc on the band-less tiles.
    await expect(
      page.getByRole("article", { name: "Fan" }).getByLabel("target band"),
    ).toHaveCount(0);
    await expect(
      page.getByRole("article", { name: "Reservoir" }).getByLabel("target band"),
    ).toHaveCount(0);

    // Total count: exactly three banded tiles.
    await expect(page.getByLabel("target band")).toHaveCount(3);
  });

  test("each tile's status indicator maps to band_status (ok for fixture)", async ({
    page,
  }) => {
    // MSW fixture puts every metric inside (or without-band for) the
    // "ok" zone (see /api/sensors/current handler comment). The Gauge
    // component mirrors the envelope's status field verbatim into a
    // role="status" element whose text is "ok" | "warn" | "crit", plus
    // a data-status attribute for deterministic attribute matching.
    for (const name of ["Temperature", "Humidity", "VPD", "Fan", "Reservoir"]) {
      const tile = page.getByRole("article", { name });
      const status = tile.getByRole("status");
      await expect(status).toHaveText("ok");
      await expect(status).toHaveAttribute("data-status", "ok");
    }
  });

  test("top bar shows Day {day_number} · {strain} from /api/grow/current", async ({
    page,
  }) => {
    // MSW fixture: day_number = 38, strain = "Sirius Black × BS01".
    // The TopBar renders them inside the banner header as "Day 38 · …".
    const banner = page.getByRole("banner");
    await expect(banner).toContainText("Day 38");
    await expect(banner).toContainText("Sirius Black × BS01");
    // Middle-dot separator is visible (U+00B7 or the ASCII " · " we
    // rendered): the exact literal from TopBar is " · ".
    await expect(banner).toContainText("·");
  });
});
