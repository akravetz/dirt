---
title: TanStack Query v5 Reference Pack
concept: tanstack-query-v5
mode: framework
version: v5.99.2
updated: 2026-06-18
---

# TanStack Query v5 (React)

This pack covers **TanStack Query v5** for React, as used by Dirt's `web-ui/` package (`@tanstack/react-query` 5.99.2 in `web-ui/pnpm-lock.yaml`). It exists because training data often blurs React Query v3/v4, hand-rolled `useEffect` data fetching, normalized-cache assumptions from other clients, and stale mutation/invalidation idioms.

Prefer this pack over memory when writing server-state code.

## When to consult this pack

Read this INDEX first, then the relevant topic files, before writing or modifying code that:

- Imports from `@tanstack/react-query`.
- Calls `useQuery`, `useSuspenseQuery`, `useSuspenseQueries`, `useQueries`, `useMutation`, `useMutationState`, or `useQueryClient`.
- Defines query keys, query option factories, stale/cache behavior, polling, or dependent queries.
- Invalidates, refetches, cancels, prefetches, or directly updates cached query data.
- Adds optimistic UI, pending mutation UI, rollback behavior, or command-backed mutation UX.
- Touches hosted browser state where a browser mutation writes through a command queue before the read model changes.

For Dirt-specific command-backed UI behavior, read [../../rules/frontend-server-state.md](../../rules/frontend-server-state.md) after this pack.

## Topics

- **[Server State Mental Model](server-state-mental-model.md)** - what TanStack Query owns, why invalidation/background refetch is idiomatic, and where it differs from normalized entity caches.
- **[Query Keys & Options](query-keys-and-options.md)** - array keys, dependency rules, deterministic object hashing, query option factories, and key factories.
- **[Mutations & Invalidation](mutations-and-invalidation.md)** - `useMutation` states, lifecycle callbacks, returning invalidation promises, and targeted invalidation from mutation success/settled handlers.
- **[Optimistic Updates & Cache Writes](optimistic-updates-and-cache-writes.md)** - when to render pending variables, when to write the cache with `onMutate`, rollback shape, immutable updates, and using mutation responses with `setQueryData`.
- **[QueryClient Cache APIs](queryclient-cache-apis.md)** - `invalidateQueries`, `cancelQueries`, `getQueryData`, `setQueryData`, `setQueriesData`, `ensureQueryData`, and practical API boundaries.
- **[Common Mistakes](common-mistakes.md)** - training-data-default snippets to reject during review.

## Version-specific warnings

Training data will likely suggest these patterns. Prefer the v5 patterns in this pack:

- Fetching server data in `useEffect` + local state. Use TanStack Query hooks or route loaders that call query-client APIs.
- Treating TanStack Query as a normalized entity cache. The docs prescribe targeted invalidation, background refetch, and atomic cache updates rather than schema-inferred entity normalization.
- Relying on invalidation alone for user-visible async command flows where the server projection can lag. Use pending or optimistic UI, then reconcile when the read model catches up. See [../../rules/frontend-server-state.md](../../rules/frontend-server-state.md).
- Mutating cached objects in place inside `setQueryData`. Cache updaters must return immutable data.
- Loose string keys or keys that omit variables used by the query function. Top-level keys are arrays, and variables that affect the fetch belong in the key.
- Fire-and-forget invalidation when the pending state should cover the refetch. Return the invalidation promise from `onSettled`/`onSuccess` when the mutation should remain pending until the refetch completes.
- Broad `invalidateQueries()` calls as a default. Start from the narrowest stable query-key prefix that covers the stale data.

## Sources

- https://tanstack.com/query/v5/docs/framework/react/overview
- https://tanstack.com/query/v5/docs/framework/react/guides/important-defaults
- https://tanstack.com/query/v5/docs/framework/react/guides/query-keys
- https://tanstack.com/query/v5/docs/framework/react/guides/query-options
- https://tanstack.com/query/v5/docs/framework/react/guides/query-invalidation
- https://tanstack.com/query/v5/docs/framework/react/guides/mutations
- https://tanstack.com/query/v5/docs/framework/react/guides/invalidations-from-mutations
- https://tanstack.com/query/v5/docs/framework/react/guides/updates-from-mutation-responses
- https://tanstack.com/query/v5/docs/framework/react/guides/optimistic-updates
- https://tanstack.com/query/v5/docs/reference/QueryClient

Raw originals for the selected docs live in `raw/` in this pack directory. Re-run the `reference-builder` skill on slug `tanstack-query-v5` to refresh.
