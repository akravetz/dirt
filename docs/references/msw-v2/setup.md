---
title: MSW v2 — Setup & wiring
concept: msw-v2
mode: library
version: 2.x
updated: 2026-04-21
---

# Setup & wiring

## Install

    pnpm add -D msw@^2

Generate the browser service-worker script (runs once per project):

    pnpm exec msw init web-ui/public --save

This writes `web-ui/public/mockServiceWorker.js` (commit it — the file is regenerated only on MSW major upgrades) and adds `msw.workerDirectory: "web-ui/public"` to `package.json` so re-runs know where the script lives. Omitting `--save` means subsequent `msw init` invocations forget the target directory.

## Browser mode (dev)

`web-ui/src/mocks/handlers.ts`:

```ts
import { http, HttpResponse } from "msw";

export const handlers = [
  // handlers go here; each FE feature appends its own
];
```

`web-ui/src/mocks/browser.ts`:

```ts
import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

export const worker = setupWorker(...handlers);
```

Wire into the dev entry (`web-ui/src/main.tsx`), guarded so prod tree-shakes it:

```ts
async function enableMocking() {
  if (!import.meta.env.DEV) return;
  const { worker } = await import("./mocks/browser");
  await worker.start({ onUnhandledRequest: "bypass" });
}

enableMocking().then(() => {
  // ... ReactDOM.createRoot(...).render(...)
});
```

### `onUnhandledRequest` policy

Decides what MSW does when a `fetch` hits a path no handler matches.

- `"bypass"` (Dirt dev default) — silently fall through to the real server. Right for dev: as BE endpoints land on `:8001`, FE hits them for real; anything not-yet-implemented is still mocked by whatever handlers exist.
- `"warn"` — log a warning but still pass through. Useful when you want to know about unmocked calls without breaking the loop.
- `"error"` — reject the request. Right for tests (any unmocked fetch is a bug).

## Node mode (Vitest)

`web-ui/src/mocks/server.ts`:

```ts
import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
```

Reference it from a test setup file (e.g. `web-ui/src/test-setup.ts`, listed under `test.setupFiles` in `vitest.config.ts`):

```ts
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./mocks/server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

`"error"` in tests because unmocked network is never what you want in a test process.

## `mockServiceWorker.js`

The file in `public/` is served at `/mockServiceWorker.js` by Vite's dev server (and would be served by FastAPI's static mount in prod — but prod doesn't start the worker, so the browser never requests it). Do NOT edit by hand — regenerate with `pnpm exec msw init` on major-version upgrades. Commit the file; it's required for browser-mode MSW to work.
