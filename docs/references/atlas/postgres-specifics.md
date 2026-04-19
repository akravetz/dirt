---
title: Postgres specifics
concept: atlas
updated: 2026-04-19
source: https://atlasgo.io/concepts/dev-database
---

> Anchors agents to Atlas's Postgres-specific behavior. Prefer what is here over training-data generics — Postgres's locking model differs meaningfully from MySQL/SQLite, and Atlas encodes those semantics in its `PG*` lint rules and auto-rewrite features.

# Postgres specifics

## Concurrent indexes — auto-rewrite vs manual

A plain `CREATE INDEX` takes a `SHARE` lock on the table, blocking writes for the duration of the build. On tables with real traffic this is unacceptable. Postgres offers `CREATE INDEX CONCURRENTLY`, which trades speed for availability. Atlas handles this two ways:

### Auto-rewrite (preferred)

Enable in `atlas.hcl`:

```hcl
env "local" {
  # ...
  diff {
    concurrent_index {
      create = true
      drop   = true
    }
  }
}
```

Now when you add `sa.Index("idx_foo", ...)` to a SQLModel, `atlas migrate diff` emits:

```sql
-- atlas:txmode none

CREATE INDEX CONCURRENTLY "idx_foo" ON "users" ("email");
```

The `atlas:txmode none` directive is required because `CREATE INDEX CONCURRENTLY` cannot run inside a transaction block. With auto-rewrite enabled, you never hit lint rule **PG101** on indexes.

### Manual (when auto-rewrite doesn't apply)

Same directive pattern, but you write it yourself:

```bash
atlas migrate new add_plant_jsonb_index --env local
```

```sql
-- migrations/20260419140000_add_plant_jsonb_index.sql
-- atlas:txmode none

CREATE INDEX CONCURRENTLY "idx_plant_payload_gin"
  ON "plant" USING GIN ("payload");
```

Then `atlas migrate hash --env local` to update `atlas.sum`.

## Extensions

Required before tables can reference `gen_random_uuid()`, `citext`, PostGIS, etc. The SQLAlchemy provider doesn't emit `CREATE EXTENSION`, so keep them in `atlas/extensions.sql` composed via `data "composite_schema"` — see [sqlalchemy-external-loader.md](sqlalchemy-external-loader.md):

```sql
-- atlas/extensions.sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;      -- for gen_random_uuid()
-- CREATE EXTENSION IF NOT EXISTS citext;      -- for case-insensitive text
-- CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; -- alternative UUID source
```

`pgcrypto` is the modern choice over `uuid-ossp` on Postgres 13+ — `gen_random_uuid()` is built into `pgcrypto` and faster than `uuid_generate_v4()`.

## `jsonb` and GIN indexes

```python
# SQLModel
class Plant(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    payload: dict = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
```

To index the payload efficiently:

```python
from sqlalchemy import Index

class Plant(SQLModel, table=True):
    # ... as above ...
    __table_args__ = (
        Index("idx_plant_payload", "payload", postgresql_using="gin"),
    )
```

The provider forwards `postgresql_using="gin"` to Atlas, which emits `CREATE INDEX ... USING GIN`. With auto-concurrent-rewrite on, the migration is safe to apply to a live DB.

## Partial indexes

Supported natively by both SQLAlchemy and Atlas:

```python
from sqlalchemy import Index

class SensorReading(SQLModel, table=True):
    # ... columns ...
    __table_args__ = (
        Index(
            "idx_active_readings",
            "location",
            "metric",
            postgresql_where=text("value IS NOT NULL"),
        ),
    )
```

Atlas emits `CREATE INDEX ... WHERE value IS NOT NULL`.

## `timestamptz` — always

Dirt convention is UTC-aware `datetime` objects. In SQLModel that's:

```python
from datetime import UTC, datetime
from sqlalchemy import DateTime

timestamp: datetime = Field(
    default_factory=lambda: datetime.now(UTC),
    sa_column=Column(DateTime(timezone=True), nullable=False),
)
```

