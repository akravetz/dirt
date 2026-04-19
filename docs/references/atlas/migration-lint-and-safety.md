---
title: Migration lint and CI safety
concept: atlas
updated: 2026-04-19
source: https://atlasgo.io/lint/analyzers
---

> Anchors agents to current Atlas v1.2 lint rules and CI integration. Prefer what is here over training-data recollection — several rule codes (PG301–PG311, TX101/TX201) are recent additions and pre-v1 snippets of `atlas migrate lint` lack the `--dev-url` requirement entirely.

# Migration lint and CI safety

`atlas migrate lint` statically analyzes generated migrations for destructive / locking / data-dependent patterns. It requires a `--dev-url` because it actually replays the changes onto a real Postgres instance to determine semantic impact.

## Running lint

```bash
# Local pre-commit: just check the newest file.
atlas migrate lint --env local --latest 1

# CI: check everything added since the PR base branch.
atlas migrate lint --env ci --git-base origin/main
```

Exit code is non-zero when any diagnostic is reported, so shell-level gating (`atlas migrate lint ... && git push`) works without parsing output.

## Rule codes

From https://atlasgo.io/lint/analyzers — the full Postgres-relevant catalog. These are the codes Atlas prints in its diagnostic output; you'll use them in `-- atlas:nolint <code>` directives.

### Destructive changes (DS*)

| Code | Trigger | Example |
|---|---|---|
| **DS101** | Schema dropped | `DROP SCHEMA test;` |
| **DS102** | Table dropped | `DROP TABLE users;` |
| **DS103** | Non-virtual column dropped | `ALTER TABLE t DROP COLUMN c;` |

### Data-dependent (MF*)

Changes that may fail at runtime depending on existing data.

| Code | Trigger |
|---|---|
| **MF101** | Unique index added on an existing column (fails on duplicates) |
| **MF102** | Non-unique index modified to unique |
| **MF103** | Adding a `NOT NULL` column without a `DEFAULT` (fails on non-empty tables) |
| **MF104** | Modifying a nullable column to `NOT NULL` |

### Backward incompatible (BC*)

Changes that break running application instances.

| Code | Trigger |
|---|---|
| **BC101** | Table renamed |
| **BC102** | Column renamed |

### Constraint deletion (CD*)

| Code | Trigger |
|---|---|
| **CD101** | Foreign key dropped |
| **CD102** | Check constraint dropped |
| **CD103** | Primary key dropped |

### Postgres-specific (PG*)

This is the most important block for Dirt — every one of these fires when Atlas would otherwise produce SQL that locks tables in production.

| Code | Trigger | Fix |
|---|---|---|
| **PG101** | `CREATE INDEX` without `CONCURRENTLY` — blocks writes | Enable `diff { concurrent_index { create = true } }` in atlas.hcl, or write the migration by hand with `-- atlas:txmode none` + `CONCURRENTLY` |
| **PG102** | `DROP INDEX` without `CONCURRENTLY` — blocks all access | Same fix via `concurrent_index { drop = true }` |
| **PG103** | Concurrent index operation inside a transaction | Add `-- atlas:txmode none` at the top of the file |
| **PG104** | `ADD PRIMARY KEY` without CONCURRENTLY-first pattern | Create `UNIQUE INDEX CONCURRENTLY`, then `ALTER TABLE ... ADD PRIMARY KEY USING INDEX` |
| **PG105** | `ADD UNIQUE` without CONCURRENTLY | Same pattern as PG104 |
| **PG110** | Suboptimal column byte alignment | Reorder columns in the SQLModel definition |
| **PG301** | Type change that rewrites the whole table | Use a new column + backfill + drop old pattern |
| **PG302** | Volatile default on `ADD COLUMN` (`now()`, `random()`) — rewrites all rows | Add column nullable, backfill, then set default |
| **PG303** | `SET NOT NULL` on an existing column — full table scan | Add a CHECK NOT VALID first, VALIDATE, then SET NOT NULL |
| **PG304** | PK on a nullable column | Declare NOT NULL first |
| **PG305** | `ADD CHECK` without `NOT VALID` — full table scan | `ADD CONSTRAINT ... CHECK (...) NOT VALID;` then `VALIDATE CONSTRAINT` |
| **PG306** | `ADD FOREIGN KEY` without `NOT VALID` — blocks writes during validation | Same NOT VALID pattern |
| **PG307** | `SET UNLOGGED` / `SET LOGGED` — full rewrite | Rare; avoid |
| **PG308** | `CREATE TRIGGER` on an existing table — blocks DML during creation | Schedule during low traffic |
| **PG309** | `ADD COLUMN ... GENERATED ... STORED` | Backfill pattern |
| **PG310** | `ADD COLUMN ... GENERATED ... AS IDENTITY` | Use `bigserial` / separate sequence |
| **PG311** | `SET ACCESS METHOD` — full rewrite | Rare |

