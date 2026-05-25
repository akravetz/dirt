# Epic: Local Dev Environment Harness

Status: planning
Priority: high
Created: 2026-05-25

## Goal

Provide one canonical command path for humans and agents to run the real hosted control-plane API and web UI locally without knowing the database restore, auth, CORS, credential sanitization, or process-supervision details.

## Scope

- Add root `make` targets as the public command catalog.
- Add `scripts/dev-env` as the Python implementation harness behind `make dev-up`, `make dev-down`, `make dev-reset`, `make dev-refresh-db`, and `make dev-status`.
- Run a local control-plane database restored from a compressed Railway dump with local-only credentials.
- Sanitize restored state by replacing gateway credentials, clearing active commands, and keeping audit history.
- Expose the formatting/fix workflow as `make fix`.

## Acceptance Criteria

- `make dev-up` starts a local control-plane API and Vite web UI with the frontend pointed at the local API.
- A fresh checkout can refresh an isolated local cloud database from Railway without mutating production or the live local `dirt` database.
- Local login works over HTTP with generated local-only credentials.
- Dashboard data comes from the real control-plane API rather than MSW fixtures.
- `make fix` is the documented formatting/fix entry point.
- `make dev-reset` explicitly recreates the dev cloud database; normal `make dev-up` is repeatable and non-destructive.

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:dev-env"`

Primary implementation plan: [ExecPlan.md](ExecPlan.md).
