---
title: Installation and CLI surface
concept: atlas
updated: 2026-04-19
source: https://atlasgo.io/getting-started
---

> Anchors agents to current Atlas v1.2 practice. Prefer what is here over training-data recollection — pre-v1 flag names and commands (e.g. `--dev`, `atlas migrate validate`) have been renamed or removed.

# Installation and CLI surface

## Installing Atlas

Community CLI, no login required for anything in this pack:

```bash
# macOS / Linux — recommended
curl -sSf https://atlasgo.sh | sh

# Homebrew
brew install ariga/tap/atlas

# Docker
docker pull arigaio/atlas
docker run --rm arigaio/atlas --help

# Verify
atlas version
```

`atlas login` unlocks Pro features (schema-rule DSL, ownership policies, `lint.*.force`). Everything in this pack works on the community build without logging in — do NOT add `atlas login` to dev onboarding unless the user asks for Pro features.

## URL format

Every Atlas command that touches a database takes a URL. The shape is shared across `--url`, `--dev-url`, `src`, and `dir`:

| Scheme | Meaning | Dirt use |
|---|---|---|
| `file://migrations` | Directory of `.sql` migration files + `atlas.sum`. | Always, for `--dir`. |
| `file://schema.hcl` | HCL schema file. | Not used (we use the SQLAlchemy loader). |
| `postgres://user:pass@host:5432/db?sslmode=disable` | Live Postgres. | `--url` in `apply` and `inspect`. |
| `docker://postgres/16/dev` | Ephemeral Postgres container spun up and torn down by Atlas. | `--dev-url` everywhere. |
| `docker://postgres/16/dev?search_path=public` | Same, scoped to a schema. | Add `search_path` when your app uses non-default schemas. |
| `sqlite://?mode=memory&_fk=1` | In-memory SQLite. | NOT used — project is migrating off SQLite. |

The `docker://` driver pulls the image on first use, starts the container, creates a throwaway database, and removes everything on exit. See [migration-workflow.md](migration-workflow.md) for the dev-DB rationale.

## Commands we actually use

All commands accept `--env <name>` to pull configuration from `atlas.hcl` instead of repeating flags. Dirt's envs are `local` (dev laptops) and `ci` (GitHub Actions).

### `atlas migrate diff <name>`

Generates a new migration file by computing the delta between the migration directory's replayed state (on `dev-url`) and the desired schema (`src`).

```bash
# Basic — relies on atlas.hcl env "local"
atlas migrate diff add_grow_state --env local

# Without an env, fully explicit
atlas migrate diff add_grow_state \
  --dir "file://migrations" \
  --to "file://schema.hcl" \
  --dev-url "docker://postgres/16/dev?search_path=public"
```

Output is `migrations/<unix-timestamp>_add_grow_state.sql` plus an updated `atlas.sum`. Review the SQL like any other diff; if Atlas produced something you don't want, adjust the SQLModel source and re-run.

### `atlas migrate apply`

Executes pending migrations against `--url`, tracking progress in the `atlas_schema_revisions` table.

```bash
# Apply all pending
atlas migrate apply --env local

# Apply the next N only
atlas migrate apply 1 --env local

# Preview without executing
atlas migrate apply --env local --dry-run

# First run against an already-populated DB
atlas migrate apply --env local --baseline "20260419120000"
```

`--tx-mode` controls transaction wrapping: `file` (default — each migration in its own txn), `all`, or `none`. Override per-file with a `-- atlas:txmode none` directive (required for `CREATE INDEX CONCURRENTLY`).

### `atlas migrate lint`

Statically analyzes pending migration files for destructive / locking / data-dependent patterns. Requires a `--dev-url` because the lint analyzers actually replay the migration onto the dev DB.

```bash
# Lint only files newer than origin/main
atlas migrate lint --env ci --git-base origin/main

# Lint the last N files (simpler, good for pre-commit)
atlas migrate lint --env local --latest 1
```

Rule codes (DS*, MF*, PG*, etc.) and how to silence individual findings live in [migration-lint-and-safety.md](migration-lint-and-safety.md).

### `atlas migrate status`

Reports which migrations are applied vs pending for `--url`.

```bash
atlas migrate status --env local
# Migration Status: PENDING
#   -- Current Version: 20260418...
#   -- Next Version:    20260419...
#   -- Executed Files:  7
#   -- Pending Files:   1
```

### `atlas migrate hash`

Recomputes `atlas.sum`. Needed after a merge conflict in `atlas.sum` or after manually editing a migration (which you should almost never do):

```bash
atlas migrate hash --env local
```

### `atlas migrate new <name>`

Creates an empty migration file for cases where Atlas can't infer the intent (data backfills, concurrent-index rewrites, extension installs):

```bash
atlas migrate new backfill_plant_ids --env local
# editor opens migrations/<timestamp>_backfill_plant_ids.sql
# write SQL, then:
atlas migrate hash --env local
```

### `atlas schema inspect`

Reverse-engineers a live database into HCL or SQL. Useful for debugging drift, NOT the source of truth:

```bash
atlas schema inspect --url "postgres://localhost:5432/dirt?sslmode=disable" --format '{{ sql . }}'
```

## Commands we do NOT use

- `atlas schema apply` — declarative (stateless) workflow. We want versioned migrations with a review trail, so we use `migrate diff` + `migrate apply` instead.
- `atlas login` / `atlas migrate push` — Atlas Cloud / Pro features.
- `atlas init` — scaffolds an `atlas.hcl` for an unfamiliar project; ours is already written.

## Common mistakes

- **`--dev` flag** — renamed to `--dev-url` years ago. Using `--dev` gives `unknown flag`.
- **Running `diff` without `--dev-url`** — fails with `Error: required flag --dev-url not set` unless your `atlas.hcl` env supplies one.
- **Editing `atlas.sum`** — it is a content hash, not a metadata file. Regenerate via `atlas migrate hash`.
- **Starting a local Postgres and passing `--dev-url "postgres://localhost:5432/dev"`** — works, but you then own its lifecycle. `docker://postgres/16/dev` is preferred; Atlas handles container lifecycle for you.
