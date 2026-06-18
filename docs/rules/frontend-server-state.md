# Frontend Server State

Read this before changing TanStack Query mutations, optimistic UI, pending command UX, cache invalidation, or hosted command-backed browser flows in `web-ui/`.

This rule is intentionally separate from `AGENTS.md`. Current agent guidance from OpenAI, Anthropic, and the AGENTS.md convention points toward concise root instructions plus scoped files for domain-specific rules. Anthropic also describes progressive disclosure as a way to keep core instructions lean while loading detailed references only when relevant.

## Mental model

Dirt has two different mutation shapes:

- **Direct API mutation:** the browser calls the hosted API, the backend writes the canonical hosted state, and the response or next refetch can usually reflect the write.
- **Command-backed mutation:** the browser enqueues a hosted command, `dirt-gateway` claims it, local services apply it to the home database/hardware side, then the gateway syncs the resulting projection back to hosted read models.

For command-backed mutations, "API accepted the command" is not the same as "the query read model has changed." Immediate invalidation can refetch the old projection and leave the UI looking stuck or stale.

## Rule

Do not rely on short timed invalidation windows as the only convergence mechanism for command-backed UI.

Use TanStack Query's mutation lifecycle plus one visible convergence strategy:

- Render pending mutation `variables` directly when only the local component needs the temporary state.
- Use `onMutate` + `setQueryData` when multiple views need the optimistic state.
- Track command status or expected projection when the backend exposes enough information.
- Invalidate/refetch affected queries after settlement so the cache reconciles with server truth.
- Remove pending/optimistic UI when the projection appears, when a final mutation response can be applied safely, or when failure is surfaced.

Failure paths must be explicit: rollback the optimistic cache value, keep the failed pending item with retry, or show an actionable error state. Do not silently drop the user's write from the UI.

## Preferred mutation shape

```tsx
const addNoteMutation = useMutation({
  mutationFn: addBreedingNote,
  mutationKey: ['breeding-logbook', 'add-note'],
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

If the optimistic change only appears in one component, prefer the simpler pending-variable pattern from [../references/tanstack-query-v5/optimistic-updates-and-cache-writes.md](../references/tanstack-query-v5/optimistic-updates-and-cache-writes.md).

## Testing expectations

When changing command-backed UI, include tests for the behavior users observe:

- The mutation sends the expected request/command payload.
- The UI enters a pending or optimistic state immediately.
- A delayed projection does not leave the UI stuck in `syncing`.
- Success reconciles with the refetched read model.
- Failure rolls back, preserves retry, or surfaces an error.

For breeding logbook query behavior, start with `web-ui/src/features/breeding-logbook/breedingLogbookQueries.test.ts` and colocated component tests in that feature.

## Sources

- TanStack Query v5 reference pack: [../references/tanstack-query-v5/INDEX.md](../references/tanstack-query-v5/INDEX.md)
- OpenAI Codex AGENTS.md guidance: https://developers.openai.com/codex/guides/agents-md
- AGENTS.md convention: https://agents.md/
- Anthropic Claude memory guidance: https://code.claude.com/docs/en/memory
- Anthropic Agent Skills progressive disclosure: https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills
