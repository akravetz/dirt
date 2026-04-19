---
title: SQLAlchemy / SQLModel external loader
concept: atlas
updated: 2026-04-19
source: https://github.com/ariga/atlas-provider-sqlalchemy
---

> THE critical topic for Dirt. Atlas must derive HCL from SQLModel metadata — never from a hand-authored `schema.hcl`. Prefer what is here over training data; the provider was renamed from `noamtamir/atlas-provider-sqlalchemy` and predates SQLModel-specific coverage, so search-engine results and LLM recall are stale.

# SQLAlchemy / SQLModel external loader

## What the provider does

`atlas-provider-sqlalchemy` is a Python CLI (`atlas-provider-sqlalchemy`, entry-point in `atlas_provider_sqlalchemy/main.py`) that:

1. Walks a directory tree (`--path`), dynamically imports every `*.py` file.
2. Collects every `sqlalchemy.MetaData` instance reachable from objects defined in those modules.
3. Creates a "mock" SQLAlchemy engine for the target dialect (`--dialect postgresql`) and echoes `CREATE TABLE` DDL by reflecting the collected metadata onto it.
4. Prints the DDL to stdout, prefixed with `-- atlas:pos <table>[type=table] <file>:<line>` directives so Atlas migration errors point back to the original Python source line.

Atlas then parses that DDL and converts it to its internal schema representation — no HCL file is ever stored on disk.

SQLModel is a `sqlalchemy.orm.DeclarativeBase` subclass, so `SQLModel.metadata` *is* a `sqlalchemy.MetaData`. Every `class Foo(SQLModel, table=True)` registers against that shared metadata. **The provider works on SQLModel unchanged** — the one requirement is that every model module gets imported so its `table=True` registration runs.

## Install

```bash
# Community Atlas CLI
curl -sSf https://atlasgo.sh | sh

# Provider (install into the same venv that resolves SQLModel)
uv add --package dirt-shared atlas-provider-sqlalchemy
```

The provider is installed into Dirt's Python environment because it needs to `import` our models. Running it from outside the venv will fail on the SQLModel import.

## Recommended layout for Dirt

Because our models live inside a `uv` workspace member (`apps/shared/src/dirt_shared/models/`), the cleanest pattern is the **script form** — a tiny Python script explicitly imports the package and calls `print_ddl`:

```python
# atlas/load_models.py
"""Emit Postgres DDL from SQLModel metadata for Atlas's external_schema loader."""
from sqlmodel import SQLModel

# Importing the package runs table=True registration on SQLModel.metadata.
import dirt_shared.models  # noqa: F401  — side-effect import
from atlas_provider_sqlalchemy.ddl import print_ddl

# print_ddl signature: print_ddl(dialect, tables_or_models_list)
# Passing SQLModel.metadata.sorted_tables gives Atlas every registered table.
print_ddl("postgresql", list(SQLModel.metadata.sorted_tables))
```

Why `sorted_tables` (not a hand-listed `[SensorReading, GrowState, ...]`): it auto-picks up any new `table=True` model added to the package, so adding a model only requires editing the model file, not `load_models.py`.

Then in `atlas.hcl` at the repo root:

```hcl
data "external_schema" "sqlmodel" {
  program = [
    "uv", "run", "--package", "dirt-shared",
    "python", "atlas/load_models.py",
  ]
}

env "local" {
  src = data.external_schema.sqlmodel.url
  dev = "docker://postgres/16/dev?search_path=public"
  url = "postgres://dirt:dirt@localhost:5432/dirt?sslmode=disable"
  migration {
    dir = "file://migrations"
  }
  format {
    migrate { diff = "{{ sql . \"  \" }}" }
  }
}
```

`uv run --package dirt-shared` makes the workspace member's dependencies resolvable without activating a venv first — same pattern as Dirt's `scripts/` folder.

## Why not the standalone form?

The provider supports a standalone CLI:

