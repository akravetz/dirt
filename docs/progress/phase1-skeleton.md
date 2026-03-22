# Phase 1: Project Skeleton

## Goal
Set up the project structure, tooling, and a minimal running FastAPI app.

## Status
Complete

## Completed
- `src/dirt/` package layout with subpackages: `api/`, `models/`, `services/`, `mcp/`, `templates/`
- `pyproject.toml` with all dependencies, ruff config, pytest config
- FastAPI app (`src/dirt/app.py`) with Jinja2 template rendering
- Config via `pydantic-settings` + `python-dotenv` (`src/dirt/config.py`)
- `.env` / `.envrc` / `.gitignore` for secrets management
- Smoke test (`tests/test_app.py`) — pytest + httpx async client
- ADR 002 (tech stack), ADR 003 (hardware/deployment)

## Next Steps
- Phase 2: Webcam capture service + live feed UI
