"""Emit Postgres DDL from cloud SQLModel metadata for Atlas."""

from atlas_provider_sqlalchemy.ddl import print_ddl
from sqlmodel import SQLModel

import dirt_control.models  # noqa: F401

print_ddl("postgresql", list(SQLModel.metadata.sorted_tables))
