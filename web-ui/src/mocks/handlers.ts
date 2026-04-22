// MSW v2 request handlers.
//
// Each FE feature appends its own `http.{get,post,...}` handler to this
// array. See docs/references/msw-v2/handlers.md for the v2 resolver
// signature — `http.get("/api/x", ({ request, params, cookies }) =>
// HttpResponse.json(...))`, NOT the v1 `rest.get(..., (req, res, ctx) =>
// res(ctx.json(...)))` shape.
//
// This array is shared between browser-mode (dev via Service Worker)
// and node-mode (Vitest via setupServer). Keep handlers relative /
// same-origin where possible; prod serves the real endpoints on the
// same origin and MSW is tree-shaken out of the prod bundle.
import type { RequestHandler } from "msw";

export const handlers: RequestHandler[] = [];