### Transaction safety (TX*)

| Code | Trigger |
|---|---|
| **TX101** | Mixing transactional and non-transactional statements in one file |
| **TX201** | Explicit `BEGIN;` inside an Atlas-wrapped migration |

### Others

- **SA101** — SQL injection (dynamic string concat in DDL).
- **NM101–NM106** — naming convention violations (Pro; not enforced in Dirt).

## Silencing findings

Use `-- atlas:nolint` directives inside the migration file. Scope:

```sql
-- atlas:nolint                          # silences all findings for the next statement
ALTER TABLE t DROP COLUMN legacy_flag;

-- atlas:nolint destructive              # silences the 'destructive' category
DROP TABLE stale_table;

-- atlas:nolint DS103 MF103              # silence specific rule codes
ALTER TABLE t DROP COLUMN c;

-- File-level: put at top of file as a standalone comment followed by blank line
-- atlas:nolint destructive

DROP TABLE a;
DROP TABLE b;
```

Use the most specific form possible; `-- atlas:nolint` with no argument silences every rule for that statement and is rarely the right answer.

## Special directives Atlas recognizes in migrations

Beyond `nolint`:

```sql
-- atlas:txmode none
CREATE INDEX CONCURRENTLY idx_foo ON bar (baz);

-- atlas:delimiter //
CREATE FUNCTION ... //
```

`atlas:txmode none` is required for `CREATE/DROP INDEX CONCURRENTLY`, `VACUUM`, `REINDEX CONCURRENTLY`. If your `atlas.hcl` has `diff.concurrent_index.create = true`, Atlas emits this directive automatically — see [postgres-specifics.md](postgres-specifics.md).

## GitHub Actions integration

Service container pattern for Dirt CI — a Postgres instance is spun up per workflow run so `atlas migrate lint --dev-url` has something to talk to.

```yaml
# .github/workflows/atlas-lint.yml
name: atlas-lint

on:
  pull_request:
    paths:
      - 'migrations/**'
      - 'apps/shared/src/dirt_shared/models/**'
      - 'atlas.hcl'
      - 'atlas/**'

jobs:
  lint:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: dev
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
        ports: ['5432:5432']
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0          # required for --git-base comparisons

      - uses: astral-sh/setup-uv@v4

      - name: Install SQLAlchemy provider into workspace
        run: uv sync --package dirt-shared

      - uses: ariga/setup-atlas@v0

      - uses: ariga/atlas-action/migrate/lint@v1
        with:
          dir: 'file://migrations'
          dev-url: 'postgres://postgres:postgres@localhost:5432/dev?sslmode=disable'
          config: 'file://atlas.hcl'
          env: 'ci'
```

The `ariga/atlas-action/migrate/lint@v1` action runs `atlas migrate lint` with the resolved inputs and posts findings as a PR check. For apply-on-merge, use `ariga/atlas-action/migrate/apply@v1` in a separate deploy workflow with `url: ${{ secrets.DIRT_PROD_DATABASE_URL }}` — do **not** combine lint and apply in one job.

## Common mistakes

- **Running `lint` without `--dev-url`.** Fails with `required flag --dev-url not set`. Lint needs to replay the migration to infer lock behavior.
- **Silencing lint globally with `env.lint.format` tweaks** to hide warnings. Diagnostics still fire; you just don't see them. Always fix the underlying pattern.
- **Assuming PG101 means "your index is broken."** It means "your `CREATE INDEX` will block writes on this table in prod." The SQL is correct; you just want it `CONCURRENTLY`.
- **Using Alembic-era mental model of "destructive == bad, allow == good."** Some destructive changes are correct (dropping a legacy column after grace period). Lint's job is to surface them; yours is to decide with `-- atlas:nolint DS103` when appropriate.
- **Skipping the `fetch-depth: 0` in CI checkout.** `--git-base origin/main` needs the full history; a shallow clone silently lints nothing.
