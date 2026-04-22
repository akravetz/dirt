---
title: MSW v2 — Retired v1 patterns
concept: msw-v2
mode: library
version: 2.x
updated: 2026-04-21
---

# Retired v1 patterns

Side-by-side. If a code suggestion matches the LEFT column, it's v1 and must not be used.

## Imports

| v1 (WRONG) | v2 (RIGHT) |
|---|---|
| `import { rest, setupWorker } from "msw"` | `import { http, HttpResponse } from "msw"`<br>`import { setupWorker } from "msw/browser"` |
| `import { rest } from "msw"` (for node) | `import { http, HttpResponse } from "msw"`<br>`import { setupServer } from "msw/node"` |
| `import { setupServer } from "msw/node"` | *(unchanged — same in v2)* |

## Request handlers

**v1:**

```ts
rest.get("/api/foo", (req, res, ctx) => {
  return res(ctx.status(200), ctx.json({ ok: true }));
});
```

**v2:**

```ts
http.get("/api/foo", () => HttpResponse.json({ ok: true }));
```

Mapping:

- `rest.get` → `http.get` (same for `post` / `put` / `patch` / `delete` / etc.).
- Resolver signature: `(req, res, ctx)` → `({ request, params, cookies, requestId })`.
- Return form: `res(ctx.json(...))` → `HttpResponse.json(...)` directly.
- `ctx.status(201)` → second-arg `{ status: 201 }` on `HttpResponse.json`.
- `ctx.set("Header", "value")` → `{ headers: { Header: "value" } }` on the HttpResponse init.
- `ctx.delay(ms)` → not a built-in anymore; `await new Promise(r => setTimeout(r, ms))` inside the async resolver.
- `ctx.body(buffer)` / `ctx.xml(...)` → pass a `Blob` / `BodyInit` to the `HttpResponse` constructor.

## Request URL

**v1:**

```ts
rest.get("/api/foo", (req) => {
  const q = req.url.searchParams.get("q");
});
```

**v2:**

```ts
http.get("/api/foo", ({ request }) => {
  const q = new URL(request.url).searchParams.get("q");
});
```

## Body parsing

**v1:**

```ts
rest.post("/api/foo", async (req) => {
  const body = await req.json();
});
```

**v2:**

```ts
http.post("/api/foo", async ({ request }) => {
  const body = await request.json();
});
```

## Path params

**v1:**

```ts
rest.get("/api/plants/:code", (req) => {
  const code = req.params.code;
});
```

**v2:**

```ts
http.get("/api/plants/:code", ({ params }) => {
  const code = params.code as string;
});
```

## Cookies

**v1:** `req.cookies` available via `ctx.cookie(...)` for setting.
**v2:** `cookies` on the resolver arg for reading. For setting, return a response with `Set-Cookie` in headers:

```ts
HttpResponse.json({ user }, {
  headers: { "Set-Cookie": "dirt_session=abc; Path=/; HttpOnly" },
});
```

## Passthrough

**v1:** `return req.passthrough()`
**v2:** `return passthrough()` (imported from `msw`), or return `undefined` to fall through to the next handler in the array.

## Delays

**v1:** `res(ctx.delay(500), ctx.json(body))`
**v2:**

```ts
http.get("/api/slow", async () => {
  await new Promise((r) => setTimeout(r, 500));
  return HttpResponse.json(body);
});
```

## Once-handlers

**v1:** `rest.get.once(...)`
**v2:** `http.get(..., resolver, { once: true })`:

```ts
http.get("/api/retry-test", () => HttpResponse.error(), { once: true });
```

## Quick recognition cheat sheet

If a suggestion contains ANY of these tokens, it's v1 — reject it:

- `rest.get` / `rest.post` / `rest.put` / `rest.patch` / `rest.delete` / `rest.all`
- `res(ctx.json(...))` or any `res(ctx....)` pattern
- `ctx.status(...)` / `ctx.json(...)` / `ctx.text(...)` / `ctx.delay(...)` / `ctx.body(...)` / `ctx.cookie(...)` / `ctx.set(...)` / `ctx.xml(...)`
- `(req, res, ctx)` as the resolver signature
- `req.url.searchParams` (v1 gave you a parsed URL; v2 gives you a string)
- `req.params` (v2 lifts it out of `request` to the top-level resolver arg)
- `import { rest, ... } from "msw"`
- `import { setupWorker } from "msw"` (no `/browser` path)
