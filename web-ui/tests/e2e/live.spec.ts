// End-to-end acceptance for frontend.live.
//
// Each `test(...)` block maps 1:1 to a distinct assertion in the plan-
// JSON acceptance[].description for this feature:
//   1. img renders whose src targets /api/feed/live.jpg
//   2. img's src is refreshed (cache-busting) within ~10s
//   3. Clicking on feed fires POST /api/ptz/look with x/y in [-1, 1]
//   4. Clicking a preset row fires POST /api/ptz/preset/{id} with the
//      matching id
//   5. Dragging the zoom slider fires POST /api/ptz/zoom
//
// Fixtures come from MSW handlers in web-ui/src/mocks/handlers.ts:
//   - /api/feed/live.jpg          → 1×1 JPEG (Content-Type image/jpeg,
//                                   Cache-Control no-store)
//   - /api/ptz/state              → 5 presets (overview + plant_a..d),
//                                   active preset "overview"
//   - /api/ptz/preset/{id}        → updates state, echoes PTZApplied
//   - /api/ptz/look               → updates state, nulls preset, echoes
//                                   PTZApplied
//   - /api/ptz/zoom               → 200 (exactly one of zoom|delta), 422
//                                   otherwise
import { expect, test } from "@playwright/test";

import { collectConsoleErrors } from "./_helpers";

