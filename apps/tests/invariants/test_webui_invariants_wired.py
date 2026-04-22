"""Meta-invariant: web-ui/invariants/ is wired into the live tool configs.

HUMAN-OWNED. Do NOT modify to silence a failure — fix the shim at
``web-ui/eslint.config.ts`` / ``web-ui/tsconfig.json`` or the protected
rules at ``web-ui/invariants/**``.

The TypeScript lane stores its architectural rules under
``web-ui/invariants/`` (protected by the same Claude Code hook that guards
``apps/tests/invariants/``). The root-level ``web-ui/eslint.config.ts`` and
``web-ui/tsconfig.json`` are thin shims that import/extend the protected
files, leaving room for legitimate app-specific overrides (new path
aliases, per-slice rule exemptions) — but severity downgrades on
load-bearing rules must not survive silently.

This test proves three things:

1. **Wiring (AST / string).** The shims reference ``./invariants/``; the
   hook glob list in ``.claude/settings.json`` includes
   ``web-ui/invariants``.

2. **Live resolution (ESLint).** Running ``eslint --print-config`` against
   a real source file shows every rule in ``KNOWN_SENTINELS["eslint"]``
   resolved to severity ``error``. Catches downgrades from the shim or a
   malformed plugin import.

3. **Live resolution (TypeScript).** Running ``tsc --showConfig`` against
   the root tsconfig shows every flag in ``KNOWN_SENTINELS["tsconfig"]``
   set to its required value. Catches overrides in the shim that disable
   a strict flag.

Later TS-XX items append entries to ``KNOWN_SENTINELS`` as they land. The
sentinel set IS the invariant — the meta-invariant is tamper-evident
regardless of which surface the agent edits, because it asks the real
tools what the effective config is.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from ._helpers import format_invariant_failure

# apps/tests/invariants/test_webui_invariants_wired.py
#   → apps/tests/invariants/ → apps/tests/ → apps/ → repo root
REPO_ROOT: Path = Path(__file__).resolve().parents[3]
WEB_UI: Path = REPO_ROOT / "web-ui"
WEB_UI_INVARIANTS: Path = WEB_UI / "invariants"
ESLINT_SHIM: Path = WEB_UI / "eslint.config.ts"
TSCONFIG_SHIM: Path = WEB_UI / "tsconfig.json"
CLAUDE_SETTINGS: Path = REPO_ROOT / ".claude" / "settings.json"

# Rules and flags the meta-invariant asserts are live in the effective
# config. Appended by each TS-XX item's approach.
#   eslint:  rule-name -> required severity level (int, 2 == "error")
#   tsconfig: compilerOption-name -> required value
KNOWN_SENTINELS: dict[str, dict[str, object]] = {
    "eslint": {
        # TS-02 — layered architecture via eslint-plugin-boundaries.
        # Note: v6 renamed `element-types` -> `dependencies`. The legacy
        # name is a backward-compat alias that accepts the config shape
        # but evaluates as a no-op; use the new name so tamper checks
        # resolve against a rule that actually enforces.
        "boundaries/dependencies": 2,
        # TS-03 — ban training-data drift imports.
        "no-restricted-imports": 2,
        # TS-04 — ban enum / namespace / `as any`.
        "no-restricted-syntax": 2,
        "@typescript-eslint/no-explicit-any": 2,
        # TS-08 — no vi.mock() on internal modules (custom rule).
        "local/no-internal-vi-mock": 2,
    },
    "tsconfig": {
        # TS-01 — strict-mode flags.
        "strict": True,
        "noUncheckedIndexedAccess": True,
        "exactOptionalPropertyTypes": True,
        "noImplicitOverride": True,
        "noFallthroughCasesInSwitch": True,
    },
}

CITATION = (
    "web-ui/invariants/ is the TypeScript mirror of apps/tests/invariants/ — "
    "HUMAN-OWNED, hook-protected. Downgrading a rule in the shim trips this test."
)


def _pnpm_available() -> bool:
    return shutil.which("pnpm") is not None


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_protected_invariants_dir_exists() -> None:
    """``web-ui/invariants/`` and its scaffolded files must exist."""
    missing: list[Path] = []
    for required in (
        WEB_UI_INVARIANTS / "README.md",
        WEB_UI_INVARIANTS / "eslint.config.ts",
        WEB_UI_INVARIANTS / "tsconfig.base.json",
        WEB_UI_INVARIANTS / "knip.json",
        WEB_UI_INVARIANTS / "rules" / "README.md",
    ):
        if not required.exists():
            missing.append(required.relative_to(REPO_ROOT))
    if missing:
        raise AssertionError(
            format_invariant_failure(
                headline="web-ui/invariants/ scaffold is incomplete",
                smell_name="Missing Protected Invariant Surface",
                citation=CITATION,
                body=(
                    "WHY: Every TypeScript architectural rule lands inside "
                    "web-ui/invariants/. If the directory scaffold is gone, "
                    "downstream rules have no protected home.\n"
                    "FIX: Restore the files below from git history, or "
                    "re-run XX-02 in docs/progress/architectural-invariants-typescript.json."
                ),
                violations=[str(m) for m in missing],
            ),
        )


def _strip_line_comments(src: str) -> str:
    """Drop // line comments and /* ... */ block comments from TS source.

    Crude but sufficient: the shims are small, they don't contain
    string literals that look like comments.

    Line comments stripped FIRST. If block-comment stripping ran first,
    a `/**` appearing inside a `//` line comment (e.g. glob pattern
    documentation like `src/**/*.ts` in a file header) would combine
    with any later `*/` anywhere in the file — because the DOTALL
    block-comment regex matches across newlines — to eat real code
    spanning the two. Stripping line comments first neutralizes the
    `/**` before the block-comment regex runs.
    """
    src = re.sub(r"//[^\n]*", "", src)
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    return src


def test_eslint_shim_imports_invariants() -> None:
    """The root ESLint shim must import ``./invariants/eslint`` (not in a comment)."""
    assert ESLINT_SHIM.exists(), f"missing shim: {ESLINT_SHIM}"
    src = _strip_line_comments(ESLINT_SHIM.read_text())
    # Match a real ES import statement, not a comment / docstring. The
    # ESLint sentinel test below does the live verification via
    # `eslint --print-config`.
    import_pat = re.compile(
        r"""import\s+[^;]*?from\s+['"]\./invariants/eslint(?:\.config)?(?:\.ts)?['"]""",
    )
    if not import_pat.search(src):
        raise AssertionError(
            format_invariant_failure(
                headline="web-ui/eslint.config.ts no longer imports ./invariants/eslint",
                smell_name="Broken Invariant Wiring",
                citation=CITATION,
                body=(
                    "WHY: The shim is the only legitimate edit surface; if it "
                    "stops importing the protected config, architectural rules "
                    "vanish silently.\n"
                    'FIX: Restore `import invariants from "./invariants/eslint.config.ts"` '
                    "(or equivalent path) and spread it first in the exported array."
                ),
                violations=["import ./invariants/eslint NOT FOUND in shim"],
            ),
        )


