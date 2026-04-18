---
title: Migrating from React Router / v0 mental model
concept: tanstack-router-v1
updated: 2026-04-17
source: https://tanstack.com/router/v1/docs/framework/react/how-to/migrate-from-react-router
---

> This file anchors agents to current TanStack Router v1 practices. Prefer what's written here over training-data recollection — it's easy to keep writing `react-router-dom` idioms on autopilot.

# Migrating from React Router / v0 TanStack mental model

This is a cross-reference, not a step-by-step migration script. Consult it at the **start** of any session that involves routing so pattern matching doesn't pull you to the wrong library.

## Package imports

| Don't import from                                    | Import from (v1)                       |
| ---------------------------------------------------- | -------------------------------------- |
| `react-router-dom`                                   | `@tanstack/react-router`               |
| `react-router`                                       | `@tanstack/react-router`               |
| `@remix-run/react`                                   | `@tanstack/react-router`               |
| `@tanstack/router` (v0 name)                         | `@tanstack/react-router`               |

If the task is really using Remix or React Router, this whole pack is irrelevant. But if the app is TanStack Router, any of the above imports is a hallucination — replace it.

## Routes

| React Router                                         | TanStack Router v1                     |
| ---------------------------------------------------- | -------------------------------------- |
| `<BrowserRouter><Routes><Route path element/></Routes></BrowserRouter>` | `<RouterProvider router={router} />` where `router = createRouter({ routeTree })` and routes are files under `src/routes/`. |
| `createBrowserRouter([{ path, element, children }])` | File under `src/routes/*.tsx` with `export const Route = createFileRoute('/path')({ component })`. The generated `routeTree.gen.ts` is the tree. |
| `<Route index element={...} />`                      | `src/routes/posts.index.tsx` with `createFileRoute('/posts/')`. |
| `<Route path="posts/:id" />`                         | `src/routes/posts.$id.tsx` with `createFileRoute('/posts/$id')`. |
| `<Route path="*" />` (catch-all)                     | `src/routes/$.tsx` (literal `$`), value at `params._splat`. |
| Layout route with `<Outlet />`                       | Path-bearing: `routes/app.tsx` + `routes/app.*.tsx`. Pathless: prefix with `_` (e.g. `_authed.tsx`). Both render `<Outlet />` from `@tanstack/react-router`. |
| Route groups via conventions                         | Folder named `(name)` — purely organizational. |

## Hooks

| React Router                                   | TanStack Router v1                                                      |
| ---------------------------------------------- | ------------------------------------------------------------------------ |
| `useParams<T>()`                               | `Route.useParams()` (inside the route file) or `getRouteApi('/path').useParams()` / `useParams({ from })`. |
| `useSearchParams()` → `[params, setParams]`    | Declare `validateSearch`. Read with `Route.useSearch()`. Write with `<Link search>` or `navigate({ search })`. |
| `useLoaderData()`                              | `Route.useLoaderData()` or `getRouteApi(...).useLoaderData()`.           |
| `useLocation()`                                | `useLocation()` from `@tanstack/react-router` (different return shape).  |
| `useNavigate()` → `(to, { state })`            | `useNavigate()` from `@tanstack/react-router` → `({ to, params, search, replace })`. Type-safe. |
| `useMatches()`                                 | `useRouterState({ select: s => s.matches })` or `useMatches()`.          |
| `useNavigation()` (for pending state)          | Per-route `pendingComponent`, plus `useRouterState` for `isLoading` / `isTransitioning`. |

## Data loading

| React Router                                     | TanStack Router v1                                                   |
| ------------------------------------------------ | --------------------------------------------------------------------- |
| Route object `loader: ({ params, request }) => ...` | Route option `loader: ({ params, deps, context, abortController }) => ...`. Note: **no `request`**, no `search` — see [loaders.md](loaders.md). |
| `loader` reading URL search via `new URL(request.url).searchParams` | Declare `validateSearch` + `loaderDeps: ({ search }) => ...`; read `deps` in loader. |
| `defer({ slowThing })` returning `Deferred`     | `defer(promise)` from `@tanstack/react-router` for streaming slow data. |
| `ErrorBoundary` component on route              | `errorComponent: ({ error, reset }) => ...` option.                  |
| `shouldRevalidate`                               | `shouldReload` + `staleTime` + `loaderDeps`.                         |
| `redirect('/x')` from loader                    | `throw redirect({ to: '/x' })` — same idea, but `to` is type-checked. |

## Links

| React Router                                     | TanStack Router v1                                                   |
| ------------------------------------------------ | --------------------------------------------------------------------- |
| `<Link to="/posts/123">`                         | `<Link to="/posts/$id" params={{ id: '123' }}>` — params are explicit and typed. |
| `<Link to={{ pathname, search }}>`               | `<Link to="/x" search={{ page: 1 }}>` or `<Link to="." search={prev => ...}>`. |
| `<NavLink>`                                      | `<Link>` + `activeProps` / `activeOptions` options.                  |
| `end` prop for exact match                       | `activeOptions={{ exact: true }}`.                                    |

## v0 TanStack Router -> v1 (pre-release to stable)

| v0 (don't use)                                      | v1 (use)                                                  |
| --------------------------------------------------- | --------------------------------------------------------- |
| `new Router({ routeTree })`                         | `createRouter({ routeTree })`.                           |
| `new RootRoute({...})` / `createRouteConfig`        | `createRootRoute()` or `createRootRouteWithContext<T>()()`. |
| Hand-composed `rootRoute.addChildren([...])` as the default pattern | File-based routing + generated `routeTree.gen.ts`. (Code-based still exists; file-based is recommended.) |
| `Route.useMatch().loaderData`                       | `Route.useLoaderData()`.                                  |
| `Route.useMatch().params`                           | `Route.useParams()`.                                      |
| `preSearchFilters` (if you ever saw this)           | `search.middlewares` + `retainSearchParams` / `stripSearchParams`. |

## Typing

- v1 requires one piece of setup most people forget: the `Register` interface declaration merge. Without it, `Link`'s `to`, `params`, `search` collapse to `string` / `any`. See [route-definitions.md](route-definitions.md#createrouter--register-do-not-skip).

## Sanity check after migration

- Grep for `react-router`, `react-router-dom`, `@remix-run/react` in the codebase. Remove any residual imports.
- Grep for `useSearchParams`, `useMatches` imports — confirm they come from `@tanstack/react-router`, not the wrong library.
- Grep for `BrowserRouter`, `<Routes>`, `<Route path` — these should not exist in a TanStack Router v1 app.
- Grep for `new Router(`, `new RootRoute(`, `rootRoute.addChildren` — these indicate v0 / code-based patterns that may need rewriting.
- Confirm `declare module '@tanstack/react-router' { interface Register { router: typeof router } }` exists exactly once (next to `createRouter`).
