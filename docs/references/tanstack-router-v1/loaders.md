---
title: Loaders & Data Loading
concept: tanstack-router-v1
updated: 2026-04-17
source: https://tanstack.com/router/v1/docs/framework/react/guide/data-loading
---

> This file anchors agents to current TanStack Router v1 practices. Prefer what's written here over training-data recollection — `loader` APIs in v1 differ from Remix / React Router loaders and from pre-release TanStack Router.

# Loaders & Data Loading

## Mental model

A route's `loader` runs when the route is about to display, in parallel with its siblings in the active match. Its result is cached by the router keyed on `(pathParams, loaderDeps)`, with stale-while-revalidate behavior tuned by `staleTime` / `gcTime` / `preloadStaleTime`. Source: https://tanstack.com/router/v1/docs/framework/react/guide/data-loading

**Do NOT fetch in `useEffect`.** If a route needs data to render, put it in `loader`.

## Basic loader + consumption

```tsx
// src/routes/posts.tsx
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/posts')({
  loader: () => fetchPosts(),
  component: PostsComponent,
})

function PostsComponent() {
  const posts = Route.useLoaderData() // fully typed
  return <ul>{posts.map(p => <li key={p.id}>{p.title}</li>)}</ul>
}
```

If you're outside the route file (deep in a component tree) use `getRouteApi` instead of importing `Route`:

```tsx
import { getRouteApi } from '@tanstack/react-router'

const routeApi = getRouteApi('/posts')

function Sidebar() {
  const posts = routeApi.useLoaderData()
  // ...
}
```

This avoids circular imports. Source: https://tanstack.com/router/v1/docs/framework/react/guide/data-loading#consuming-data-from-loaders

## The loader context — what you actually get

