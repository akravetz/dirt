// End-to-end acceptance for frontend.dashboard.plants_strip.
//
// Each `test(...)` block maps 1:1 to a distinct assertion in the plan-
// JSON acceptance[].description for this feature. The evaluator runs a
// coverage audit against the description; collapsing these into one
// mega-test would obscure which assertions are really exercised. See
// web-ui/tests/e2e/README.md §2.
//
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
      .getByRole("region", { name: "Environment history" })
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

  test("each card's soil-moisture bar surfaces aria-valuenow in [0,100] with the expected bounds", async ({
    page,
  }) => {
    // Shape+presence: every card's progressbar exposes aria-valuemin=0,
    // aria-valuemax=100, and a numeric aria-valuenow in that range.
    // Asserting literal percentages couples the spec to live moisture
    // data (which varies with each capture); the contract is [0, 100].
    for (const name of ["Plant A", "Plant B", "Plant C", "Plant D"]) {
      const card = page.getByRole("button", { name, exact: true });
      const bar = card.getByRole("progressbar");
      await expect(bar).toHaveAttribute("aria-valuemin", "0");
      await expect(bar).toHaveAttribute("aria-valuemax", "100");
      const raw = await bar.getAttribute("aria-valuenow");
      expect(raw).not.toBeNull();
      const pct = Number(raw);
      expect(Number.isFinite(pct)).toBe(true);
      expect(pct).toBeGreaterThanOrEqual(0);
      expect(pct).toBeLessThanOrEqual(100);
    }
  });

  test("clicking plant A triggers GET /api/plants/a", async ({ page }) => {
    // Listener installed BEFORE the click so we see the network request
    // deterministically.
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