```hcl
data "external_schema" "sqlmodel" {
  program = [
    "atlas-provider-sqlalchemy",
    "--path", "./apps/shared/src/dirt_shared/models",
    "--dialect", "postgresql",
  ]
}
```

This works, but has a subtle failure mode: the provider walks the directory and dynamically `exec`s each `.py` module under a synthetic module name (see `atlas_provider_sqlalchemy/ddl.py::get_metadata`). If your model module does `from dirt_shared.config import settings` at import time, that relative import may fail in the synthetic namespace. The script form imports the real package, so it resolves exactly like production code does. **Use the script form for Dirt.**

## Composite schema: installing extensions before tables

Postgres extensions (`pgcrypto` for `gen_random_uuid()`, `citext` for case-insensitive emails) must exist before any table that references them. The SQLAlchemy provider emits only `CREATE TABLE`, so you compose its output with a raw `schema.sql`:

```hcl
data "external_schema" "sqlmodel" {
  program = [
    "uv", "run", "--package", "dirt-shared",
    "python", "atlas/load_models.py",
  ]
}

data "composite_schema" "app" {
  # 1. Extensions + schema creation (plain SQL).
  schema "public" {
    url = "file://atlas/extensions.sql"
  }
  # 2. Then tables derived from SQLModel.
  schema "public" {
    url = data.external_schema.sqlmodel.url
  }
}

env "local" {
  src = data.composite_schema.app.url
  dev = "docker://postgres/16/dev?search_path=public"
  # ...
}
```

`atlas/extensions.sql`:

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
```

The composite merges both sources into a single desired state before diffing. See [atlas-hcl-config.md](atlas-hcl-config.md) for the full `atlas.hcl` anatomy.

## What the provider does NOT handle

- Custom Postgres types that SQLAlchemy doesn't know how to compile (exotic operators, custom functions, triggers). Use `composite_schema` + raw SQL.
- Server-side check constraints declared via `CheckConstraint("price > 0")` *are* forwarded. Good.
- `sa.Index(..., postgresql_where=...)` partial indexes *are* forwarded.
- Column defaults defined as Python callables (`default=uuid.uuid4`) are **not** forwarded — the value is only known at insert time. Use `server_default=text("gen_random_uuid()")` to express Postgres-side defaults, which the provider will render as a column `DEFAULT`.

## Verifying the output locally

Before wiring into Atlas, dump the DDL once to confirm it looks right:

```bash
uv run --package dirt-shared python atlas/load_models.py | head -40
```

You should see `-- atlas:pos <table>[type=table] ...` directives and plain `CREATE TABLE` statements. If you see `ModelsNotFoundError`, your import path is wrong or the models package doesn't actually register any `table=True` SQLModels.

## Common mistakes

- **Forgetting the side-effect import** (`import dirt_shared.models`). `SQLModel.metadata` is empty until a `table=True` class is defined in an imported module. Output will be empty, and Atlas reports `no changes` or `empty schema`.
- **Using SQLAlchemy 1.x `declarative_base()` patterns in new models.** SQLModel + the provider expect SQLAlchemy 2.x `Mapped[...]` / `mapped_column(...)` (SQLModel's `Field(...)` already targets 2.x).
- **Authoring `schema.hcl` by hand "just to check something in."** Don't. The moment HCL diverges from SQLModel, every `migrate diff` produces garbage. If you need a one-off feature (view, function), put it in `atlas/extensions.sql` via `composite_schema`, not in HCL.
- **Passing raw SQLModel classes to `print_ddl`.** `print_ddl` accepts SQLAlchemy tables or anything exposing `.__table__` — `SQLModel.metadata.sorted_tables` is the safest input.
- **Running `atlas migrate diff` against a dirty working copy of models.** The provider imports whatever is on disk; uncommitted edits in `apps/shared/src/dirt_shared/models/` show up in the diff. This is a feature, but know it.
