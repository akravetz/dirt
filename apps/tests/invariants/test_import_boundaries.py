"""
INVARIANT TEST — HUMAN-OWNED

This test is protected by Codex hooks and MUST NOT be modified by
the agent. If it fails, the agent must fix the offending production code
to satisfy the contracts in ``import_boundaries.invariant.ini`` —
never modify the .ini file or this wrapper.

Architectural import boundaries are enforced by ``import-linter`` rather
than custom AST checks. The .ini config is the single source of truth
for "which package may import which". The seven contracts there encode:

  1. Five cross-package isolation rules (dirt_shared is pure; HW lives
     in dirt_hwd; web is the UI/API; mcp mounts into web; voice is its
     own process). Apps share state ONLY through the database or HTTP
     across process boundaries.
  2. Two API-layer rules (dirt_hwd.api and dirt_web.api may not reach
     past the service layer into dirt_shared.db / .models — sessions and
     model usage stay encapsulated in services).

Both the .ini file and this wrapper live in ``apps/tests/invariants/``,
the directory protected from agent edits.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

_CONFIG = Path(__file__).parent / "import_boundaries.invariant.ini"


def test_import_boundaries() -> None:
    """Run import-linter against the protected config; fail loudly on any broken contract."""
    assert _CONFIG.exists(), f"missing invariant config: {_CONFIG}"

    result = subprocess.run(
        ["lint-imports", "--config", str(_CONFIG)],
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        return

    pytest.fail(
        "\n=========================================================\n"
        "SMELL: Cross-package import boundary violation\n"
        "  (Hexagonal Architecture — Cockburn 2005;\n"
        "   ArchUnit-style fitness functions — Newman, _Building\n"
        "   Microservices_ ch. on coupling)\n"
        "=========================================================\n\n"
        "WHY this rule exists:\n"
        "  Each dirt-* package is a deployable unit with a clear\n"
        "  responsibility (dirt_hwd = hardware daemon; dirt_web = UI/API;\n"
        "  dirt_mcp = MCP server; dirt_voice = voice channel; dirt_shared\n"
        "  = pure, stateless code). Direct cross-app imports collapse\n"
        "  these units into one — a code change in dirt_hwd suddenly\n"
        "  affects dirt_web's deployment, the test isolation guarantees\n"
        "  break, and the package boundary becomes fiction. The api/*\n"
        "  layer rule has the same shape one level down: API routes are\n"
        "  HTTP edge code, services are business logic. If api reaches\n"
        "  past services into db/models directly, route handlers can\n"
        "  open ad-hoc sessions, bypass auth checks, and corrupt the\n"
        "  ingest invariants the service layer enforces.\n\n"
        "WHAT was detected (from import-linter):\n"
        f"{result.stdout}\n"
        f"{result.stderr if result.stderr.strip() else ''}\n"
        "HOW to fix:\n"
        "  - Cross-app violation: pull the shared logic into dirt_shared\n"
        "    (if it's pure / stateless), or call across the process\n"
        "    boundary via HTTP. Direct Python import of a peer app is\n"
        "    never the answer — even 'just one helper'.\n"
        "  - api/* → db/models violation: move the offending logic into\n"
        "    a service in dirt_shared.services (or dirt_hwd.services if\n"
        "    HW-owning). The api route should call the service function.\n\n"
        "DO NOT edit import_boundaries.invariant.ini or this test file.\n"
        "Both are HUMAN-OWNED and protected by Codex hooks. Fix\n"
        "the production code instead.\n"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
