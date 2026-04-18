---
title: Route Definitions & File-Based Routing
concept: tanstack-router-v1
updated: 2026-04-17
source: https://tanstack.com/router/v1/docs/framework/react/routing/routing-concepts
---

> This file anchors agents to current TanStack Router v1 practices. Prefer what's written here over training-data recollection — training data commonly confuses v1 with `react-router-dom` or pre-release v0 TanStack APIs.

# Route Definitions & File-Based Routing

## The shape

TanStack Router v1 is **file-based first**. You do NOT build a central `<Routes><Route /></Routes>` tree in JSX. Instead:

1. Each route is a file under `src/routes/`.
2. The bundler plugin (Vite/Rspack/Webpack/Esbuild) generates `src/routeTree.gen.ts` at dev/build time.
3. `createRouter({ routeTree })` in `src/router.tsx` wires it up.
4. You register the router's type via TypeScript declaration merging so the whole app gets type safety.

Source: https://tanstack.com/router/v1/docs/framework/react/routing/file-based-routing

## Minimal project skeleton

```
src/
├── main.tsx                # <RouterProvider router={router} />
├── router.tsx              # createRouter + Register declaration merge
├── routeTree.gen.ts        # GENERATED — do not hand-edit
└── routes/
    ├── __root.tsx          # root route (must be named __root)
    ├── index.tsx           # /
    ├── about.tsx           # /about
    ├── posts.tsx           # /posts (layout for posts.*)
    ├── posts.index.tsx     # /posts exactly
    └── posts.$postId.tsx   # /posts/:postId
```

## `createFileRoute` — the per-file API

Every non-root route file exports a `Route` built with `createFileRoute`:

```tsx
// src/routes/posts.$postId.tsx
import { createFileRoute } from '@tanstack/react-router'

export const Route = createFileRoute('/posts/$postId')({
  loader: ({ params }) => fetchPost(params.postId),
  component: PostComponent,
})

function PostComponent() {
  const { postId } = Route.useParams()
  return <div>Post {postId}</div>
}
```

The string argument to `createFileRoute('/posts/$postId')` is **written and maintained by the plugin** — don't guess it. The plugin syncs it with the filename. When you move/rename a file, the plugin rewrites the string. Source: https://tanstack.com/router/v1/docs/framework/react/routing/routing-concepts

## The root route

