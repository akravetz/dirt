"""
INVARIANT TEST — HUMAN-OWNED

This test is protected by Claude Code hooks and MUST NOT be modified by the
agent. If this test fails, the agent must fix its code to satisfy the test,
never modify this file.

Purpose: forbid patching ``dirt_*`` (production) modules from tests.

The smell: ``mock.patch("dirt_shared.services.X.thing")`` or
``monkeypatch.setattr("dirt_…", …)`` says the production code has no
seam — the only way to substitute behavior is to rewrite the module-level
binding from outside. That's a Hard-Coded Dependency (Feathers, WELC
ch. 9). The fault is in production, not the test.

Architecturally: production code accepts collaborators by constructor or
function parameter. Tests inject a fake / spy / in-memory implementation
directly. See ``apps/shared/tests/test_daily_report.py`` for the
gold-standard shape — ``_FakeCamera`` / ``_FakeSynthesis`` /
``_FakeTelegram`` are all constructor-injected, the orchestrator's tests
contain zero ``patch()`` calls.

Detection (AST):
  * Walk ``apps/*/tests/**/*.py`` plus ``apps/shared/src/dirt_shared/testing.py``
    (the latter is fixture code that lives under ``src/`` for packaging
    but is semantically test infrastructure).
  * Identify ``Call`` nodes that look like:
      - ``patch("…")`` / ``mock.patch("…")`` / ``mocker.patch("…")`` /
        ``unittest.mock.patch("…")``
      - ``patch.object(<module>, "name", …)`` / ``mock.patch.object(...)``
      - ``monkeypatch.setattr("…", …)``
      - ``monkeypatch.setattr(<module>, "name", …)``  (object form)
  * Resolve the first argument:
      - ``Constant("dirt_…")`` → flag if it starts with ``dirt_``.
      - ``JoinedStr`` (f-string) → flag unconditionally. Dynamic patch
        targets imply cross-module rewiring; the construction itself is
        the architectural signal.
      - ``Name`` / ``Attribute`` → resolve via the file's top-level
        imports; flag if the dotted name starts with ``dirt_``.
  * Patches against external libraries (``httpx``, ``time``, ``asyncio``,
    ``builtins``, etc.) are not flagged — those are legitimate boundary
    doubles.

If a test legitimately *needs* to patch a ``dirt_*`` module, that need is
the signal to refactor production code, not to add an allowlist entry
here. There is no ``KNOWN_DEBT`` allowlist by design — each violation is
a burn-down item.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ._helpers import (
    APPS,
    APPS_ROOT,
    build_import_map,
    format_invariant_failure,
)

PROD_PREFIX = "dirt_"


def _resolve_dotted(node: ast.expr, imports: dict[str, str]) -> str:
    """Best-effort dotted-name resolution. Unknown names return their literal."""
    if isinstance(node, ast.Name):
        return imports.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        base = _resolve_dotted(node.value, imports)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _classify_call(call: ast.Call) -> str | None:
    """Return ``"patch"`` / ``"patch.object"`` / ``"monkeypatch.setattr"``
    if this is a known patching construct, else ``None``."""
    func = call.func
    if isinstance(func, ast.Name) and func.id == "patch":
        return "patch"
    if isinstance(func, ast.Attribute):
        if func.attr == "patch":
            base = func.value
            if isinstance(base, ast.Name) and base.id in ("mock", "mocker"):
                return "patch"
            if isinstance(base, ast.Attribute) and base.attr == "mock":
                return "patch"
        if func.attr == "object":
            base = func.value
            # patch.object(...) or mock.patch.object(...)
            if isinstance(base, ast.Name) and base.id == "patch":
                return "patch.object"
            if isinstance(base, ast.Attribute) and base.attr == "patch":
                return "patch.object"
        if func.attr == "setattr":
            base = func.value
            if isinstance(base, ast.Name) and base.id == "monkeypatch":
                return "monkeypatch.setattr"
    return None


def _first_arg_targets_dirt(
    call: ast.Call, imports: dict[str, str]
) -> tuple[bool, str]:
    """Inspect the first arg of patch/setattr; return ``(matches, repr)``."""
    if not call.args:
        return (False, "")
    arg = call.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        if arg.value.startswith(PROD_PREFIX):
            return (True, arg.value)
        return (False, "")
    if isinstance(arg, ast.JoinedStr):
        # Dynamic patch targets are inherently a smell — they imply
        # rewiring is being computed across modules at runtime. Flag
        # without trying to resolve the f-string's parts.
        return (True, "<dynamic f-string target>")
    if isinstance(arg, (ast.Name, ast.Attribute)):
        resolved = _resolve_dotted(arg, imports)
        if resolved.startswith(PROD_PREFIX):
            return (True, resolved)
    return (False, "")


def _violations_in_file(py: Path) -> list[tuple[int, str, str]]:
    """Return ``(lineno, kind, target_repr)`` for every offending Call."""
    tree = ast.parse(py.read_text())
    imports = build_import_map(tree)
    out: list[tuple[int, str, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        kind = _classify_call(node)
        if kind is None:
            continue
        matches, target = _first_arg_targets_dirt(node, imports)
        if matches:
            out.append((node.lineno, kind, target))
    return out


def _files_for_app(app: str) -> list[Path]:
    """Test tree + (for dirt_shared) the fixture module under src/."""
    pkg_short = app.removeprefix("dirt_")
    files: list[Path] = []
    test_dir = APPS_ROOT / pkg_short / "tests"
    if test_dir.exists():
        files.extend(test_dir.rglob("*.py"))
    if app == "dirt_shared":
        fixture = APPS_ROOT / pkg_short / "src" / app / "testing.py"
        if fixture.exists():
            files.append(fixture)
    return files


@pytest.mark.parametrize("app", APPS)
def test_no_patching_production_code(app: str) -> None:
    """Tests must not patch ``dirt_*`` modules — production lacks a seam."""
    files = _files_for_app(app)
    if not files:
        pytest.skip(f"{app} has no tests")

    violations: list[str] = []
    for py in files:
        rel = py.relative_to(APPS_ROOT)
        for lineno, kind, target in _violations_in_file(py):
            violations.append(f"apps/{rel}:{lineno}  {kind}({target!r})")

    if violations:
        pytest.fail(
            format_invariant_failure(
                headline=(
                    f"{app}: {len(violations)} patch(es) on dirt_* production module(s)"
                ),
                smell_name="Hard-Coded Dependency",
                citation=(
                    "Feathers, Working Effectively with Legacy Code, ch. 9;\n"
                    "   Fowler, 'Mocks Aren't Stubs', 2007"
                ),
                body=(
                    "A test that patches dirt_* says the production code has no\n"
                    "seam to substitute the dependency. The fault is in production,\n"
                    "not the test.\n\n"
                    "FIX: refactor the production code to accept the dependency by\n"
                    "constructor or function parameter. The test then injects a\n"
                    "fake / spy / in-memory implementation directly — no patch().\n"
                    "See apps/shared/tests/test_daily_report.py for the gold-\n"
                    "standard shape (FakeCamera / FakeSynthesis / FakeTelegram\n"
                    "all constructor-injected, zero patch() calls in the file).\n\n"
                    "Patches against external libraries (httpx.MockTransport,\n"
                    "time.sleep, asyncio.run, builtins.open, etc.) remain allowed\n"
                    "— only `dirt_*` targets fail this invariant."
                ),
                violations=violations,
            )
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