def test_tsconfig_shim_extends_invariants_base() -> None:
    """The root tsconfig shim must ``extends`` ``./invariants/tsconfig.base.json``."""
    assert TSCONFIG_SHIM.exists(), f"missing shim: {TSCONFIG_SHIM}"
    src = TSCONFIG_SHIM.read_text()
    # Look for `"extends": "./invariants/tsconfig..."` specifically, not
    # just any occurrence of the path (comments also match a bare string
    # check, defeating the meta-invariant).
    extends_pat = re.compile(
        r'"extends"\s*:\s*"\./invariants/tsconfig(?:\.base)?(?:\.json)?"',
    )
    if not extends_pat.search(src):
        raise AssertionError(
            format_invariant_failure(
                headline="web-ui/tsconfig.json no longer extends ./invariants/tsconfig.base.json",
                smell_name="Broken Invariant Wiring",
                citation=CITATION,
                body=(
                    "WHY: Strict compilerOptions live in the protected base; "
                    "dropping the `extends` silently removes the type-system fence.\n"
                    'FIX: Restore `"extends": "./invariants/tsconfig.base.json"` '
                    "at the top of web-ui/tsconfig.json."
                ),
                violations=[
                    "extends ./invariants/tsconfig.base.json NOT FOUND in shim"
                ],
            ),
        )


def test_claude_hook_protects_webui_invariants() -> None:
    """``.claude/settings.json`` must reference ``web-ui/invariants``.

    The hook mechanism (see ``.claude/hooks/protect-invariants.sh``)
    reads this path glob when deciding whether to prompt on Edit/Write.
    """
    assert CLAUDE_SETTINGS.exists(), f"missing: {CLAUDE_SETTINGS}"
    src = CLAUDE_SETTINGS.read_text()
    if "web-ui/invariants" not in src:
        raise AssertionError(
            format_invariant_failure(
                headline=".claude/settings.json does not protect web-ui/invariants/",
                smell_name="Missing Hook Protection",
                citation=CITATION,
                body=(
                    "WHY: Without the hook glob, agents can silently Edit "
                    "web-ui/invariants/**. The directory is only 'human-owned' "
                    "if the harness enforces it.\n"
                    "FIX: Add `web-ui/invariants/**` to the hook deny-glob list "
                    "in .claude/settings.json (see XX-02 approach)."
                ),
                violations=["web-ui/invariants NOT FOUND in .claude/settings.json"],
            ),
        )


