"""
INVARIANT TEST — HUMAN-OWNED

This test is protected by Codex hooks and MUST NOT be modified by
the agent. If this test fails, fix the offending package's
``pyproject.toml`` (add the missing dep, drop the unused one, or add a
justified ``[tool.deptry.per_rule_ignores]`` entry) — never modify this
wrapper or silence deptry globally.

Purpose: forbid both *unused* and *undeclared* dependencies per
workspace package. Agents reliably either (a) ``import httpx`` without
``uv add`` (the package works because httpx arrives as a transitive
peer but the declaration lies), or (b) leave an import dead after a
refactor and never prune the pyproject.toml entry (silent bit-rot in
every deploy for the life of the repo).

``deptry`` catches both in one pass. We run it per workspace package
(``apps/<app>/src/``) so each package's dependency contract is checked
against its own ``pyproject.toml`` rather than a merged view — which
lets dirt-hwd legitimately declare ``pyserial`` while dirt-web doesn't.

Per-package config lives at ``[tool.deptry]`` / ``[tool.deptry.*]`` in
each ``apps/<app>/pyproject.toml``. The only allowed runtime option
here is ``--known-first-party <pkg>`` so deptry treats the package's
own imports as first-party rather than transitive.
"""

from __future__ import annotations

import subprocess

import pytest

from ._helpers import APPS, APPS_ROOT, format_invariant_failure


@pytest.mark.parametrize("app", APPS)
def test_dependency_hygiene(app: str) -> None:
    """Each workspace package's declared deps must match its imports."""
    pkg_dir = APPS_ROOT / app.removeprefix("dirt_")
    src_dir = pkg_dir / "src"
    assert src_dir.exists(), f"missing src dir: {src_dir}"

    result = subprocess.run(
        [
            "uv",
            "run",
            "--no-sync",
            "deptry",
            str(src_dir),
            "--known-first-party",
            app,
            "--config",
            str(pkg_dir / "pyproject.toml"),
        ],
        capture_output=True,
        text=True,
        cwd=APPS_ROOT.parent,
    )
    if result.returncode == 0:
        return

    # deptry writes findings to stderr, summary to stdout.
    violations = [
        line.strip()
        for line in (result.stdout + result.stderr).splitlines()
        if line.strip() and "DEP0" in line
    ]

    pytest.fail(
        format_invariant_failure(
            headline=(
                f"{app}: deptry found {len(violations)} dependency issue(s) "
                "in pyproject.toml vs imports"
            ),
            smell_name="Dependency Drift / Unused or Undeclared Dependency",
            citation="Wheeler, _Package Managers Don't Lie_ (2021 / FOSDEM);\n"
            "   PEP 621 — Storing project metadata in pyproject.toml",
            body=(
                "WHY this rule exists:\n"
                "  Agents reliably regress dependency hygiene two ways:\n"
                "   (a) `import httpx` without `uv add` — the package works\n"
                "       today because httpx arrives transitively, but the\n"
                "       declaration lies and the next transitive drop breaks\n"
                "       the app silently.\n"
                "   (b) An import goes dead after a refactor and the\n"
                "       pyproject.toml entry is never pruned — each deploy\n"
                "       pulls extra bytes and pin-management is more work.\n\n"
                "HOW to fix:\n"
                "  DEP001 (missing dep):\n"
                "    `uv add --package dirt-<app> <module>` — declare it.\n"
                "  DEP002 (unused dep):\n"
                "    Remove the line from the package's dependencies list.\n"
                "    If the dep IS real but consumed transparently (e.g.\n"
                "    `jinja2` via `fastapi.templating`), add it to that\n"
                "    package's `[tool.deptry.per_rule_ignores] DEP002 = [...]`\n"
                "    with a comment WHY.\n"
                "  DEP003 (transitive dep, imported directly):\n"
                "    If the peer is re-exported at import time (sqlalchemy via\n"
                "    sqlmodel), keep the direct import and add it to\n"
                "    `[tool.deptry.per_rule_ignores] DEP003 = [...]` with a\n"
                "    comment WHY. Otherwise declare it explicitly with\n"
                "    `uv add --package dirt-<app> <module>`.\n"
                "  DEP004 (dev dep used in production):\n"
                "    Either promote to a real dep or move the import into\n"
                "    tests/.\n\n"
                "DO NOT edit this invariant. DO NOT run deptry with `--ignore`\n"
                "at the CLI level — every ignore must live in a package's\n"
                "pyproject.toml with a WHY comment so the next agent can\n"
                "reason about it."
            ),
            violations=violations or [result.stdout.strip() or result.stderr.strip()],
        )
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
