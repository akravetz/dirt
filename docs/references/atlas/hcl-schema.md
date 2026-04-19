---
title: HCL schema reference
concept: atlas
updated: 2026-04-19
source: https://atlasgo.io/atlas-schema/hcl
---

> Anchors agents to current Atlas v1.2 HCL syntax. Dirt does not author HCL by hand — the SQLAlchemy loader emits it — but you will read it when debugging what Atlas inferred from SQLModel metadata (`atlas schema inspect`, `atlas migrate diff --dry-run`, the raw HCL emitted by `atlas-provider-sqlalchemy`). Memorize the shape so you can read the output.

# HCL schema reference

Atlas's HCL schema language looks like Terraform HCL but has its own block types. Every block has a type (`table`, `column`, `index`, …), a label, and a body of attributes. References use dot-notation: `schema.public`, `table.users.column.id`, `enum.status`.

## Top-level blocks

```hcl
schema "public" {
  comment = "main app schema"
}

table "users" {
  schema  = schema.public
  comment = "application users"
  # columns, indexes, constraints...
}

enum "account_status" {
  schema = schema.public
  values = ["active", "disabled", "pending"]
}
```

Top-level blocks: `schema`, `table`, `enum`, `sequence`, `function`, `trigger`, `view`, `materialized`, `extension`, `role` (the last few are Postgres-specific).

## `table` block

```hcl
table "sensor_reading" {
  schema = schema.public

  column "id" {
    type = serial
  }
  column "timestamp" {
    type    = timestamptz
    null    = false
    default = sql("now()")
  }
  column "location" {
    type = varchar(64)
    null = false
  }
  column "metric" {
    type = varchar(32)
    null = false
  }
  column "value" {
    type = double_precision
    null = false
  }

  primary_key {
    columns = [column.id]
  }

  index "idx_sensor_reading_timestamp" {
    columns = [column.timestamp]
  }

  index "idx_sensor_reading_location_metric" {
    columns = [column.location, column.metric]
  }
}
```

## `column` block

```hcl
column "name" {
  type = text        # required
  null = false       # default true — match SQLModel field nullability
  default = "anonymous"
  comment = "display name"
}

# SQL function default (UUID, now(), etc.)
column "id" {
  type    = uuid
  null    = false
  default = sql("gen_random_uuid()")
}

# Generated column (PostgreSQL STORED)
column "full_name" {
  type = text
  as {
    expr = "first_name || ' ' || last_name"
    type = STORED
  }
}
```

## Postgres column types

From https://atlasgo.io/atlas-schema/hcl-types — use these exactly:

| HCL | SQL |
|---|---|
| `integer` / `int` | `INTEGER` |
| `bigint` | `BIGINT` |
| `smallint` | `SMALLINT` |
| `serial` / `bigserial` / `smallserial` | `SERIAL` families |
| `boolean` | `BOOLEAN` |
| `varchar` / `varchar(255)` | `VARCHAR` |
| `char(n)` | `CHAR(n)` |
| `text` | `TEXT` |
| `uuid` | `UUID` (pair with `default = sql("gen_random_uuid()")`) |
| `json` / `jsonb` | `JSON` / `JSONB` |
| `date` | `DATE` |
| `time` / `timetz` | `TIME` / `TIME WITH TIME ZONE` |
| `timestamp` / `timestamptz` | `TIMESTAMP` / `TIMESTAMP WITH TIME ZONE` |
| `interval` | `INTERVAL` |
| `numeric(p,s)` | `NUMERIC(p,s)` |
| `real` / `double_precision` | `REAL` / `DOUBLE PRECISION` |
| `bytea` | `BYTEA` |
| `enum.<name>` | references an `enum "<name>"` block |
| `sql("int[]")` | escape hatch for arrays and exotic types |

Prefer `timestamptz` over `timestamp` — Dirt timestamps are always UTC-aware `datetime` values.

## `primary_key` / `foreign_key` / `index` / `check`

```hcl
primary_key {
  columns = [column.id]
}

foreign_key "sensor_reading_node_fk" {
  columns     = [column.node_id]
  ref_columns = [table.sensor_node.column.id]
  on_delete   = CASCADE   # NO_ACTION | CASCADE | SET_NULL | SET_DEFAULT | RESTRICT
  on_update   = NO_ACTION
}

# Simple index
index "idx_metric" {
  columns = [column.metric]
}

# Composite index with ordering
index "idx_composite" {
  on { column = column.timestamp; desc = true }
  on { column = column.location }
}

# Partial index (Postgres)
index "idx_active_readings" {
  columns = [column.location]
  where   = "value IS NOT NULL"
}

# GIN on a jsonb column
index "idx_jsonb" {
  type    = GIN
  columns = [column.payload]
}

# Check constraint
check "sensor_reading_value_positive" {
  expr = "value >= 0"
}
```

Index types: `BTREE` (default), `HASH`, `GIN`, `GIST`, `BRIN`. Postgres supports `nulls_distinct` on v15+: `index "u" { unique = true; columns = [column.c]; nulls_distinct = false }`.

## `enum` block

```hcl
enum "plant_stage" {
  schema = schema.public
  values = ["veg", "flower_early", "flower_late"]
}

table "plant" {
  schema = schema.public
  column "stage" {
    type = enum.plant_stage
    null = false
  }
}
```

Adding a value later emits `ALTER TYPE ... ADD VALUE`. Removing a value requires a manual migration — Postgres has no `DROP VALUE` — and will be flagged destructive.

## Referencing across tables

Dot-path resolution: `table.<name>.column.<col>`, `table.<schema>.<name>.column.<col>` when disambiguating across schemas, `enum.<name>`, `schema.<name>`.

## Postgres-only blocks

Row-level security:

```hcl
table "secrets" {
  schema = schema.public
  # ...
  row_security {
    enabled  = true
    enforced = true
  }
}
```

Partitions:

```hcl
table "logs" {
  schema = schema.public
  column "ts" { type = timestamptz; null = false }
  partition {
    type    = RANGE
    columns = [column.ts]
  }
}
```

Sequences, functions, triggers, extensions (`extension "pgcrypto" {}`) all live at the top level — see the source docs when you actually need them.

## Common mistakes

- **`type = "text"`** with quotes — HCL type values are identifiers, not strings. Write `type = text`.
- **`type = timestamp with time zone`** — use `timestamptz` (Atlas's canonical name). Same DB type, different HCL spelling.
- **`default = "now()"`** — treated as a string literal `"now()"`. Use `default = sql("now()")` for expressions.
- **Referencing a missing column** — Atlas fails with an unhelpful HCL parser error at `atlas migrate diff`. Always regenerate HCL from SQLModel rather than hand-patching.
- **`on_delete = "CASCADE"`** with quotes — the action is an identifier: `on_delete = CASCADE`.
