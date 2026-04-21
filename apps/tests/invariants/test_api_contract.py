"""
INVARIANT TEST — HUMAN-OWNED

This test is protected by Claude Code hooks and MUST NOT be modified by
the agent. If this test fails, the agent must fix its code to satisfy
the test, never modify this file.

Purpose: Enforce that the dirt_web FastAPI app stays in lockstep with
the frozen OpenAPI contract at ``contracts/webapp-v1.yaml``.

Three assertions:

1. **Spec ⊆ App**: Every (path, method) declared in the spec is either
   served by the app OR marked as `EXPECTED_MISSING` (a Phase 2 feature
   that hasn't shipped yet). The expected-missing table shrinks
   monotonically as features land — entries that are no longer missing
   cause an `xpassed` failure.

2. **App ⊆ Spec**: Every non-framework, non-legacy route in the app
   appears in the spec. The `LEGACY_ROUTES` table holds the pre-rewrite
   HTML / HTMX endpoints that exist today and will be deleted in Phase 2.
   Adding a new route without updating the spec fails this check.

3. **Models import**: The generated Pydantic models from
   ``dirt_contracts.webapp_v1.models`` import cleanly. This catches drift
   between the YAML and the generator output (regenerate with
   ``scripts/gen-contract``).

Phase 2 endpoint round-trip checks (call the endpoint, parse JSON with
the generated model) are added per-feature when the corresponding entry
is removed from EXPECTED_MISSING.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

CONTRACT_PATH = Path(__file__).resolve().parents[3] / "contracts" / "webapp-v1.yaml"

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

# Pre-rewrite HTML/HTMX endpoints that exist today. Phase 2 generators
# DELETE these as the SPA replaces them. The set must shrink to empty by
# the end of Phase 2; do not extend it.
LEGACY_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        ("/", "GET"),  # Jinja dashboard — replaced by SPA shell
        ("/login", "GET"),  # Jinja login page — replaced by SPA /login route
        ("/login", "POST"),  # form-post — replaced by /api/auth/login
        ("/logout", "GET"),  # 302 redirect — replaced by /api/auth/logout
        ("/feed/live", "GET"),  # renamed to /api/feed/live.jpg
        ("/feed/image", "GET"),  # HTMX fragment — deleted
        ("/feed/status", "GET"),  # HTMX fragment — deleted
        ("/sensors/current", "GET"),  # HTMX fragment — replaced by JSON
        ("/api/sensors/readings", "GET"),  # renamed to /api/sensors/history
        ("/api/snapshots/latest", "GET"),  # renamed to /api/feed/snapshot/latest
    }
)

# Contract endpoints not yet implemented in the app. Each entry maps to
# the plan-JSON feature id that will deliver it. The Phase 2 evaluator
# removes entries here as features land. An entry that's already
# implemented produces an `xpassed` failure (strict).
EXPECTED_MISSING: dict[tuple[str, str], str] = {
    ("/api/auth/login", "POST"): "backend.auth",
    ("/api/auth/logout", "POST"): "backend.auth",
    ("/api/auth/me", "GET"): "backend.auth",
    ("/api/grow/current", "GET"): "backend.grow.current",
    ("/api/sensors/current", "GET"): "backend.sensors.current",
    ("/api/sensors/history", "GET"): "backend.sensors.history",
    ("/api/humidifier/state", "GET"): "backend.humidifier.state",
    ("/api/humidifier/history", "GET"): "backend.humidifier.history",
    ("/api/plants", "GET"): "backend.plants.list",
    ("/api/plants/{code}", "GET"): "backend.plants.detail",
    ("/api/plants/{code}/moisture", "GET"): "backend.plants.moisture",
    ("/api/system/devices", "GET"): "backend.system.devices",
    ("/api/feed/live.jpg", "GET"): "backend.feed.live",
    ("/api/feed/snapshot/latest", "GET"): "backend.feed.snapshot",
    ("/api/ptz/state", "GET"): "backend.ptz.state",
    ("/api/ptz/preset/{id}", "POST"): "backend.ptz.preset",
    ("/api/ptz/look", "POST"): "backend.ptz.look",
    ("/api/ptz/zoom", "POST"): "backend.ptz.zoom",
    ("/api/wiki/tree", "GET"): "backend.wiki.tree",
    ("/api/wiki/file", "GET"): "backend.wiki.file",
    ("/api/wiki/search", "GET"): "backend.wiki.search",
}


def _load_spec() -> dict:
    with CONTRACT_PATH.open() as fh:
        return yaml.safe_load(fh)


def _spec_endpoints(spec: dict) -> frozenset[tuple[str, str]]:
    """All (path, METHOD) tuples declared in the OpenAPI paths section."""
    pairs: set[tuple[str, str]] = set()
    valid_methods = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
    for path, ops in spec.get("paths", {}).items():
        for method in ops:
            mu = method.upper()
            if mu in valid_methods:
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
