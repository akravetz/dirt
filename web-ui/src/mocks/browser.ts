// MSW v2 browser worker (dev only).
//
// Started from src/main.tsx under an `import.meta.env.DEV` guard with a
// DYNAMIC import so the prod build tree-shakes this module + all of msw
// out of the bundle. Do NOT statically import this file from main.tsx.
//
// The Service Worker script itself lives at web-ui/public/mockServiceWorker.js
// (generated via `pnpm exec msw init web-ui/public --save`). That file is
// committed to the repo and regenerated only on MSW major upgrades.
import { setupWorker } from "msw/browser";
import { handlers } from "./handlers";

export const worker = setupWorker(...handlers);
