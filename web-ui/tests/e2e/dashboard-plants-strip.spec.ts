// End-to-end acceptance for frontend.dashboard.plants_strip.
//
// Each `test(...)` block maps 1:1 to a distinct assertion in the plan-
// JSON acceptance[].description for this feature. The evaluator runs a
// coverage audit against the description; collapsing these into one
// mega-test would obscure which assertions are really exercised. See
// web-ui/tests/e2e/README.md §2.
//
// Fixture values come from the MSW handler for /api/plants in
// web-ui/src/mocks/handlers.ts (four plants A/B/C/D with sticker
// colours yellow/orange/pink/blue and moisture percentages
// 62/48/54/66). MSW intercepts in dev AND in the Vite build Playwright
// runs against, so the spec is independent of the backend stack.
import { expect, test } from "@playwright/test";

test.describe("dashboard plants strip", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    // Wait for the plants strip to mount — it renders only after
    // /api/plants resolves, so every assertion below needs to wait past
    // the initial paint. Using the region landmark (aria-label="Plants")
    // is the least brittle signal.
    await expect(page.getByRole("region", { name: "Plants" })).toBeVisible();
  });

  test("four plant cards (A, B, C, D) render below the sparklines", async ({
    page,
  }) => {
    // Each card is an accessible button with the plant's display name as
    // its aria-label. exact: true prevents fuzzy matches against the
    // drawer header rows that the plant_detail feature will introduce.
    const strip = page.getByRole("region", { name: "Plants" });
    await expect(strip.getByRole("button", { name: "Plant A", exact: true })).toBeVisible();
    await expect(strip.getByRole("button", { name: "Plant B", exact: true })).toBeVisible();
    await expect(strip.getByRole("button", { name: "Plant C", exact: true })).toBeVisible();
    await expect(strip.getByRole("button", { name: "Plant D", exact: true })).toBeVisible();

    // Scoped count: exactly four cards inside the strip (guards against
    // stray buttons inflating the total).
    await expect(strip.getByRole("button")).toHaveCount(4);

    // Positional check: the plants strip sits below the Environment
    // sparklines region. Comparing bounding rects keeps this robust to
    // intervening sections (humidifier strip, etc.) while still
    // asserting the "below the sparklines" intent literally.
    const sparklinesBottom = await page
      .getByRole("region", { name: "Environment sparklines" })
      .evaluate((el) => el.getBoundingClientRect().bottom);
    const stripTop = await strip.evaluate(
      (el) => el.getBoundingClientRect().top,
    );
    expect(stripTop).toBeGreaterThanOrEqual(sparklinesBottom);
  });

  test("each card's sticker chip colour matches the /api/plants fixture", async ({
    page,
  }) => {
    // The sticker chip inside each card surfaces its colour via the
    // data-color attribute. The spec reads that attribute directly,
    // which keeps the assertion anchored to the fixture's
    // `sticker_color` string (yellow/orange/pink/blue per plant) rather
    // than to a Tailwind class name that can drift under the
    // designer's hand.
    const expectations: ReadonlyArray<{ name: string; color: string }> = [
      { name: "Plant A", color: "yellow" },
      { name: "Plant B", color: "orange" },
      { name: "Plant C", color: "pink" },
      { name: "Plant D", color: "blue" },
    ];
    for (const { name, color } of expectations) {
      const card = page.getByRole("button", { name, exact: true });
      const sticker = card.getByLabel("sticker");
      await expect(sticker).toHaveAttribute("data-color", color);
    }
  });

  test("each card's soil-moisture bar reflects the fixture's moisture.current_pct", async ({
    page,
  }) => {
    // The moisture bar is a role="progressbar" whose aria-valuenow is
    // the plant's moisture percentage. Reading aria-valuenow directly
    // is the semantic way to assert "bar width matches moisture" — the
    // SVG fill rect's width is driven off the same integer, so the
    // visual width and the announced value stay in sync.
    //
    // MSW fixture values (see web-ui/src/mocks/handlers.ts):
    //   A: 62, B: 48, C: 54, D: 66
    const expectations: ReadonlyArray<{ name: string; pct: string }> = [
      { name: "Plant A", pct: "62" },
      { name: "Plant B", pct: "48" },
      { name: "Plant C", pct: "54" },
      { name: "Plant D", pct: "66" },
    ];
    for (const { name, pct } of expectations) {
      const card = page.getByRole("button", { name, exact: true });
      const bar = card.getByRole("progressbar");
      await expect(bar).toHaveAttribute("aria-valuenow", pct);
      await expect(bar).toHaveAttribute("aria-valuemin", "0");
      await expect(bar).toHaveAttribute("aria-valuemax", "100");
    }
  });

  test("clicking plant A triggers GET /api/plants/a", async ({ page }) => {
    // Listener installed BEFORE the click so we see the network request
    // deterministically. page.on('request', ...) fires for MSW-intercepted
    // fetches just like for real-network ones.
    const requests: string[] = [];
    page.on("request", (req) => {
      const u = new URL(req.url());
      if (u.pathname.startsWith("/api/plants/")) {
        requests.push(u.pathname);
      }
    });

    await page.getByRole("button", { name: "Plant A", exact: true }).click();

    // Wait for the fetch to go out. prefetchQuery is fire-and-forget
    // but still lands on the network layer synchronously after the
    // click.
    await expect
      .poll(() => requests.filter((p) => p === "/api/plants/a").length, {
        timeout: 5000,
      })
      .toBeGreaterThan(0);
  });
});
