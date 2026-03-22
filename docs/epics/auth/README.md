# Epic: Authentication

Status: planning
Priority: medium
Created: 2026-03-22

## Goal

Single-user authentication for the web UI. Credentials loaded from `.env`, session-based login with a cookie. All routes protected behind login. Since this is local-network only, this is a convenience barrier rather than a security boundary.

## Scope

- Login page (Jinja2 + HTMX)
- Session management (cookie-based)
- Route protection middleware
- Credentials from `.env` via pydantic-settings

## Acceptance Criteria

- Unauthenticated requests redirect to login page
- Valid credentials from `.env` grant a session cookie
- All API and UI routes require authentication
- Session persists across page refreshes

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:auth"`
