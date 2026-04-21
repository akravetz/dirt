"""Invariant: knip reports no unused files / exports / dependencies in web-ui/.

HUMAN-OWNED. Do NOT modify the test; fix the dead code instead.

TypeScript-side analogue of PY-02 (deptry) on the Python side. Agents
leave behind stray exports + unused deps after every refactor; knip
catches both in one pass so the CI signal is immediate and cheap.

The Python test is a thin shell-out wrapper: it runs
``pnpm --dir web-ui knip --no-progress`` and asserts exit 0. The real
rules live in ``web-ui/invariants/knip.json`` (hook-protected).
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from ._helpers import format_invariant_failure

REPO_ROOT: Path = Path(__file__).resolve().parents[3]
WEB_UI: Path = REPO_ROOT / "web-ui"
KNIP_CONFIG: Path = WEB_UI / "invariants" / "knip.json"


def _pnpm_available() -> bool:
    return shutil.which("pnpm") is not None


@pytest.mark.skipif(not _pnpm_available(), reason="pnpm not installed")
def test_no_unused_files_exports_or_deps() -> None:
    assert KNIP_CONFIG.exists(), f"missing: {KNIP_CONFIG}"
    proc = subprocess.run(
        ["pnpm", "--dir", str(WEB_UI), "knip", "--no-progress"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        # knip prints a terse, agent-readable report to stdout.
        violations = [line for line in proc.stdout.splitlines() if line.strip()]
        raise AssertionError(
            format_invariant_failure(
                headline="knip reports unused code in web-ui/",
                smell_name="Dead TypeScript Code",
                citation=(
                    "web-ui/invariants/knip.json pins the expected entry "
                    "points + project globs. Unused exports / files / deps "
                    "accumulate after refactors; knip catches them in one pass."
                ),
                body=(
                    "WHY: dead code confuses future readers and inflates the "
                    "bundle; unused deps inflate install time.\n"
                    "FIX: delete the flagged exports / files / deps, or — if "
                    "genuinely needed — add the correct entry pattern in "
                    "web-ui/invariants/knip.json (the config is HUMAN-OWNED; "
                    "escape hatches require human review)."
                ),
                violations=violations or [f"knip exit {proc.returncode}"],
            ),
        )
