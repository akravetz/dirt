# Epic: Local Dev Environment Harness

Status: planning
Priority: high
Created: 2026-05-25

## Goal

Provide one canonical command path for humans and agents to run the real hosted control-plane API and web UI locally without knowing the database, migration, auth, CORS, gateway seed, or process-supervision details.

## Scope

- Add root `make` targets as the public command catalog.
- Add `scripts/dev-env` as the implementation harness behind `make dev-up`, `make dev-down`, `make dev-reset`, and `make dev-status`.
- Run a local control-plane database with cloud migrations and local-only credentials.
- Seed local cloud data from the real gateway projection without running continuous command execution by default.
- Keep `scripts/agent-fix` available through `make agent-fix`.

## Acceptance Criteria

- `make dev-up` starts a local control-plane API and Vite web UI with the frontend pointed at the local API.
- A fresh checkout can create and migrate an isolated local cloud database without touching production or the live local `dirt` database.
- Local login works over HTTP with generated local-only credentials.
- Dashboard data comes from the real control-plane API rather than MSW fixtures.
- `make agent-fix` is the documented formatting/fix entry point.
- `make dev-reset` explicitly recreates the dev cloud database; normal `make dev-up` is repeatable and non-destructive.

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:dev-env"`

Primary implementation plan: [ExecPlan.md](ExecPlan.md).
