---
title: Search Params (typed URL state)
concept: tanstack-router-v1
updated: 2026-04-17
source: https://tanstack.com/router/v1/docs/framework/react/guide/search-params
---

> This file anchors agents to current TanStack Router v1 practices. Prefer what's written here over training-data recollection — search params in v1 are a first-class typed primitive; they are NOT `useSearchParams()` from `react-router-dom` and they are NOT raw `URLSearchParams`.

# Search Params in TanStack Router v1

## Mental model

Search params in v1 are **typed application state in the URL**, serialized as JSON-aware key=value pairs (arrays/objects automatically encoded). Each route declares `validateSearch`; the resulting type flows into loaders (via `loaderDeps`), into components (`useSearch`), into `<Link />`/`navigate` call sites as a required/optional `search` field, and **into child routes** (child routes inherit the parent's search types). Source: https://tanstack.com/router/v1/docs/framework/react/guide/search-params

You do NOT use `useSearchParams` and you do NOT manipulate `URLSearchParams` directly.

## Declaring + validating search

### Plain function (no dependency)

```tsx
// src/routes/shop/products.tsx
type ProductSearch = {
  page: number
  filter: string
  sort: 'newest' | 'oldest' | 'price'
}

export const Route = createFileRoute('/shop/products')({
  validateSearch: (search: Record<string, unknown>): ProductSearch => ({
    page: Number(search.page ?? 1),
    filter: (search.filter as string) ?? '',
    sort: (search.sort as ProductSearch['sort']) ?? 'newest',
  }),
})
```

The input is already JSON-parsed (so `page` as `3` arrives as a number, `includeCategories` as `['a','b']` arrives as an array). Your job is validate + fall back, then return the typed shape. Source: https://tanstack.com/router/v1/docs/framework/react/guide/search-params#validating-and-typing-search-params

### Zod v4 (direct — no adapter needed)

```tsx
import { z } from 'zod'

const productSearchSchema = z.object({
  page: z.number().default(1),
  filter: z.string().default(''),
  sort: z.enum(['newest', 'oldest', 'price']).default('newest'),
})

export const Route = createFileRoute('/shop/products/')({
  validateSearch: productSearchSchema, // Zod v4 implements Standard Schema
})
```

### Zod v3 (needs the adapter)

```tsx
import { z } from 'zod'
import { zodValidator, fallback } from '@tanstack/zod-adapter'

const productSearchSchema = z.object({
  page: fallback(z.number(), 1).default(1),
  filter: fallback(z.string(), '').default(''),
  sort: fallback(z.enum(['newest','oldest','price']), 'newest').default('newest'),
})

export const Route = createFileRoute('/shop/products/')({
  validateSearch: zodValidator(productSearchSchema),
})
```

Reason: the adapter is what preserves the distinction between the schema's **input** type (what you pass to `<Link search={...}>`) and its **output** type (what `useSearch` returns). Raw Zod v3 `.catch()` collapses the typing. Source: https://tanstack.com/router/v1/docs/framework/react/guide/search-params#zod

### Valibot / ArkType / Effect Schema

All implement Standard Schema — pass them directly, no adapter:

```tsx
import * as v from 'valibot'
const schema = v.object({
  page: v.optional(v.fallback(v.number(), 1), 1),
  filter: v.optional(v.fallback(v.string(), ''), ''),
  sort: v.optional(v.fallback(v.picklist(['newest','oldest','price']), 'newest'), 'newest'),
})
export const Route = createFileRoute('/shop/products/')({ validateSearch: schema })
```

```tsx
import { type } from 'arktype'
const schema = type({
  page: 'number = 1',
  filter: 'string = ""',
  sort: '"newest" | "oldest" | "price" = "newest"',
})
export const Route = createFileRoute('/shop/products/')({ validateSearch: schema })
```

Source: https://tanstack.com/router/v1/docs/framework/react/guide/search-params#valibot and #arktype

## Reading search params

### Inside the route's component

```tsx
export const Route = createFileRoute('/shop/products')({
  validateSearch: productSearchSchema,
  component: ProductList,
})

function ProductList() {
  const { page, filter, sort } = Route.useSearch() // fully typed
  // ...
}
```

### Elsewhere (no direct access to `Route`)

```tsx
import { getRouteApi, useSearch } from '@tanstack/react-router'

const routeApi = getRouteApi('/shop/products')

function Sidebar() {
  const { page } = routeApi.useSearch()
  // or:
  const search = useSearch({ from: '/shop/products' })
}
```

### Unknown route / loose typing

```tsx
const search = useSearch({ strict: false })
// All known keys become `T | undefined`.
```

### Child route inheritance

Search types merge down the tree. A child of `/shop/products` sees its parent's `ProductSearch` in `beforeLoad({ search })`. Source: https://tanstack.com/router/v1/docs/framework/react/guide/search-params#search-params-are-inherited-from-parent-routes

## Writing search params

### `<Link search />`

```tsx
<Link from={Route.fullPath} search={(prev) => ({ page: prev.page + 1 })}>
  Next page
</Link>
```

- The `search` function receives the current typed search and returns either a partial (merged) or full replacement depending on your router config — default behavior is full replace per typed shape; use the spread form below for explicit merge.

Generic, pathless update (stays on current route):

```tsx
<Link to="." search={(prev) => ({ ...prev, page: prev.page + 1 })}>
  Next page
</Link>
```

Source: https://tanstack.com/router/v1/docs/framework/react/guide/search-params#link-search

### `useNavigate` / `navigate({ search })`

```tsx
const navigate = useNavigate({ from: Route.fullPath })
navigate({ search: (prev) => ({ ...prev, page: prev.page + 1 }) })
```

`router.navigate({ search })` and `<Navigate search />` behave identically.

## Using search params in loaders

Search is intentionally **not** on the loader context. Use `loaderDeps` to declare which fields your loader depends on — this makes them part of the cache key:

```tsx
export const Route = createFileRoute('/posts')({
  validateSearch: z.object({ offset: z.number().catch(0) }),
  loaderDeps: ({ search }) => ({ offset: search.offset }),
  loader: ({ deps }) => fetchPosts({ offset: deps.offset }),
})
```

See [loaders.md](loaders.md) for more. Only include the fields the loader actually uses — do **not** return the whole `search` object (it causes cache-busting on unrelated param changes).

## Search middlewares

`search.middlewares` transforms the search used when building links from the route or its descendants (and on navigation, after validation). Two batteries-included helpers:

### `retainSearchParams` — keep a param stuck across navigations

```tsx
import { retainSearchParams } from '@tanstack/react-router'
import { z } from 'zod'
import { zodValidator } from '@tanstack/zod-adapter'

const schema = z.object({ rootValue: z.string().optional() })

export const Route = createRootRoute({
  validateSearch: zodValidator(schema),
  search: {
    middlewares: [retainSearchParams(['rootValue'])],
  },
})
```

### `stripSearchParams` — drop defaults from the URL

```tsx
import { stripSearchParams } from '@tanstack/react-router'

const defaultValues = { one: 'abc', two: 'xyz' }
const schema = z.object({
  one: z.string().default(defaultValues.one),
  two: z.string().default(defaultValues.two),
})

export const Route = createFileRoute('/hello')({
  validateSearch: zodValidator(schema),
  search: {
    middlewares: [stripSearchParams(defaultValues)],
  },
})
```

### Custom middleware + chaining

```tsx
export const Route = createFileRoute('/search')({
  validateSearch: zodValidator(
    z.object({
      retainMe: z.string().optional(),
      arrayWithDefaults: z.string().array().default(['foo', 'bar']),
      required: z.string(),
    }),
  ),
  search: {
    middlewares: [
      retainSearchParams(['retainMe']),
      stripSearchParams({ arrayWithDefaults: ['foo', 'bar'] }),
    ],
  },
})
```

Source: https://tanstack.com/router/v1/docs/framework/react/guide/search-params#transforming-search-with-search-middlewares

## Custom serialization

If you need a non-JSON wire format (base64, msgpack, etc.), set `parseSearch` and `stringifySearch` on the router. For most projects the default JSON-aware serializer is what you want. Source: https://tanstack.com/router/v1/docs/framework/react/guide/custom-search-param-serialization (raw/guide-custom-search-param-serialization.md).

## Common mistakes

**Mistake: `useSearchParams()`.**
```tsx
// WRONG — react-router-dom
const [params, setParams] = useSearchParams()
const page = params.get('page')
// RIGHT — validateSearch + useSearch
export const Route = createFileRoute('/x')({
  validateSearch: z.object({ page: z.number().default(1) }),
})
const { page } = Route.useSearch()
```

**Mistake: mutating the URL via `window.history.replaceState` or building strings.**
Always go through `<Link search>`, `navigate({ search })`, or `<Navigate search />`. String URLs lose validation, middlewares, and parent search inheritance.

**Mistake: returning whole `search` from `loaderDeps`.**
Causes cache-busting on every unrelated param change. Pick only the fields the loader actually uses.

**Mistake: using Zod v3 directly as `validateSearch`.**
Works at runtime, but the `Link` typing breaks (search becomes required even when it has defaults, or types are lost). Wrap with `zodValidator(schema)` from `@tanstack/zod-adapter` for v3. Zod v4, Valibot, ArkType, and Effect Schema can be passed directly.

**Mistake: declaring the same search key in parent AND child with different types.**
Types merge down — if the parent says `sort: 'asc' | 'desc'` and the child says `sort: number`, you get a type conflict. Keep each key owned by one level.

**Mistake: forgetting defaults / `.catch()` / `fallback()`.**
A malformed search in a bookmarked URL (user types in something weird) will throw from `validateSearch`, hitting `errorComponent`. Nearly always you want fallback values instead.
