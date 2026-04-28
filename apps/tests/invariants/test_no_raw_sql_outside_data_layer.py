"""
INVARIANT TEST — HUMAN-OWNED

This test is protected by Codex hooks and MUST NOT be modified by
the agent. If this test fails, the agent must move the query into a
service (or a model, or a migration) — never modify this file's ALLOWED
prefixes to paper over a new smell.

Purpose: forbid raw SQL strings outside the data layer. The schema and
every runtime query must live in one of three places:

  * ``apps/shared/src/dirt_shared/models/``   — SQLModel class bodies.
  * ``apps/shared/src/dirt_shared/services/`` — service methods using
    SQLModel's ``select(...)`` or (rarely, with WHY comment) raw
    ``text("SELECT ...")`` for Postgres-specific aggregation.
  * ``apps/shared/src/dirt_shared/db.py``     — engine factory + the
    session-level health-check (``SELECT 1``).
  * ``migrations/``                           — Atlas-generated SQL.

The schema is owned by Atlas (see ADR-006 + ``test_schema_managed_by_atlas.py``
for the DDL half). This invariant covers the DML half: no agent slipping
a one-off ``"SELECT * FROM plant"`` into a route handler to "just get
the data quickly." Ad-hoc SQL in API / UI code bypasses the service
layer's session / transaction / auth guarantees and is the fastest
way to corrupt ingest invariants.

Detection (AST): walk ``apps/*/src/dirt_*/**/*.py``; for every string
literal (``Constant`` with str value OR a ``JoinedStr`` / f-string
whose static prefix is a SQL keyword), flag if the upper-cased stripped
value starts with any of ``SQL_KEYWORDS``. Covers multi-line strings
(``sql = '''SELECT ...'''``), implicit string concatenation (flagged at
the first string fragment), and f-strings that start with a SQL
keyword. Files under ``ALLOWED_PREFIXES`` are skipped wholesale.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ._helpers import (
    APPS,
    APPS_ROOT,
    format_invariant_failure,
    iter_py,
    pkg_src_dir,
)

# Relative-to-apps/ path prefixes that legitimately hold SQL literals.
# Matches a file iff ``rel.startswith(prefix)``.
ALLOWED_PREFIXES: tuple[str, ...] = (
    "shared/src/dirt_shared/models/",
    "shared/src/dirt_shared/services/",
    "shared/src/dirt_shared/db.py",
    # Test infrastructure — pg_database catalog query for stale-clone
    # cleanup, plus CREATE/DROP DATABASE template wiring. None of this
    # SQL touches application tables; it's all database-level admin
    # scoped to the per-worktree dirt_test_<hash>_* prefix.
    "shared/src/dirt_shared/testing.py",
)

# SQL statements whose presence as a string literal anywhere outside
# ALLOWED_PREFIXES is a smell. Upper-cased, trailing space included so
# "SELECTED" / "CREATEDATE" don't false-positive. "CREATE/ALTER/DROP
# TABLE" overlaps test_schema_managed_by_atlas.py; intentional — this
# invariant is about any SQL literal at all, not specifically DDL vs
# DML.
SQL_KEYWORDS: tuple[str, ...] = (
    "SELECT ",
    "INSERT INTO ",
    "UPDATE ",
    "DELETE FROM ",
    "CREATE TABLE",
    "ALTER TABLE",
    "DROP TABLE",
    "WITH ",  # CTE prefix
)


def _looks_like_sql(value: str) -> bool:
    """True if the stripped upper-cased value starts with a SQL keyword."""
    stripped = value.strip().upper()
    return any(stripped.startswith(kw) for kw in SQL_KEYWORDS)


def _literal_prefix(node: ast.AST) -> str | None:
    """Static prefix of a string node, or None if the node isn't a string.

    Handles:
      * ``ast.Constant`` with ``str`` value — the prefix is the whole value.
      * ``ast.JoinedStr`` (f-string) — the prefix is the first FormattedValue-
        or-Constant chain's concatenated ``Constant`` text, up to the first
        ``FormattedValue`` (where the interpolation happens).
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        pieces: list[str] = []
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                pieces.append(part.value)
            else:
                break
        return "".join(pieces) if pieces else None
    return None


def _violations_in_file(py: Path) -> list[tuple[int, str]]:
    tree = ast.parse(py.read_text())
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        prefix = _literal_prefix(node)
        if prefix is None:
            continue
        if _looks_like_sql(prefix):
            # Keep the first 60 chars for the violation message.
            snippet = prefix.strip().split("\n", 1)[0][:60]
            out.append((node.lineno, snippet))
    return out


@pytest.mark.parametrize("app", APPS)
def test_no_raw_sql_outside_data_layer(app: str) -> None:
    """Raw SQL strings must not appear outside models/services/db/migrations."""
    pkg_dir = pkg_src_dir(app)
    assert pkg_dir.exists(), f"package dir missing: {pkg_dir}"

    violations: list[str] = []
    for py in iter_py(pkg_dir):
        rel = str(py.relative_to(APPS_ROOT))
        if any(rel.startswith(p) for p in ALLOWED_PREFIXES):
            continue
        for lineno, snippet in _violations_in_file(py):
            violations.append(f'apps/{rel}:{lineno}  "{snippet}..."')

    if violations:
        pytest.fail(
            format_invariant_failure(
                headline=(
                    f"{app}: {len(violations)} raw-SQL literal(s) outside the "
                    "data layer"
                ),
                smell_name="Leaky Data Access / Bypassed Service Layer",
                citation=(
                    "Fowler, _Patterns of Enterprise Application Architecture_\n"
                    "   — Data Mapper + Repository; ADR-006 (Atlas owns the\n"
                    "   schema); apps/tests/invariants/test_schema_managed_by_atlas.py"
                ),
                body=(
                    "WHY this rule exists:\n"
                    "  dirt_shared.services is the single place that opens DB\n"
                    "  sessions, wraps queries in transactions, and runs auth /\n"
                    "  ingest validation. A raw `SELECT *` or `INSERT INTO` in\n"
                    "  a route handler bypasses all three — every new such call\n"
                    "  site is a candidate for a silent data-corruption bug.\n"
                    "  Schema DDL specifically must go through Atlas\n"
                    "  (see test_schema_managed_by_atlas.py).\n\n"
                    "FIX:\n"
                    "  - Runtime query: add a method to the relevant service in\n"
                    "    apps/shared/src/dirt_shared/services/ and call it from\n"
                    "    the route handler / CLI / tool. Use SQLModel's typed\n"
                    "    `select(Model).where(...)` — raw `text(...)` is\n"
                    "    reserved for Postgres aggregation primitives that\n"
                    "    SQLModel doesn't model (window funcs, date_trunc,\n"
                    "    etc.), and lives only inside a service method.\n"
                    "  - Schema change: edit a SQLModel class in\n"
                    "    apps/shared/src/dirt_shared/models/ then run\n"
                    "    `atlas migrate diff <name> --env local`. NEVER write\n"
                    "    `CREATE TABLE` / `ALTER TABLE` in app code.\n\n"
                    "IF a SQL literal genuinely belongs elsewhere (which is\n"
                    "almost never the case), add the containing file's\n"
                    "prefix to `ALLOWED_PREFIXES` in this invariant and the\n"
                    "next agent will respect it."
                ),
                violations=violations,
            )
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
