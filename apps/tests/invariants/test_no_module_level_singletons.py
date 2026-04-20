"""
INVARIANT TEST — HUMAN-OWNED

This test is protected by Claude Code hooks and MUST NOT be modified by the
agent. If this test fails, the agent must fix its code to satisfy the test,
never modify this file.

Purpose: forbid module-level singleton instantiation in production code.

The smell: ``engine = create_async_engine(...)`` at the top of a module
creates a Hidden Dependency (Feathers, WELC ch. 9). Any function in the
module — or any other module that imports the binding — silently couples to
that singleton. Tests can only swap it via ``monkeypatch.setattr(...)``,
and production cannot run with a different instance (read replica,
multi-tenant, fresh cryptographic key, etc.).

Architecturally: stateful objects are constructed by the composition root
(``app.py`` / ``main.py`` / ``__main__.py``) and passed down to consumers
via constructor parameters or function arguments. The consumer becomes
testable without monkey-patching.

Detection (AST):
  * Walk ``apps/*/src/dirt_*/**/*.py``.
  * For each top-level ``Assign`` / ``AnnAssign`` whose value contains a
    ``Call``.
  * For each ``Call`` whose ``func`` is a bare ``Name`` (``Foo(...)`` —
    not ``mod.Foo(...)`` and not ``x().y()``; method chains slip past
    because their inner Calls have ``Attribute`` funcs, which is correct).
  * If the ``Name.id`` is not in ``SAFE_CONSTRUCTORS`` and the file is not
    in ``COMPOSITION_ROOTS`` → violation.

The two allowlists below are NOT debt tolerance — they enumerate
constructors / files where module-level instantiation is the *intended*
architectural pattern. Each entry exists with a one-line justification.
Adding a new entry is a deliberate decision; if you find yourself wanting
to add one because "it's just easier than refactoring," refactor instead.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ._helpers import (
    APPS,
    APPS_ROOT,
    COMPOSITION_ROOTS,
    format_invariant_failure,
    iter_py,
    pkg_src_dir,
)

# Bare-Name calls (``Foo(...)``) whose module-level use is fine because the
# resulting object is either immutable, a framework idiom (FastAPI router
# at module level is the framework's expected shape), or a declarative
# value with no external resource state.
SAFE_CONSTRUCTORS: frozenset[str] = frozenset({
    # Stdlib pure / immutable values
    "Path", "PurePath", "PurePosixPath", "PureWindowsPath",
    "ZoneInfo",                                      # immutable timezone
    "Decimal", "Fraction",                           # immutable numerics
    "date", "time", "datetime", "timedelta", "timezone", "tzinfo",  # immutable datetime values
    # Builtin numeric / string constructors — used for type-casting constants
    "int", "float", "bool", "complex", "str", "bytes", "bytearray",
    # Builtin containers used as module-level constants
    "frozenset", "tuple", "set", "dict", "list",
    "namedtuple", "NamedTuple",
    # Type machinery (no runtime state)
    "TypeVar", "ParamSpec", "TypeAdapter",
    # Enum class definitions (declarative, not state)
    "Enum", "IntEnum", "StrEnum", "Flag", "SAEnum",
    # FastAPI / Starlette routing & templates — module-level binding is the
    # framework idiom; tests exercise the app, not these bindings.
    "FastAPI", "APIRouter", "Jinja2Templates",
    # Project-specific declarative tool descriptions (voice agent).
    # ToolSpec instances carry no external state; they're config objects.
    "ToolSpec",
})


def _iter_calls(value: ast.expr):
    """Yield every ``Call`` node anywhere inside ``value``."""
    for node in ast.walk(value):
        if isinstance(node, ast.Call):
            yield node


def _violations_in_file(py: Path) -> list[tuple[int, str]]:
    """Return ``(lineno, constructor_name)`` for every offending Call."""
    tree = ast.parse(py.read_text())
    out: list[tuple[int, str]] = []
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            value: ast.expr | None = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            value = stmt.value
        else:
            continue
        for call in _iter_calls(value):
            # Only flag bare-Name Calls. ``mod.Foo(...)`` and ``x().y()``
            # have Attribute funcs and slip past — that's intentional;
            # the smells in this codebase all use bare-Name constructors.
            if not isinstance(call.func, ast.Name):
                continue
            name = call.func.id
            if name in SAFE_CONSTRUCTORS:
                continue
            out.append((stmt.lineno, name))
    return out


@pytest.mark.parametrize("app", APPS)
def test_no_module_level_singletons(app: str) -> None:
    """No production module may instantiate a stateful singleton at import."""
    pkg_dir = pkg_src_dir(app)
    assert pkg_dir.exists(), f"package dir missing: {pkg_dir}"

    violations: list[str] = []
    for py in iter_py(pkg_dir):
        rel = str(py.relative_to(APPS_ROOT))
        if rel in COMPOSITION_ROOTS:
            continue
        for lineno, name in _violations_in_file(py):
            violations.append(f"apps/{rel}:{lineno}  {name}(...)")

    if violations:
        pytest.fail(format_invariant_failure(
            headline=(
                f"{app}: {len(violations)} module-level singleton "
                "instantiation(s)"
            ),
            smell_name="Hidden Dependency / Module-level Singleton",
            citation="Feathers, Working Effectively with Legacy Code, ch. 9",
            body=(
                "Module-level instantiation creates a hidden dependency.\n"
                "Functions in the module — and other modules that import the\n"
                "binding — silently couple to that singleton. Tests can only\n"
                "swap it via patch(). Production can't construct a different\n"
                "instance per request, per user, or per environment.\n\n"
                "FIX: Construct the object once in the composition root\n"
                "(app.py / main.py) and pass it to consumers as a constructor\n"
                "or function parameter. The consumer then becomes testable\n"
                "without monkey-patching.\n\n"
                "If the constructor is genuinely fine at module level (an\n"
                "immutable value or framework idiom), add its bare name to\n"
                "SAFE_CONSTRUCTORS in this file with a one-line comment\n"
                "justifying it. SAFE_CONSTRUCTORS is not a debt list — it's\n"
                "an enumeration of non-smells.\n\n"
                f"Composition roots already allowed: {sorted(COMPOSITION_ROOTS)}"
            ),
            violations=violations,
        ))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
