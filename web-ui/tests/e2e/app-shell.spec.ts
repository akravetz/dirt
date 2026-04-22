// End-to-end acceptance for the app shell (brand, primary-nav tabs,
// theme toggle, route transitions, aria-current, console hygiene).
//
// This file is the REFERENCE IMPLEMENTATION for future FE features'
// Playwright specs — see tests/e2e/README.md for the authoring
// conventions it embodies:
//
//   - One `test(...)` block per distinct assertion from the plan-JSON
//     acceptance[].description. The evaluator audits coverage by
//     matching description assertions to test cases; bundling them
//     into one mega-test produces a passing-but-ambiguous coverage
//     report.
//   - Typed locators (`getByRole`, `getByLabel`, `getByText`) instead
//     of raw CSS where possible. When the rendered DOM doesn't
//     trivially expose an accessible handle (e.g. `aria-current` on a
//     native <button>), fall back to `page.evaluate` or a scoped
//     attribute locator rather than inventing `data-testid`s.
//   - Parity with docs/plans/evaluator-checks/app-shell.sh. The .sh
//     script remains the evaluator's current rubric for the already-
//     landed frontend.app.shell feature; this spec must stay in
//     lockstep with it until that .sh script is retired.
import { expect, test } from "@playwright/test";

import { collectConsoleErrors } from "./_helpers";

test.describe("app shell", () => {
  test("dirt. brand heading renders", async ({ page }) => {
    await page.goto("/");
    const heading = page.getByRole("heading", { level: 1 });
    // The trailing "." is a styled <span> inside <h1>; asserting on
    // textContent matches the legacy shell-script (which also accepts
    // "dirt" with or without the glyph).
    await expect(heading).toContainText("dirt");
  });

  test("exactly 3 primary-nav tab buttons (Dashboard / Live / Wiki)", async ({
    page,
  }) => {
    await page.goto("/");
    // Scope the count to the buttons whose visible label is one of the
    // three tabs. This tolerates the presence of other buttons in the
    // shell (theme toggle, log out) without making the assertion
    // brittle.
    const dashboard = page.getByRole("button", { name: "Dashboard", exact: true });
    const live = page.getByRole("button", { name: "Live", exact: true });
    const wiki = page.getByRole("button", { name: "Wiki", exact: true });
    await expect(dashboard).toHaveCount(1);
    await expect(live).toHaveCount(1);
    await expect(wiki).toHaveCount(1);
  });

  test("theme toggle button is present", async ({ page }) => {
    await page.goto("/");
    // Wait for React to hydrate the primary-nav before counting
    // auxiliary buttons — goto awaits `load`, which fires BEFORE
    // hydration, so querying synchronously sees a pre-hydration DOM.
    await expect(
      page.getByRole("button", { name: "Dashboard", exact: true }),
    ).toBeVisible();
    // Accessible name (aria-label OR visible text) matches
    // /theme|light|dark/i — same rubric as the legacy .sh script.
    // `getByRole`'s `name` option already unifies aria-label and
    // accessible name, so either spelling ("Switch to dark theme"
    // aria-label or a button whose visible text is "Light"/"Dark")
    // satisfies the match.
    const themeToggle = page.getByRole("button", {
      name: /theme|light|dark/i,
    });
    expect(await themeToggle.count()).toBeGreaterThan(0);
  });

  test("clicking Dashboard navigates to / with aria-current=page", async ({
    page,
  }) => {
    // Start on /live so clicking Dashboard actually produces a
    // transition — otherwise a bugged implementation that never
    // updates the URL could still pass.
    await page.goto("/live");
    const btn = page.getByRole("button", { name: "Dashboard", exact: true });
    await btn.click();
    await expect(page).toHaveURL(/\/$/);
    await expect(btn).toHaveAttribute("aria-current", "page");
  });

  test("clicking Live navigates to /live with aria-current=page", async ({
    page,
  }) => {
    await page.goto("/");
    const btn = page.getByRole("button", { name: "Live", exact: true });
    await btn.click();
    await expect(page).toHaveURL(/\/live$/);
    await expect(btn).toHaveAttribute("aria-current", "page");
  });

  test("clicking Wiki navigates to /wiki with aria-current=page", async ({
    page,
  }) => {
    await page.goto("/");
    const btn = page.getByRole("button", { name: "Wiki", exact: true });
    await btn.click();
    await expect(page).toHaveURL(/\/wiki$/);
    await expect(btn).toHaveAttribute("aria-current", "page");
  });

  test("page console has no error-level entries", async ({ page }) => {
    const errors = collectConsoleErrors(page);
    await page.goto("/");
    // Touch each primary-nav route so any lazy-loaded chunk that would
    // explode on navigation gets exercised inside this same assertion.
    await page.getByRole("button", { name: "Live", exact: true }).click();
    await expect(page).toHaveURL(/\/live$/);
    await page.getByRole("button", { name: "Wiki", exact: true }).click();
    await expect(page).toHaveURL(/\/wiki$/);
    await page.getByRole("button", { name: "Dashboard", exact: true }).click();
    await expect(page).toHaveURL(/\/$/);
    expect(errors.read()).toEqual([]);
  });
});
