---
title: Optimistic Updates & Cache Writes
concept: tanstack-query-v5
updated: 2026-06-18
source: https://tanstack.com/query/v5/docs/framework/react/guides/optimistic-updates
---

> This file anchors agents to current TanStack Query v5 optimistic update practices. Prefer the smallest optimistic mechanism that makes the UI truthful.

# Optimistic Updates & Cache Writes

TanStack Query documents two optimistic update styles:

1. Render pending `variables` from the mutation result.
2. Update query cache directly in `onMutate`.

## Prefer pending variables for local-only optimistic display

If only one component needs to show the pending change, render it from the mutation:

```tsx
const queryClient = useQueryClient()

const addNoteMutation = useMutation({
  mutationFn: addBreedingNote,
  mutationKey: ['breeding-logbook', 'add-note'],
  onSettled: () =>
    queryClient.invalidateQueries({
      queryKey: ['breeding-logbook', 'plants'],
    }),
})

const pendingNote = addNoteMutation.isPending
  ? addNoteMutation.variables
  : undefined
```

When the query and mutation are in different components, use `useMutationState` with a `mutationKey`:

```tsx
const pendingNotes = useMutationState<AddNoteInput>({
  filters: {
    mutationKey: ['breeding-logbook', 'add-note'],
    status: 'pending',
  },
  select: (mutation) => mutation.state.variables,
})
```

This avoids touching cached server data and keeps rollback simple.

## Use `onMutate` when multiple views need the optimistic state

Direct cache updates are appropriate when multiple rendered queries should reflect the same pending change.

```tsx
const addNoteMutation = useMutation({
  mutationFn: addBreedingNote,
  onMutate: async (input, context) => {
    await context.client.cancelQueries({
      queryKey: ['breeding-logbook', 'plants', input.plantId],
    })

    const previousPlant = context.client.getQueryData<PlantDetail>([
      'breeding-logbook',
      'plants',
      input.plantId,
    ])

    context.client.setQueryData<PlantDetail>(
      ['breeding-logbook', 'plants', input.plantId],
      (old) =>
        old
          ? {
              ...old,
              notes: [
                ...old.notes,
                { id: input.clientId, text: input.text, pending: true },
              ],
            }
          : old,
    )

    return { previousPlant }
  },
  onError: (_error, input, result, context) => {
    context.client.setQueryData(
      ['breeding-logbook', 'plants', input.plantId],
      result?.previousPlant,
    )
  },
  onSettled: (_data, _error, input, _result, context) =>
    context.client.invalidateQueries({
      queryKey: ['breeding-logbook', 'plants', input.plantId],
    }),
})
```

The important sequence is:

1. Cancel outgoing refetches for the affected query.
2. Snapshot the old cache value.
3. Write the optimistic cache value immutably.
4. Roll back on error.
5. Invalidate/refetch on settlement.

## Use mutation responses when they contain the final object

If the backend returns the updated object, use `setQueryData` in `onSuccess` instead of immediately refetching:

```tsx
const updatePlantMutation = useMutation({
  mutationFn: updatePlant,
  onSuccess: (plant) => {
    queryClient.setQueryData(
      ['breeding-logbook', 'plants', plant.id],
      plant,
    )
  },
})
```

The Updates from Mutation Responses guide says `setQueryData` is useful when the mutation already returns the updated object. The same guide warns updates must be immutable.

## Sources

- https://tanstack.com/query/v5/docs/framework/react/guides/optimistic-updates
- https://tanstack.com/query/v5/docs/framework/react/guides/updates-from-mutation-responses
