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
    api      — web routes (may use services, models)
    mcp      — MCP server (may use services, models, must not use api)
"""

import pytest
from pytestarch import Rule, get_evaluable_architecture

SRC_ROOT = "src"
MODULE_ROOT = "src/dirt"


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
    rule.assert_applies(evaluable)


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
    rule.assert_applies(evaluable)


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
    rule.assert_applies(evaluable)


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
    rule.assert_applies(evaluable)


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
    rule.assert_applies(evaluable)


def test_mcp_does_not_import_api(evaluable):
    """MCP server must not depend on API routes."""
    rule = (
        Rule()
        .modules_that()
        .are_sub_modules_of("src.dirt.mcp")
        .should_not()
        .import_modules_that()
        .are_sub_modules_of("src.dirt.api")
    )
    rule.assert_applies(evaluable)


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
    rule.assert_applies(evaluable)
