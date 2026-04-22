---
title: MSW v2 — TanStack Query integration
concept: msw-v2
mode: library
version: 2.x
updated: 2026-04-21
---

# TanStack Query integration

MSW intercepts at the `fetch` layer, **below** TanStack Query. That means Query has no awareness of mocking: cache, retries, `queryFn` errors, `refetchOnWindowFocus`, `refetchOnMount` all behave exactly as they would against a real server. This is a feature — your tests and dev loop exercise the real integration.

## Typical pattern

Component code imports the typed client, not MSW:

```ts
import { createDirtApiClient } from "@/api-client";
import { useQuery } from "@tanstack/react-query";

const api = createDirtApiClient();

export const useSensorsCurrent = () =>
  useQuery({
    queryKey: ["sensors.current"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/sensors/current");
      if (error) throw error;
      return data;
    },
  });
```

MSW handler in `web-ui/src/mocks/handlers.ts`:

```ts
import { http, HttpResponse } from "msw";
import type { components } from "@/api-client/generated/schema";

type SensorsCurrent = components["schemas"]["SensorsCurrent"];

const fixture: SensorsCurrent = {
  // Values chosen to match the mockup screenshot — see
  // docs/plans/refs/dashboard.png and the companion notes.
  temperature_c: 24.5,
  humidity_pct: 58.0,
  // ...
};

export const handlers = [
  http.get("/api/sensors/current", () => HttpResponse.json(fixture)),
];
```

The fixture is typed against the generated contract schema, so any contract drift surfaces as a TypeScript error at `pnpm typecheck` time — you can't ship a mock that disagrees with the frozen OpenAPI.

## Retries

Query retries failed queries by default (3 attempts, exponential backoff). If a mock returns a 5xx, you'll see three requests through MSW before the error surfaces to the component. For tests where you want to assert error UI without waiting for retries, disable them on the test's QueryClient:

```ts
new QueryClient({ defaultOptions: { queries: { retry: false } } });
```

## Mutations

Mutations work the same way — MSW intercepts `fetch`, Query's `useMutation` sees the real `Response`. Nothing special about `http.post` / `http.put` / `http.delete` handlers from Query's perspective.

## Error shapes

Query throws whatever `queryFn` throws. Match your mock error body to what the real endpoint returns so error-state UI is exercised realistically:

```ts
http.get("/api/plants/:code", ({ params }) => {
  if (params.code === "z") {
    return HttpResponse.json(
      { error: "plant_not_found", code: params.code },
      { status: 404 },
    );
  }
  return HttpResponse.json(fixtureFor(params.code));
});
```

If the real endpoint returns a structured body the UI displays (e.g. `error_detail` to render in a toast), the mock should return it too.

## Cache correctness

Because MSW is at the fetch layer, deduplication, `staleTime`, `gcTime`, and `queryKey` cache keys all behave normally. Tests that want to assert "this component triggers exactly one network request" can use `server.events.on("request:match", ...)` — see [testing.md](testing.md).
