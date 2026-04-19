---
title: atlas.hcl configuration
concept: atlas
updated: 2026-04-19
source: https://atlasgo.io/atlas-schema/projects
---

> Anchors agents to current Atlas v1.2 project config. Prefer what is here over training-data recollection — the `env {}` block in v1 has grown `lint`, `diff`, `format`, `schema`, and `data {}` sub-blocks that older snippets lack.

# atlas.hcl configuration

`atlas.hcl` at the repo root is Atlas's project file. It declares **environments** (selectable via `--env <name>`), **data sources** (external loaders, composite schemas), and global **format / lint / diff policy**. This file is the argument vector for every `atlas` invocation in Dirt.

## Dirt reference config

```hcl
# atlas.hcl — repo root

# ── Data sources ───────────────────────────────────────────────────────────

data "external_schema" "sqlmodel" {
  program = [
    "uv", "run", "--package", "dirt-shared",
    "python", "atlas/load_models.py",
  ]
}

data "composite_schema" "app" {
  # Extensions + schema bootstrap run first.
  schema "public" {
    url = "file://atlas/extensions.sql"
  }
  # SQLModel-derived tables layer on top.
  schema "public" {
    url = data.external_schema.sqlmodel.url
  }
}

# ── Local dev environment ──────────────────────────────────────────────────

env "local" {
  src = data.composite_schema.app.url
  dev = "docker://postgres/16/dev?search_path=public"
  url = getenv("DIRT_DATABASE_URL")  # e.g. postgres://dirt:dirt@localhost:5432/dirt?sslmode=disable

  migration {
    dir = "file://migrations"
  }

  # Auto-rewrite CREATE INDEX / DROP INDEX to CONCURRENTLY — see postgres-specifics.md.
  diff {
    concurrent_index {
      create = true
      drop   = true
    }
  }

  format {
    migrate {
      diff = "{{ sql . \"  \" }}"
    }
  }
}

# ── CI environment ─────────────────────────────────────────────────────────

env "ci" {
  src = data.composite_schema.app.url
  # CI provides Postgres as a service container — see migration-lint-and-safety.md.
  dev = "postgres://postgres:postgres@localhost:5432/dev?sslmode=disable"

  migration {
    dir = "file://migrations"
  }

  lint {
    latest = 1
    # Optional: compare against PR base branch for multi-file lint.
    # git { base = "origin/main" }
  }
}
```

Invocation:

```bash
atlas migrate diff add_grow_state --env local
atlas migrate apply --env local
atlas migrate lint --env ci --git-base origin/main
```

## Block anatomy

### `data "external_schema" "<name>"`

Runs `program` (argv list) and captures stdout as raw DDL. Atlas parses it with the dialect inferred from the target env's `dev`/`url`. Access the rendered URL via `data.external_schema.<name>.url`.

```hcl
data "external_schema" "sqlmodel" {
  program     = ["uv", "run", "--package", "dirt-shared", "python", "atlas/load_models.py"]
  working_dir = "/optional/cwd"   # defaults to where atlas.hcl lives
}
```

### `data "composite_schema" "<name>"`

Merges multiple schema sources into one desired state. Each nested `schema "<name>"` block is applied to the named Postgres schema in declaration order, so bootstrap SQL (extensions, custom types) goes first and SQLModel DDL goes last.

### `env "<name>"`

Self-contained environment. Attributes used in Dirt:

| Attribute | Purpose |
|---|---|
| `src` | Desired state. Point at `data.composite_schema.app.url` so Atlas reads SQLModel + bootstrap in one pass. |
| `url` | Target database being managed (`apply`, `inspect`, `status`). Pull from env var via `getenv(...)`. |
| `dev` | Scratch DB used by `diff` and `lint` to replay migrations. `docker://postgres/16/...` locally, a CI service container in GH Actions. |
| `migration.dir` | `file://migrations`. |
| `format.migrate.diff` | Output template. `{{ sql . "  " }}` = SQL indented with two spaces. |
| `diff.concurrent_index` | Auto-rewrite index DDL to `CONCURRENTLY` — prevents PG101 lint hits. See [postgres-specifics.md](postgres-specifics.md). |
| `lint.latest` / `lint.git.base` | How `atlas migrate lint` picks which files to analyze. |

### Variables and functions

Atlas supports Terraform-style variables, locals, and a built-in helper set:

```hcl
variable "pg_version" {
  type    = string
  default = "16"
}

locals {
  dev_url = "docker://postgres/${var.pg_version}/dev?search_path=public"
}

env "local" {
  dev = local.dev_url
  url = getenv("DIRT_DATABASE_URL")
  # ...
}
```

Pass `--var pg_version=17` on the command line to override. `getenv("FOO")` reads process env; if `FOO` is unset it returns an empty string (pair with `coalesce()` for defaults).

### `for_each` (multi-tenant / per-branch envs)

Not used in Dirt, but good to recognize: `env` blocks can iterate over a set/list to produce one env per tenant. See https://atlasgo.io/atlas-schema/projects for the syntax if the repo ever grows multiple DBs.

## What does NOT belong in `atlas.hcl`

- Secrets (DB passwords, cloud tokens). Use `getenv(...)` and load from the environment / systemd unit file.
- Application config. Atlas is a database tool; business config belongs in `apps/shared/src/dirt_shared/config.py`.
- Schema facts. The schema is derived — never put raw HCL schema blocks here. The one exception: extension installs in `atlas/extensions.sql`, which is referenced, not inlined.

## Common mistakes

- **Omitting `dev` on the `env` block** and passing `--dev-url` on the CLI every time. Works, but duplicates state. Put it in the env.
- **Quoting attribute values that should be references.** `src = "data.composite_schema.app.url"` is a string literal, not a reference. Drop the quotes: `src = data.composite_schema.app.url`.
- **Hardcoding `url = "postgres://dirt:dirt@..."`** with a real password in a committed file. Always use `getenv()`.
- **Putting `src = "file://schema.hcl"`** — that bypasses the SQLAlchemy loader entirely. In Dirt, `src` always resolves through `data.composite_schema.app.url`.
- **Using `env` with no label** — `env { ... }` is invalid. Always `env "<name>" { ... }`.
