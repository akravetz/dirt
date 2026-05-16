# Epic: Python Quality Radar

Status: planning
Priority: high
Created: 2026-05-16

## Goal

Build a high-recall, low-friction audit system for Python code quality and architecture debt in Dirt. The first result is a report that points reviewers toward likely vibe-coding failure modes: duplication, oversized functions, weak boundary contracts, broad exception handling, hidden dependency drift, under-tested hot spots, and stale abstractions.

## Scope

- Add a report-only Python debt radar command for production code under `apps/*/src`.
- Rank findings by file and category so humans can review likely debt pockets.
- Use review outcomes to promote repeated true positives into durable architectural constraints.
- Keep the existing human-owned invariants untouched; add new invariants only after detectors prove useful.

## Acceptance Criteria

- A developer can run one command from the repo root and get a deterministic Markdown and JSON report.
- The report identifies at least complexity, clone, boundary-payload, broad-exception, suppression, dependency, and test-proximity signals.
- The first report is reviewed and converted into a prioritized remediation backlog.
- At least three repeated true-positive patterns become new agent-owned or human-owned guardrails.

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:python-quality-radar"`
