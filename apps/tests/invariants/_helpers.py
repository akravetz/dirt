"""Shared helpers for invariant tests — HUMAN-OWNED.

Single source of truth for constants and AST utilities duplicated across
the invariant suite. Keep this module small: anything test-specific
(SAFE_CONSTRUCTORS, BANNED_CLOCK_CALLS, SHELL_MODULES, etc.) lives with
its test so the allowlist sits next to the rule it qualifies.

Naming: ``_helpers.py`` (leading underscore) marks this as an internal
invariants-tests module, not a test file. Functions inside don't need a
prefix — ``from ._helpers import pkg_src_dir`` is the import shape.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

# apps/tests/invariants/_helpers.py → apps/
APPS_ROOT: Path = Path(__file__).resolve().parents[2]

APP_SOURCE_DIRS: dict[str, str] = {
    "dirt_hwd": "hwd/src/dirt_hwd",
    "dirt_shared": "shared/src/dirt_shared",
    "dirt_voice": "voice/src/dirt_voice",
    "dirt_control": "control-plane/src/dirt_control",
}

# APPS is the pre-existing broad invariant suite. Milestone-specific app
# sets opt in below as each rule family is deliberately expanded.
APPS: tuple[str, ...] = (
    "dirt_hwd",
    "dirt_shared",
    "dirt_voice",
)

STAGE1_GENERIC_APPS: tuple[str, ...] = (*APPS, "dirt_control")

# Files where wiring stateful singletons / reading the wall clock at
# startup is the intended architectural pattern. Used by both the
# module-level-singleton invariant and the concrete-clock invariant.
COMPOSITION_ROOTS: frozenset[str] = frozenset(
    {
        "hwd/src/dirt_hwd/app.py",  # builds dirt-hwd FastAPI app + lifespan
        # builds control-plane FastAPI app, lifespan, sessions, engine, asset store
        "control-plane/src/dirt_control/app.py",
    }
)


def pkg_src_dir(pkg: str) -> Path:
    """``dirt_control`` → ``apps/control-plane/src/dirt_control``."""
    return APPS_ROOT / APP_SOURCE_DIRS[pkg]


def iter_py(root: Path) -> Iterator[Path]:
    """Recursively yield all ``*.py`` files under ``root``."""
    yield from root.rglob("*.py")


def build_import_map(tree: ast.Module) -> dict[str, str]:
    """Map ``local_name -> dotted_name`` for top-level imports.

    ``import x.y``             → ``"x" -> "x"``  (leftmost binds)
    ``import x.y as a``        → ``"a" -> "x.y"``
    ``from x.y import z``      → ``"z" -> "x.y.z"``
    ``from x.y import z as a`` → ``"a" -> "x.y.z"``

    Used by invariants that need to resolve a ``Call``'s target through
    the file's imports (datetime aliasing, patch() target resolution).
    """
    out: dict[str, str] = {}
    for stmt in tree.body:
        if isinstance(stmt, ast.Import):
            for alias in stmt.names:
                if alias.asname:
                    out[alias.asname] = alias.name
                else:
                    leftmost = alias.name.split(".")[0]
                    out[leftmost] = leftmost
        elif isinstance(stmt, ast.ImportFrom):
            module = stmt.module or ""
            for alias in stmt.names:
                local = alias.asname or alias.name
                out[local] = f"{module}.{alias.name}" if module else alias.name
    return out


def format_invariant_failure(
    *,
    headline: str,
    smell_name: str,
    citation: str,
    body: str,
    violations: list[str],
) -> str:
    """Render the standard SMELL/body/violations shape invariant tests use.

    Args:
        headline: First line, minus trailing period. E.g.
            ``"dirt_shared: 4 concrete clock read(s) in production code"``.
        smell_name: The smell label. E.g.
            ``"Hidden Dependency / Module-level Singleton"``.
        citation: Parenthesised citation block (may be multiline).
        body: The WHY / FIX / notes content — newlines preserved as-is.
        violations: Pre-formatted violation lines. Each is rendered as
            an indented bullet.
    """
    bullets = "\n".join(f"  {v}" for v in violations)
    return (
        f"\n{headline}.\n\n"
        f"SMELL: {smell_name}\n"
        f"  ({citation})\n\n"
        f"{body}\n\n"
        f"Violations:\n{bullets}"
    )
