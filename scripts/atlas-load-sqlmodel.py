#!/usr/bin/env python3
"""Emit HCL describing the SQLModel metadata for Atlas.

Invoked by ``atlas.hcl``'s ``data "external_schema" "sqlmodel"`` block —
Atlas runs this, captures stdout, parses it as HCL, and uses it as the
"desired state" for migration diffs.

Importing ``dirt_shared.models`` populates ``SQLModel.metadata`` as a
side effect; we hand the resulting sorted tables to
``atlas_provider_sqlalchemy.ddl.print_ddl`` which writes the DDL to
stdout in a form Atlas understands.

Run manually to debug:
    uv run --package dirt-shared python scripts/atlas-load-sqlmodel.py postgresql
"""
from __future__ import annotations

import sys

from atlas_provider_sqlalchemy.ddl import print_ddl
from sqlmodel import SQLModel

# Side-effect import: populates SQLModel.metadata.
import dirt_shared.models  # noqa: F401


def main(argv: list[str]) -> int:
    # Atlas passes the dialect as the first arg. Default to postgresql for
    # direct invocation (debugging / CI).
    dialect = argv[1] if len(argv) > 1 else "postgresql"
    tables = list(SQLModel.metadata.sorted_tables)
    print_ddl(dialect, tables)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
