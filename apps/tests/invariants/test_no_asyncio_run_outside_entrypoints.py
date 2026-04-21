"""
INVARIANT TEST — HUMAN-OWNED

This test is protected by Claude Code hooks and MUST NOT be modified by
the agent. If this test fails, the agent must remove the stray
``asyncio.run(...)`` — never modify this file to paper over it.

Purpose: forbid ``asyncio.run()`` calls outside (a) a file-level
``if __name__ == "__main__":`` block or (b) a known composition-root
module. Agents reach for ``asyncio.run()`` to "fix" a sync call site
that needs to consume a coroutine, but calling it inside a process
that already owns an event loop (uvicorn workers, pytest-asyncio, the
dirt-voice channel runner) raises ``RuntimeError: asyncio.run() cannot
be called from a running event loop`` in dev and silently drops
exceptions in daemon contexts.

Detection (AST):
  * Walk ``apps/*/src/dirt_*/**/*.py``.
  * For every ``Call`` node, resolve its target through the file's
    top-level imports (the same trick used by test_no_concrete_clock_
    in_production.py) so aliasing doesn't evade detection
    (``from asyncio import run; run(...)``, ``import asyncio as _a;
    _a.run(...)``).
  * Flag if the resolved target is ``asyncio.run`` UNLESS the Call is
    inside an ``if __name__ == "__main__":`` block at module level, or
    the file is listed in ``COMPOSITION_ROOTS`` from ``_helpers.py``.
  * ``asyncio.run_coroutine_threadsafe`` is NOT flagged — it's the
    correct way to hand work to an event loop from a C thread and
    doesn't create a new loop.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from ._helpers import (
    APPS,
    APPS_ROOT,
    COMPOSITION_ROOTS,
    build_import_map,
    format_invariant_failure,
    iter_py,
    pkg_src_dir,
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


def _is_name_eq_main(test: ast.expr) -> bool:
    """True if ``test`` is the canonical ``__name__ == "__main__"`` expression."""
    if not isinstance(test, ast.Compare):
        return False
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    if not isinstance(test.left, ast.Name) or test.left.id != "__name__":
        return False
    right = test.comparators[0]
    return (
        isinstance(right, ast.Constant)
        and isinstance(right.value, str)
        and right.value == "__main__"
    )


def _collect_main_block_node_ids(tree: ast.Module) -> set[int]:
    """IDs of every AST node living inside a top-level ``if __name__ == '__main__':``."""
    out: set[int] = set()
    for stmt in tree.body:
        if isinstance(stmt, ast.If) and _is_name_eq_main(stmt.test):
            for sub in ast.walk(stmt):
                out.add(id(sub))
    return out


def _violations_in_file(py: Path) -> list[tuple[int, str]]:
    tree = ast.parse(py.read_text())
    imports = build_import_map(tree)
    main_ids = _collect_main_block_node_ids(tree)
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if id(node) in main_ids:
            continue
        target = _resolve_call_target(node.func, imports)
        if target == "asyncio.run":
            out.append((node.lineno, target))
    return out


@pytest.mark.parametrize("app", APPS)
def test_no_asyncio_run_outside_entrypoints(app: str) -> None:
    """Production code must not call ``asyncio.run()`` except inside __main__ / composition roots."""
    pkg_dir = pkg_src_dir(app)
    assert pkg_dir.exists(), f"package dir missing: {pkg_dir}"

    violations: list[str] = []
    for py in iter_py(pkg_dir):
        rel = str(py.relative_to(APPS_ROOT))
        if rel in COMPOSITION_ROOTS:
            continue
        for lineno, target in _violations_in_file(py):
            violations.append(f"apps/{rel}:{lineno}  {target}(...)")

    if violations:
        pytest.fail(
            format_invariant_failure(
                headline=(
                    f"{app}: {len(violations)} stray asyncio.run() call(s) "
                    "outside composition roots / __main__"
                ),
                smell_name="Double-Loop / Sync-Wrapping an Async Call Site",
                citation=(
                    "CPython asyncio docs — `asyncio.run()` cannot be called\n"
                    "   from a running event loop; Lennart Regebro, _Modern\n"
                    "   Python Cookbook_ — 'One event loop per process'"
                ),
                body=(
                    "WHY this rule exists:\n"
                    "  `asyncio.run()` creates a new event loop. Calling it\n"
                    "  inside a process that already has one (uvicorn workers,\n"
                    "  pytest-asyncio, the voice channel runner) either raises\n"
                    "  `RuntimeError: asyncio.run() cannot be called from a\n"
                    "  running event loop` or silently drops exceptions. Agents\n"
                    "  reach for it as a shortcut when a sync call site needs\n"
                    "  to consume a coroutine — almost always the wrong fix.\n\n"
                    "FIX:\n"
                    "  - Inside async code: `await the_coro()`. Make the caller\n"
                    "    async too. FastAPI and pytest-asyncio both handle it.\n"
                    "  - Inside a threadpool / sync-adapter: use\n"
                    "    `asyncio.run_coroutine_threadsafe(coro, loop)` (which\n"
                    "    is explicitly NOT flagged by this invariant) if you\n"
                    "    have a handle to the loop. Otherwise use\n"
                    "    `anyio.from_thread.run(coro)` — properly scoped to the\n"
                    "    surrounding async context.\n"
                    "  - If this really is a top-level CLI entrypoint, move the\n"
                    "    `asyncio.run(main())` inside\n"
                    "    `if __name__ == '__main__':` — then the rule accepts\n"
                    "    it as the process's single event-loop owner.\n\n"
                    "IF the file genuinely is a composition root (dirt-hwd or\n"
                    "dirt-web app factory), add it to `COMPOSITION_ROOTS` in\n"
                    "apps/tests/invariants/_helpers.py with a WHY comment.\n"
                    "That list is deliberately short."
                ),
                violations=violations,
            )
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
