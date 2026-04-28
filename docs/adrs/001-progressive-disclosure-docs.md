# ADR 001: Progressive Disclosure Documentation Structure

## Status

Accepted

## Context

AI coding assistants load AGENTS.md into every conversation. Large monolithic docs waste context tokens on irrelevant sections. We need a documentation structure that gives agents enough context to orient themselves without bloating every session.

## Decision

We will use a three-tier progressive disclosure model:

1. **Discovery** — `AGENTS.md` (always loaded, <100 lines). Contains project summary, essential commands, and pointers to deeper docs.
2. **Activation** — `docs/README.md` and topic-specific files. Read when starting a task in that area.
3. **Execution** — ADRs, rule files, progress logs. Read only when the specific topic is relevant.

Documentation lives in `docs/` with subdirectories: `adrs/`, `progress/`, `rules/`.

## Consequences

- AGENTS.md stays lean and fast to parse.
- Deeper context is available on demand without polluting unrelated sessions.
- Requires discipline to put detail in the right tier rather than dumping everything in AGENTS.md.
