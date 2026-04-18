---
title: Common mistakes / anti-patterns
concept: tanstack-router-v1
updated: 2026-04-17
source: https://tanstack.com/router/v1/docs/framework/react/guide/data-loading
---

> This file anchors agents to current TanStack Router v1 practices. Prefer what's written here over training-data recollection. Every entry below is a pattern training data will make you *want* to write — and each one is wrong for v1.

# Common mistakes / anti-patterns

Review this before writing any router code in a new session. The failure mode this file exists to prevent is "plausible-looking code that references the wrong library or a prior-version API".

## 1. Wrong library imports

```tsx
// WRONG
import { BrowserRouter, Routes, Route, Link, useParams } from 'react-router-dom'
import { useLoaderData } from 'react-router'
import { useNavigate } from '@remix-run/react'
```

```tsx
// RIGHT — everything comes from @tanstack/react-router
import {
  Link, Outlet, RouterProvider,
  createFileRoute, createRootRoute, createRootRouteWithContext, createRouter,
  useNavigate, useSearch, useLocation, useRouter, useRouterState,
  getRouteApi, redirect, defer, retainSearchParams, stripSearchParams,
} from '@tanstack/react-router'
```

## 2. Hand-authored `<Routes>` tree

```tsx
// WRONG
<BrowserRouter>
  <Routes>
    <Route path="/" element={<Home />}>
      <Route path="posts/:id" element={<Post />} />
    </Route>
  </Routes>
</BrowserRouter>
```

```tsx
// RIGHT — file-based + generated tree
// src/routes/__root.tsx
export const Route = createRootRoute({ component: () => <Outlet /> })
// src/routes/index.tsx
export const Route = createFileRoute('/')({ component: Home })
// src/routes/posts.$id.tsx
export const Route = createFileRoute('/posts/$id')({ component: Post })
// src/router.tsx
import { routeTree } from './routeTree.gen'
export const router = createRouter({ routeTree })
// src/main.tsx
<RouterProvider router={router} />
```

## 3. v0 / code-based-as-default syntax

```tsx
// WRONG — v0 / pre-release
const rootRoute = new RootRoute({ component: Root })
const postsRoute = new Route({ getParentRoute: () => rootRoute, path: 'posts' })
const router = new Router({ routeTree: rootRoute.addChildren([postsRoute]) })
```

```tsx
// RIGHT — v1, file-based
const router = createRouter({ routeTree })   // routeTree from routeTree.gen.ts
```

(Code-based routing still exists via `createRootRoute().addChildren([...])`, but file-based is the recommended default. Use code-based only when you have a specific reason, and use the `createRootRoute` / `createRoute` factories, not `new Router` / `new RootRoute`.)

## 4. Catch-all as `*.tsx`

```tsx
// WRONG
// src/routes/*.tsx
```

```tsx
// RIGHT
// src/routes/$.tsx — literal dollar sign as filename
// value lands at params._splat (not params['*'])
```

## 5. `useSearchParams` instead of `validateSearch`

```tsx
// WRONG
const [params, setParams] = useSearchParams()
const page = Number(params.get('page') ?? 1)
setParams({ page: String(page + 1) })
```

```tsx
// RIGHT — declare once, consume anywhere
export const Route = createFileRoute('/shop')({
  validateSearch: z.object({ page: z.number().default(1) }),
  component: Shop,
})

function Shop() {
  const { page } = Route.useSearch()
  return (
    <Link from={Route.fullPath} search={(prev) => ({ page: prev.page + 1 })}>
      Next
    </Link>
  )
}
```

## 6. Loader reading `search` off its context

```tsx
// WRONG — loader context has no `search`
export const Route = createFileRoute('/posts')({
  loader: ({ search }) => fetchPosts(search),   // TS error, and wouldn't work at runtime
})
```

```tsx
// RIGHT — deps-as-key
export const Route = createFileRoute('/posts')({
  validateSearch: z.object({ offset: z.number().catch(0) }),
  loaderDeps: ({ search }) => ({ offset: search.offset }),
  loader: ({ deps }) => fetchPosts({ offset: deps.offset }),
})
```

## 7. Returning the whole `search` from `loaderDeps`

```tsx
// WRONG — invalidates on ANY search change
loaderDeps: ({ search }) => search,
loader: ({ deps }) => fetchPosts({ page: deps.page }),
```

```tsx
// RIGHT — only the fields the loader uses
loaderDeps: ({ search }) => ({ page: search.page, limit: search.limit }),
loader: ({ deps }) => fetchPosts(deps),
```

## 8. `useLoaderData` with no argument imported from the wrong library

```tsx
// WRONG
import { useLoaderData } from 'react-router'
const data = useLoaderData()
```

```tsx
// RIGHT — in the route file
const data = Route.useLoaderData()
// RIGHT — elsewhere
const data = getRouteApi('/posts').useLoaderData()
```

## 9. Fetching in `useEffect`

```tsx
// WRONG — waterfall, no caching, lost SWR
function Posts() {
  const [posts, setPosts] = useState([])
  useEffect(() => { fetch('/api/posts').then(r => r.json()).then(setPosts) }, [])
}
```

```tsx
// RIGHT
export const Route = createFileRoute('/posts')({
  loader: () => fetch('/api/posts').then(r => r.json()),
  component: () => {
    const posts = Route.useLoaderData()
    // ...
  },
})
```

## 10. Hand-editing `routeTree.gen.ts`

It's regenerated by the plugin on every file change. Any edits you make will be wiped. Change the files under `src/routes/` instead.

## 11. Forgetting `Register`

If `<Link to="...">` autocompletes as free-form `string`, you skipped this:

```tsx
// src/router.tsx
declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
```

Without it, nothing in `@tanstack/react-router` knows what your route tree looks like — every hook falls back to `unknown` / `string`.

## 12. Building URLs as strings

```tsx
// WRONG
<a href={`/posts/${postId}?tab=${tab}`}>Post</a>
navigate(`/posts/${postId}`)
```

```tsx
// RIGHT
<Link to="/posts/$id" params={{ id: postId }} search={{ tab }}>Post</Link>
navigate({ to: '/posts/$id', params: { id: postId } })
```

## 13. Bare Zod v3 as `validateSearch`

Zod v3 works at runtime but loses the input/output distinction, which breaks `Link` / `navigate` typing (search becomes required even when defaults exist). Use the adapter:

```tsx
// Zod v3: WRONG
validateSearch: z.object({ page: z.number().default(1) })
// Zod v3: RIGHT
import { zodValidator } from '@tanstack/zod-adapter'
validateSearch: zodValidator(z.object({ page: z.number().default(1) }))
// Zod v4, Valibot, ArkType, Effect Schema: RIGHT — direct
validateSearch: z.object({ page: z.number().default(1) }) // Zod v4 is Standard Schema
```

## 14. Mutating URL via `window.history`

```tsx
// WRONG
window.history.replaceState({}, '', `?page=${page}`)
```

```tsx
// RIGHT
navigate({ to: '.', search: (prev) => ({ ...prev, page }), replace: true })
```

Doing it manually skips validation, middlewares, and the router's cache invalidation.

## Quick audit checklist

Before you commit router code, grep for:

- `react-router`, `react-router-dom`, `@remix-run/react` — should not appear.
- `useSearchParams` — should not appear.
- `new Router(`, `new RootRoute(` — should not appear.
- `BrowserRouter`, `<Routes>`, `<Route path=` — should not appear.
- `useEffect(() => fetch(` inside a route component — probably should be a `loader`.
- `routeTree.gen.ts` in a diff — only acceptable when regenerated by the plugin; never hand-edits.