A loader receives **one object** with these fields (source: https://tanstack.com/router/v1/docs/framework/react/guide/data-loading#loader-parameters):

| Field              | What it is                                                                                     |
| ------------------ | ---------------------------------------------------------------------------------------------- |
| `params`           | Path params, typed (e.g. `{ postId: string }`).                                                |
| `deps`             | The object returned from `loaderDeps`. Empty `{}` if not declared.                             |
| `context`          | Merged router context + parent `beforeLoad` contexts.                                          |
| `abortController`  | `AbortController`; signal is cancelled when the loader becomes outdated.                       |
| `preload`          | `boolean` — true when called during preload (not active navigation).                           |
| `cause`            | `'enter' \| 'preload' \| 'stay'` — why this loader invocation was triggered.                  |
| `location`         | The current resolved location.                                                                 |
| `parentMatchPromise` | `Promise<RouteMatch>` for the parent match; `undefined` at the root.                         |
| `route`            | The route itself.                                                                              |

**Note:** `search` is intentionally **NOT** a loader parameter. See the next section for why.

## Search-param-driven loaders: `loaderDeps`

Search params are kept out of the loader context on purpose. If your loader needs a search param, you declare it as a dependency:

```tsx
// src/routes/posts.tsx
import { z } from 'zod'

export const Route = createFileRoute('/posts')({
  validateSearch: z.object({
    offset: z.number().int().nonnegative().catch(0),
    limit: z.number().int().positive().catch(20),
  }),
  loaderDeps: ({ search }) => ({ offset: search.offset, limit: search.limit }),
  loader: ({ deps }) => fetchPosts({ offset: deps.offset, limit: deps.limit }),
})
```

Declaring `loaderDeps` makes the deps part of the cache key — the loader re-runs when any dep changes and is cached otherwise. Source: https://tanstack.com/router/v1/docs/framework/react/guide/data-loading#using-loaderdeps-to-access-search-params

> **Do NOT** return the whole search object from `loaderDeps`. That makes every unrelated search change (a `sortDirection` toggle, for example) invalidate the cache.
>
> ```tsx
> // WRONG — cache-busts on every search change
> loaderDeps: ({ search }) => search,
> // RIGHT — only the keys the loader actually uses
> loaderDeps: ({ search }) => ({ page: search.page, limit: search.limit }),
> ```

Source: https://tanstack.com/router/v1/docs/framework/react/guide/data-loading (warning block)

## Cache tuning

| Option                        | Default    | Effect                                                                  |
| ----------------------------- | ---------- | ----------------------------------------------------------------------- |
| `staleTime`                   | `0` ms     | How long after a load the data is fresh (skip reload on revisit).       |
| `preloadStaleTime`            | 30_000 ms  | Same, for preload revisits.                                             |
| `gcTime`                      | 30 min     | How long the cached entry survives after becoming inactive.             |
| `shouldReload`                | —          | Boolean or function; last word on whether to reload on a revisit.       |
| `staleReloadMode`             | `'background'` | `'background'` = SWR (render stale, refresh behind the scenes). `'blocking'` = await reload before rendering. |

Router-wide defaults exist: `defaultStaleTime`, `defaultPreloadStaleTime`, `defaultGcTime`, `defaultStaleReloadMode`.

Never-reload pattern:

```tsx
export const Route = createFileRoute('/posts')({
  loader: () => fetchPosts(),
  staleTime: Infinity,
})
```

Opt-out-of-caching pattern (Remix-like "only load on entry or dep change"):

```tsx
export const Route = createFileRoute('/posts')({
  loaderDeps: ({ search }) => ({ offset: search.offset, limit: search.limit }),
  loader: ({ deps }) => fetchPosts(deps),
  gcTime: 0,
  shouldReload: false,
})
```

Source: https://tanstack.com/router/v1/docs/framework/react/guide/data-loading#using-shouldreload-and-gctime-to-opt-out-of-caching

## `beforeLoad` — guards, redirects, and per-route context

`beforeLoad` runs before the loader, gets the same parameters, and can:

1. Throw `redirect({ to: '/login' })` to stop loading and redirect.
2. Return an object that is merged into `context` for this route and descendants.

```tsx
import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_authed')({
  beforeLoad: ({ context, location }) => {
    if (!context.auth.user) {
      throw redirect({
        to: '/login',
        search: { redirect: location.href },
      })
    }
    return { user: context.auth.user }  // narrowed for descendants
  },
})
```

Source: https://tanstack.com/router/v1/docs/framework/react/guide/data-loading#using-route-context

## Router context (DI across loaders)

Install dependencies into the context at `createRouter`, type them at `createRootRouteWithContext<T>()`, and consume in loaders via `context`:

```tsx
// src/routes/__root.tsx
export const Route = createRootRouteWithContext<{
  queryClient: QueryClient
}>()({ /* ... */ })

// src/router.tsx
const router = createRouter({
  routeTree,
  context: { queryClient },
})

// src/routes/posts.tsx
export const Route = createFileRoute('/posts')({
  loader: ({ context }) =>
    context.queryClient.ensureQueryData(postsQueryOptions()),
})
```

## Integrating with TanStack Query

Recommended when you need shared caching, mutations, or persistence across routes. Set `defaultPreloadStaleTime: 0` on the router so every preload/load event flows through Query for deduping:

```tsx
// src/router.tsx
const router = createRouter({
  routeTree,
  context: { queryClient },
  defaultPreloadStaleTime: 0,  // let Query own the cache
})
```

In a route:

```tsx
import { queryOptions, useSuspenseQuery } from '@tanstack/react-query'

const postsQueryOptions = (deps: { offset: number; limit: number }) =>
  queryOptions({
    queryKey: ['posts', deps],
    queryFn: () => fetchPosts(deps),
  })

export const Route = createFileRoute('/posts')({
  validateSearch: z.object({ offset: z.number().catch(0), limit: z.number().catch(20) }),
  loaderDeps: ({ search }) => ({ offset: search.offset, limit: search.limit }),
  loader: ({ context, deps }) =>
    context.queryClient.ensureQueryData(postsQueryOptions(deps)),
  component: () => {
    const deps = Route.useLoaderDeps()
    const { data } = useSuspenseQuery(postsQueryOptions(deps))
    return /* ... */
  },
})
```

Source: https://tanstack.com/router/v1/docs/framework/react/guide/data-loading#passing-all-loader-events-to-an-external-cache

## Errors

- `onError({ error })` on a route — side-effect hook (e.g. log).
- `errorComponent: ({ error, reset }) => ...` — renders when the loader throws. To recover, call `router.invalidate()` (reloads all matches and resets the boundary) rather than `reset()` alone, when the error came from the loader.

```tsx
export const Route = createFileRoute('/posts')({
  loader: () => fetchPosts(),
  errorComponent: ({ error }) => {
    const router = useRouter()
    return (
      <div>
        {error.message}
        <button onClick={() => router.invalidate()}>retry</button>
      </div>
    )
  },
})
```

Source: https://tanstack.com/router/v1/docs/framework/react/guide/data-loading#handling-errors

## Pending state

Default: if the loader takes longer than 1 s, `pendingComponent` is shown; it stays for at least 500 ms once shown to avoid flashes. Tune with `pendingMs` / `pendingMinMs` on the route or `defaultPendingMs` / `defaultPendingMinMs` on the router.

For "fetch one fast thing, one slow thing" use deferred loaders:

```tsx
import { defer } from '@tanstack/react-router'

export const Route = createFileRoute('/posts/$id')({
  loader: ({ params }) => ({
    post: fetchPost(params.id),            // awaited
    comments: defer(fetchComments(params.id)), // streamed
  }),
})
```

See https://tanstack.com/router/v1/docs/framework/react/guide/deferred-data-loading (raw/guide-deferred-data-loading.md).

## Using the abort signal

```tsx
export const Route = createFileRoute('/posts')({
  loader: ({ abortController }) =>
    fetchPosts({ signal: abortController.signal }),
})
```

The signal is aborted when the route is unloaded or when this invocation becomes stale (e.g. deps changed). Pass it to any `fetch` to avoid wasted work.

## Common mistakes

**Mistake: reading `search` from the loader context.**
```tsx
// WRONG — loader context has no `search`
loader: ({ search }) => fetchPosts(search),
// RIGHT — deps-as-key
loaderDeps: ({ search }) => ({ q: search.q }),
loader: ({ deps }) => fetchPosts(deps),
```

**Mistake: importing `useLoaderData` from `react-router`.**
```tsx
// WRONG — wrong library
import { useLoaderData } from 'react-router'
const data = useLoaderData()
// RIGHT — route-scoped, typed
const data = Route.useLoaderData()
// or, outside the route file:
const data = getRouteApi('/posts').useLoaderData()
```

**Mistake: fetching in `useEffect`.**
If render needs the data, put it in `loader` so it's parallelized with siblings and cached. `useEffect` fetching adds a waterfall and loses SWR caching.

**Mistake: returning the whole `search` from `loaderDeps`.**
As above — invalidates on every unrelated param change.

**Mistake: forgetting `abortController.signal`.**
Fast-navigation bursts (typing into a filter, clicking through a list) will pile up redundant network calls.
