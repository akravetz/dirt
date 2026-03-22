# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Dirt** — Home grow monitoring system. Webcam live feed, temperature/humidity sensors graphed over time, and an MCP server for Claude Desktop integration. Python >=3.13, managed with `uv`.

- **Repo**: https://github.com/akravetz/dirt
- **Project Board**: https://github.com/users/akravetz/projects/1/views/1

## Commands

- **Run**: `uv run python main.py`
- **Test all**: `uv run pytest -v`
- **Unit tests**: `uv run pytest tests/ --ignore=tests/e2e --ignore=tests/invariants -v`
- **Invariants**: `uv run pytest tests/invariants/ -v`
- **E2E tests**: `uv run pytest tests/e2e/ -v`
- **Single test**: `uv run pytest tests/test_foo.py::test_name -v`
- **Lint**: `uv run ruff check src/ tests/`
- **Format**: `uv run ruff format src/ tests/`
- **Add dependency**: `uv add <package>` (dev: `uv add --optional dev <package>`)

## Documentation (Progressive Disclosure)

This file is the discovery layer. Read deeper docs before starting work in an area.

- **`docs/README.md`** — Full project description, documentation map
- **`docs/adrs/`** — Architecture Decision Records. Read before proposing alternatives to settled choices.
- **`docs/epics/`** — Epic context and scope. Read the relevant epic README before starting work. Issues are tracked on the [GitHub project board](https://github.com/users/akravetz/projects/1/views/1) — find issues for an epic with `gh issue list --repo akravetz/dirt --label "epic:<slug>"`.
- **`docs/progress/`** — Feature progress tracking between PRs. Update after completing work.
- **`docs/rules/`** — Codebase rules and conventions. Read before making changes.

## Test Ownership

- **`tests/invariants/`** — HUMAN-OWNED. You MUST NOT modify these files. They encode sacred architectural rules (auth boundaries, import boundaries). If an invariant test fails, fix your code to satisfy the test — never modify the test. Flag invariant failures to the user.
- **`tests/e2e/`** — Agent-owned. Playwright E2E tests you can create and update freely.
- **`tests/`** (other) — Agent-owned. Unit and integration tests you can create and update freely.
