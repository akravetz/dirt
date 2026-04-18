---
title: TanStack Router v1 Reference Pack
concept: tanstack-router-v1
mode: framework
version: v1
updated: 2026-04-17
---

# TanStack Router v1 (React)

This pack covers **TanStack Router v1** for React — the current, file-based, type-safe router published at `@tanstack/react-router`. v1 is a breaking rewrite of v0 (the pre-v1 preview): the API surface is different, the bundler plugin generates a `routeTree.gen.ts`, route definitions use `createFileRoute('/path')({...})`, and search params are a first-class typed primitive validated per-route. This pack exists because training data commonly drifts toward React Router (`react-router-dom`) patterns (`<Route path element />`, `useLoaderData` from `react-router`, `useSearchParams`) or half-remembered v0 TanStack APIs (`new Router({...})`, `rootRoute.addChildren([...])` as the default, `useMatch` instead of `Route.useParams`). Prefer what's in this pack over recollection.

## When to consult this pack

Read this INDEX first — and the relevant topic files — before writing or modifying any code that:

- Defines a route file under `src/routes/` (anything using `createFileRoute`, `createRootRoute`, `createRootRouteWithContext`).
- Uses `Outlet`, `Link`, `useNavigate`, `useSearch`, `useParams`, `useLoaderData`, `getRouteApi` from `@tanstack/react-router`.
- Writes or calls a route `loader`, `beforeLoad`, `loaderDeps`, `staleTime`, `shouldReload`, or error boundaries.
- Reads or writes URL search params, adds `validateSearch` (Zod/Valibot/ArkType), or configures `search.middlewares` (`retainSearchParams`, `stripSearchParams`).
- Sets up `createRouter` + `Register` declaration merging in `src/router.tsx`.
- Configures the Vite/Rspack/Webpack plugin or regenerates `routeTree.gen.ts`.

If the task sounds like "add a page", "fetch data for a route", "make a filter/paginated list with URL state", or "guard a route" — read the matching topic below before touching code.

## Topics

- **[Route Definitions & File-Based Routing](route-definitions.md)** — directory & flat file naming, `$param`, `_layout`, `(group)`, `_` suffix (non-nested), `-` prefix (excluded), splat `$.tsx`, `{-$optional}`; how `createFileRoute` pairs with the generated `routeTree.gen.ts`; `createRouter` + `Register` type registration. Read when you're adding/moving a route file or wiring the router for the first time.
- **[Loaders & Data Loading](loaders.md)** — `loader` signature, the full `loaderContext` (`params`, `deps`, `context`, `abortController`, `preload`, `cause`), `loaderDeps` for search-driven data, `staleTime` / `gcTime` / `preloadStaleTime`, `staleReloadMode`, `beforeLoad` + route context, `Route.useLoaderData`, `errorComponent` + `router.invalidate()`, integrating TanStack Query. Read before writing any data-fetching in a route.
- **[Search Params (typed URL state)](search-params.md)** — `validateSearch` with plain functions, Zod v3 (via `zodValidator`) vs. Zod v4 (direct), Valibot, ArkType; `Route.useSearch` vs. `useSearch({ from })` vs. `useSearch({ strict: false })`; `<Link search={prev => ...} />`, `to="."`, `navigate({ search })`; `search.middlewares`, `retainSearchParams`, `stripSearchParams`; loader access via `loaderDeps`. Read when any URL state is involved (filters, pagination, sort, modal open state, tabs).
- **[Migrating from React Router / v0 mental model](migration-from-react-router.md)** — explicit mapping from `react-router-dom` idioms (`<Route element>`, `useLoaderData`, `useSearchParams`, `<Outlet />` from `react-router-dom`) and v0 TanStack (`new Router`, `createRouteConfig`, `rootRoute.addChildren`) to v1 equivalents. Read once when starting a project so you stop pattern-matching to the wrong library.
- **[Common mistakes / anti-patterns](common-mistakes.md)** — the training-data-default patterns you will be tempted to write and the v1-correct replacements, side-by-side. Consult when a review flags something, or proactively before writing any route code for the first time in a session.

## Version-specific warnings

Training data will likely suggest these patterns. They are wrong for TanStack Router v1:

- `import { BrowserRouter, Routes, Route } from 'react-router-dom'` — **wrong library**. v1 is `@tanstack/react-router` and routes are defined per-file via `createFileRoute('/path')({...})`, registered through a generated `routeTree.gen.ts`. See [route-definitions.md](route-definitions.md) and [migration-from-react-router.md](migration-from-react-router.md).
- `const rootRoute = new RootRoute({...})` or `new Router({...})` — **v0 / pre-release syntax**. Use `createRootRoute()` / `createRootRouteWithContext<T>()()` and `createRouter({ routeTree })`. See [route-definitions.md](route-definitions.md).
- `const [searchParams, setSearchParams] = useSearchParams()` — that's `react-router-dom`. In v1 you declare `validateSearch` and read `Route.useSearch()`; you write with `<Link search={prev => ...} />` or `navigate({ search })`. See [search-params.md](search-params.md).
- `loader` reading `search` directly off its context — `search` is intentionally NOT in the loader context. Declare `loaderDeps: ({ search }) => ({ ... })` and read `deps` in the loader. See [loaders.md](loaders.md).
- `loaderDeps: ({ search }) => search` (returning the whole search object) — causes cache-busting on every unrelated param change. Pick only the fields the loader actually uses. See [loaders.md](loaders.md).
- `useLoaderData()` with no argument imported from `react-router` — in v1 it's `Route.useLoaderData()` (scoped to the route file) or `getRouteApi('/path').useLoaderData()`. See [loaders.md](loaders.md).
- Manually wiring a central `<Routes>` / `<Route>` tree in JSX — v1 has no JSX route tree. Routes are files under `src/routes/`, the plugin generates `routeTree.gen.ts`, and you pass that to `createRouter`. See [route-definitions.md](route-definitions.md).
- Forgetting the TypeScript `Register` declaration — without `declare module '@tanstack/react-router' { interface Register { router: typeof router } }` you lose all type safety. See [route-definitions.md](route-definitions.md).
- Using `*` in filenames for catch-all — v1 uses `$.tsx` (the filename is literally a dollar sign). The splat value lands at `params._splat`. See [route-definitions.md](route-definitions.md).
- Assuming Zod schemas are drop-in — Zod v4 can be passed directly to `validateSearch`; Zod v3 needs `zodValidator(schema)` from `@tanstack/zod-adapter` to preserve input vs. output types. See [search-params.md](search-params.md).

## Sources

- https://tanstack.com/router/v1/docs/framework/react/overview
- https://tanstack.com/router/v1/docs/framework/react/routing/routing-concepts
- https://tanstack.com/router/v1/docs/framework/react/routing/file-based-routing
- https://tanstack.com/router/v1/docs/framework/react/routing/file-naming-conventions
- https://tanstack.com/router/v1/docs/framework/react/guide/data-loading
- https://tanstack.com/router/v1/docs/framework/react/guide/search-params
- https://tanstack.com/router/v1/docs/framework/react/guide/path-params
- https://tanstack.com/router/v1/docs/framework/react/guide/creating-a-router
- https://tanstack.com/router/v1/docs/framework/react/api/file-based-routing
- https://tanstack.com/router/v1/docs/framework/react/how-to/migrate-from-react-router

Raw originals for all of the above live in `raw/` in this pack directory. Re-run the `reference-builder` skill on slug `tanstack-router-v1` to refresh.
