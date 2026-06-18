---
title: Server State Mental Model
concept: tanstack-query-v5
updated: 2026-06-18
source: https://tanstack.com/query/v5/docs/framework/react/overview
---

> This file anchors agents to current TanStack Query v5 practices. Prefer what's written here over training-data recollection, especially when deciding between local state, invalidation, and direct cache writes.

# Server State Mental Model

TanStack Query manages **server state**: data owned outside React, fetched asynchronously, cached by query key, shared across components, and refreshed when it becomes stale. It is not a general client-state store and it is not a normalized GraphQL-style entity cache.

Use it for API-backed state that needs loading/error states, retries, deduplication, caching, invalidation, refetching, or optimistic mutation handling.

## Idiomatic flow

```tsx
import { useQuery } from '@tanstack/react-query'

const plantsQuery = useQuery({
  queryKey: ['breeding-logbook', 'plants'],
  queryFn: fetchBreedingPlants,
})
```

Keep render code derived from query state:

```tsx
if (plantsQuery.isPending) return <Spinner />
if (plantsQuery.isError) return <ErrorState error={plantsQuery.error} />

return <PlantList plants={plantsQuery.data} />
```

Do not mirror query data into component state just to render it. Copying query data into `useState` creates a second source of truth and breaks background refresh semantics.

## Invalidation is normal, not a workaround

TanStack Query's invalidation model is intentional. The Query Invalidation guide says invalidating a query marks it stale and active rendered queries refetch in the background. The same guide contrasts this with normalized-cache libraries and says TanStack Query prescribes targeted invalidation, background refetching, and atomic updates.

Use invalidation when a mutation changed server state and the most reliable source of truth is a later read:

```tsx
await queryClient.invalidateQueries({
  queryKey: ['breeding-logbook', 'plants'],
})
```

Use direct cache writes when the mutation response or local variables contain enough information to update visible state correctly. See [optimistic-updates-and-cache-writes.md](optimistic-updates-and-cache-writes.md).

## Dirt command-backed caveat

Some Dirt hosted UI mutations enqueue commands that the gateway later applies to the local database and syncs back to the hosted read model. For those flows, invalidation remains necessary but may not be sufficient for responsive UI: an immediate refetch can legitimately return the old projection.

For command-backed hosted UI, pair TanStack Query's standard mutation tools with a pending or optimistic representation. See [../../rules/frontend-server-state.md](../../rules/frontend-server-state.md).

## Sources

- https://tanstack.com/query/v5/docs/framework/react/overview
- https://tanstack.com/query/v5/docs/framework/react/guides/query-invalidation
