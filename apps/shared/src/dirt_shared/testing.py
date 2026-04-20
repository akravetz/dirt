"""Shared pytest fixtures for Dirt apps.

This module is meant to be loaded via pytest_plugins from every conftest
in the repo:

    # conftest.py (root or any app's tests/)
    pytest_plugins = ["dirt_shared.testing"]

Fixtures provided:

- ``isolate_observability_logs`` (autouse) — points observability writes at
  a per-test tmp directory via the ``DIRT_LOGS_DIR`` env var.

- ``pg_engine`` — per-test Postgres database cloned from a session-wide
  ``dirt_test_template`` via ``CREATE DATABASE ... TEMPLATE``. Every
  module-level ``engine`` binding (``dirt_shared.db.engine`` and the
  service modules that imported it) is monkeypatched to point at the
  per-test engine, so ``ingest_reading(...)`` and friends transparently
  write to the isolated DB.

Post-cutover (ADR-006): SQLite is gone; all test DBs are Postgres
clones. The session fixture shells out to ``atlas migrate apply`` to
stamp the template schema; this requires the ``atlas`` binary on PATH.
"""
from __future__ import annotations

import importlib
import subprocess
import uuid
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from dirt_shared.observability import LOGS_DIR_ENV

# ============================================================
# Observability log isolation (autouse)
# ============================================================


@pytest.fixture(autouse=True)
def isolate_observability_logs(tmp_path, monkeypatch):
    """Point ``dirt.observability.logs_dir()`` at a per-test tmp directory.

    The env-var approach (vs monkeypatching the module's ``LOGS_DIR``
    constant) survives the writer thread reading paths lazily — every
    write resolves the env var freshly via :func:`logs_dir`.
    """
    test_logs = tmp_path / "logs"
    monkeypatch.setenv(LOGS_DIR_ENV, str(test_logs))
    yield test_logs


# ============================================================
# Postgres per-test isolation
# ============================================================

# Repo root relative to this file:
#   apps/shared/src/dirt_shared/testing.py
#   parents[0] = dirt_shared/, [1] = src/, [2] = shared/, [3] = apps/, [4] = repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]
_MIGRATIONS = _REPO_ROOT / "migrations"
_TEMPLATE = "dirt_test_template"

# Every module in the codebase that does `from dirt_shared.db import engine`.
# Each gets its module-level `engine` binding monkeypatched to the per-test
# engine so service functions transparently hit the isolated schema.
_ENGINE_HOLDERS: tuple[str, ...] = (
    "dirt_shared.db",
    "dirt_shared.services.readings",
    "dirt_shared.services.grow_state",
    "dirt_shared.services.snapshots",
    "dirt_shared.services.capture",
    "dirt_shared.services.plants",
    "dirt_shared.services.humidifier_state",
    "dirt_shared.services.system_status",
    "dirt_voice.tools.sensors",
)


def _pg_admin_url() -> str:
    """URL for CREATE/DROP DATABASE — connects to the ``postgres`` DB."""
    from dirt_shared.config import settings

    return (
        f"postgres://{settings.dirt_pg_user}:{settings.dirt_pg_password}"
        f"@{settings.dirt_pg_host}:{settings.dirt_pg_port}/postgres"
    )


def _pg_url(dbname: str) -> str:
    """SQLAlchemy asyncpg URL for a given database."""
    from dirt_shared.config import settings

    return (
        f"postgresql+asyncpg://{settings.dirt_pg_user}:{settings.dirt_pg_password}"
        f"@{settings.dirt_pg_host}:{settings.dirt_pg_port}/{dbname}"
    )


@pytest_asyncio.fixture(scope="session")
async def _pg_template() -> str:
    """Build ``dirt_test_template`` once per session (drop + create + migrate).

    Session-scoped so the schema + seed rows are applied exactly once per
    ``pytest`` invocation regardless of how many tests request a DB.
    """
    from dirt_shared.config import settings

    admin_url = _pg_admin_url()
    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(
            f'DROP DATABASE IF EXISTS "{_TEMPLATE}" WITH (FORCE)'
        )
        await admin.execute(f'CREATE DATABASE "{_TEMPLATE}"')
    finally:
        await admin.close()

    template_url = (
        f"postgres://{settings.dirt_pg_user}:{settings.dirt_pg_password}"
        f"@{settings.dirt_pg_host}:{settings.dirt_pg_port}/{_TEMPLATE}"
        "?sslmode=disable"
    )
    result = subprocess.run(
        [
            "atlas", "migrate", "apply",
            "--dir", f"file://{_MIGRATIONS}",
            "--url", template_url,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "atlas migrate apply failed for template:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    yield _TEMPLATE

    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(
            f'DROP DATABASE IF EXISTS "{_TEMPLATE}" WITH (FORCE)'
        )
    finally:
        await admin.close()


@pytest_asyncio.fixture
async def pg_engine(_pg_template: str, monkeypatch):
    """Per-test: clone the session template into a fresh DB and yield its engine.

    The per-test DB is dropped on teardown. Every module-level ``engine``
    reference listed in ``_ENGINE_HOLDERS`` is monkeypatched to point at
    the fresh engine.
    """
    dbname = f"test_{uuid.uuid4().hex[:12]}"
    admin_url = _pg_admin_url()

    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(
            f'CREATE DATABASE "{dbname}" TEMPLATE "{_pg_template}"'
        )
    finally:
        await admin.close()

    # NullPool — each async session opens its own connection. Prevents
    # connections from being held in the pool across operations, which
    # causes "attached to a different loop" errors when pytest-asyncio
    # runs fixture teardown on a different loop than the test body.
    test_engine = create_async_engine(_pg_url(dbname), poolclass=NullPool)

    for mod_path in _ENGINE_HOLDERS:
        try:
            mod = importlib.import_module(mod_path)
        except ImportError:
            continue
        if hasattr(mod, "engine"):
            monkeypatch.setattr(f"{mod_path}.engine", test_engine)

    yield test_engine

    await test_engine.dispose()
    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
    finally:
        await admin.close()
