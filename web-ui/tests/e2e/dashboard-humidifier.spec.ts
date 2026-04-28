// End-to-end acceptance for the dashboard humidifier metric.
//
// Humidifier is now part of the contract-driven sensor dashboard:
// /api/sensors/metadata includes `humidifier_intensity_pct`, the gauge
// renders it as "Humidifier", and /api/sensors/history serves its
// sparkline. There is no separate /api/humidifier/* widget in the
// current app.
import { expect, test } from "@playwright/test";

test.describe("dashboard humidifier metric", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("region", { name: "Environment gauges" }),
    ).toBeVisible();
    await expect(
      page.getByRole("article", { name: "Humidifier", exact: true }),
    ).toBeVisible();
  });

  test("humidifier tile renders the normalized intensity percent", async ({
    page,
  }) => {
    const tile = page.getByRole("article", { name: "Humidifier", exact: true });
    await expect(tile).toContainText(/\d/);
    await expect(tile).toContainText("%");
  });

  test("humidifier tile surfaces its envelope status", async ({ page }) => {
    const tile = page.getByRole("article", { name: "Humidifier", exact: true });
    const status = tile.getByRole("status");
    await expect(status).toHaveText(/^(ok|warn|crit)$/);
    const text = (await status.textContent())?.trim() ?? "";
    await expect(status).toHaveAttribute("data-status", text);
  });

  test("humidifier tile does not invent a target band", async ({ page }) => {
    const tile = page.getByRole("article", { name: "Humidifier", exact: true });
    await expect(tile.getByLabel("target band")).toHaveCount(0);
  });

  test("humidifier sparkline renders from /api/sensors/history", async ({
    page,
  }) => {
    const article = page.getByRole("article", { name: "Humidifier sparkline" });
    await expect(article).toBeVisible();
    await expect(article.getByLabel("sparkline", { exact: true })).toBeVisible();
  });

  test("range changes fetch humidifier history for the selected range", async ({
    page,
  }) => {
    const requests: { range: string | null; metric: string | null }[] = [];
    page.on("request", (req) => {
      const url = new URL(req.url());
      if (url.pathname !== "/api/sensors/history") return;
      requests.push({
        range: url.searchParams.get("range"),
        metric: url.searchParams.get("metric"),
      });
    });

    await page.goto("/");
    await expect(
      page.getByRole("article", { name: "Humidifier sparkline" }),
    ).toBeVisible();

    const rangeGroup = page.getByRole("group", { name: "Sparkline range" });
    await rangeGroup.getByRole("button", { name: "1h" }).click();

    await expect
      .poll(
        () =>
          requests.filter(
            (r) =>
              r.range === "1h" && r.metric === "humidifier_intensity_pct",
          ).length,
        { timeout: 5000 },
      )
      .toBe(1);
  });
});