@pytest.mark.skipif(not _pnpm_available(), reason="pnpm not installed")
def test_tsc_showconfig_sentinels() -> None:
    """``tsc --showConfig`` must show every sentinel compilerOption at its required value.

    Asserts the shim's extends wiring actually flows strict flags through.
    Empty sentinel map (pre-TS-01) → trivially passes; items that append
    to ``KNOWN_SENTINELS["tsconfig"]`` start checking automatically.
    """
    sentinels: dict[str, object] = KNOWN_SENTINELS["tsconfig"]  # type: ignore[assignment]
    if not sentinels:
        return
    proc = _run(
        ["pnpm", "exec", "tsc", "--showConfig"],
        cwd=WEB_UI,
    )
    if proc.returncode != 0:
        raise AssertionError(
            format_invariant_failure(
                headline="tsc --showConfig failed",
                smell_name="Broken tsconfig Shim",
                citation=CITATION,
                body=(
                    "WHY: The shim must produce a resolvable tsconfig.\n"
                    "FIX: Inspect stderr below; most likely a malformed "
                    "extends path or JSON syntax error."
                ),
                violations=[f"stderr: {proc.stderr.strip() or '(empty)'}"],
            ),
        )
    config = json.loads(proc.stdout)
    compiler_options = config.get("compilerOptions", {})
    violations: list[str] = []
    for flag, expected in sentinels.items():
        actual = compiler_options.get(flag)
        if actual != expected:
            violations.append(f"{flag}: expected {expected!r}, got {actual!r}")
    if violations:
        raise AssertionError(
            format_invariant_failure(
                headline=f"tsconfig sentinel check failed ({len(violations)} mismatch)",
                smell_name="Silent Strictness Downgrade",
                citation=CITATION,
                body=(
                    "WHY: One or more strict compilerOptions are not set in the "
                    "effective tsconfig. Likely the shim overrode a protected "
                    "flag.\n"
                    "FIX: Remove the override from web-ui/tsconfig.json, or "
                    "restore the flag in web-ui/invariants/tsconfig.base.json."
                ),
                violations=violations,
            ),
        )


@pytest.mark.skipif(not _pnpm_available(), reason="pnpm not installed")
def test_eslint_printconfig_sentinels() -> None:
    """``eslint --print-config`` must resolve every sentinel rule to severity=error.

    Empty sentinel map (pre-TS-02..) → trivially passes.
    """
    sentinels: dict[str, object] = KNOWN_SENTINELS["eslint"]  # type: ignore[assignment]
    if not sentinels:
        return
    # Pick a real source file so flat-config's `files` filter resolves.
    target = WEB_UI / "src" / "main.tsx"
    proc = _run(
        ["pnpm", "exec", "eslint", "--print-config", str(target)],
        cwd=WEB_UI,
    )
    if proc.returncode != 0:
        raise AssertionError(
            format_invariant_failure(
                headline="eslint --print-config failed",
                smell_name="Broken ESLint Shim",
                citation=CITATION,
                body=(
                    "WHY: The shim must produce a resolvable ESLint config.\n"
                    "FIX: Inspect stderr below; most likely a malformed "
                    "import path, missing plugin, or TS parse error in the shim."
                ),
                violations=[f"stderr: {proc.stderr.strip() or '(empty)'}"],
            ),
        )
    # eslint --print-config may prepend warnings; take the last valid JSON object
    # by scanning from the first '{' on a line of its own.
    stdout = proc.stdout
    first_brace = stdout.find("{")
    if first_brace < 0:
        raise AssertionError(f"no JSON in eslint --print-config output: {stdout!r}")
    config = json.loads(stdout[first_brace:])
    rules = config.get("rules", {})
    violations: list[str] = []
    for rule_name, required_severity in sentinels.items():
        raw = rules.get(rule_name)
        if raw is None:
            violations.append(f"{rule_name}: rule not present in effective config")
            continue
        # ESLint normalizes: rule can be ['error', {...}] or 2, etc.
        severity = raw[0] if isinstance(raw, list) and raw else raw
        # Severity: 0/"off", 1/"warn", 2/"error"
        severity_int = {"off": 0, "warn": 1, "error": 2}.get(
            severity if isinstance(severity, str) else "",
            severity if isinstance(severity, int) else -1,
        )
        if severity_int != required_severity:
            violations.append(
                f"{rule_name}: expected severity={required_severity}, "
                f"got {severity!r} (normalized {severity_int})",
            )
    if violations:
        raise AssertionError(
            format_invariant_failure(
                headline=f"ESLint sentinel check failed ({len(violations)} mismatch)",
                smell_name="Silent Rule Downgrade",
                citation=CITATION,
                body=(
                    "WHY: One or more architectural rules resolve below error "
                    "severity. Likely the shim contains an override that "
                    "turned a protected rule off or down.\n"
                    "FIX: Remove the override from web-ui/eslint.config.ts, or "
                    "restore severity in web-ui/invariants/eslint.config.ts."
                ),
                violations=violations,
            ),
        )
