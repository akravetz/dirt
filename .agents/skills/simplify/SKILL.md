---
name: simplify
description: Review and simplify changed code by defaulting to parallel subagent review for reuse, code quality, and efficiency, then directly applying worthwhile cleanup fixes. Use whenever the user asks to simplify, clean up, de-duplicate, make code more maintainable, reduce complexity, review current changes for unnecessary code, or run a simplify pass over a diff, branch, PR, or recently edited files.
---

# Simplify

## Overview

Run a focused cleanup pass over the current code changes. Prefer the repository's existing patterns, helpers, and abstractions; remove needless complexity; and fix clear issues directly.

Parallel review agents are the default path. Use the sequential fallback only when this Codex runtime cannot spawn agents.

## Workflow

1. Inspect the worktree with `git status --short`, `git diff`, and, when staged changes exist, `git diff --staged`.
2. If there are no git changes, review the files named by the user or the files most clearly touched in the current conversation.
3. Gather enough local context to judge reuse opportunities: nearby modules, existing helpers, exported types, tests, and conventions.
4. Spawn the parallel review agents described below.
5. Aggregate their findings, discard false positives and low-value churn, then directly edit the code for the fixes that are clearly better.
6. Run focused validation appropriate to the touched files.
7. Finish with a short summary of the changes and any validation that could not be run.

## Default Parallel Review

When `spawn_agent` is available, launch three read-only review agents in parallel before making edits. Treat the user's request to use this skill as permission to use parallel review subagents by default.

Give each agent the same compact context: the relevant diff, touched file list, user request, and any key architectural constraints already discovered. Ask each agent to return only concrete findings with file paths, line references when possible, why the issue matters, and a suggested fix. Instruct all review agents not to edit files.

### Reuse Reviewer

Ask this agent to find places where the changes add new code that should reuse existing code. Scope includes helpers, utilities, shared components, constants, types, schemas, fixtures, test helpers, hooks, services, commands, and established local patterns.

Prompt shape:

```text
Review the current diff only for code reuse opportunities. Do not edit files.
Find new or changed code that duplicates existing helpers, types, constants,
components, services, fixtures, or local patterns. Return concise findings with
file paths, line references when possible, and concrete replacement suggestions.
```

### Quality Reviewer

Ask this agent to find avoidable complexity or maintainability problems. Scope includes redundant state, parameter sprawl, over-broad abstractions, unnecessary wrappers, duplicated branches, raw strings where constants or types exist, unclear names, brittle tests, comments that only narrate obvious code, and code that conflicts with local style.

Prompt shape:

```text
Review the current diff only for code quality and maintainability. Do not edit
files. Look for avoidable complexity, weak abstractions, naming problems,
duplicated logic, brittle tests, and code that diverges from local conventions.
Return concise findings with concrete fixes.
```

### Efficiency Reviewer

Ask this agent to find unnecessary work and resource risks. Scope includes repeated computation, duplicate IO or network calls, missed batching or concurrency, hot-path bloat, no-op update churn, over-broad scans, avoidable loading, time-of-check/time-of-use patterns, leaks, and expensive tests.

Prompt shape:

```text
Review the current diff only for efficiency and resource-use issues. Do not edit
files. Look for repeated computation, duplicate IO, avoidable network calls,
missed batching or concurrency, broad reads, leaks, and hot-path regressions.
Return concise findings with concrete fixes.
```

## Fallback

If this runtime cannot spawn agents, run the same three reviews locally in this order: reuse, quality, efficiency. Keep the passes separate so findings do not collapse into a generic review.

## Fix Policy

Prefer changes that reduce code, reuse existing behavior, or make the code easier to reason about without changing intent. Do not apply speculative rewrites, broad refactors, style-only churn, or changes outside the user's requested scope.

When agent findings conflict, inspect the code yourself and choose the smallest correct fix. The main Codex agent owns all edits and validation.

## Validation

Run the narrowest useful validation for the files changed: unit tests, type checks, linters, formatters, or targeted smoke checks. If validation is expensive or unavailable, run a cheaper focused check and state the remaining gap.
