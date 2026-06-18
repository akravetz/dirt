---
title: QueryClient Cache APIs
concept: tanstack-query-v5
updated: 2026-06-18
source: https://tanstack.com/query/v5/docs/reference/QueryClient
---

> This file anchors agents to current TanStack Query v5 `QueryClient` practices. Prefer official cache APIs over local mirrors or manual global stores.

# QueryClient Cache APIs

Get the current client in React components with `useQueryClient()` and pass it into loaders or utilities where the app already has router context.

## `invalidateQueries`

Marks matching queries stale and refetches active rendered queries in the background.

```tsx
await queryClient.invalidateQueries({
  queryKey: ['breeding-logbook', 'plants'],
})
```

Use `exact: true` when only the exact key should match:

```tsx
await queryClient.invalidateQueries({
  queryKey: ['breeding-logbook', 'plants'],
  exact: true,
})
```

## `cancelQueries`

Cancel outgoing refetches before writing an optimistic value, so late network responses do not overwrite the optimistic update.

```tsx
await queryClient.cancelQueries({
  queryKey: ['breeding-logbook', 'plants', plantId],
})
```

## `getQueryData`

Synchronously reads cached data for a single key.

```tsx
const plant = queryClient.getQueryData<PlantDetail>([
  'breeding-logbook',
  'plants',
  plantId,
])
```

Use this for snapshots and conditional cache logic. It returns `undefined` if the query is not cached.

## `setQueryData`

Synchronously writes one cached query. The QueryClient reference describes this as an immediate cache update.

```tsx
queryClient.setQueryData<PlantDetail>(
  ['breeding-logbook', 'plants', plantId],
  (old) =>
    old
      ? {
          ...old,
          status: 'culled',
        }
      : old,
)
```

Never mutate `old` in place. Return a new object/array for changed data.

## `setQueriesData`

Updates multiple existing cached queries that match filters. Use it when a single mutation affects several already-cached list variants.

```tsx
queryClient.setQueriesData<PlantSummary[]>(
  { queryKey: ['breeding-logbook', 'plants'] },
  (old) =>
    old?.map((plant) =>
      plant.id === plantId ? { ...plant, status: 'culled' } : plant,
    ),
)
```

Keep these updaters narrow and tested. If the transformation becomes complex, prefer invalidation plus a visible pending state.

## `ensureQueryData`

Use `ensureQueryData` when a loader or prefetch path needs data and should reuse the query cache if available:

```tsx
await queryClient.ensureQueryData(breedingPlantsQueryOptions(filters))
```

Pair this with query option factories so hooks and loaders share the same key/function.

## Sources

- https://tanstack.com/query/v5/docs/reference/QueryClient
- https://tanstack.com/query/v5/docs/framework/react/guides/query-invalidation
