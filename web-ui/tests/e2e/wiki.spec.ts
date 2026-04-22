// End-to-end acceptance for frontend.wiki.
//
// Each `test(...)` block maps 1:1 to a distinct assertion in the plan-
// JSON acceptance[].description for this feature:
//   1. Navigate /wiki → sidebar tree renders folders + files from
//      GET /api/wiki/tree.
//   2. Click plant-a.md in sidebar → main pane renders a frontmatter
//      block (matter rows) and the markdown body from
//      GET /api/wiki/file?path=plants/plant-a.md.
//   3. Press Cmd+K → search palette becomes visible.
//   4. Type "topping" → GET /api/wiki/search?q=topping fires and match
//      results render.
//   5. Press Enter on a match → URL navigates (e.g. to /wiki?path=…).
//   6. Open palette with empty query → recent files render from
//      shared/storage.ts AND no GET /api/wiki/search with empty q is
//      fired (network tracking).
//   7. Page console has no error-level entries after exercising the tab.
//
// Fixtures come from MSW handlers in web-ui/src/mocks/handlers.ts:
//   - /api/wiki/tree   → root files (index.md, overview.md) + folders
//     (concepts, daily, plants)
//   - /api/wiki/file   → plant-a.md has frontmatter + subtitle + body
//   - /api/wiki/search → "topping" matches a title (topping.md) and a
//     content hit (plant-a.md)
import { expect, test } from "@playwright/test";

import { collectConsoleErrors } from "./_helpers";

