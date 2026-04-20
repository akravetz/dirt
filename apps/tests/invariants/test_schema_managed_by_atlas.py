"""
INVARIANT TEST — HUMAN-OWNED

This test is protected by Claude Code hooks and MUST NOT be modified by the
agent. If this test fails, the agent must fix its code to satisfy the test,
never modify this file.

Purpose: Enforce that Atlas owns all DDL in this project, per ADR-006.

Rules:
  - ``apps/shared/src/dirt_shared/db.py`` must NOT contain the SQLAlchemy
    auto-DDL calls that bypassed Atlas (``metadata.create_all``,
    ``SQLModel.metadata.create_all``).
  - That same file must NOT contain the old hand-rolled idempotent ALTER
    migration tuple (``_COLUMN_MIGRATIONS``).
  - ``migrations/`` must exist at the repo root with at least one ``*.sql``
    file + ``atlas.sum``.
  - ``atlas.hcl`` must exist at the repo root.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DB_PY = _REPO_ROOT / "apps" / "shared" / "src" / "dirt_shared" / "db.py"
_MIGRATIONS = _REPO_ROOT / "migrations"
_ATLAS_HCL = _REPO_ROOT / "atlas.hcl"


def test_db_py_has_no_create_all() -> None:
    """``db.py`` must not auto-create tables — Atlas owns that."""
    assert _DB_PY.exists(), f"{_DB_PY} must exist"
    source = _DB_PY.read_text()
    # Look for .create_all( as a substring — catches both
    # `SQLModel.metadata.create_all` and `metadata.create_all` variants.
    forbidden = re.search(r"\.create_all\s*\(", source)
    assert forbidden is None, (
        "db.py must not contain .create_all(…); Atlas owns DDL "
        "(see ADR-006). Offending match: "
        f"{forbidden.group(0) if forbidden else None!r}"
    )


def test_db_py_has_no_column_migrations_tuple() -> None:
    """The hand-rolled ``_COLUMN_MIGRATIONS`` tuple is gone — Atlas owns migrations."""
    source = _DB_PY.read_text()
    assert "_COLUMN_MIGRATIONS" not in source, (
        "db.py must not define _COLUMN_MIGRATIONS; new columns go through "
        "`atlas migrate diff` (see ADR-006)."
    )


def test_migrations_directory_present() -> None:
    """Atlas's migrations/ directory must exist with at least one *.sql file + atlas.sum."""
    assert _MIGRATIONS.is_dir(), f"{_MIGRATIONS} must exist as a directory"
    sql_files = sorted(_MIGRATIONS.glob("*.sql"))
    assert sql_files, (
        f"{_MIGRATIONS} must contain at least one *.sql file "
        "(run `atlas migrate diff <name> --env local` to generate one)"
    )
    atlas_sum = _MIGRATIONS / "atlas.sum"
    assert atlas_sum.exists(), (
        f"{atlas_sum} must exist; run `atlas migrate hash --env local` to (re)generate."
    )


def test_atlas_hcl_present() -> None:
    """atlas.hcl must exist at the repo root."""
    assert _ATLAS_HCL.exists(), f"{_ATLAS_HCL} must exist"
    source = _ATLAS_HCL.read_text()
    # Sanity check: the external schema data block is the whole point.
    assert 'data "external_schema"' in source, (
        "atlas.hcl must declare `data \"external_schema\"` pointing at "
        "scripts/atlas-load-sqlmodel.py so SQLModel stays the source of truth."
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
