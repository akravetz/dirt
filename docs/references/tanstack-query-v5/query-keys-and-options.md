---
title: Query Keys & Options
concept: tanstack-query-v5
updated: 2026-06-18
source: https://tanstack.com/query/v5/docs/framework/react/guides/query-keys
---

> This file anchors agents to current TanStack Query v5 practices. Prefer object-style hook options and stable array query keys over older or ad hoc patterns.

# Query Keys & Options

Query keys identify cached data. In v5 docs, query keys are arrays at the top level. They can contain strings, numbers, and serializable objects, but they must be unique to the data returned by the query function.

## Include fetch variables in the key

If a query function depends on a value that changes the result, include that value in the key:

```tsx
useQuery({
  queryKey: ['breeding-logbook', 'plants', { generation, includeCulled }],
  queryFn: () => fetchBreedingPlants({ generation, includeCulled }),
})
```

Do not close over a variable in `queryFn` while leaving it out of `queryKey`; the cache will reuse the wrong data.

## Object order is stable; array order matters

TanStack Query hashes object members deterministically, so these represent the same key:

```tsx
['plants', { generation, includeCulled }]
['plants', { includeCulled, generation }]
```

Array position still matters:

```tsx
['plants', generation, includeCulled]
['plants', includeCulled, generation]
```

Prefer named object segments once a key has more than one variable.

## Use query option factories for reuse

When a query is used by hooks, route loaders, prefetching, or tests, put the key and function in one option factory:

```tsx
import { queryOptions } from '@tanstack/react-query'

export function breedingPlantsQueryOptions(filters: PlantFilters) {
  return queryOptions({
    queryKey: ['breeding-logbook', 'plants', filters],
    queryFn: () => fetchBreedingPlants(filters),
  })
}
```

Then consume the same definition everywhere:

```tsx
const plantsQuery = useQuery(breedingPlantsQueryOptions(filters))
await queryClient.ensureQueryData(breedingPlantsQueryOptions(filters))
```

This prevents query-key drift between render code, loaders, invalidation, and tests.

## Key factories

For a feature with multiple related queries, use a small local key factory:

```tsx
const breedingLogbookKeys = {
  all: ['breeding-logbook'] as const,
  plants: () => [...breedingLogbookKeys.all, 'plants'] as const,
  plantList: (filters: PlantFilters) =>
    [...breedingLogbookKeys.plants(), filters] as const,
  plant: (plantId: string) =>
    [...breedingLogbookKeys.plants(), plantId] as const,
}
```

Invalidate from the narrowest prefix that reflects what changed:

```tsx
await queryClient.invalidateQueries({
  queryKey: breedingLogbookKeys.plants(),
})
```

## Sources

- https://tanstack.com/query/v5/docs/framework/react/guides/query-keys
- https://tanstack.com/query/v5/docs/framework/react/guides/query-options
