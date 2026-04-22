// End-to-end acceptance for frontend.plant_detail.
//
// Each `test(...)` block maps 1:1 to a distinct assertion in the plan-
// JSON acceptance[].description for this feature. The evaluator runs a
// coverage audit against the description; collapsing these into one
// mega-test would obscure which assertions are really exercised. See
// web-ui/tests/e2e/README.md §2.
//
// Fixtures come from the MSW handlers for /api/plants/:code and
// /api/plants/:code/moisture in web-ui/src/mocks/handlers.ts (six-entry
// timeline, sticker A=yellow, moisture.current_pct=62). MSW intercepts
// in dev AND in the Vite build Playwright runs against, so the spec is
// independent of the backend stack.
import { expect, test } from "@playwright/test";

test.describe("plant detail", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
    // Wait for the plants strip to mount before interacting. The
    // drawer is only reachable via a click on one of the four cards.
    await expect(page.getByRole("region", { name: "Plants" })).toBeVisible();
  });

  test("clicking plant A's card opens the drawer", async ({ page }) => {
    // Drawer starts hidden.
    await expect(page.getByRole("dialog", { name: "Plant detail" })).toHaveCount(0);
    await page.getByRole("button", { name: "Plant A", exact: true }).click();
    await expect(
      page.getByRole("dialog", { name: "Plant detail" }),
    ).toBeVisible();
  });

  test("drawer header shows sticker + name + status tag from /api/plants/a", async ({
    page,
  }) => {
    await page.getByRole("button", { name: "Plant A", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Plant detail" });
    await expect(dialog).toBeVisible();

    // Sticker chip surfaces its colour via data-color, matching
    // fixture sticker_color=yellow for plant A.
    await expect(dialog.getByLabel("sticker")).toHaveAttribute("data-color", "yellow");

    // Name rendered as a heading inside the drawer.
    await expect(
      dialog.getByRole("heading", { level: 2, name: "Plant A" }),
    ).toBeVisible();

    // Status + label rows from the fixture (status=primary →
    // "Primary"; label="Primary · bushy").
    const statusRow = dialog.getByRole("status", { name: "Plant status" });
    await expect(statusRow).toHaveText("Primary");
    await expect(dialog).toContainText("Primary · bushy");
  });

  test("moisture hero displays moisture.current_pct from the response", async ({
    page,
  }) => {
    await page.getByRole("button", { name: "Plant A", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Plant detail" });
    await expect(dialog).toBeVisible();

    // Fixture sets moisture.current_pct=62 for plant A. The hero
    // renders the integer inside a Moisture section; scoping to the
    // section avoids accidental matches against the timeline (entry
    // counts, day numbers, etc.).
    const moisture = dialog.getByRole("region", { name: "Moisture" });
    await expect(moisture).toContainText("62");
    await expect(moisture).toContainText("%");
  });

  test("timeline list row count equals response.timeline.length", async ({
    page,
  }) => {
    await page.getByRole("button", { name: "Plant A", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Plant detail" });
    await expect(dialog).toBeVisible();

    // MSW fixture yields exactly 6 timeline entries for every plant.
    // Each <li> is itself labelled "timeline entry" and belongs to the
    // timeline <ul>; scoping via the Timeline section landmark guards
    // against accidental matches if other regions gain listitems later.
    const timeline = dialog.getByRole("region", { name: "Timeline" });
    await expect(timeline.getByLabel("timeline entry")).toHaveCount(6);
    await expect(timeline.getByRole("listitem")).toHaveCount(6);
  });

  test("pressing ESC closes the drawer", async ({ page }) => {
    await page.getByRole("button", { name: "Plant A", exact: true }).click();
    const dialog = page.getByRole("dialog", { name: "Plant detail" });
    await expect(dialog).toBeVisible();

    // The drawer takes focus on mount via useEffect-driven
    // dialogRef.focus(); pressing Escape on the page is routed to it.
    await page.keyboard.press("Escape");

    // Dialog unmounts when parent flips selectedPlant → null.
    await expect(dialog).toHaveCount(0);
  });
});
