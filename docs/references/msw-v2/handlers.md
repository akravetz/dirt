---
title: MSW v2 — Request handlers
concept: msw-v2
mode: library
version: 2.x
updated: 2026-04-21
---

# Request handlers

## The `http` namespace

Replaces v1's `rest`. Imports:

```ts
import { http, HttpResponse } from "msw";
```

Per-method factories: `http.get`, `http.post`, `http.put`, `http.patch`, `http.delete`, `http.head`, `http.options`, `http.all`.

## Resolver signature

```ts
http.get("/api/sensors/current", ({ request, params, cookies, requestId }) => {
  // return an HttpResponse (or a Promise of one, or `undefined` to let the next handler try)
});
```

- `request` — standard `Request` object. `.url` is a **string**, `.headers` is `Headers`. Body accessors are `async`: `.json()`, `.text()`, `.formData()`, `.arrayBuffer()`.
- `params` — object of URL path params declared with `:name` in the path (e.g. `http.get("/api/plants/:code", ({ params }) => params.code)`).
- `cookies` — parsed request cookies as `Record<string, string>`.
- `requestId` — unique per-request UUID; useful for logging / event correlation.

## `HttpResponse` factory

`HttpResponse` builds an actual `Response` object. Common patterns:

```ts
HttpResponse.json({ ok: true });
HttpResponse.json(body, { status: 201, headers: { "Cache-Control": "no-store" } });
HttpResponse.text("plain body", { status: 202 });
HttpResponse.error();                           // network-level failure
new HttpResponse(null, { status: 204 });        // no-content
new HttpResponse(new Blob([...]), {
  headers: { "Content-Type": "image/jpeg" },
});
```

## Query params

`request.url` is a string — wrap in `new URL(...)` to get `searchParams`:

```ts
http.get("/api/sensors/history", ({ request }) => {
  const url = new URL(request.url);
  const range = url.searchParams.get("range") ?? "24h";
  const metric = url.searchParams.get("metric");
  if (!metric) return new HttpResponse(null, { status: 400 });
  return HttpResponse.json({ range, metric, points: [] });
});
```

## Body parsing

All body accessors are async. Call with `await`:

```ts
http.post("/api/auth/login", async ({ request }) => {
  const { username, password } = await request.json();
  if (password !== "correct") {
    return HttpResponse.json({ error: "invalid_credentials" }, { status: 401 });
  }
  return HttpResponse.json(
    { user: { username } },
    { headers: { "Set-Cookie": "dirt_session=mock; Path=/; HttpOnly" } },
  );
});
```

Form data (`multipart/form-data` or `application/x-www-form-urlencoded`):

```ts
http.post("/api/upload", async ({ request }) => {
  const form = await request.formData();
  const file = form.get("file") as File;
  return HttpResponse.json({ name: file.name, size: file.size });
});
```

## Passthrough

A handler returning `undefined` falls through to the next handler. A handler returning `passthrough()` bypasses MSW entirely and hits the real network:

```ts
import { passthrough } from "msw";

http.get("/api/real-only", () => passthrough());
```

## Path patterns

Handlers match against the URL pathname:

- Exact: `"/api/plants"`
- Path param: `"/api/plants/:code"` → `params.code`
- Wildcard suffix: `"/api/plants/*"` — matches any path under `/api/plants/`
- Absolute URL: `"http://example.com/api"` — matches only cross-origin requests to that host

Relative same-origin paths are idiomatic in dev since FE + BE share `:8001` in production.

## Handler ordering

Handlers in the array are tried top-to-bottom; first match wins. More-specific paths before wildcards is the convention, but the runtime just takes the first one that matches.

## Status-specific helpers

There's no `HttpResponse.badRequest()` etc. Use the status code directly:

```ts
HttpResponse.json({ error: "bad_request" }, { status: 400 });
HttpResponse.json({ error: "unauthorized" }, { status: 401 });
HttpResponse.json({ error: "not_found" }, { status: 404 });
HttpResponse.json({ error: "internal" }, { status: 500 });
```

## Delays

`ctx.delay(ms)` is retired. Use an async resolver with `setTimeout`:

```ts
http.get("/api/slow", async () => {
  await new Promise((r) => setTimeout(r, 1500));
  return HttpResponse.json({ ok: true });
});
```
