---
title: MSW v2 — Testing with Vitest
concept: msw-v2
mode: library
version: 2.x
updated: 2026-04-21
---

# Testing with Vitest

## Setup

See the node-mode wiring in [setup.md](setup.md). `setupServer(...handlers)` is imported from `web-ui/src/mocks/server.ts`; its lifecycle attaches in a test-setup file listed under `test.setupFiles` in `vitest.config.ts`:

```ts
// web-ui/src/test-setup.ts
import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./mocks/server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

## Lifecycle

- `listen` — start intercepting. Once per test run.
- `resetHandlers` — after each test, remove any per-test handlers added via `server.use(...)`. The default `handlers` array from `mocks/handlers.ts` stays registered.
- `close` — stop intercepting. Once at the end.

`onUnhandledRequest: "error"` makes any unmocked `fetch` fail the test. This is the right policy for tests — an unmocked fetch is never what you want in a test process.

## Per-test overrides

Use `server.use(...)` inside a test to override the default handlers just for that test. Override is torn down by `afterEach(resetHandlers)`:

```ts
import { http, HttpResponse } from "msw";
import { render, screen } from "@testing-library/react";
import { server } from "../mocks/server";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SensorGauge } from "./SensorGauge";

test("SensorGauge renders crit status when temperature is out of band", async () => {
  server.use(
    http.get("/api/sensors/current", () =>
      HttpResponse.json({
        temperature_c: 40, // above the crit band
        // ... other required fields
      }),
    ),
  );

  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });

  render(
    <QueryClientProvider client={client}>
      <SensorGauge metric="temperature_c" />
    </QueryClientProvider>,
  );

  expect(await screen.findByText(/crit/i)).toBeInTheDocument();
});
```

## Error-path testing

Simulate a 500 to exercise error UI:

```ts
server.use(
  http.get("/api/sensors/current", () =>
    HttpResponse.json({ error: "internal" }, { status: 500 }),
  ),
);
```

Combine with `retry: false` on the QueryClient so the test doesn't wait for retry backoffs.

## Asserting a handler was hit

`setupServer` emits events:

```ts
const matched: Request[] = [];
server.events.on("request:match", ({ request }) => matched.push(request));

// ... run the component ...

expect(
  matched.filter((r) => r.url.endsWith("/api/sensors/current")),
).toHaveLength(1);
```

Useful for dedup/cache/refetch assertions.

## Component-level patterns

Render the component with a fresh `QueryClient` per test, disable retries, let MSW respond. No need to mock the api-client module or inject fakes — the network layer is already mocked. Keeps tests close to the real integration and avoids `vi.mock("@/api-client")`, which is blocked by the TS-08 invariant anyway.

## Common pitfall

If a test hangs, check that it's not waiting for Query's exponential retry backoff on an error response. Either set `retry: false` on the QueryClient or use fake timers + `vi.advanceTimersByTime(...)`. Retry-false is almost always what you want in tests.
