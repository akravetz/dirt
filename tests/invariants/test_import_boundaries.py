"""
INVARIANT TEST — HUMAN-OWNED

This test is protected by Claude Code hooks and MUST NOT be modified by the agent.
If this test fails, the agent must fix its code to satisfy the test, never modify
this file.

Purpose: Enforces module import boundaries so the codebase maintains clean
architectural separation between layers.

Architecture layers:
    models   — data models (no app dependencies)
    services — business logic (may use models, must not use api/mcp)
    api      — web routes (may use services, must not use models or db directly)
    mcp      — MCP server (may only use services and config)
"""

import pytest
from pytestarch import Rule, get_evaluable_architecture

SRC_ROOT = "src"
MODULE_ROOT = "src/dirt"


def _check_rule(rule, evaluable, fix_message):
    """Assert a pytestarch rule, appending actionable guidance on failure."""
    try:
        rule.assert_applies(evaluable)
    except AssertionError as e:
        raise AssertionError(f"{e}\n\nFIX: {fix_message}") from None


@pytest.fixture(scope="module")
def evaluable():
    return get_evaluable_architecture(SRC_ROOT, MODULE_ROOT)


def test_models_do_not_import_api(evaluable):
    """Models are pure data — they must not depend on API routes."""
    rule = (
        Rule()
        .modules_that()
        .are_sub_modules_of("src.dirt.models")
        .should_not()
        .import_modules_that()
        .are_sub_modules_of("src.dirt.api")
    )
    _check_rule(
        rule,
        evaluable,
        "Models in src/dirt/models/ are pure data classes with no app dependencies. "
        "Move any logic that depends on API routes into src/dirt/services/ instead.",
    )


def test_models_do_not_import_services(evaluable):
    """Models must not depend on services."""
    rule = (
        Rule()
        .modules_that()
        .are_sub_modules_of("src.dirt.models")
        .should_not()
        .import_modules_that()
        .are_sub_modules_of("src.dirt.services")
    )
    _check_rule(
        rule,
        evaluable,
        "Models in src/dirt/models/ are pure data classes with no app dependencies. "
        "Move any business logic into src/dirt/services/ and keep models free of "
        "service imports.",
    )


def test_models_do_not_import_mcp(evaluable):
    """Models must not depend on MCP server."""
    rule = (
        Rule()
        .modules_that()
        .are_sub_modules_of("src.dirt.models")
        .should_not()
        .import_modules_that()
        .are_sub_modules_of("src.dirt.mcp")
    )
    _check_rule(
        rule,
        evaluable,
        "Models in src/dirt/models/ are pure data classes with no app dependencies. "
        "Move any MCP-related logic into src/dirt/mcp/ and keep models free of "
        "MCP imports.",
    )


def test_services_do_not_import_api(evaluable):
    """Services must not depend on API routes."""
    rule = (
        Rule()
        .modules_that()
        .are_sub_modules_of("src.dirt.services")
        .should_not()
        .import_modules_that()
        .are_sub_modules_of("src.dirt.api")
    )
    _check_rule(
        rule,
        evaluable,
        "Services in src/dirt/services/ contain business logic that is shared by "
        "multiple consumers (API routes, MCP tools). They must not depend on any "
        "specific consumer. Remove the API import and keep the dependency direction: "
        "api -> services, not services -> api.",
    )


def test_services_do_not_import_mcp(evaluable):
    """Services must not depend on MCP server."""
    rule = (
        Rule()
        .modules_that()
        .are_sub_modules_of("src.dirt.services")
        .should_not()
        .import_modules_that()
        .are_sub_modules_of("src.dirt.mcp")
    )
    _check_rule(
        rule,
        evaluable,
        "Services in src/dirt/services/ contain business logic that is shared by "
        "multiple consumers (API routes, MCP tools). They must not depend on any "
        "specific consumer. Remove the MCP import and keep the dependency direction: "
        "mcp -> services, not services -> mcp.",
    )


def test_mcp_only_imports_services_and_config(evaluable):
    """MCP server may only import from services and config — nothing else."""
    rule = (
        Rule()
        .modules_that()
        .are_sub_modules_of("src.dirt.mcp")
        .should_not()
        .import_modules_except_modules_that()
        .have_name_matching(r"^src\.dirt\.(services|config|mcp)")
    )
    _check_rule(
        rule,
        evaluable,
        "The MCP server (src/dirt/mcp/) may only import from dirt.services and "
        "dirt.config. It must not import from dirt.db, dirt.models, dirt.api, or "
        "any other internal package. All data access and business logic should go "
        "through service functions in src/dirt/services/. If you need a new "
        "capability, add a service function rather than importing directly.",
    )


def test_api_does_not_import_mcp(evaluable):
    """API routes must not depend on MCP server."""
    rule = (
        Rule()
        .modules_that()
        .are_sub_modules_of("src.dirt.api")
        .should_not()
        .import_modules_that()
        .are_sub_modules_of("src.dirt.mcp")
    )
    _check_rule(
        rule,
        evaluable,
        "The API routes (src/dirt/api/) and MCP server (src/dirt/mcp/) are sibling "
        "consumers that must not depend on each other. If both need the same logic, "
        "extract it into a service function in src/dirt/services/.",
    )


def test_api_does_not_import_models(evaluable):
    """API routes must not import models directly — use services instead."""
    rule = (
        Rule()
        .modules_that()
        .are_sub_modules_of("src.dirt.api")
        .should_not()
        .import_modules_that()
        .are_sub_modules_of("src.dirt.models")
    )
    _check_rule(
        rule,
        evaluable,
        "API routes must not import model classes from src/dirt/models/. Instead, "
        "call a service function in src/dirt/services/ that returns the data you need. "
        "The API route should only format the service response for its transport "
        "(HTML, JSON, etc.).",
    )


def test_api_does_not_import_db(evaluable):
    """API routes must not use the DB layer — services manage their own sessions."""
    rule = (
        Rule()
        .modules_that()
        .are_sub_modules_of("src.dirt.api")
        .should_not()
        .import_modules_that()
        .are_named("src.dirt.db")
    )
    _check_rule(
        rule,
        evaluable,
        "API routes must not import from dirt.db or manage DB sessions. Services "
        "manage their own sessions internally. Move query logic into a service "
        "function in src/dirt/services/ that creates its own AsyncSession from "
        "dirt.db.engine, then call that service function from the API route.",
    )