test.describe("live tab", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/live");
    // Wait for the live feed + preset list to mount so subsequent
    // assertions have a settled DOM to target.
    await expect(
      page.getByRole("figure", { name: "Live camera feed" }),
    ).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Presets" }),
    ).toBeVisible();
  });

  test("img element renders whose src targets /api/feed/live.jpg", async ({
    page,
  }) => {
    const figure = page.getByRole("figure", { name: "Live camera feed" });
    const img = figure.locator("img");
    await expect(img).toBeVisible();
    // src carries the cache-bust query param, so match the path prefix.
    const src = await img.getAttribute("src");
    expect(src).not.toBeNull();
    expect(src ?? "").toMatch(/^\/api\/feed\/live\.jpg(\?|$)/);
  });

  test("img's src is refreshed via cache-busting within ~10s", async ({
    page,
  }) => {
    // Clock travel — advance fake time without waiting wall-clock 10s.
    // CameraFeed uses setInterval(…, 10_000); Playwright's page.clock
    // installs a mock clock that advances on fastForward().
    await page.clock.install();
    await page.goto("/live");

    const figure = page.getByRole("figure", { name: "Live camera feed" });
    const img = figure.locator("img");
    await expect(img).toBeVisible();

    const initial = await img.getAttribute("src");
    expect(initial).not.toBeNull();

    // Track every request to /api/feed/live.jpg so we can observe the
    // refresh in the network layer as well as in the DOM attribute.
    const feedRequests: string[] = [];
    page.on("request", (req) => {
      const url = new URL(req.url());
      if (url.pathname === "/api/feed/live.jpg") {
        feedRequests.push(url.search); // different query params per tick
      }
    });

    // Advance the clock past REFRESH_MS (10_000ms) to trigger the
    // setInterval callback in CameraFeed, which rotates the cache-bust
    // query param and causes a fresh fetch.
    await page.clock.fastForward(12_000);

    // Wait for the src attribute to observably change.
    await expect
      .poll(async () => await img.getAttribute("src"), { timeout: 5_000 })
      .not.toBe(initial);

    // And confirm at least one fresh network request was issued.
    expect(feedRequests.length).toBeGreaterThan(0);
  });

  test("clicking on the feed fires POST /api/ptz/look with x and y in [-1, 1]", async ({
    page,
  }) => {
    const lookRequests: Array<{ x: number; y: number }> = [];
    page.on("request", async (req) => {
      if (req.url().endsWith("/api/ptz/look") && req.method() === "POST") {
        const body = req.postData();
        if (body) {
          const parsed = JSON.parse(body) as { x: number; y: number };
          lookRequests.push(parsed);
        }
      }
    });

    const feedButton = page
      .getByRole("figure", { name: "Live camera feed" })
      .getByRole("button", { name: "Live camera feed" });
    await expect(feedButton).toBeVisible();

    const box = await feedButton.boundingBox();
    expect(box).not.toBeNull();
    if (!box) return;

    // Click at ~75% across, 25% down → expected normalized (0.5, -0.5).
    const targetX = box.x + box.width * 0.75;
    const targetY = box.y + box.height * 0.25;
    await page.mouse.click(targetX, targetY);

    await expect.poll(() => lookRequests.length, { timeout: 5_000 }).toBe(1);
    const body = lookRequests[0];
    expect(body).toBeDefined();
    if (!body) return;
    // Both coords must be inside [-1, 1]; exact values within a pixel of
    // the click position expectation.
    expect(body.x).toBeGreaterThanOrEqual(-1);
    expect(body.x).toBeLessThanOrEqual(1);
    expect(body.y).toBeGreaterThanOrEqual(-1);
    expect(body.y).toBeLessThanOrEqual(1);
    expect(body.x).toBeGreaterThan(0.4);
    expect(body.x).toBeLessThan(0.6);
    expect(body.y).toBeGreaterThan(-0.6);
    expect(body.y).toBeLessThan(-0.4);
  });

  test("clicking a preset row fires POST /api/ptz/preset/{id} with the matching id", async ({
    page,
  }) => {
    const presetPosts: string[] = [];
    page.on("request", (req) => {
      const url = new URL(req.url());
      const match = url.pathname.match(/^\/api\/ptz\/preset\/([^/]+)$/);
      if (match?.[1] && req.method() === "POST") {
        presetPosts.push(match[1]);
      }
    });

    // Click the "Plant B" row — id="plant_b" in the fixture.
    const presets = page.getByRole("region", { name: "Presets" });
    await presets.getByRole("button", { name: "Plant B" }).click();

    await expect.poll(() => presetPosts, { timeout: 5_000 }).toContain("plant_b");

    // Different preset → different id in the request URL, confirming
    // id matches the clicked row rather than a hardcoded value.
    await presets.getByRole("button", { name: "Plant D" }).click();
    await expect.poll(() => presetPosts, { timeout: 5_000 }).toContain("plant_d");
  });

  test("dragging the zoom slider fires POST /api/ptz/zoom on release", async ({
    page,
  }) => {
    const zoomPosts: Array<{ zoom?: number; delta?: number }> = [];
    page.on("request", (req) => {
      if (req.url().endsWith("/api/ptz/zoom") && req.method() === "POST") {
        const body = req.postData();
        if (body) {
          zoomPosts.push(JSON.parse(body));
        }
      }
    });

    const zoomSlider = page.getByLabel("Zoom");
    await expect(zoomSlider).toBeVisible();

    // Focus, then step the range up a few times via keyboard (the
    // native range input sends ArrowRight as a +step commit). Pressing
    // and releasing the key fires onKeyUp → commit → POST /api/ptz/zoom.
    await zoomSlider.focus();
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("ArrowRight");
    await page.keyboard.press("ArrowRight");

    // At least one POST /api/ptz/zoom fires; the final body reflects the
    // new absolute zoom value.
    await expect.poll(() => zoomPosts.length, { timeout: 5_000 }).toBeGreaterThan(0);
    const last = zoomPosts[zoomPosts.length - 1];
    expect(last).toBeDefined();
    if (!last) return;
    // New value is an absolute zoom (the component posts {zoom} on
    // commit); and it must be greater than the starting value of 1.
    expect(typeof last.zoom).toBe("number");
    if (typeof last.zoom === "number") {
      expect(last.zoom).toBeGreaterThan(1);
      expect(last.zoom).toBeLessThanOrEqual(4);
    }
  });

  test("page console has no error-level entries after exercising the tab", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/live");
    await expect(
      page.getByRole("figure", { name: "Live camera feed" }),
    ).toBeVisible();
    // Touch each interactive primitive so any lazy render path is hit.
    await page
      .getByRole("region", { name: "Presets" })
      .getByRole("button", { name: "Plant A" })
      .click();
    await page.getByLabel("Zoom").focus();
    await page.keyboard.press("ArrowRight");
    expect(errors.read()).toEqual([]);
  });
});
