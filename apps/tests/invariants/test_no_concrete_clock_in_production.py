"""
INVARIANT TEST — HUMAN-OWNED

This test is protected by Claude Code hooks and MUST NOT be modified by the
agent. If this test fails, the agent must fix its code to satisfy the test,
never modify this file.

Purpose: forbid concrete clock reads (``datetime.now()``, ``time.time()``,
etc.) inside production-code execution paths.

The smell: a function that calls ``datetime.now()`` in its body has a
hidden dependency on wall-clock time. Tests can only verify behavior "at
this exact moment" by patching the global. Behavior at midnight,
month-end, or DST transitions becomes effectively untestable.

Architecturally: pass time in as a callable parameter with a sane
default. The default is evaluated once at function-definition time and
is the *fix*, not the smell:

    def archive_loop(
        snapshot_dir: Path,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        today = clock().date()
        ...

Tests pass ``clock=lambda: datetime(2026, 4, 19, tzinfo=UTC)``. See
``apps/shared/src/dirt_shared/services/daily_sensors.py`` (``SensorReader``)
and ``daily_report.py`` (``DailyReport``) for the gold-standard shape
already used in dirt.

Detection (AST):
  * Walk ``apps/*/src/dirt_*/**/*.py``.
  * For every ``Call`` node, resolve its target through the file's
    top-level imports so aliasing doesn't evade detection
    (``from datetime import datetime as dt; dt.now()`` resolves to
    ``"datetime.datetime.now"``; ``from time import time; time()``
    resolves to ``"time.time"``).
  * Flag if the resolved target is in ``BANNED_CLOCK_CALLS`` UNLESS the
    Call lives inside a parameter default of some function or lambda
    (the body-vs-defaults distinction is the architectural insight —
    the invariant enforces a positive pattern, not just a ban).
  * Composition roots are skipped wholesale (same allowlist as the
    sibling singleton invariant).

Known evasion paths, accepted in v1:
  * Stored references — ``_now = datetime.now; _now()`` slips past
    because the call site is a bare ``Name`` with no import binding to
    ``datetime``.
  * Deeply chained attribute/call expressions where the leftmost base
    is itself a ``Call`` result rather than a ``Name`` (e.g.
    ``asyncio.get_event_loop().time()``) slip past for the same reason.
  Both patterns are vanishingly rare in real code; if they appear they
  are active evasion, and code review catches them.
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

# Shell modules: by-design owners of timestamping / clock semantics.
# Their entire job is to be the boundary where time enters the system.
# Forcing clock injection here would force every caller to thread a
# clock parameter for no testability gain.
SHELL_MODULES: frozenset[str] = frozenset(
    {
        # observability owns log timestamps + filename rotation per
        # docs/observability.md ("log_event handles path, rotation,
        # timestamp, and correlation ID").
        "shared/src/dirt_shared/observability.py",
        # voice.py: time boundary for session logs and audio clips
        # (same role observability plays for web/hwd).
        "voice/src/dirt_voice/channels/voice.py",
    }
)

# Directory exemptions: any file under one of these prefixes is skipped.
# Used for SQLModel schema files where ``default_factory=_utcnow`` is the
# idiomatic Python ORM pattern for DB-managed timestamps. The model
# layer is declarative; "what time was this row inserted" is a database
# concern, not a business-logic decision.
MODEL_DIRS: frozenset[str] = frozenset(
    {
        "shared/src/dirt_shared/models",
    }
)

# Fully-qualified call targets, *post-import-resolution*. Each entry
# corresponds to a real way a Python file can ask "what time is it now?"
# in a way that drives a *decision*. Duration-measurement primitives
# (``time.monotonic``, ``time.perf_counter``) are deliberately omitted —
# they show up only in ``started = monotonic(); ...; elapsed =
# monotonic() - started`` shapes that feed telemetry, not control flow.
BANNED_CLOCK_CALLS: frozenset[str] = frozenset(
    {
        # datetime module — `from datetime import datetime; datetime.now()`
        # resolves to "datetime.datetime.now" because `datetime` (the local)
        # binds to `datetime.datetime` (the class) per the import map below.
        "datetime.datetime.now",
        "datetime.datetime.utcnow",
        "datetime.datetime.today",
        "datetime.date.today",
        # `import datetime; datetime.now()` (atypical but possible) and
        # bare `now()` after `from datetime.datetime import now` (very rare).
        "datetime.now",
        "datetime.utcnow",
        "datetime.today",
        "date.today",
        # time module — only the wall-clock readers; not monotonic/perf_counter.
        "time.time",
        "time.process_time",
    }
)


def _resolve_call_target(func_node: ast.expr, imports: dict[str, str]) -> str:
    """Qualified name of a Call's target, resolving import aliases.

    Returns ``""`` when the leftmost base is not a ``Name`` (e.g. a Call
    result like ``foo().bar()``) — those are accepted evasion paths.
    """
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


def _collect_default_node_ids(tree: ast.Module) -> set[int]:
    """``id()``s of every AST node living inside any parameter default.

    Defaults are evaluated once at function-definition time, so a
    ``datetime.now(UTC)`` expression there is the production default for
    the injected clock — exactly the fix this invariant rewards.
    """
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            for default in (*node.args.defaults, *node.args.kw_defaults):
                if default is None:
                    continue
                for sub in ast.walk(default):
                    out.add(id(sub))
    return out


def _violations_in_file(py: Path) -> list[tuple[int, str]]:
    tree = ast.parse(py.read_text())
    imports = build_import_map(tree)
    default_ids = _collect_default_node_ids(tree)
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if id(node) in default_ids:
            continue
        target = _resolve_call_target(node.func, imports)
        if target in BANNED_CLOCK_CALLS:
            out.append((node.lineno, target))
    return out


@pytest.mark.parametrize("app", APPS)
def test_no_concrete_clock_in_production(app: str) -> None:
    """Production code must not call ``datetime.now()`` / ``time.time()`` inline."""
    pkg_dir = pkg_src_dir(app)
    assert pkg_dir.exists(), f"package dir missing: {pkg_dir}"

    violations: list[str] = []
    for py in iter_py(pkg_dir):
        rel = str(py.relative_to(APPS_ROOT))
        if rel in COMPOSITION_ROOTS or rel in SHELL_MODULES:
            continue
        if any(rel.startswith(d + "/") for d in MODEL_DIRS):
            continue
        for lineno, target in _violations_in_file(py):
            violations.append(f"apps/{rel}:{lineno}  {target}(...)")

    if violations:
        pytest.fail(
            format_invariant_failure(
                headline=(
                    f"{app}: {len(violations)} concrete clock read(s) "
                    "in production code"
                ),
                smell_name="Non-Deterministic Test / Hidden Time Dependency",
                citation=(
                    "Meszaros, xUnit Test Patterns; Bernhardt, 'Functional\n"
                    "   Core, Imperative Shell', 2012"
                ),
                body=(
                    "See this file's module docstring for the smell description\n"
                    "and the basic ``clock=`` callable-default pattern.\n\n"
                    "FIX — PREFERRED PATH (services): inject the clock on\n"
                    "``__init__`` and store ``self._clock``; thread it from the\n"
                    "composition root via ``build_core_services(clock=...)`` so\n"
                    "every service in the bundle reads from one source. Tests\n"
                    "pass a frozen clock at construction. Gold standards:\n"
                    "``SensorReader`` in daily_sensors.py, ``DailyReport`` in\n"
                    "daily_report.py, and the rest of app_wiring.py.\n\n"
                    "ANTI-PATTERN: do NOT add per-method ``now=None, today=None``\n"
                    "kwargs that fall back to ``datetime.now(UTC)`` inside the\n"
                    "body. That's a half-finished test seam — N fallbacks\n"
                    "scattered across the class instead of one clock stored on\n"
                    "the instance, and every caller has to remember the kwarg.\n\n"
                    "FIX — FREE FUNCTIONS / UTILITIES: a ``clock=`` kwarg with a\n"
                    "default IS the right shape; there's no ``self`` to hang the\n"
                    "clock off. Example: ``find_archivable_dates`` in archive.py.\n\n"
                    "FIX — SHELL MODULES: if the file's job is to BE the time\n"
                    "boundary (log filename rotation, audio clip filenames, the\n"
                    "process's session log), add it to ``SHELL_MODULES`` above\n"
                    "with a one-line WHY comment. observability.py and the voice\n"
                    "channel are the canonical examples."
                ),
                violations=violations,
            )
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
