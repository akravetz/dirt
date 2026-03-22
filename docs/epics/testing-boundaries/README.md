# Epic: Testing & Boundaries

Status: complete
Priority: high
Created: 2026-03-22

## Goal

Establish two layers of test defense: human-owned invariant tests that encode sacred architectural rules (agent cannot modify), and agent-owned E2E tests using Playwright for confidence after code changes.

## Scope

### Layer 1: Invariant Tests (human-owned, agent-protected)

- `tests/invariants/` directory protected by Claude Code hooks
- Auth boundary test — every route except `/login` and `/logout` requires authentication
- Import boundary tests — modules don't reach across architectural layers (pytestarch)
- PreToolUse hooks block agent from modifying these files

### Layer 2: E2E Tests (agent-owned)

- `tests/e2e/` directory using Playwright (headless)
- Login flow: render form, submit credentials, access protected page
- Live feed page: loads, HTMX polling works, image element present
- Logout: clears session, redirects to login

### Enforcement

- PreToolUse hooks in `.claude/settings.json` (committed to repo)
- CLAUDE.md rules declaring test ownership
- If an invariant test fails, the agent must fix its code — never the test

## Acceptance Criteria

1. `tests/invariants/test_auth_boundary.py` asserts all routes require auth except `/login`, `/logout`
2. `tests/invariants/test_import_boundaries.py` enforces module boundaries via pytestarch
3. `tests/e2e/test_login_flow.py` — full login/logout cycle in Playwright
4. `tests/e2e/test_live_feed.py` — page loads, image element present
5. PreToolUse hooks block modifications to `tests/invariants/`
6. CLAUDE.md updated with test ownership rules
7. All tests passing

## Out of Scope

- PostToolUse auto-run of invariant tests (can add later)
- CI pipeline (will be its own epic)

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:testing-boundaries"`
