# Epic: Authentication

Status: complete
Priority: medium
Created: 2026-03-22

## Goal

Single-user authentication for the web UI. Credentials loaded from `.env`, session-based login with a cookie. All routes protected behind login. Since this is local-network only, this is a convenience barrier rather than a security boundary.

## Scope

- Login page (Jinja2 + HTMX)
- Session management (cookie-based)
- Route protection middleware
- Logout action
- Credentials from `.env` via pydantic-settings

## Acceptance Criteria

1. Unauthenticated requests to any route (UI and API) redirect to `/login`
2. `/login` page renders a username/password form
3. Valid credentials (from `.env` `AUTH_USERNAME`/`AUTH_PASSWORD`) grant a session cookie
4. Invalid credentials show an error message on the login page
5. Authenticated session persists across page refreshes (cookie-based)
6. `/logout` clears the session and redirects to `/login`
7. `/login` and `/logout` are the only unauthenticated routes
8. Tests cover: login success, login failure, protected route redirect, logout

## Out of Scope

- Password hashing (single user, local network)
- Registration / user management
- Token-based auth / API keys (revisit for MCP epic)
- Session expiration / timeout
- CSRF protection (local network, single user)

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:auth"`