Root route goes in `src/routes/__root.tsx` (two leading underscores). Use `createRootRoute()` for no context, or `createRootRouteWithContext<T>()()` for typed context (note the **double call** — it's a factory).

```tsx
// src/routes/__root.tsx
import { Outlet, createRootRouteWithContext } from '@tanstack/react-router'
import type { QueryClient } from '@tanstack/react-query'

export interface MyRouterContext {
  queryClient: QueryClient
}

export const Route = createRootRouteWithContext<MyRouterContext>()({
  component: () => (
    <>
      <nav>{/* ... */}</nav>
      <Outlet />
    </>
  ),
  notFoundComponent: () => <div>404 Not Found</div>,
})
```

Source: https://tanstack.com/router/v1/docs/framework/react/routing/routing-concepts#the-root-route

## File naming rules (complete)

Source: https://tanstack.com/router/v1/docs/framework/react/routing/file-naming-conventions

| Token                       | Meaning                                                                  |
| --------------------------- | ------------------------------------------------------------------------ |
| `__root.tsx`                | Root route. Required. Must live at the routes-dir root.                  |
| `index.tsx` or `.index.tsx` | Matches the parent route exactly. `posts.index.tsx` = `/posts` exactly.  |
| `$name`                     | Dynamic path param. `posts.$postId.tsx` -> `/posts/:postId`.             |
| `$.tsx`                     | Splat / catch-all. Captured under `params._splat`. NOT `*.tsx`.          |
| `{-$name}`                  | **Optional** path param. `posts.{-$category}.tsx` matches `/posts` or `/posts/tech`. |
| `_prefix` (leading `_`)     | **Pathless layout route**. Wraps children without adding a URL segment.  |
| `suffix_` (trailing `_`)    | **Non-nested route**. Un-nests from parent. `posts_.$postId.edit.tsx` renders standalone. |
| `-prefix` (leading `-`)     | **Excluded** from the route tree. For colocated components/utilities.    |
| `(folder)`                  | **Route group**. Folder name is purely organizational — no URL effect.   |
| `.` separator               | Flat-route nesting. `settings.profile.tsx` = `/settings/profile`.        |
| `[x]` escaping              | Escape a literal special char. `script[.]js.tsx` -> `/script.js`.        |
| `route.tsx` in a folder     | The folder's own route config file (e.g. `account/route.tsx` -> `/account`). |

### Dynamic params

```tsx
// src/routes/posts.$postId.tsx
export const Route = createFileRoute('/posts/$postId')({
  loader: ({ params }) => fetchPost(params.postId),
  component: () => {
    const { postId } = Route.useParams()
    return <div>{postId}</div>
  },
})
```

Multiple segments compose: `/posts/$postId/$revisionId` gives `params: { postId, revisionId }`.

### Splat (catch-all)

File: `src/routes/files/$.tsx` -> matches `/files/anything/here/...`, with `params._splat === 'anything/here/...'`. (v1 still accepts the `*` key for backwards compat; it will be removed in v2. Use `_splat`.) Source: https://tanstack.com/router/v1/docs/framework/react/routing/routing-concepts#splat--catch-all-routes

### Optional params (v1)

```tsx
// src/routes/posts.{-$category}.tsx  — matches /posts AND /posts/tech
export const Route = createFileRoute('/posts/{-$category}')({
  component: () => {
    const { category } = Route.useParams() // string | undefined
    return <div>{category ?? 'All'}</div>
  },
})
```

### Layout routes (path-bearing)

Two equivalent shapes:

```
routes/app.tsx              // or routes/app/route.tsx
routes/app.dashboard.tsx    // or routes/app/dashboard.tsx
routes/app.settings.tsx     // or routes/app/settings.tsx
```

`/app/dashboard` renders `<AppLayout><Dashboard/></AppLayout>`. `app.tsx` must render `<Outlet />` from `@tanstack/react-router`.

### Pathless layout routes (`_` prefix)

Wrap children in shared UI/logic without adding a URL segment. The name after `_` is only used as a route ID.

```
routes/_authed.tsx
routes/_authed.dashboard.tsx     // matches /dashboard — wrapped by _authed
routes/_authed.settings.tsx      // matches /settings — same
```

```tsx
// src/routes/_authed.tsx
import { Outlet, createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/_authed')({
  beforeLoad: ({ context }) => {
    if (!context.auth.user) throw redirect({ to: '/login' })
  },
  component: () => <Outlet />,
})
```

Constraint: pathless layout routes cannot themselves contain `$param` in their own name, because they don't consume a URL segment. Source: https://tanstack.com/router/v1/docs/framework/react/routing/routing-concepts#pathless-layout-routes

### Route groups `(folder)`

Use for organization only. `routes/(auth)/login.tsx` -> `/login`, not `/auth/login`. Purely cosmetic; does not affect the component tree.

## `createRouter` + `Register` (do NOT skip)

```tsx
// src/router.tsx
import { createRouter } from '@tanstack/react-router'
import { routeTree } from './routeTree.gen'

export const router = createRouter({
  routeTree,
  defaultPreload: 'intent',          // prefetch on hover/focus
  defaultPreloadStaleTime: 0,        // if you're using TanStack Query as cache
  // context: { queryClient }        // if root uses createRootRouteWithContext
})

declare module '@tanstack/react-router' {
  interface Register {
    router: typeof router
  }
}
```

Without the `declare module` block, `Link`, `useNavigate`, `useParams`, `useSearch`, etc. lose type safety everywhere. The official docs call this out as "DO NOT SKIP THIS SECTION". Source: https://tanstack.com/router/v1/docs/framework/react/guide/creating-a-router#router-type-safety

## Mounting

```tsx
// src/main.tsx
import { RouterProvider } from '@tanstack/react-router'
import { router } from './router'

createRoot(document.getElementById('root')!).render(
  <RouterProvider router={router} />,
)
```

## Links & navigation (type-safe)

```tsx
import { Link, useNavigate } from '@tanstack/react-router'

<Link to="/posts/$postId" params={{ postId: '123' }} search={{ tab: 'comments' }}>
  Post
</Link>

const navigate = useNavigate()
navigate({ to: '/posts/$postId', params: { postId: '123' } })
```

`to` is autocompleted from the union of registered routes. `params` and `search` are required if the target route declares them. Never build URLs as strings (`` `/posts/${id}` ``) — you lose typing and search-param inheritance.

## Common mistakes

**Mistake: mounting a JSX `<Routes>` tree.**

```tsx
// WRONG — react-router-dom pattern; does not exist in TanStack Router v1
<BrowserRouter>
  <Routes>
    <Route path="/posts/:id" element={<Post />} />
  </Routes>
</BrowserRouter>
```

```tsx
// RIGHT — v1: file + generated tree
// src/routes/posts.$id.tsx
export const Route = createFileRoute('/posts/$id')({ component: Post })
// src/router.tsx
const router = createRouter({ routeTree })
// src/main.tsx
<RouterProvider router={router} />
```

**Mistake: `new Router({...})` / `rootRoute.addChildren([...])` as the default.**
That's v0 or code-based routing. File-based is the recommended v1 path. Use `createRouter({ routeTree })` where `routeTree` is imported from the generated `./routeTree.gen`.

**Mistake: `*.tsx` for catch-all.**
Splat routes are `$.tsx`. Access via `params._splat`, not `params['*']` (legacy shim will be removed in v2).

**Mistake: forgetting `Register`.**
If `Link`'s `to` prop shows `string` instead of a union of your route paths, you forgot the `declare module` block.

**Mistake: hand-editing `routeTree.gen.ts`.**
It's regenerated by the plugin on every change. Edit the file under `src/routes/`, save, and the plugin updates the tree.

**Mistake: writing the route path as a string that mismatches the filename.**
The plugin owns the `createFileRoute('/...')` string argument. If you move `posts.$postId.tsx` into a folder, the plugin will rewrite the argument — don't try to keep it manually in sync.
