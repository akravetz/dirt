"""
INVARIANT TEST - HUMAN-OWNED

This test is protected by Codex hooks and MUST NOT be modified by
the agent without explicit human approval. If this test fails, fix the
browser API shape by moving DTOs to ``dirt_control.api.browser_schemas``
or query/model access to ``dirt_control.services``; do not weaken the rule.

Purpose: browser API route modules are HTTP boundary adapters. The package
aggregate only composes feature routers, route modules declare explicit
FastAPI response models, DTO classes live in the browser schema package,
and route modules do not build SQLAlchemy statements directly.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from ._helpers import (
    APPS_ROOT,
    build_import_map,
    format_invariant_failure,
    iter_py,
    pkg_src_dir,
)

BROWSER_API_DIR: Path = pkg_src_dir("dirt_control") / "api" / "browser"
BROWSER_AGGREGATE_MODULE: Path = BROWSER_API_DIR / "__init__.py"

PATH_OPERATION_METHODS: frozenset[str] = frozenset(
    {"get", "post", "put", "patch", "delete", "options", "head", "trace", "api_route"}
)
ROUTE_REGISTRATION_METHODS: frozenset[str] = PATH_OPERATION_METHODS | frozenset(
    {"add_api_route"}
)
SQLALCHEMY_BUILDER_NAMES: frozenset[str] = frozenset(
    {"select", "insert", "update", "delete"}
)


def _read_tree(py: Path) -> ast.Module:
    return ast.parse(py.read_text())


def _rel_path(py: Path) -> str:
    return f"apps/{py.relative_to(APPS_ROOT)}"


def _browser_route_modules() -> list[Path]:
    return sorted(py for py in iter_py(BROWSER_API_DIR) if py.name != "__init__.py")


def _resolve_expr_name(node: ast.expr, imports: dict[str, str]) -> str | None:
    if isinstance(node, ast.Name):
        return imports.get(node.id, node.id)
    if isinstance(node, ast.Attribute):
        base = _resolve_expr_name(node.value, imports)
        return f"{base}.{node.attr}" if base is not None else node.attr
    if isinstance(node, ast.Subscript):
        return _resolve_expr_name(node.value, imports)
    return None


def _router_names(tree: ast.Module) -> set[str]:
    imports = build_import_map(tree)
    router_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_apirouter_call(node.value, imports):
            router_names.update(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and _is_apirouter_call(node.value, imports)
        ):
            router_names.add(node.target.id)
    return router_names


def _is_apirouter_call(node: ast.expr | None, imports: dict[str, str]) -> bool:
    if not isinstance(node, ast.Call):
        return False
    return _resolve_expr_name(node.func, imports) == "fastapi.APIRouter"


def _router_operation_call(
    node: ast.expr,
    *,
    router_names: set[str],
    methods: frozenset[str],
) -> ast.Call | None:
    if not isinstance(node, ast.Call):
        return None
    if not isinstance(node.func, ast.Attribute) or node.func.attr not in methods:
        return None
    if not isinstance(node.func.value, ast.Name):
        return None
    if node.func.value.id not in router_names:
        return None
    return node


def _router_operation_calls(
    tree: ast.Module,
    *,
    router_names: set[str],
    methods: frozenset[str],
) -> list[tuple[int, str, ast.Call]]:
    operations: list[tuple[int, str, ast.Call]] = []
    for node in ast.walk(tree):
        call = _router_operation_call(node, router_names=router_names, methods=methods)
        if call is not None:
            operations.append((call.lineno, call.func.attr, call))
    return operations


def _has_response_model_keyword(call: ast.Call) -> bool:
    return any(keyword.arg == "response_model" for keyword in call.keywords)


def _pydantic_dto_classes(py: Path) -> list[tuple[int, str, str]]:
    tree = _read_tree(py)
    imports = build_import_map(tree)
    violations: list[tuple[int, str, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for base in node.bases:
            base_name = _resolve_expr_name(base, imports)
            if base_name is not None and _is_pydantic_dto_base(base_name):
                violations.append((node.lineno, node.name, base_name))
                break

    return violations


def _is_pydantic_dto_base(base_name: str) -> bool:
    return (
        base_name == "pydantic.BaseModel"
        or base_name.startswith("dirt_control.api.browser_schemas.")
        or base_name == "dirt_shared.cloud_contract.CloudContractModel"
        or (
            base_name.startswith("dirt_shared.cloud_contract.")
            and base_name.endswith("Payload")
        )
    )


def _sqlalchemy_builder_calls(py: Path) -> list[tuple[int, str]]:
    tree = _read_tree(py)
    imports = build_import_map(tree)
    violations: list[tuple[int, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        call_name = _resolve_expr_name(node.func, imports)
        if call_name is not None and _is_sqlalchemy_builder_call(call_name):
            violations.append((node.lineno, call_name))

    return violations


def _is_sqlalchemy_builder_call(call_name: str) -> bool:
    if not call_name.startswith("sqlalchemy."):
        return False
    return call_name.rsplit(".", maxsplit=1)[-1] in SQLALCHEMY_BUILDER_NAMES


def _class_lineno(py: Path, class_name: str) -> int:
    tree = _read_tree(py)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            return node.lineno
    return 1


def test_browser_aggregate_only_includes_feature_routers() -> None:
    """The browser package aggregate composes routers; it defines no routes."""
    assert BROWSER_AGGREGATE_MODULE.exists(), (
        f"browser aggregate module missing: {BROWSER_AGGREGATE_MODULE}"
    )

    tree = _read_tree(BROWSER_AGGREGATE_MODULE)
    router_names = _router_names(tree)
    violations: list[str] = []

    for lineno, method, _call in _router_operation_calls(
        tree,
        router_names=router_names,
        methods=ROUTE_REGISTRATION_METHODS,
    ):
        violations.append(
            f"{_rel_path(BROWSER_AGGREGATE_MODULE)}:{lineno}  "
            f"uses router.{method}(...) in the aggregate module"
        )

    if violations:
        pytest.fail(
            format_invariant_failure(
                headline=(
                    "dirt_control.api.browser: aggregate module defines browser "
                    "path operation(s)"
                ),
                smell_name="Mixed Composition Root / HTTP Adapter",
                citation=(
                    "Cockburn, Hexagonal Architecture; Fowler, _Patterns of\n"
                    "   Enterprise Application Architecture_ - Service Layer"
                ),
                body=(
                    "WHY this rule exists:\n"
                    "  dirt_control.api.browser.__init__ is the browser router\n"
                    "  aggregate. It should create the /api APIRouter and include\n"
                    "  focused feature routers only. Putting path operations in\n"
                    "  the aggregate re-creates the old browser mega-module.\n\n"
                    "FIX:\n"
                    "  Move the route handler to the appropriate feature module\n"
                    "  under apps/control-plane/src/dirt_control/api/browser/ and\n"
                    "  include that feature router from the aggregate."
                ),
                violations=violations,
            )
        )


def test_browser_route_modules_do_not_define_pydantic_dtos() -> None:
    """Browser request/response DTO classes live in browser_schemas."""
    violations: list[str] = []

    for py in _browser_route_modules():
        for lineno, class_name, base_name in _pydantic_dto_classes(py):
            violations.append(
                f"{_rel_path(py)}:{lineno}  class {class_name}({base_name})"
            )

    if violations:
        pytest.fail(
            format_invariant_failure(
                headline=(
                    "dirt_control.api.browser: Pydantic DTO class(es) defined "
                    "inside browser route modules"
                ),
                smell_name="Schema/Route Boundary Collapse",
                citation=(
                    "Cockburn, Hexagonal Architecture; Evans, _Domain-Driven\n"
                    "   Design_ - Explicit Boundaries"
                ),
                body=(
                    "WHY this rule exists:\n"
                    "  Browser route modules should be HTTP adapters. Defining\n"
                    "  request or response DTO classes next to handlers hides the\n"
                    "  browser contract and makes generated OpenAPI shape drift\n"
                    "  harder to review.\n\n"
                    "FIX:\n"
                    "  Move the DTO class to a focused module under\n"
                    "  apps/control-plane/src/dirt_control/api/browser_schemas/.\n"
                    "  Import the schema into the route module and keep the route\n"
                    "  handler focused on dependencies, service calls, and returns."
                ),
                violations=violations,
            )
        )


def test_browser_route_modules_do_not_build_sqlalchemy_statements() -> None:
    """Browser routes call services instead of constructing SQLAlchemy queries."""
    violations: list[str] = []

    for py in _browser_route_modules():
        for lineno, call_name in _sqlalchemy_builder_calls(py):
            violations.append(f"{_rel_path(py)}:{lineno}  calls {call_name}(...)")

    if violations:
        pytest.fail(
            format_invariant_failure(
                headline=(
                    "dirt_control.api.browser: SQLAlchemy statement builder "
                    "call(s) in browser route modules"
                ),
                smell_name="Leaky HTTP Boundary / Inline Data Access",
                citation=(
                    "Cockburn, Hexagonal Architecture; Fowler, _Patterns of\n"
                    "   Enterprise Application Architecture_ - Service Layer"
                ),
                body=(
                    "WHY this rule exists:\n"
                    "  Browser route modules are not the data layer. Direct\n"
                    "  select/insert/update/delete calls let handlers bypass the\n"
                    "  focused service modules that own transaction shape, auth\n"
                    "  checks, and projection rules. The Milestone 7 import\n"
                    "  invariant separately blocks direct dirt_control.models and\n"
                    "  SQLAlchemy imports from this package.\n\n"
                    "FIX:\n"
                    "  Move query construction into a focused module under\n"
                    "  apps/control-plane/src/dirt_control/services/ and call that\n"
                    "  service from the browser route handler."
                ),
                violations=violations,
            )
        )


def test_browser_routes_declare_explicit_response_models() -> None:
    """Every browser route registration must spell out response_model."""
    violations: list[str] = []

    for py in _browser_route_modules():
        tree = _read_tree(py)
        router_names = _router_names(tree)
        for lineno, method, call in _router_operation_calls(
            tree,
            router_names=router_names,
            methods=ROUTE_REGISTRATION_METHODS,
        ):
            if not _has_response_model_keyword(call):
                violations.append(
                    f"{_rel_path(py)}:{lineno}  router.{method}(...) "
                    "omits response_model=..."
                )

    if violations:
        pytest.fail(
            format_invariant_failure(
                headline=(
                    "dirt_control.api.browser: browser route(s) without explicit "
                    "response_model"
                ),
                smell_name="Implicit Boundary Contract",
                citation=(
                    "Fowler, _Patterns of Enterprise Application Architecture_ -\n"
                    "   Service Layer; FastAPI response model documentation"
                ),
                body=(
                    "WHY this rule exists:\n"
                    "  The hosted browser contract is generated from FastAPI\n"
                    "  OpenAPI. Every browser route must declare the response\n"
                    "  schema at registration so a route cannot silently drift to\n"
                    "  an inferred or untyped response. The 204 logout route is\n"
                    "  valid because it explicitly says response_model=None.\n\n"
                    "FIX:\n"
                    "  Add response_model=<BrowserResponseDTO> to the route\n"
                    "  decorator, or response_model=None only for a deliberate\n"
                    "  no-body response such as HTTP 204."
                ),
                violations=violations,
            )
        )


def test_browser_schema_bases_forbid_extra_fields() -> None:
    """Browser-owned request and response bases reject unknown JSON fields."""
    common = importlib.import_module("dirt_control.api.browser_schemas.common")
    common_path = Path(common.__file__)
    violations: list[str] = []

    for class_name in ("BrowserRequest", "BrowserResponse"):
        cls = getattr(common, class_name, None)
        lineno = _class_lineno(common_path, class_name)
        if cls is None:
            violations.append(
                f"{_rel_path(common_path)}:{lineno}  missing {class_name}"
            )
            continue
        extra = getattr(cls, "model_config", {}).get("extra")
        if extra != "forbid":
            violations.append(
                f"{_rel_path(common_path)}:{lineno}  {cls.__module__}.{class_name}  "
                f"model_config extra is {extra!r}; expected 'forbid'"
            )

    if violations:
        pytest.fail(
            format_invariant_failure(
                headline=(
                    "dirt_control.api.browser_schemas: browser schema base(s) "
                    "allow unknown fields"
                ),
                smell_name="Loose Boundary Contract",
                citation=(
                    "Dirt Boundary Contract Rule; Pydantic ConfigDict\n"
                    "   extra='forbid'"
                ),
                body=(
                    "WHY this rule exists:\n"
                    "  BrowserRequest and BrowserResponse are the base classes for\n"
                    "  Dirt-owned hosted browser API contracts. Unknown fields\n"
                    "  should fail loudly so stale generated clients, misspelled\n"
                    "  request keys, or obsolete response projections do not pass\n"
                    "  silently.\n\n"
                    "FIX:\n"
                    '  Keep model_config = ConfigDict(extra="forbid") on both\n'
                    "  BrowserRequest and BrowserResponse in\n"
                    "  dirt_control.api.browser_schemas.common."
                ),
                violations=violations,
            )
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
