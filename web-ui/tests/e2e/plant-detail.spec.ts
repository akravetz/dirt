// End-to-end acceptance for frontend.plant_detail.
//
// Each `test(...)` block maps 1:1 to a distinct assertion in the plan-
// JSON acceptance[].description for this feature. The evaluator runs a
// coverage audit against the description; collapsing these into one
// mega-test would obscure which assertions are really exercised. See
// web-ui/tests/e2e/README.md §2.
//
import { expect, test } from "@playwright/test";

type PlantDetailPayload = {
  plant_id: string;
  sticker_color: string | null;
  name: string;
  status: string;
  moisture: { current_pct: number | null };
  timeline: unknown[];
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function assertPlantDetailPayload(value: unknown): asserts value is PlantDetailPayload {
  expect(isRecord(value)).toBe(true);
  if (!isRecord(value)) {
    throw new Error("plant detail payload must be an object");
  }
  expect(typeof value.plant_id).toBe("string");
  expect(typeof value.name).toBe("string");
  expect(typeof value.status).toBe("string");
  expect(value.sticker_color === null || typeof value.sticker_color === "string").toBe(
    true,
  );
  expect(Array.isArray(value.timeline)).toBe(true);
  expect(isRecord(value.moisture)).toBe(true);
  if (!isRecord(value.moisture)) {
    throw new Error("plant detail moisture payload must be an object");
  }
  expect(
    value.moisture.current_pct === null ||
      typeof value.moisture.current_pct === "number",
  ).toBe(true);
}

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
    // Capture the response so the header assertions derive from the
    // live payload rather than hard-coded values.
    const responsePromise = page.waitForResponse(
      (resp) =>
        new URL(resp.url()).pathname === "/api/plants/a" && resp.ok(),
    );
    await page.getByRole("button", { name: "Plant A", exact: true }).click();
    const payload: unknown = await (await responsePromise).json();
    assertPlantDetailPayload(payload);

    const dialog = page.getByRole("dialog", { name: "Plant detail" });
    await expect(dialog).toBeVisible();
    expect(payload.plant_id).toBe("a");

    // Sticker chip surfaces its colour via data-color — whatever the
    // response reports.
    const sticker = dialog.getByLabel("sticker");
    if (payload.sticker_color === null) {
      await expect(sticker).not.toHaveAttribute("data-color");
    } else {
      await expect(sticker).toHaveAttribute("data-color", payload.sticker_color);
    }

    // Name rendered as a heading inside the drawer.
    await expect(
      dialog.getByRole("heading", { level: 2, name: payload.name }),
    ).toBeVisible();

    // Status row displays a title-cased status word matching the
    // response's enum value ("primary" | "secondary" | "retired").
    const statusRow = dialog.getByRole("status", { name: "Plant status" });
    const expectedStatus =
      payload.status.charAt(0).toUpperCase() + payload.status.slice(1);
    await expect(statusRow).toHaveText(expectedStatus);
  });

  test("moisture hero displays moisture.current_pct from the response", async ({
    page,
  }) => {
    const responsePromise = page.waitForResponse(
      (resp) =>
        new URL(resp.url()).pathname === "/api/plants/a" && resp.ok(),
    );
    await page.getByRole("button", { name: "Plant A", exact: true }).click();
    const payload: unknown = await (await responsePromise).json();
    assertPlantDetailPayload(payload);

    const dialog = page.getByRole("dialog", { name: "Plant detail" });
    await expect(dialog).toBeVisible();

    const moisture = dialog.getByRole("region", { name: "Moisture" });
    // Hero renders the integer percent; live value drifts per capture,
    // so assert against the response's own reported number (rounded to
    // the integer the hero displays).
    expect(payload.moisture.current_pct).not.toBeNull();
    const rounded = Math.round(payload.moisture.current_pct ?? 0).toString();
    await expect(moisture).toContainText(rounded);
    await expect(moisture).toContainText("%");
  });

  test("timeline list row count equals response.timeline.length", async ({
    page,
  }) => {
    const responsePromise = page.waitForResponse(
      (resp) =>
        new URL(resp.url()).pathname === "/api/plants/a" && resp.ok(),
    );
    await page.getByRole("button", { name: "Plant A", exact: true }).click();
    const payload: unknown = await (await responsePromise).json();
    assertPlantDetailPayload(payload);

    const dialog = page.getByRole("dialog", { name: "Plant detail" });
    await expect(dialog).toBeVisible();

    // Row count == the live response's timeline length — the plan's
    // literal contract. Real grow history grows over time.
    const expectedCount = payload.timeline.length;
    expect(expectedCount).toBeGreaterThan(0);
    const timeline = dialog.getByRole("region", { name: "Timeline" });
    await expect(timeline.getByLabel("timeline entry")).toHaveCount(expectedCount);
    await expect(timeline.getByRole("listitem")).toHaveCount(expectedCount);
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
