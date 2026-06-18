---
title: Common Mistakes
concept: tanstack-query-v5
updated: 2026-06-18
source: https://tanstack.com/query/v5/docs/framework/react/guides/query-invalidation
---

> This file lists TanStack Query v5 mistakes agents are likely to make from stale training data or over-generalized frontend habits.

# Common Mistakes

## Fetching with `useEffect`

```tsx
// Wrong
useEffect(() => {
  fetchPlants().then(setPlants)
}, [])
```

```tsx
// Right
const plantsQuery = useQuery({
  queryKey: ['breeding-logbook', 'plants'],
  queryFn: fetchPlants,
})
```

## Omitting variables from the query key

```tsx
// Wrong: generation changes the fetch result but not the cache key.
useQuery({
  queryKey: ['breeding-logbook', 'plants'],
  queryFn: () => fetchPlants({ generation }),
})
```

```tsx
// Right
useQuery({
  queryKey: ['breeding-logbook', 'plants', { generation }],
  queryFn: () => fetchPlants({ generation }),
})
```

## Mutating cached data in place

```tsx
// Wrong
queryClient.setQueryData(['plants'], (old) => {
  old.push(newPlant)
  return old
})
```

```tsx
// Right
queryClient.setQueryData(['plants'], (old) =>
  old ? [...old, newPlant] : old,
)
```

## Invalidating too broadly by default

```tsx
// Usually too broad
queryClient.invalidateQueries()
```

```tsx
// Better
queryClient.invalidateQueries({
  queryKey: ['breeding-logbook', 'plants', plantId],
})
```

## Assuming invalidation changes cached data synchronously

`invalidateQueries` marks matching queries stale and refetches active queries in the background. It does not itself change the cached data to match a mutation. If the UI must reflect a write immediately, render pending variables or update the cache with `setQueryData`.

This matters especially for Dirt hosted commands because the immediate refetch can return the previous projection while the gateway is still applying the command.

## Leaving mutation state stuck behind a projection

Do not equate "command accepted by the hosted API" with "read model has already changed." Keep visible pending state until either:

- The refetched query contains the expected projection.
- The mutation response contains a final object that can be applied safely.
- The command fails and the UI rolls back or offers retry.

See [../../rules/frontend-server-state.md](../../rules/frontend-server-state.md).

## Sources

- https://tanstack.com/query/v5/docs/framework/react/guides/query-keys
- https://tanstack.com/query/v5/docs/framework/react/guides/query-invalidation
- https://tanstack.com/query/v5/docs/framework/react/guides/optimistic-updates
- https://tanstack.com/query/v5/docs/framework/react/guides/updates-from-mutation-responses
