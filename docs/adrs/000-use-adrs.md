# ADR 000: Use Architecture Decision Records

## Status

Accepted

## Context

This project will evolve incrementally — webcam capture first, then sensors, then a full dashboard and MCP server. Decisions made early (tech stack, protocols, data storage) will constrain later work. We need a way to capture *why* choices were made so future sessions (human or AI) don't revisit settled questions or unknowingly contradict prior reasoning.

## Decision

We will use Architecture Decision Records (ADRs) in `docs/adrs/`, following the Michael Nygard format (Status, Context, Decision, Consequences). Each ADR addresses one decision, is numbered sequentially, and is never deleted — only superseded.

## Consequences

- Decisions are discoverable and auditable without reading git history.
- Future Claude sessions can check ADRs before proposing alternatives to settled choices.
- Small overhead per decision (~5 minutes to write), but prevents repeated debate.
