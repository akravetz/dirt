---
title: Mutations & Invalidation
concept: tanstack-query-v5
updated: 2026-06-18
source: https://tanstack.com/query/v5/docs/framework/react/guides/mutations
---

> This file anchors agents to current TanStack Query v5 mutation practices. Prefer lifecycle callbacks plus targeted invalidation over scattered refetch calls.

# Mutations & Invalidation

Use `useMutation` for create/update/delete operations and other server side effects.

```tsx
const addNoteMutation = useMutation({
  mutationFn: (input: AddNoteInput) => addBreedingNote(input),
})
```

A mutation is one of `idle`, `pending`, `error`, or `success`. Render directly from `isPending`, `isError`, `error`, `data`, and `variables` instead of inventing a parallel local status machine.

## Invalidate from mutation callbacks

When a mutation makes query data stale, invalidate affected queries from `onSuccess` or `onSettled`:

```tsx
const queryClient = useQueryClient()

const addNoteMutation = useMutation({
  mutationFn: (input: AddNoteInput) => addBreedingNote(input),
  onSettled: (_data, _error, variables) =>
    queryClient.invalidateQueries({
      queryKey: ['breeding-logbook', 'plants', variables.plantId],
    }),
})
```

If pending UI should remain until the refetch completes, return the invalidation promise:

```tsx
const addNoteMutation = useMutation({
  mutationFn: addBreedingNote,
  onSettled: () =>
    queryClient.invalidateQueries({
      queryKey: ['breeding-logbook', 'plants'],
    }),
})
```

The Optimistic Updates guide explicitly calls out returning the invalidation promise so the mutation stays pending until the refetch finishes.

## Choose `onSuccess` vs `onSettled`

Use `onSuccess` when stale data should be refreshed only after a successful server write.

Use `onSettled` when the UI should reconcile after either success or failure. This is common for optimistic updates, because failure may need rollback followed by a refetch.

```tsx
useMutation({
  mutationFn: updatePlant,
  onSuccess: (plant) =>
    queryClient.invalidateQueries({
      queryKey: ['breeding-logbook', 'plants', plant.id],
    }),
})
```

## Consecutive mutation ordering

Do not assume consecutive `mutate` calls resolve in submit order. The mutations guide warns that asynchronous mutation functions may fulfill out of order.

For concurrent optimistic UI, select `mutation.state.submittedAt` via `useMutationState` or store a client-side pending id.

## Sources

- https://tanstack.com/query/v5/docs/framework/react/guides/mutations
- https://tanstack.com/query/v5/docs/framework/react/guides/invalidations-from-mutations
- https://tanstack.com/query/v5/docs/framework/react/guides/optimistic-updates
