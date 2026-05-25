# Epic: Local Dev Environment Harness

Status: planning
Priority: high
Created: 2026-05-25

## Goal

Provide one canonical command path for humans and agents to run the real hosted control-plane API and web UI locally without knowing the database restore, auth, CORS, credential sanitization, or process-supervision details.

## Scope

- Add root `make` targets as the public command catalog.
- Add `scripts/dev-env` as the Python implementation harness behind `make dev-up`, `make dev-down`, `make dev-reset`, `make dev-refresh-db`, `make dev-refresh-assets`, and `make dev-status`.
- Run a local control-plane database restored from a compressed Railway dump with local-only credentials.
- Sanitize restored state by replacing gateway credentials, clearing active commands, and keeping audit history.
- Add an asset-store boundary so production uses S3 and dev can serve local files from `var/dev/control-plane/assets/`.
- Add `make dev-refresh-assets` as a TODO stub for later production asset mirroring.
- Expose the formatting/fix workflow as `make fix`.

## Acceptance Criteria

- `make dev-up` starts a local control-plane API and Vite web UI with the frontend pointed at the local API.
- A fresh checkout can refresh an isolated local cloud database from Railway without mutating production or the live local `dirt` database.
- Local login works over HTTP with generated local-only credentials.
- Dashboard data comes from the real control-plane API rather than MSW fixtures.
- Restored asset metadata can resolve to local files when files are present under `var/dev/control-plane/assets/<object_key>`.
- `make dev-refresh-assets` exists and clearly reports that production asset mirroring is not implemented yet.
- `make fix` is the documented formatting/fix entry point.
- `make dev-reset` explicitly recreates the dev cloud database; normal `make dev-up` is repeatable and non-destructive.

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:dev-env"`

Primary implementation plan: [ExecPlan.md](ExecPlan.md).
