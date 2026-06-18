# Codebase Rules

This directory contains conventions and constraints that agents must follow when working in this codebase. Read relevant rule files before making changes in affected areas.

## Rules Index

| Rule | Read before |
|---|---|
| [boundary-contracts.md](boundary-contracts.md) | changing FastAPI request/response bodies, gateway/control-plane sync payloads, cloud outbox JSON, command claim/result payloads, generated API contracts, or any other process/network/persistence boundary. |
| [data-modeling.md](data-modeling.md) | creating or changing SQLModel table models, SQL migrations, primary keys, foreign keys, natural keys, uniqueness constraints, table names, or persisted identifiers. |
| [frontend-server-state.md](frontend-server-state.md) | changing TanStack Query mutations, optimistic UI, pending command UX, cache invalidation, or hosted command-backed browser flows in `web-ui/`. |
