"""
INVARIANT TEST — HUMAN-OWNED

This test is protected by Claude Code hooks and MUST NOT be modified by the
agent. If this test fails, the agent must fix its code to satisfy the test,
never modify this file.

Purpose: Enforce architectural boundaries across the uv workspace, so no
app silently grows a dependency on a peer. Phase 0 established these five
packages:

    dirt_shared   — models, config, db, observability, non-HW services (pure)
    dirt_hwd      — HW-owning daemon: serial, humidifier, archive, ingest
    dirt_web      — web UI + sensors/snapshots/feed API + MCP mount
    dirt_mcp      — MCP server (mounted into dirt_web)
    dirt_voice    — voice channel (own process)

Rules:
  dirt_shared  may NOT import any dirt_{hwd,web,mcp,voice}  (pure base)
  dirt_hwd     may NOT import dirt_{web,mcp,voice}
  dirt_web     may NOT import dirt_{hwd,voice}               (may import mcp)
  dirt_mcp     may NOT import dirt_{hwd,web,voice}
  dirt_voice   may NOT import dirt_{hwd,web,mcp}

Within-app: api-layer modules (dirt_web.api.*, dirt_hwd.api.*) may NOT
import dirt_shared.db or dirt_shared.models directly — they must go
through dirt_shared.services so session management stays in one place.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

APPS_ROOT = Path(__file__).resolve().parents[2]  # apps/tests/invariants → apps/

# Each workspace app → packages it is NOT permitted to import.
CROSS_APP_FORBIDDEN: dict[str, tuple[str, ...]] = {
    "dirt_shared": ("dirt_hwd", "dirt_web", "dirt_mcp", "dirt_voice"),
    "dirt_hwd":    ("dirt_web", "dirt_mcp", "dirt_voice"),
    "dirt_web":    ("dirt_hwd", "dirt_voice"),
    "dirt_mcp":    ("dirt_hwd", "dirt_web", "dirt_voice"),
    "dirt_voice":  ("dirt_hwd", "dirt_web", "dirt_mcp"),
}

# api/* layer must not reach past services into db/models.
API_LAYER_FORBIDDEN: tuple[str, ...] = ("dirt_shared.db", "dirt_shared.models")


def _pkg_src_dir(pkg: str) -> Path:
    # dirt_shared → apps/shared/src/dirt_shared
    return APPS_ROOT / pkg.removeprefix("dirt_") / "src" / pkg


def _iter_py(root: Path):
    yield from root.rglob("*.py")


def _file_imports(py: Path) -> list[tuple[int, str]]:
    """Return (lineno, dotted-module) for every import statement in ``py``."""
    tree = ast.parse(py.read_text())
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            out.append((node.lineno, node.module))
    return out


def _matches(imp: str, forbidden: str) -> bool:
    """True if ``imp`` is the forbidden module or a submodule of it."""
    return imp == forbidden or imp.startswith(forbidden + ".")


@pytest.mark.parametrize("app", sorted(CROSS_APP_FORBIDDEN.keys()))
def test_cross_app_imports(app: str) -> None:
    """Each app's source must not import peer-app packages it doesn't depend on."""
    forbidden = CROSS_APP_FORBIDDEN[app]
    pkg_dir = _pkg_src_dir(app)
    assert pkg_dir.exists(), f"package dir missing: {pkg_dir}"

    violations: list[str] = []
    for py in _iter_py(pkg_dir):
        rel = py.relative_to(APPS_ROOT)
        for lineno, imp in _file_imports(py):
            for bad in forbidden:
                if _matches(imp, bad):
                    violations.append(f"apps/{rel}:{lineno}  imports  {imp}")

    if violations:
        pytest.fail(
            f"\n{app} has {len(violations)} forbidden cross-app import(s).\n"
            f"Forbidden for {app}: {forbidden}\n"
            "FIX: push shared code into dirt_shared, or call across apps via HTTP\n"
            "(process boundary) — not by direct Python import.\n\n"
            + "\n".join(violations)
        )


@pytest.mark.parametrize("app", ["dirt_hwd", "dirt_web"])
def test_api_layer_does_not_touch_db_or_models(app: str) -> None:
    """API routes must not import db/models directly — go through services."""
    api_dir = _pkg_src_dir(app) / "api"
    if not api_dir.exists():
        pytest.skip(f"{app} has no api/ layer")

    violations: list[str] = []
    for py in _iter_py(api_dir):
        rel = py.relative_to(APPS_ROOT)
        for lineno, imp in _file_imports(py):
            for bad in API_LAYER_FORBIDDEN:
                if _matches(imp, bad):
                    violations.append(f"apps/{rel}:{lineno}  imports  {imp}")

    if violations:
        pytest.fail(
            f"\n{app}.api has {len(violations)} direct db/model import(s).\n"
            "FIX: move the logic into dirt_shared.services (or dirt_hwd.services\n"
            "if HW-owning) and have the api route call the service function.\n\n"
            + "\n".join(violations)
        )
