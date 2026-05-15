# Codex Execution Plans (ExecPlans)

This document defines an execution plan, or `ExecPlan`: a living design document that a coding agent can follow to deliver a working feature or system change. Write every ExecPlan for a reader who is new to this repository and has only the current working tree plus the ExecPlan file in front of them. Do not rely on chat history, prior agent memory, or unstated context.

This file follows the OpenAI Cookbook ExecPlan pattern, adapted to Dirt's `.agents/` convention. The original article is: https://developers.openai.com/cookbook/articles/codex_exec_plans

## How To Use ExecPlans

When authoring an ExecPlan, follow this file closely. If this file is not already in context, read it in full before writing or revising the plan. Start from the skeleton below, then fill it in as you inspect the repository and learn what the change requires.

When implementing an ExecPlan, continue through the next milestone without asking the user for routine next steps. Keep the plan current as work proceeds. At every stopping point, update progress, discoveries, decisions, and next actions so a later agent can resume from the ExecPlan alone.

When discussing or changing an ExecPlan, record the decision and rationale inside the plan. The plan is part of the implementation record, not a disposable note.

For uncertain designs, include prototyping milestones. A prototype is a small, testable experiment used to validate feasibility before committing to a larger implementation.

## Non-Negotiable Requirements

Every ExecPlan must be self-contained. It must include the knowledge, assumptions, definitions, commands, and file paths needed for a novice to complete the work.

Every ExecPlan must remain a living document. Contributors must update it as progress is made, surprises are found, and design choices are finalized.

Every ExecPlan must enable end-to-end implementation without prior knowledge of Dirt. If a term is not ordinary English, define it the first time it appears and connect it to concrete files or commands in this repository.

Every ExecPlan must produce demonstrably working behavior. Do not define success as merely changing code. Define how a human can observe the new behavior through tests, a local server, a command, an HTTP request, a UI flow, logs, or another concrete signal.

Purpose comes first. Begin each ExecPlan by explaining what the user can do after the change that they could not do before, why that matters, and how they can see it working.

Every ExecPlan must follow the repository's simple clean architecture rule in `docs/rules/simple-clean-architecture.md`: build the simplest truthful model, prefer direct explicit code and data, add abstractions only for real shared responsibility, choose direct cutover for source-owned code, and do not leave dead wrappers or compatibility layers behind.

## Formatting Rules

An ExecPlan is a single Markdown document. If an ExecPlan is embedded inside another Markdown conversation, wrap it in one fenced code block labeled `md`. If the ExecPlan is checked in as its own `.md` file, omit the outer fence.

Do not nest triple-backtick fences inside an ExecPlan. When commands, snippets, transcripts, or diffs are needed, indent them instead.

Use plain prose first. Lists are useful for progress tracking and short summaries, but narrative sections should explain the work in sentences. Avoid tables unless they make the plan clearer.

Use two blank lines after headings. Use standard Markdown headings. Keep file paths repository-relative and exact.

## Content Guidelines

Make the plan readable to someone who has never worked in this repo. Name the files, modules, functions, commands, services, and tests that matter. Explain how the parts fit together before asking the reader to edit them.

Do not outsource important decisions to the implementer. Resolve ambiguity in the plan and explain why. If a later discovery changes the decision, record the change in the `Decision Log`.

Keep work safe and repeatable. Prefer additive, testable changes. If a step can be run twice safely, say so. If a step is risky, include a backup, rollback, or retry path.

Validation is mandatory. Include exact commands, working directories, expected outcomes, and how to interpret failures. When possible, describe a test or scenario that would fail before the change and pass after it.

Capture concise evidence. When terminal output, logs, or diffs prove success, include short excerpts in `Artifacts and Notes`.

## Required Sections

Every ExecPlan must contain these sections:

1. `Purpose / Big Picture`
2. `Progress`
3. `Surprises & Discoveries`
4. `Decision Log`
5. `Outcomes & Retrospective`
6. `Context and Orientation`
7. `Plan of Work`
8. `Concrete Steps`
9. `Validation and Acceptance`
10. `Idempotence and Recovery`
11. `Artifacts and Notes`
12. `Interfaces and Dependencies`

The `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` sections are living sections. Keep them accurate as the implementation changes.

## Milestones

Milestones should tell the implementation story. For each milestone, explain what will exist afterward, what files or commands are involved, and how to verify the result. Each milestone should be independently testable and should move the system closer to the final user-visible outcome.

Progress is separate from milestones. Milestones explain the path; `Progress` records the actual current state.

## Prototypes

Use prototyping milestones when they reduce risk. A prototype should be small, additive, and easy to discard. State what question the prototype answers, how to run it, what evidence would make it successful, and what criteria would cause it to be abandoned.

Parallel implementations are allowed during migrations when they reduce risk. The plan must explain how both paths are validated and how the old path will be retired.

## Skeleton

# Short, action-oriented title

This ExecPlan is a living document. Keep `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` current as work proceeds.

This plan follows `.agents/PLANS.md`.

## Purpose / Big Picture

Explain what someone gains after this change, why it matters, and how they can observe it working.

## Progress

Use checkboxes with timestamps. Every stopping point must update this section.

- [x] (2026-05-03 00:00Z) Example completed step.
- [ ] Example remaining step.
- [ ] Example partially completed step. Completed: specific work. Remaining: specific work.

## Surprises & Discoveries

Record unexpected behavior, bugs, performance observations, or implementation facts that affect the plan. Include concise evidence.

- Observation: ...
  Evidence: ...

## Decision Log

Record important decisions in this format:

- Decision: ...
  Rationale: ...
  Date/Author: ...

## Outcomes & Retrospective

Summarize outcomes, gaps, and lessons at major milestones or completion. Compare the result against the original purpose.

## Context and Orientation

Describe the current repository state relevant to this task. Define non-obvious terms. Name key files and explain how they interact.

## Plan of Work

Describe the sequence of edits and additions. For each part, name the file and the function, module, route, service, or component to change.

## Concrete Steps

List exact commands and working directories. Include short expected transcripts when useful.

    cd /home/akcom/code/dirt
    uv run pytest apps/shared/tests -q

Expected result:

    ... passed

## Validation and Acceptance

Describe how to prove the change works. Use observable behavior: commands, HTTP responses, UI actions, logs, or tests. Include expected output or state.

## Idempotence and Recovery

Explain which steps are safe to repeat. For risky steps, describe how to retry, roll back, or recover.

## Artifacts and Notes

Include concise transcripts, diffs, links to generated artifacts, or log excerpts that prove progress or completion.

## Interfaces and Dependencies

Specify the concrete interfaces that must exist at the end of the work: modules, functions, routes, schemas, command names, environment variables, services, and external dependencies.

## Revision Notes

When this ExecPlan is revised, add a dated note describing what changed and why.
