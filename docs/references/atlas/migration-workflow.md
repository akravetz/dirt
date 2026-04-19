---
title: Migration workflow
concept: atlas
updated: 2026-04-19
source: https://atlasgo.io/versioned/diff
---

> Anchors agents to current Atlas v1.2 versioned-migrations workflow. Prefer what is here over training-data instincts toward Alembic's `autogenerate` / `upgrade head` or hand-written numeric migrations.

# Migration workflow

Dirt uses Atlas's **versioned** workflow: each schema change is a timestamped SQL file under `migrations/`, reviewed in PRs, hash-locked in `atlas.sum`, and applied in order to Postgres at deploy time. The declarative (stateless) `atlas schema apply` workflow is **not** used.

## The loop

```
1. Edit a SQLModel class in apps/shared/src/dirt_shared/models/
2. atlas migrate diff <short_name> --env local        # generates migrations/<ts>_<name>.sql
3. Read the generated SQL. If wrong, fix the model and re-run.
4. atlas migrate lint --env local --latest 1          # sanity check (optional locally, required in CI)
5. git add migrations/ apps/shared/... && commit
6. atlas migrate apply --env local                    # apply locally
7. PR → CI runs `atlas migrate lint` against origin/main
8. Merge → deployment pipeline runs `atlas migrate apply` against prod URL
```

## `atlas migrate diff` — generating migrations

```bash
atlas migrate diff add_grow_state --env local
```

Under the hood Atlas:

1. Spins up the dev DB from `env.local.dev` (`docker://postgres/16/dev?search_path=public`).
2. Replays every existing file in `migrations/` onto it, in filename-timestamp order — this is the **current state**.
3. Reads the **desired state** via `env.local.src` → `data.composite_schema.app.url` → SQLModel DDL (plus extensions.sql). See [sqlalchemy-external-loader.md](sqlalchemy-external-loader.md).
4. Computes the delta and writes one new `migrations/<unix-timestamp>_add_grow_state.sql` file.
5. Recomputes `atlas.sum` (a per-file SHA-256 ledger that prevents silent edits to old migrations).
6. Tears down the dev container.

If the diff is empty (current == desired), Atlas exits with `The migration directory is synced with the desired state, no changes to be made`. That is success, not an error.

### When the diff is wrong

- The generated SQL does something you don't want (e.g. drops a column you only meant to rename): **fix the model**, then delete the freshly generated file, then re-run `diff`. Do not hand-edit the SQL.
- Atlas can't figure out your intent (e.g. column rename, which it sees as drop+add): write an empty migration with `atlas migrate new <name>`, author the SQL yourself, then `atlas migrate hash` to update `atlas.sum`.

## The dev DB — why Atlas needs it

Atlas does **not** parse SQL statically. It runs them against a real database and inspects the result. This catches:

- SQL that a specific Postgres version rejects (e.g. `GENERATED STORED` on pg12).
- Constraint name collisions that only the server sees.
- Normalization differences — Postgres rewrites e.g. `NUMERIC` without precision internally, and Atlas needs the canonical form to produce stable diffs.

`docker://postgres/16/dev?search_path=public` tells Atlas to spin up an ephemeral container, create a throwaway DB, run the workflow, and destroy everything. First run pulls the image (~150 MB); subsequent runs reuse the Docker cache. Match the major version to production (16+) — a pg15 dev container won't verify a pg16-only feature.

If the dev DB is slow to spin up on your laptop, fall back to a locally running Postgres:

```bash
docker run -d --rm --name atlas-dev -p 5433:5432 -e POSTGRES_PASSWORD=dev postgres:16
# then in atlas.hcl:
# dev = "postgres://postgres:dev@localhost:5433/postgres?sslmode=disable"
```

## `atlas migrate apply` — executing migrations

```bash
# Default — apply all pending migrations
atlas migrate apply --env local

# Constrain the batch
atlas migrate apply 1 --env local        # apply exactly one
atlas migrate apply --env local --dry-run

# Transaction control (per-run default)
atlas migrate apply --env local --tx-mode file   # default: each file in its own txn
atlas migrate apply --env local --tx-mode all    # one txn for everything
atlas migrate apply --env local --tx-mode none   # no wrapping — required for CONCURRENTLY
```

Atlas tracks applied migrations in `atlas_schema_revisions`. Don't drop or edit that table. Each row stores a file's hash; if the file on disk changes after being applied, the next `apply` refuses to run.

### Baseline for an existing DB

If Dirt's Postgres already has tables before Atlas is introduced (e.g. migrated from the SQLite dump by hand), bootstrap the revisions table by declaring a baseline:

```bash
# 1. Generate a migration that reflects the current DB.
atlas migrate diff baseline \
  --env local \
  --to "postgres://..." # point --to at the live DB temporarily

# 2. Commit the baseline file, then mark it applied without actually running it.
atlas migrate apply --env local --baseline "<timestamp>"
```

Subsequent `apply` runs start from the next migration after baseline.

### Rollback?

Atlas does **not** auto-generate down migrations. If you need to back out a change, write a new forward migration that undoes it. This matches the reality that most production rollbacks require data-preserving maneuvers a naive `DROP` would destroy.

## `atlas migrate status`

```bash
atlas migrate status --env local
```

Output: `Migration Status: OK` or `PENDING`, with counts of executed vs pending files and the current/next version. Use this before `apply` when you're unsure of DB state.

## The `migrations/` directory

```
migrations/
├── 20260419120000_initial_schema.sql
├── 20260420093012_add_grow_state.sql
├── 20260421144401_backfill_plant_ids.sql
└── atlas.sum
```

- Filenames sort lexically == chronologically, driving apply order.
- `atlas.sum` is **generated**. If you get a merge conflict in it, resolve by keeping both sides' hashes and re-running `atlas migrate hash --env local`.
- Never rename or delete an applied migration file. To reverse a change, add a new forward migration.

## Common mistakes

- **Running `atlas migrate diff` without reviewing the SQL.** Generated migrations can drop columns when you meant to rename, or reorder tables in ways that hit lint rules. Always read the output before committing.
- **Editing an applied migration.** `atlas.sum` will mismatch and the next `apply` will refuse to run. Revert the edit or regenerate `atlas.sum` with `atlas migrate hash` — but understand this is destructive if the change has already shipped.
- **`atlas migrate apply` before `atlas migrate diff`.** Useless; `apply` only runs files that already exist in `migrations/`. If you expected a new change and got `no pending migrations`, you forgot to `diff`.
- **Using Alembic's `--autogenerate` + `upgrade head` mental model.** The file layout and commands differ; `alembic upgrade head` → `atlas migrate apply`, `alembic revision --autogenerate -m` → `atlas migrate diff <name>`.
- **Forgetting `atlas migrate hash` after `atlas migrate new`.** An empty-created migration file is not hashed automatically, so `apply` will reject it.
