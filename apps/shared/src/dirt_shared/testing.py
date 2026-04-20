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



def _pg_admin_url() -> str:
    """URL for CREATE/DROP DATABASE — connects to the ``postgres`` DB."""
    from dirt_shared.config import Settings
    settings = Settings()

    return (
        f"postgres://{settings.dirt_pg_user}:{settings.dirt_pg_password}"
        f"@{settings.dirt_pg_host}:{settings.dirt_pg_port}/postgres"
    )


def _pg_url(dbname: str) -> str:
    """SQLAlchemy asyncpg URL for a given database."""
    from dirt_shared.config import Settings
    settings = Settings()

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
    from dirt_shared.config import Settings
    settings = Settings()

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
    # Session-scoped one-shot atlas migrate against an ephemeral template
    # DB. We are inside an async fixture but there is nothing else on the
    # loop during setup — async subprocess_exec would just add noise. The
    # ASYNC221 rule is valuable elsewhere; this is the single justified
    # exception.
    result = subprocess.run(  # noqa: ASYNC221
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
async def app_engine(_pg_template: str):
    """Per-test: clone the session template into a fresh DB and yield its engine.

    Pure fixture — yields the AsyncEngine and nothing else. No
    monkey-patching of module-level bindings. New-style tests (post
    singleton-retirement, see ``docs/proposals/singleton-retirement.md``)
    construct service classes / FastAPI apps with this engine directly:

        async def test_something(app_engine):
            svc = ReadingsService(app_engine)
            ...

        async def test_endpoint(app_engine):
            app = create_app(engine=app_engine, run_mcp=False)
            ...

    The per-test DB is dropped on teardown.
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

    try:
        yield test_engine
    finally:
        await test_engine.dispose()
        admin = await asyncpg.connect(admin_url)
        try:
            await admin.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')
        finally:
            await admin.close()


@pytest_asyncio.fixture
async def pg_engine(app_engine):
    """DEPRECATED ALIAS for ``app_engine``.

    Kept so existing tests under ``apps/*/tests/`` that still reference
    ``pg_engine`` keep working through the singleton-retirement landing.
    New tests should depend on ``app_engine`` directly. The
    ``_ENGINE_HOLDERS`` monkey-patch loop has been removed — no service
    module retains a module-level ``engine`` binding to patch.
    """
    yield app_engine
