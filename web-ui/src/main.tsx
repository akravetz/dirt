import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createRouter, RouterProvider } from "@tanstack/react-router";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { routeTree } from "./routeTree.gen";
import "./styles.css";

const queryClient = new QueryClient();
const router = createRouter({
  routeTree,
  context: { queryClient },
  defaultPreload: "intent",
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

// MSW v2 dev-only boot.
//
// The `import.meta.env.DEV` guard + dynamic import is what lets the prod
// build tree-shake msw + src/mocks/** out of the bundle entirely:
// - In dev, `DEV === true`; the branch is live; `import("./mocks/browser")`
//   pulls msw in and `worker.start(...)` registers the Service Worker at
//   /mockServiceWorker.js before React mounts.
// - In prod, Vite inlines `DEV === false`; the early `return` makes the
//   dynamic import unreachable; Rollup drops both the import and every
//   downstream msw chunk. Verify with `grep -rli msw dist/**/*.js`.
//
// `onUnhandledRequest: "bypass"` is correct for dev — real BE endpoints
// pass through to :8001 (or Vite's proxy); only mocked paths are
// intercepted. Tests use "error" (see src/test-setup.ts).
async function enableMocking(): Promise<void> {
  if (!import.meta.env.DEV) return;
  const { worker } = await import("./mocks/browser");
  await worker.start({ onUnhandledRequest: "bypass" });
}

const rootEl = document.getElementById("root");
if (!rootEl) throw new Error("#root not found");

// Render after mocking boot resolves. `.catch` logs and falls through:
// a dev-only MSW registration failure must not block the app from
// mounting — we still want to see whatever the real BE returns.
enableMocking()
  .catch((err: unknown) => {
    console.error("mock worker start failed; continuing without mocks", err);
  })
  .then(() => {
    createRoot(rootEl).render(
      <StrictMode>
        <QueryClientProvider client={queryClient}>
          <RouterProvider router={router} />
        </QueryClientProvider>
      </StrictMode>,
    );
  });
