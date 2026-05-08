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

import hashlib
import subprocess
import uuid
from pathlib import Path

import asyncpg
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from dirt_shared.models.device import Capability, Device
from dirt_shared.models.site import Site
from dirt_shared.models.tent import Tent
from dirt_shared.models.zone import Zone
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


def _worktree_id() -> str:
    """Short stable hash of this worktree's repo root.

    Used to namespace the template DB + per-test clones so concurrent
    pytest runs in different worktrees don't fight over the same
    ``dirt_test_template`` (DROP/CREATE races, stale-template visibility).

    Hash is deterministic per filesystem location; re-running tests in
    the same worktree reuses the same template name across sessions.
    """
    return hashlib.sha256(str(_REPO_ROOT).encode()).hexdigest()[:10]


def _template_name() -> str:
    """Worktree-namespaced template DB name."""
    return f"dirt_test_template_{_worktree_id()}"


def _test_db_prefix() -> str:
    """Worktree-namespaced prefix for per-test clone DB names."""
    return f"dirt_test_{_worktree_id()}_"


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


async def _drop_stale_test_dbs(admin: asyncpg.Connection) -> None:
    """Drop any leftover per-test clones from this worktree's prefix.

    Crashed/interrupted prior sessions can leave ``dirt_test_<worktree>_*``
    databases behind. They're harmless (next clone uses a fresh uuid),
    but accumulating them slowly drinks the connection slot pool. Sweep
    them at session start.

    Scoped to this worktree's prefix so a parallel session in another
    worktree doesn't have its in-flight clones yanked out from under it.
    """
    rows = await admin.fetch(
        "SELECT datname FROM pg_database WHERE datname LIKE $1",
        _test_db_prefix() + "%",
    )
    for (dbname,) in rows:
        await admin.execute(f'DROP DATABASE IF EXISTS "{dbname}" WITH (FORCE)')


@pytest_asyncio.fixture(scope="session")
async def _pg_template() -> str:
    """Build the worktree-namespaced template once per session.

    Template name is ``dirt_test_template_<worktree_hash>`` so two
    pytests in different worktrees never collide on DROP/CREATE/TEMPLATE
    operations. Per-test clones are namespaced the same way (see
    ``_TEST_DB_PREFIX``); session start sweeps any stale clones from
    this worktree's prefix that a previous crashed run left behind.
    """
    from dirt_shared.config import Settings

    settings = Settings()

    template = _template_name()
    admin_url = _pg_admin_url()
    admin = await asyncpg.connect(admin_url)
    try:
        await _drop_stale_test_dbs(admin)
        await admin.execute(f'DROP DATABASE IF EXISTS "{template}" WITH (FORCE)')
        await admin.execute(f'CREATE DATABASE "{template}"')
    finally:
        await admin.close()

    template_url = (
        f"postgres://{settings.dirt_pg_user}:{settings.dirt_pg_password}"
        f"@{settings.dirt_pg_host}:{settings.dirt_pg_port}/{template}"
        "?sslmode=disable"
    )
    # Session-scoped one-shot atlas migrate against an ephemeral template
    # DB. We are inside an async fixture but there is nothing else on the
    # loop during setup — async subprocess_exec would just add noise. The
    # ASYNC221 rule is valuable elsewhere; this is the single justified
    # exception.
    result = subprocess.run(  # noqa: ASYNC221
        [
            "atlas",
            "migrate",
            "apply",
            "--dir",
            f"file://{_MIGRATIONS}",
            "--url",
            template_url,
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "atlas migrate apply failed for template:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    yield template

    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(f'DROP DATABASE IF EXISTS "{template}" WITH (FORCE)')
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
    dbname = f"{_test_db_prefix()}{uuid.uuid4().hex[:12]}"
    admin_url = _pg_admin_url()

    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(f'CREATE DATABASE "{dbname}" TEMPLATE "{_pg_template}"')
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


# ============================================================
# Scoped test data builders
# ============================================================


async def create_test_device(  # noqa: PLR0913
    session: AsyncSession,
    *,
    device_id: str,
    tent_id: str | None,
    site_id: str = "homebox",
    zone_id: str | None = None,
    name: str | None = None,
    kind: str = "env_sensor",
    controller: str = "test",
    enabled: bool = True,
) -> Device:
    """Create a test-owned device in a scoped site/tent/zone.

    Use this in behavior tests instead of asserting against production-ish
    migration seed inventory. Seed topology tests should still query the
    canonical migrated rows directly.
    """
    site_pk = (await session.exec(select(Site.id).where(Site.site_id == site_id))).one()
    tent_pk = None
    if tent_id is not None:
        tent_pk = (
            await session.exec(
                select(Tent.id)
                .where(Tent.site_id == site_pk)
                .where(Tent.tent_id == tent_id)
            )
        ).one()

    zone_pk = None
    if zone_id is not None:
        zone_pk = (
            await session.exec(
                select(Zone.id)
                .where(Zone.site_id == site_pk)
                .where(Zone.tent_id == tent_pk)
                .where(Zone.zone_id == zone_id)
            )
        ).one()

    device = Device(
        site_id=site_pk,
        tent_id=tent_pk,
        zone_id=zone_pk,
        device_id=device_id,
        name=name or device_id,
        kind=kind,
        controller=controller,
        enabled=enabled,
    )
    session.add(device)
    await session.flush()
    if device.id is None:
        raise RuntimeError("test device insert did not assign a primary key")
    return device


async def create_test_capability(  # noqa: PLR0913
    session: AsyncSession,
    *,
    device: Device,
    capability_id: str,
    name: str | None = None,
    kind: str = "measurement",
    metric_name: str | None = None,
    unit: str | None = None,
    source: str = "test",
    enabled: bool = True,
) -> Capability:
    """Create a test-owned capability for a device."""
    if device.id is None:
        raise ValueError("device must be flushed before adding a capability")
    capability = Capability(
        device_id=device.id,
        capability_id=capability_id,
        name=name or capability_id,
        kind=kind,
        metric_name=metric_name or capability_id,
        unit=unit,
        source=source,
        enabled=enabled,
    )
    session.add(capability)
    await session.flush()
    if capability.id is None:
        raise RuntimeError("test capability insert did not assign a primary key")
    return capability
