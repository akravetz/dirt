"""
INVARIANT TEST — HUMAN-OWNED

This test is protected by Claude Code hooks and MUST NOT be modified by
the agent. If this test fails, the agent must fix its code to satisfy
the test, never modify this file.

Purpose: Enforce that the dirt_web FastAPI app stays in lockstep with
the frozen OpenAPI contract at ``contracts/webapp-v1.yaml``.

Three assertions:

1. **Spec ⊆ App**: Every (path, method) declared in the spec is either
   served by the app OR marked as `expected_missing` in
   ``contract_status.json`` (a Phase 2 feature that hasn't shipped yet).
   The expected-missing table shrinks monotonically as features land —
   entries that are no longer missing cause a "falsely missing" failure.

2. **App ⊆ Spec**: Every non-framework, non-legacy route in the app
   appears in the spec. The ``legacy_routes`` table in
   ``contract_status.json`` holds the pre-rewrite HTML / HTMX endpoints
   that exist today and will be deleted in Phase 2. Adding a new route
   without updating the spec fails this check.

3. **Models import**: The generated Pydantic models from
   ``dirt_contracts.webapp_v1.models`` import cleanly. This catches drift
   between the YAML and the generator output (regenerate with
   ``scripts/gen-contract``).

Phase 2 endpoint round-trip checks (call the endpoint, parse JSON with
the generated model) are added per-feature when the corresponding entry
is removed from expected_missing.

Note on data-vs-logic split: the two shrinking tables (expected_missing,
legacy_routes) live in the sibling ``contract_status.json`` data file,
which is NOT human-owned — agents flip entries there as features land
without tripping the protect-invariants hook. Test logic stays here and
stays sacred.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

CONTRACT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "webapp-v1.yaml"
STATUS_PATH = Path(__file__).resolve().parent / "contract_status.json"

# FastAPI framework-generated paths — not part of the application contract.
FRAMEWORK_PATHS = frozenset(
    {
        "/openapi.json",
        "/docs",
        "/docs/oauth2-redirect",
        "/redoc",
    }
)

# Mounts whose paths are NOT covered by webapp-v1.yaml. The MCP mount has its
# own bearer-auth contract (test_hwd_routes / dirt_mcp tests). Sensor ingest
# lives on dirt_hwd, not dirt_web, but the mount could in principle be added
# here in the future.
EXEMPT_PATH_PREFIXES = ("/mcp",)

# Loaded once at import time from contract_status.json. The agent-editable
# data file holds the two shrinking tables; this module only owns the test
# logic that reads them.
_VALID_METHODS = frozenset({"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"})


def _parse_endpoint_key(key: str) -> tuple[str, str]:
    """Split 'METHOD /path' → ('/path', 'METHOD'). Loud failure on bad shape.

    The key format mirrors how OpenAPI displays operations and how curl
    would invoke them, so contract_status.json reads naturally. We
    normalize back to (path, method) tuples for set arithmetic against
    the spec/app endpoint pairs.
    """
    parts = key.split(" ", 1)
    if len(parts) != 2:
        raise ValueError(
            f"contract_status.json: bad endpoint key {key!r}; "
            f"expected 'METHOD /path' (e.g. 'GET /api/grow/current')"
        )
    method, path = parts[0].upper(), parts[1]
    if method not in _VALID_METHODS:
        raise ValueError(
            f"contract_status.json: unknown method {method!r} in key {key!r}"
        )
    if not path.startswith("/"):
        raise ValueError(f"contract_status.json: path must start with / in key {key!r}")
    return (path, method)


def _load_status() -> tuple[dict[tuple[str, str], str], dict[tuple[str, str], str]]:
    """Load + validate contract_status.json. Returns (expected_missing, legacy_routes).

    Each table maps (path, method) → string note. expected_missing's
    note is a plan-JSON feature_id (must be dotted); legacy_routes'
    note is free-form prose explaining what replaces the legacy route.
    """
    with STATUS_PATH.open() as fh:
        raw = json.load(fh)

    def _section(name: str) -> dict[tuple[str, str], str]:
        section = raw.get(name, {})
        if not isinstance(section, dict):
            raise TypeError(f"contract_status.json[{name!r}] must be an object")
        return {
            _parse_endpoint_key(k): v
            for k, v in section.items()
            if not k.startswith("$")
        }

    return _section("expected_missing"), _section("legacy_routes")


EXPECTED_MISSING, LEGACY_ROUTES = _load_status()


def _load_spec() -> dict:
    with CONTRACT_PATH.open() as fh:
        return yaml.safe_load(fh)


def _spec_endpoints(spec: dict) -> frozenset[tuple[str, str]]:
    """All (path, METHOD) tuples declared in the OpenAPI paths section."""
    pairs: set[tuple[str, str]] = set()
    for path, ops in spec.get("paths", {}).items():
        for method in ops:
            mu = method.upper()
            if mu in _VALID_METHODS:
                pairs.add((path, mu))
    return frozenset(pairs)


def _app_endpoints() -> frozenset[tuple[str, str]]:
    """All (path, METHOD) pairs the dirt-web app actually serves.

    Mount prefixes in EXEMPT_PATH_PREFIXES are dropped (MCP carries its
    own bearer-auth contract). Framework paths (`/openapi.json`, `/docs`)
    are dropped.
    """
    from dirt_web.app import create_app

    app = create_app(run_mcp=False)
    pairs: set[tuple[str, str]] = set()
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if path is None or methods is None:
            continue
        if path in FRAMEWORK_PATHS:
            continue
        if any(path.startswith(p) for p in EXEMPT_PATH_PREFIXES):
            continue
        for method in methods:
            mu = method.upper()
            # Starlette adds HEAD for every GET — collapse them.
            if mu == "HEAD":
                continue
            pairs.add((path, mu))
    return frozenset(pairs)


@pytest.fixture(scope="module")
def spec() -> dict:
    return _load_spec()


@pytest.fixture(scope="module")
def spec_endpoints(spec: dict) -> frozenset[tuple[str, str]]:
    return _spec_endpoints(spec)


@pytest.fixture(scope="module")
def app_endpoints() -> frozenset[tuple[str, str]]:
    return _app_endpoints()


def test_contract_is_loadable(spec: dict) -> None:
    """The YAML parses and looks like an OpenAPI 3.1 doc with a paths section."""
    assert spec.get("openapi", "").startswith("3."), (
        f"contracts/webapp-v1.yaml has unexpected openapi version: {spec.get('openapi')!r}"
    )
    assert spec.get("paths"), "OpenAPI doc has no paths"
    assert spec.get("components", {}).get("schemas"), (
        "OpenAPI doc has no components.schemas section"
    )


def test_generated_pydantic_models_import() -> None:
    """The generated Pydantic models import cleanly.

    Catches drift between the YAML and the codegen output. Regenerate
    with ``scripts/gen-contract`` if this fails.
    """
    from dirt_contracts.webapp_v1 import models

    # Spot-check a few load-bearing schemas to catch upstream renames
    # without enumerating everything.
    for name in (
        "GrowCurrent",
        "SensorsCurrent",
        "HumidifierState",
        "PlantsResponse",
        "PlantDetail",
        "PTZState",
        "WikiFile",
        "WikiSearchResponse",
        "ErrorDetail",
    ):
        assert hasattr(models, name), (
            f"generated models module is missing {name}; "
            f"contract / codegen drift — re-run scripts/gen-contract"
        )


def test_spec_subset_of_app(
    spec_endpoints: frozenset[tuple[str, str]],
    app_endpoints: frozenset[tuple[str, str]],
) -> None:
    """Every spec endpoint exists in the app OR is in EXPECTED_MISSING.

    A spec endpoint that's neither implemented nor expected-missing is
    contract drift — either implement it, or add it to EXPECTED_MISSING
    with a feature id (which means the human plans to implement it).
    """
    unaccounted = []
    for endpoint in sorted(spec_endpoints):
        if endpoint in app_endpoints:
            continue
        if endpoint in EXPECTED_MISSING:
            continue
        unaccounted.append(endpoint)

    assert not unaccounted, (
        "Contract endpoints with no implementation and no EXPECTED_MISSING entry:\n"
        + "\n".join(f"  {m} {p}" for p, m in unaccounted)
        + "\nEither implement these in dirt_web, or add them to EXPECTED_MISSING."
    )


def test_expected_missing_entries_are_actually_missing(
    app_endpoints: frozenset[tuple[str, str]],
) -> None:
    """EXPECTED_MISSING shrinks monotonically. Any entry that's now served
    by the app must be removed from the table — leaving it stale lets
    contract drift accumulate silently."""
    falsely_missing = [ep for ep in EXPECTED_MISSING if ep in app_endpoints]
    assert not falsely_missing, (
        "These endpoints are listed in EXPECTED_MISSING but the app actually serves them. "
        "Remove them from EXPECTED_MISSING in apps/tests/invariants/test_api_contract.py:\n"
        + "\n".join(f"  {m} {p}" for p, m in falsely_missing)
    )


def test_app_subset_of_spec(
    spec_endpoints: frozenset[tuple[str, str]],
    app_endpoints: frozenset[tuple[str, str]],
) -> None:
    """Every app route is in the spec OR is a known legacy route.

    Adding a new endpoint without updating the contract fails here.
    Phase 2 generators must update contracts/webapp-v1.yaml + run
    scripts/gen-contract before exposing a new route.
    """
    extras = []
    for endpoint in sorted(app_endpoints):
        if endpoint in spec_endpoints:
            continue
        if endpoint in LEGACY_ROUTES:
            continue
        extras.append(endpoint)

    assert not extras, (
        "App routes not in webapp-v1.yaml and not on the legacy-deprecation list:\n"
        + "\n".join(f"  {m} {p}" for p, m in extras)
        + "\nUpdate contracts/webapp-v1.yaml + run scripts/gen-contract."
    )


def test_legacy_routes_still_present(
    app_endpoints: frozenset[tuple[str, str]],
) -> None:
    """Legacy routes that are still in the LEGACY_ROUTES allowlist must
    still exist on the app — once a generator deletes one, the
    corresponding LEGACY_ROUTES entry must be removed too. Stale entries
    let the deprecation list mask real coverage gaps."""
    stale_legacy = [ep for ep in LEGACY_ROUTES if ep not in app_endpoints]
    assert not stale_legacy, (
        "These entries are in LEGACY_ROUTES but the app no longer serves them. "
        "Remove them from LEGACY_ROUTES in apps/tests/invariants/test_api_contract.py:\n"
        + "\n".join(f"  {m} {p}" for p, m in stale_legacy)
    )


@pytest.mark.parametrize(
    "endpoint",
    sorted(EXPECTED_MISSING.keys()),
    ids=lambda ep: f"{ep[1]}_{ep[0]}",
)
def test_expected_missing_endpoint_has_feature_id(
    endpoint: tuple[str, str],
) -> None:
    """Every EXPECTED_MISSING entry maps to a non-empty feature id (which
    must match a feature in docs/plans/webapp-rewrite.json once the plan
    JSON exists). Empty/None values mean the human forgot to plan it."""
    feature_id = EXPECTED_MISSING[endpoint]
    assert feature_id, f"EXPECTED_MISSING[{endpoint!r}] has empty feature_id"
    assert "." in feature_id, (
        f"feature_id {feature_id!r} should be dotted (e.g. 'backend.sensors.current')"
    )
