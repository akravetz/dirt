"""
INVARIANT TEST — HUMAN-OWNED

This test is protected by Claude Code hooks and MUST NOT be modified by
the agent. If this test fails, the agent must fix its code (route the
env read through ``dirt_shared.config.Settings``) — never modify this
file's ALLOWED set to paper over a new smell.

Purpose: forbid ad-hoc ``os.environ`` / ``os.getenv`` reads inside
production code. The single source of truth for runtime configuration
is ``Settings`` in ``apps/shared/src/dirt_shared/config.py``. Sprinkling
``os.getenv("FOO")`` at call sites is untyped, undocumented, and
untestable — every new knob bypasses validation, the ``.env`` loader,
and the tests that assert startup config shape.

Detection (AST): walk ``apps/*/src/dirt_*/**/*.py``; for every ``Call``
node, resolve its target through the file's top-level imports so
aliasing doesn't evade detection (``from os import getenv``,
``import os as _os``, etc.). Flag if the resolved target is one of
``BANNED_ENV_CALLS``. Also flag subscripting ``os.environ[...]``. Files
in ``ALLOWED`` are skipped wholesale — those are the handful of
boundary modules that legitimately sit between the OS and the
application.

Known evasion paths, accepted in v1:
  * ``_get = os.environ.get; _get("FOO")`` slips past — the call site
    is a bare ``Name`` with no import binding. Vanishingly rare in real
    code; if it appears it's active evasion and code review catches it.
  * Stored aliases through attribute chains on arbitrary Call results
    slip past for the same reason.
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
    iter_py,
    pkg_src_dir,
)

# Files where reading an env var directly is the architectural point.
# Everything else must go through Settings. If you are tempted to add a
# file here, ask first whether the knob belongs in Settings instead —
# the answer is "yes" more often than "no".
ALLOWED: frozenset[str] = frozenset(
    {
        # Settings itself — canonical env reader.
        "shared/src/dirt_shared/config.py",
        # observability.py: reads DIRT_LOGS_DIR on every write so the pytest
        # isolate_observability_logs autouse fixture can redirect writes
        # per-test. Documented in CLAUDE.md (Observability / Test isolation)
        # and again in the module docstring.
        "shared/src/dirt_shared/observability.py",
        # services/capture.py + services/system_status.py: discover the PTZ
        # camera daemon's unix socket by probing DIRT_CAMERA_SOCKET /
        # XDG_RUNTIME_DIR — a hardware-boundary path that doesn't belong in
        # Settings (discovered at call time from the systemd runtime dir).
        "shared/src/dirt_shared/services/capture.py",
        "shared/src/dirt_shared/services/system_status.py",
        # services/wiki.py: DIRT_WIKI_DIR override exists only to let tests
        # point the wiki service at a tmp tree; production reads fall
        # through to the repo-root default. A Settings field would force
        # every non-wiki test to stub a Settings object.
        "shared/src/dirt_shared/services/wiki.py",
    }
)

# Fully-qualified call targets, post-import-resolution. Anything that
# asks "what's in the environment?" at runtime.
BANNED_ENV_CALLS: frozenset[str] = frozenset(
    {
        "os.getenv",
        "os.environ.get",
        "os.environ.setdefault",
        "os.environ.pop",
        # `from os import getenv` → local name "getenv" resolves to "os.getenv"
        # via build_import_map. Same for environ.
    }
)


def _resolve_call_target(func_node: ast.expr, imports: dict[str, str]) -> str:
    """Qualified name of a Call's target, resolving import aliases."""
    if isinstance(func_node, ast.Name):
        return imports.get(func_node.id, func_node.id)
    if isinstance(func_node, ast.Attribute):
        attrs: list[str] = [func_node.attr]
        node: ast.expr = func_node.value
        while isinstance(node, ast.Attribute):
            attrs.insert(0, node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            base = imports.get(node.id, node.id)
            return ".".join([base, *attrs])
    return ""


def _resolve_subscript_target(value_node: ast.expr, imports: dict[str, str]) -> str:
    """Qualified name of a Subscript's value — e.g. ``os.environ[...]``."""
    if isinstance(value_node, ast.Attribute):
        attrs: list[str] = [value_node.attr]
        node: ast.expr = value_node.value
        while isinstance(node, ast.Attribute):
            attrs.insert(0, node.attr)
            node = node.value
        if isinstance(node, ast.Name):
            base = imports.get(node.id, node.id)
            return ".".join([base, *attrs])
    if isinstance(value_node, ast.Name):
        return imports.get(value_node.id, value_node.id)
    return ""


def _violations_in_file(py: Path) -> list[tuple[int, str]]:
    tree = ast.parse(py.read_text())
    imports = build_import_map(tree)
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            target = _resolve_call_target(node.func, imports)
            if target in BANNED_ENV_CALLS:
                out.append((node.lineno, f"{target}(...)"))
        elif isinstance(node, ast.Subscript):
            target = _resolve_subscript_target(node.value, imports)
            if target == "os.environ":
                out.append((node.lineno, "os.environ[...]"))
    return out


@pytest.mark.parametrize("app", APPS)
def test_no_env_reads_outside_config(app: str) -> None:
    """Production code must not call ``os.environ`` / ``os.getenv`` outside ALLOWED."""
    pkg_dir = pkg_src_dir(app)
    assert pkg_dir.exists(), f"package dir missing: {pkg_dir}"

    violations: list[str] = []
    for py in iter_py(pkg_dir):
        rel = str(py.relative_to(APPS_ROOT))
        if rel in ALLOWED:
            continue
        for lineno, target in _violations_in_file(py):
            violations.append(f"apps/{rel}:{lineno}  {target}")

    if violations:
        pytest.fail(
            format_invariant_failure(
                headline=(
                    f"{app}: {len(violations)} ad-hoc env read(s) "
                    "outside dirt_shared.config"
                ),
                smell_name="Untyped Configuration Sprawl / Hidden Dependency on Env",
                citation=(
                    "Hunt & Thomas, _The Pragmatic Programmer_ — 'Keep\n"
                    "   Configuration Out of Code'; 12-Factor App §III"
                ),
                body=(
                    "WHY this rule exists:\n"
                    "  Every runtime knob belongs in Settings (typed, validated,\n"
                    "  documented in one place, discoverable in one grep). An\n"
                    "  `os.getenv('FOO')` at a call site is untyped (str | None,\n"
                    "  caller has to coerce), undocumented (no one knows the knob\n"
                    "  exists until it breaks), and untestable (can't stub\n"
                    "  Settings to exercise the happy path).\n\n"
                    "FIX:\n"
                    "  - Add a field to `Settings` in\n"
                    "    apps/shared/src/dirt_shared/config.py. Type it,\n"
                    "    validation_alias='<NAME>', sane default.\n"
                    "  - Thread it through a slice method (capture(), humidifier(),\n"
                    "    etc.) the way the existing shape does, OR inject the\n"
                    "    Settings instance into the service's __init__.\n"
                    "  - Tests construct Settings with the value they want to\n"
                    "    exercise — no monkeypatching of os.environ.\n\n"
                    "IF the knob genuinely belongs at the OS boundary (a unix\n"
                    "socket path discovered from XDG_RUNTIME_DIR, a test-only\n"
                    "tmp-dir override) and cannot live in Settings without\n"
                    "inverting the dep, add the file to `ALLOWED` in this\n"
                    "invariant with a one-line WHY comment. Those additions are\n"
                    "reviewed with the human maintainer — the answer is usually\n"
                    "'put it in Settings'."
                ),
                violations=violations,
            )
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
