---
title: MSW v2 Reference Pack
concept: msw-v2
mode: library
version: 2.x
updated: 2026-04-21
---

# MSW v2 (Mock Service Worker)

This pack covers **MSW v2.x** for intercepting network requests in the dev loop, interactive browser testing, and node-based unit tests. v2 shipped Oct 2023 as a breaking rewrite of v1's API: the `rest` namespace was replaced with `http`, the `(req, res, ctx)` resolver signature collapsed into `({ request, params, cookies }) => HttpResponse.json(...)`, and entry points split into `msw/browser` (Service Worker) and `msw/node` (request interceptor). This pack exists because training data commonly drifts back to v1 patterns like `rest.get('/api/foo', (req, res, ctx) => res(ctx.json({...})))` — that syntax is wrong for v2, and v2 is what's installed.

## When to consult this pack

Read this INDEX and the relevant topic files before writing any code that:

- Imports from `msw`, `msw/browser`, or `msw/node`.
- Defines a request handler (`http.get`, `http.post`, `http.put`, `http.patch`, `http.delete`, or `graphql.query`/`mutation`).
- Configures `setupWorker` (browser) or `setupServer` (node / Vitest).
- Starts or stops the worker/server in a dev entry or test hook (`beforeAll` / `afterEach` / `afterAll`).
- Runs `msw init <public-dir>` or edits `public/mockServiceWorker.js`.
- Adds a fixture for an FE feature that needs a mocked backend response during parallel development.

## Dirt-specific wiring

In this repo, MSW runs in two contexts:

1. **Dev loop** — `pnpm --dir web-ui dev` on `:5173`. The Service Worker intercepts `fetch` in the browser and serves fixtures declared in `web-ui/src/mocks/handlers.ts`. Guarded by `if (import.meta.env.DEV)` in `web-ui/src/main.tsx` so the import + start happen only in dev.
2. **Vitest unit tests** — node-mode `setupServer` intercepts `fetch` in the test process. Same handler registry, different host.

Production build (`pnpm build` → `web-ui/dist/` served by FastAPI on `:8001`) has MSW tree-shaken out entirely. Verify with `grep -l msw web-ui/dist/**/*.js` returning nothing. No post-BE-merge "wire-up" step is needed: once the real endpoint lands, prod hits real BE on same-origin; dev continues to mock for fast loops until someone deletes the handler.

ESLint boundaries forbid importing from `web-ui/src/mocks/**` anywhere except the dev-entry shim in `main.tsx` and test files. UI components, routes, and the api-client never import mocks — they fetch normally, MSW intercepts at the network layer.

## Topics

- **[Setup & wiring](setup.md)** — install, `msw init <public-dir>`, `setupWorker` vs `setupServer` import paths, dev-entry conditional start, `onUnhandledRequest` policy choices, the `mockServiceWorker.js` quirk.
- **[Request handlers](handlers.md)** — `http.{get,post,put,patch,delete}` + the `({ request, params, cookies })` resolver arg, `HttpResponse.json` / `.text` / `.error`, status codes, headers, `new URL(request.url).searchParams` for query access, body parsing, path params, passthrough.
- **[TanStack Query integration](react-query.md)** — how MSW interception interacts with Query's cache, retries, and error handling; recommended test patterns against a Query-wrapped component.
- **[Testing with Vitest](testing.md)** — `setupServer`, the `beforeAll` / `afterEach` / `afterAll` lifecycle, `server.use(...)` for per-test handler overrides, `onUnhandledRequest: 'error'` in tests to catch unmocked fetches loudly.
- **[Retired v1 patterns](retired-v1.md)** — side-by-side v1 → v2 migration. Consult when a suggestion or edit smells like v1 (`rest.get`, `res(ctx.json(...))`, `req.url.searchParams`, `ctx.status`).

## Version-specific warnings

Training data will likely suggest these patterns. They are **wrong for v2**:

- `import { rest } from 'msw'` — **removed in v2**. Use `import { http, HttpResponse } from 'msw'`. See [retired-v1.md](retired-v1.md).
- `rest.get('/api/foo', (req, res, ctx) => res(ctx.json({...})))` — **v1 resolver signature**. In v2: `http.get('/api/foo', () => HttpResponse.json({...}))`. See [handlers.md](handlers.md).
- `ctx.status(500)` / `ctx.json(...)` / `ctx.text(...)` — **gone**. Status and body come from the `HttpResponse` factory: `new HttpResponse(null, { status: 500 })` or `HttpResponse.json(body, { status: 201 })`. See [handlers.md](handlers.md).
- `req.url.searchParams.get('q')` — v1 exposed a parsed URL on the request. In v2, `request.url` is a string; wrap with `new URL(request.url).searchParams.get('q')`. See [handlers.md](handlers.md).
- `import { setupWorker } from 'msw'` — **moved**. v2 is `import { setupWorker } from 'msw/browser'`. Node tests use `import { setupServer } from 'msw/node'`. See [setup.md](setup.md).
- `msw init <dir>` without `--save` — **will not persist the `msw.workerDirectory` config in package.json**; subsequent installs/upgrades won't know where the worker lives. Always pass `--save`. See [setup.md](setup.md).
- `ctx.delay(ms)` — removed. Use `await new Promise(r => setTimeout(r, ms))` inside an async resolver. See [retired-v1.md](retired-v1.md).
