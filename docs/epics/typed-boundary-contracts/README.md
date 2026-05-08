# Epic: Typed Boundary Contracts

Status: planning
Priority: high
Created: 2026-05-08

## Goal

Make Pydantic DTOs the single schema enforcement mechanism for payloads crossing Dirt service boundaries, starting with the hosted gateway/control-plane sync path.

## Scope

- Shared Pydantic contract models for gateway/control-plane requests and responses.
- Producer-side validation in `dirt-gateway`.
- Receiver-side reuse in `dirt-control-plane`.
- Typed outbox event payloads.
- Focused tests and invariants that prevent raw boundary dictionaries from returning.
- Progressive-disclosure documentation so future agents load the rule before editing boundary code.

## Acceptance Criteria

- Missing required gateway fields fail before enqueue or HTTP delivery.
- Gateway client responses are validated before command or asset logic consumes them.
- Control-plane browser and gateway routes expose Pydantic response models where they return JSON.
- Documentation maps point agents to `docs/rules/boundary-contracts.md` before boundary work.

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:typed-boundary-contracts"`

## ExecPlan

Implementation plan: `docs/epics/typed-boundary-contracts/ExecPlan.md`