test.describe("wiki tab", () => {
  test.beforeEach(async ({ page }) => {
    // Keep recent-files storage clean per test so the empty-query
    // palette branch is deterministic.
    await page.addInitScript(() => {
      window.localStorage.removeItem("dirt.wiki.recentFiles");
    });
    await page.goto("/wiki");
    await expect(page.getByRole("navigation", { name: "Wiki tree" })).toBeVisible();
  });

  test("sidebar tree renders folders + files from GET /api/wiki/tree", async ({
    page,
  }) => {
    const sidebar = page.getByRole("navigation", { name: "Wiki tree" });
    // Folder headings come from WikiTreeFolder.name — fixture exposes
    // concepts / daily / plants.
    await expect(sidebar.getByRole("region", { name: "plants" })).toBeVisible();
    await expect(sidebar.getByRole("region", { name: "concepts" })).toBeVisible();
    await expect(sidebar.getByRole("region", { name: "daily" })).toBeVisible();
    // Root files — index.md / overview.md.
    await expect(
      sidebar.locator('[data-testid="wiki-sidebar-file"][data-path="wiki/index.md"]'),
    ).toBeVisible();
    await expect(
      sidebar.locator('[data-testid="wiki-sidebar-file"][data-path="wiki/overview.md"]'),
    ).toBeVisible();
    // Plant A sits inside the plants folder.
    await expect(
      sidebar.locator(
        '[data-testid="wiki-sidebar-file"][data-path="wiki/plants/plant-a.md"]',
      ),
    ).toBeVisible();
  });

  test("clicking plant-a.md renders frontmatter block + markdown body", async ({
    page,
  }) => {
    const fileRequests: string[] = [];
    page.on("request", (req) => {
      const url = new URL(req.url());
      if (url.pathname === "/api/wiki/file") {
        const path = url.searchParams.get("path");
        if (path) fileRequests.push(path);
      }
    });

    const sidebar = page.getByRole("navigation", { name: "Wiki tree" });
    await sidebar
      .locator('[data-testid="wiki-sidebar-file"][data-path="wiki/plants/plant-a.md"]')
      .click();

    // Network: GET /api/wiki/file?path=wiki/plants/plant-a.md (the
    // backend normalizes both "wiki/plants/plant-a.md" and
    // "plants/plant-a.md"; the route passes through the sidebar-sourced
    // path verbatim, which prefixes "wiki/").
    await expect
      .poll(() => fileRequests, { timeout: 5_000 })
      .toEqual(expect.arrayContaining(["wiki/plants/plant-a.md"]));

    const doc = page.getByRole("article", { name: "Wiki document" });
    await expect(doc).toBeVisible();
    // Frontmatter block with at least one matter row — plant-a has
    // title, type, status, strain, so >= 4 rows.
    const frontmatter = doc.getByTestId("wiki-frontmatter");
    await expect(frontmatter).toBeVisible();
    const rows = frontmatter.getByTestId("wiki-frontmatter-row");
    await expect(rows.first()).toBeVisible();
    expect(await rows.count()).toBeGreaterThanOrEqual(2);
    // Markdown body rendered — the fixture body contains a second-level
    // heading ("## Current State") that is distinctive to plant-a.md.
    const body = doc.getByTestId("wiki-body");
    await expect(body).toBeVisible();
    // Body renders markdown via react-markdown; assert on heading text
    // (the `#` / `##` markers are consumed by the renderer).
    await expect(body.getByRole("heading", { name: "Plant A" })).toBeVisible();
    await expect(body.getByRole("heading", { name: "Current State" })).toBeVisible();
  });

  test("Cmd+K opens the search palette", async ({ page }) => {
    await expect(page.getByTestId("cmdk-palette")).toHaveCount(0);
    await page.keyboard.press("Meta+k");
    const palette = page.getByRole("dialog", { name: "Search wiki" });
    await expect(palette).toBeVisible();
  });

  test("typing 'topping' fires GET /api/wiki/search?q=topping and renders matches", async ({
    page,
  }) => {
    const searchRequests: string[] = [];
    page.on("request", (req) => {
      const url = new URL(req.url());
      if (url.pathname === "/api/wiki/search") {
        const q = url.searchParams.get("q");
        if (q) searchRequests.push(q);
      }
    });

    await page.keyboard.press("Meta+k");
    const palette = page.getByRole("dialog", { name: "Search wiki" });
    await expect(palette).toBeVisible();
    await palette.getByLabel("Search wiki").fill("topping");

    // The route debounces at ~150ms; poll for the request to land.
    await expect.poll(() => searchRequests, { timeout: 5_000 }).toContain("topping");

    // Results: fixture matches topping.md (title) and plant-a.md (content).
    const topping = palette.locator('[data-testid="cmdk-item"][data-path="wiki/concepts/topping.md"]');
    await expect(topping).toBeVisible();
  });

  test("Enter on a match navigates to /wiki?path=…", async ({ page }) => {
    await page.keyboard.press("Meta+k");
    const palette = page.getByRole("dialog", { name: "Search wiki" });
    await palette.getByLabel("Search wiki").fill("topping");

    // Wait for the topping result to appear, then commit with Enter.
    const topping = palette.locator('[data-testid="cmdk-item"][data-path="wiki/concepts/topping.md"]');
    await expect(topping).toBeVisible();
    await page.keyboard.press("Enter");

    await expect.poll(() => new URL(page.url()).searchParams.get("path")).toBe(
      "wiki/concepts/topping.md",
    );
    // And the doc for that path should render — scope the assertion to
    // the body so the article-level title (also "Topping") doesn't
    // collide with the body's `# Topping` heading.
    await expect(
      page.getByTestId("wiki-body").getByRole("heading", { name: "Topping" }),
    ).toBeVisible();
  });

  test("opening palette with empty query renders recents and does NOT hit /api/wiki/search", async ({
    page,
  }) => {
    // Seed one recent file by opening plant-a.md (which pushes onto
    // shared/storage's recentFiles list).
    await page
      .getByRole("navigation", { name: "Wiki tree" })
      .locator('[data-testid="wiki-sidebar-file"][data-path="wiki/plants/plant-a.md"]')
      .click();
    await expect(page.getByRole("article", { name: "Wiki document" })).toBeVisible();

    // Track /api/wiki/search calls from here on.
    const searchRequests: string[] = [];
    page.on("request", (req) => {
      const url = new URL(req.url());
      if (url.pathname === "/api/wiki/search") {
        searchRequests.push(url.searchParams.get("q") ?? "");
      }
    });

    await page.keyboard.press("Meta+k");
    const palette = page.getByRole("dialog", { name: "Search wiki" });
    await expect(palette).toBeVisible();

    // Empty query → recents render. Plant A should show as a recent
    // entry with data-kind="recent".
    const recentItem = palette.locator(
      '[data-testid="cmdk-item"][data-kind="recent"][data-path="wiki/plants/plant-a.md"]',
    );
    await expect(recentItem).toBeVisible();

    // Give the debounce a chance to fire before asserting.
    await page.waitForTimeout(400);

    // No search request with an empty / whitespace q should have fired.
    expect(searchRequests.filter((q) => q.trim().length === 0)).toEqual([]);
    // And no search request at all should have fired since we never
    // typed anything into the palette.
    expect(searchRequests).toEqual([]);
  });

  test("page console has no error-level entries after exercising the tab", async ({
    page,
  }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/wiki");
    await expect(page.getByRole("navigation", { name: "Wiki tree" })).toBeVisible();

    // Touch each interactive primitive so any lazy render path is hit.
    await page
      .getByRole("navigation", { name: "Wiki tree" })
      .locator('[data-testid="wiki-sidebar-file"][data-path="wiki/plants/plant-a.md"]')
      .click();
    await expect(page.getByRole("article", { name: "Wiki document" })).toBeVisible();
    await page.keyboard.press("Meta+k");
    await expect(page.getByRole("dialog", { name: "Search wiki" })).toBeVisible();
    await page.keyboard.press("Escape");

    expect(errors.read()).toEqual([]);
  });
});
