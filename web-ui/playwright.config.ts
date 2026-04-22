import { defineConfig, devices } from "@playwright/test";

// Playwright config for the web-ui e2e suite.
//
// CONVENTIONS (see tests/e2e/README.md for the full authoring guide):
//
// - `testDir: "./tests/e2e"` — one .spec.ts per FE feature.
// - `baseURL` defaults to http://localhost:5173 (the Vite dev server
//   started by `pnpm dev`). Override with the `PLAYWRIGHT_BASE_URL`
//   env var when a parallel worktree already holds the default port.
// - Chromium only by default — Dirt has no cross-browser matrix; the
//   e2e suite is a harness for asserting the app's own DOM contract,
//   not a browser-compatibility check. Adding Firefox/WebKit here
//   would triple install + runtime cost for zero coverage gain.
// - `webServer` is intentionally NOT configured. We assume the
//   operator already has `pnpm dev` running on :5173 (or the
//   overridden baseURL); CI scripts start it externally. Wiring a
//   webServer block here would race against an already-running dev
//   server across worktrees and produce EADDRINUSE-flavoured
//   failures that mask real test errors.
//
// To run locally:
//     pnpm --dir web-ui dev                   # terminal 1
//     pnpm --dir web-ui test:e2e              # terminal 2
//
// First-time-per-machine setup (NOT per-worktree — browser binaries
// are a machine-level install):
//     pnpm --dir web-ui exec playwright install --with-deps chromium
export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:5173",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
