---
title: Atlas Reference Pack
concept: atlas
mode: framework
version: 1.2.0
updated: 2026-04-19
---

# Atlas (ariga/atlas)

This pack covers [Atlas](https://atlasgo.io/) v1.2.0 (released 2026-04-10) — the open-source schema-as-code migration CLI from ariga. In this project Atlas replaces Alembic / hand-written SQL migrations. The source of truth for our schema is the `SQLModel` classes under `apps/shared/src/dirt_shared/models/`; Atlas reads that metadata via the `atlas-provider-sqlalchemy` loader (SQLModel is a SQLAlchemy 2.x subclass, so `SQLModel.metadata` *is* a `sqlalchemy.MetaData` — the provider works unchanged). Target DB is Postgres 16+, dev DB is an ephemeral `docker://postgres/16/dev` container.

## When to consult this pack

Read this INDEX first (plus the relevant topic files) before:

- editing `atlas.hcl` at the repo root
- running `atlas migrate diff <name>`, `atlas migrate apply`, `atlas migrate lint`, or `atlas schema inspect`
- adding a new SQLModel table in `apps/shared/src/dirt_shared/models/*.py` and generating the migration for it
- authoring or hand-editing a migration file under `migrations/`
- wiring Atlas into GitHub Actions

Prefer what is written in this pack over recollection — training data commonly suggests Alembic, hand-written SQL, `enum`/`namespace`-style Python config files, or pre-v1 Atlas patterns (no `atlas migrate lint --dev-url`, no `data "external_schema"` block). All wrong for v1.2.

## Topics

- **[Installation and CLI surface](installation-and-cli.md)** — installing Atlas, the commands we actually use (`migrate diff|apply|lint|status|hash|new`, `schema inspect|apply`), URL format conventions.
- **[HCL schema reference](hcl-schema.md)** — `schema`, `table`, `column`, `primary_key`, `foreign_key`, `index`, `check`, `enum` blocks. Postgres-specific types (uuid, jsonb, timestamptz, arrays). Read when hand-writing or reading generated HCL.
- **[SQLAlchemy / SQLModel external loader](sqlalchemy-external-loader.md)** — THE critical topic for Dirt. How `atlas-provider-sqlalchemy` imports SQLModel tables and emits DDL, the `data "external_schema"` block, where to point `--path`, and the SQLModel-specific gotcha about `table=True` metadata registration.
- **[atlas.hcl configuration](atlas-hcl-config.md)** — anatomy of our `atlas.hcl`: `env "local"` vs `env "ci"`, `src` / `dev` / `migration` / `url`, variable interpolation (`var.*`, `local.*`), `data "composite_schema"` for extension/schema bootstrap.
- **[Migration workflow](migration-workflow.md)** — dev-first loop: write SQLModel → `atlas migrate diff` → review → `atlas migrate apply`. Why Atlas needs a dev DB, how the `docker://postgres/16/dev` provider works, `atlas.sum` integrity, baseline for existing DBs, `atlas migrate status`.
- **[Migration lint and CI safety](migration-lint-and-safety.md)** — every lint rule code (DS*, MF*, BC*, PG*, TX*) and what triggers it, the `-- atlas:nolint`/`-- atlas:txmode none` directives, CI wiring via `ariga/atlas-action` + Postgres service container in GitHub Actions.
- **[Postgres specifics](postgres-specifics.md)** — `CREATE INDEX CONCURRENTLY`, partial indexes (`where = ...`), enums in HCL, `jsonb`, `timestamptz`, extensions (`uuid-ossp`, `pgcrypto`), `NOT VALID` for cheap constraint adds, and the lint rules that guard each.

## Version-specific warnings

Patterns training data will suggest but that are wrong for Atlas v1.2 / current Dirt layout:

- **Alembic `env.py` + `alembic revision --autogenerate`** — not used in this repo. We use `atlas migrate diff --env local` against SQLModel metadata. See [sqlalchemy-external-loader.md](sqlalchemy-external-loader.md).
- **Hand-written SQL migration files named `V001__init.sql`** (Flyway-style). Atlas's default format is `{timestamp}_{name}.sql` with a co-located `atlas.sum` checksum file. Never edit `atlas.sum` by hand — regenerate with `atlas migrate hash`. See [migration-workflow.md](migration-workflow.md).
- **`atlas migrate diff --to file://schema.hcl`** (direct HCL authoring). We do not author HCL. Our `--to` resolves through `data "external_schema"` → `atlas-provider-sqlalchemy` → SQLModel metadata. See [sqlalchemy-external-loader.md](sqlalchemy-external-loader.md).
- **`CREATE INDEX` against a live table** — flagged by lint rule **PG101**. Atlas can auto-rewrite to `CONCURRENTLY` via `diff { concurrent_index { create = true } }` in `atlas.hcl`. See [postgres-specifics.md](postgres-specifics.md).
- **`ALTER TABLE ... ADD COLUMN x NOT NULL`** — flagged by **MF103** (non-nullable column without default breaks against existing rows). Add a default or split into two migrations. See [migration-lint-and-safety.md](migration-lint-and-safety.md).
- **Running `atlas` against SQLite (`var/dirt.db`)** — we are migrating off SQLite to Postgres. All dev / CI / prod URLs target Postgres 16+. The sqlite provider exists but is not our path.
- **`atlas init` / `atlas schema apply` as a replacement for `migrate`** — `schema apply` is the declarative (stateless) workflow. We use the versioned workflow (`migrate diff` + `migrate apply`) so each change is a reviewable, hash-locked file in `migrations/`. See [migration-workflow.md](migration-workflow.md).
- **Pre-v1 Atlas flag names** — `--dev` has been `--dev-url` since v0.8. `atlas migrate validate` is now `atlas migrate hash --dry-run`. `atlas migrate lint` *requires* a `--dev-url` (it replays migrations onto it).
- **`atlas login` for OSS workflows** — `login` unlocks Atlas Pro (ownership policy, enforce-lint). Everything in this pack works on the community CLI without auth. See [installation-and-cli.md](installation-and-cli.md).

## Sources

- https://atlasgo.io/getting-started
- https://atlasgo.io/atlas-schema/hcl
- https://atlasgo.io/atlas-schema/projects
- https://atlasgo.io/versioned/diff
- https://atlasgo.io/versioned/apply
- https://atlasgo.io/versioned/lint
- https://atlasgo.io/lint/analyzers
- https://atlasgo.io/concepts/dev-database
- https://atlasgo.io/integrations/github-actions
- https://github.com/ariga/atlas (HEAD df19880, 2026-04-14)
- https://github.com/ariga/atlas-provider-sqlalchemy (v0.5.0, HEAD ce07556, 2025-12-14)
- Raw sources copied into `raw/` for audit.
