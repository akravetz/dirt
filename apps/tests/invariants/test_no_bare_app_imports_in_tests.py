"""
INVARIANT TEST — HUMAN-OWNED

This test is protected by Claude Code hooks and MUST NOT be modified by the
agent. If this test fails, the agent must fix its code to satisfy the test,
never modify this file.

Purpose: forbid bare FastAPI ``app`` imports in test code.

The smell: ``from dirt_<app>.app import app`` binds tests to the
module-level singleton built once at import. That instance:
- starts every background lifespan side-effect on construction
- holds a single ``app.state`` shared across every test that imports it
- forces ``mock.patch`` to suppress lifespan side effects (the smell B
  invariant catches separately)

Architecturally: tests construct a fresh app per test via
``create_app(...)`` from the same module — passing the per-test engine,
disabling MCP / background services as needed, and using
``app.dependency_overrides[provider] = lambda: fake`` to swap collaborators.

Detection (AST):
  * Walk apps/*/tests/**/*.py.
  * For each top-level ``ImportFrom`` whose module matches
    ``dirt_(hwd|web|mcp|voice)\\.app``:
    if any ``alias.name == "app"`` → violation.
    Importing ``create_app``, ``lifespan``, ``AuthMiddleware``, etc. is fine.

There is no allowlist by design — each violation is a burn-down item.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ._helpers import APPS, APPS_ROOT, format_invariant_failure

# A module name like "dirt_hwd.app" — flag any `from <pkg>.app import app`.
_TARGET_PKGS: frozenset[str] = frozenset({
    "dirt_hwd.app", "dirt_web.app", "dirt_mcp.app", "dirt_voice.app",
    # dirt_shared has no .app module, listed for completeness.
    "dirt_shared.app",
})


def _bare_app_imports(py: Path) -> list[tuple[int, str]]:
    """Return ``(lineno, module)`` for every offending bare-app import."""
    tree = ast.parse(py.read_text())
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if node.module not in _TARGET_PKGS:
            continue
        for alias in node.names:
            if alias.name == "app":
                out.append((node.lineno, node.module))
    return out


@pytest.mark.parametrize("app", APPS)
def test_no_bare_app_imports_in_tests(app: str) -> None:
    """Tests must use ``create_app(...)`` instead of importing the singleton."""
    pkg_short = app.removeprefix("dirt_")
    test_dir = APPS_ROOT / pkg_short / "tests"
    if not test_dir.exists():
        pytest.skip(f"{app} has no tests")

    violations: list[str] = []
    for py in test_dir.rglob("*.py"):
        rel = py.relative_to(APPS_ROOT)
        for lineno, module in _bare_app_imports(py):
            violations.append(
                f"apps/{rel}:{lineno}  from {module} import app"
            )

    if violations:
        pytest.fail(format_invariant_failure(
            headline=f"{app}: {len(violations)} bare-app import(s) in tests",
            smell_name="Bare FastAPI app singleton import in tests",
            citation="derived from Hidden Dependency / Module-level Singleton",
            body=(
                "Tests importing ``from dirt_<app>.app import app`` bind to the\n"
                "module-level composition root, which drags every background\n"
                "lifespan side-effect, every default service wiring, and the\n"
                "single shared ``app.state`` across the test session. This\n"
                "forces tests to patch lifespan internals to keep them quiet.\n\n"
                "FIX: use ``from dirt_<app>.app import create_app`` and build a\n"
                "per-test app:\n\n"
                "    @pytest.fixture\n"
                "    async def client(app_engine):\n"
                "        app = create_app(engine=app_engine, run_mcp=False)\n"
                "        ...\n\n"
                "Override services with ``app.dependency_overrides[provider]``\n"
                "to substitute fakes — no ``mock.patch`` needed."
            ),
            violations=violations,
        ))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