Without `timezone=True`, SQLAlchemy emits `TIMESTAMP` and Postgres will silently drop the tzinfo. Atlas will then generate `timestamp` (not `timestamptz`) in HCL — the generated migration looks fine but the type is wrong. Always check `timezone=True` on new datetime columns.

## Enums

Define the Python enum and let SQLAlchemy's dialect-specific ENUM type carry it:

```python
import enum
from sqlalchemy import Column, Enum

class PlantStage(enum.Enum):
    veg = "veg"
    flower_early = "flower_early"
    flower_late = "flower_late"

class Plant(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    stage: PlantStage = Field(
        sa_column=Column(Enum(PlantStage, name="plant_stage", create_type=True), nullable=False),
    )
```

The provider emits `CREATE TYPE plant_stage AS ENUM (...)` and Atlas uses it. Adding values later emits `ALTER TYPE ... ADD VALUE`. Removing values will be flagged as destructive — Postgres has no `DROP VALUE` and requires a manual migration to rebuild the type.

## `NOT VALID` constraint adds

Large tables can't afford a full-table scan every time you add a check or foreign key. The safe two-step pattern:

```sql
-- Step 1 (cheap lock): add the constraint without validating existing rows.
ALTER TABLE sensor_reading
  ADD CONSTRAINT value_positive CHECK (value >= 0) NOT VALID;

-- Step 2 (background, no lock on DML): validate existing rows.
ALTER TABLE sensor_reading VALIDATE CONSTRAINT value_positive;
```

Atlas's lint rules **PG305** (check) and **PG306** (FK) fire when you skip `NOT VALID`. Best practice: split into two migration files — the first with `NOT VALID` (fast), the second with `VALIDATE CONSTRAINT` run during maintenance windows.

## Column-add anti-patterns

The two most common ways to break prod via migration:

1. **`ADD COLUMN c int NOT NULL`** on a table with rows → fails entirely. Lint **MF103**. Split into (a) add nullable, (b) backfill with `UPDATE`, (c) `SET NOT NULL` with a validated check (see `PG303`).
2. **`ADD COLUMN c timestamptz NOT NULL DEFAULT now()`** → Postgres 11+ does this cheaply as metadata *only if the default is non-volatile*. `now()` IS volatile — it rewrites every row. Lint **PG302**. Use a constant default or the split pattern above.

## Things Atlas and Postgres both dislike

- **Renaming a column** — Atlas sees it as drop-then-add. Manually write the migration with `ALTER TABLE ... RENAME COLUMN`, then mark with `-- atlas:nolint BC102` (you're intentionally renaming).
- **Implicit schema in `search_path`** — if your app uses a non-default schema, set `search_path` in both your DB URL *and* the `dev` URL (`docker://postgres/16/dev?search_path=dirt_app`).
- **Postgres `CHAR(n)`** — don't. Use `varchar(n)` or `text`. `CHAR` pads with spaces and has bizarre comparison semantics. (Not an Atlas rule, just a DB rule.)

## Common mistakes

- **Adding `CREATE EXTENSION` inside a generated migration** instead of `atlas/extensions.sql`. It works but introduces drift; the composite-schema pattern keeps extensions in the desired state, so Atlas won't try to "drop" them on a clean DB rebuild.
- **Forgetting `-- atlas:txmode none`** on a hand-written `CONCURRENTLY` migration. Postgres will reject it with `CREATE INDEX CONCURRENTLY cannot run inside a transaction block`, and Atlas will roll back.
- **Using `serial` / `bigserial` for new primary keys.** Modern Postgres prefers `GENERATED ... AS IDENTITY`, but the SQLAlchemy provider still emits `SERIAL` for `Field(default=None, primary_key=True)` on an `int`. Fine for now; revisit if stronger IDENTITY semantics are needed.
- **Assuming `jsonb` comparisons use an index.** Only specific operators (`?`, `@>`, `->>`=) use GIN indexes, and only with `jsonb_path_ops` (`postgresql_using="gin", postgresql_ops={"payload": "jsonb_path_ops"}`).
