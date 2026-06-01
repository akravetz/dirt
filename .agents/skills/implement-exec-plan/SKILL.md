---
name: implement-exec-plan
description: Execute an ExecPlan or similar milestone-based implementation plan from a repository document. Use when the user asks Codex to implement an ExecPlan, run through milestones, carry out a plan file, continue an implementation plan, or perform a milestone-by-milestone implementation loop with subagents, verification, simplification, and plan updates.
---

# Implement ExecPlan

## Operating Contract

Treat the plan document as the source of truth. Work milestone by milestone in order, starting at the first unchecked or clearly incomplete milestone. Continue until the plan is complete, or stop only when human input is genuinely required.

Use subagents for implementation when the environment supports them. The main agent owns orchestration, targeted review, verification, shared-state validation, and concise plan updates. Worker agents own concrete implementation edits for one milestone at a time.

## Context Discipline Contract

Keep the main context window clean. The main agent must not become a second implementation agent.

Main agent owns:

- milestone selection and worker briefs
- targeted diff review
- verification commands and acceptance checks
- shared-state validation actions explicitly required by the plan, such as database backup/apply/smoke checks
- concise ExecPlan progress, surprise, and outcome updates

Worker agents own:

- source, test, migration, contract, generated-client, frontend, and documentation edits required by the milestone
- focused validation for their own changes
- simplification cleanup for their own changes
- correction loops after main-agent verification feedback
- a concise report with changed files, commands/results, acceptance criteria satisfied, known gaps, and an ExecPlan update draft

Before the main agent edits any non-ExecPlan file, it must ask: "Is this implementation?" If yes, delegate it to a worker or send bounded feedback to the existing worker instead.

Main-agent non-ExecPlan edits are allowed only when all are true:

- the worker is unavailable or the fix is required to unblock verification immediately
- the edit is mechanical, low-risk, and under 10 lines
- the edit is recorded in the ExecPlan outcome or final summary

If verification fails, the default action is to send the failed criterion, evidence, and smallest acceptable correction back to the same worker. Do not locally fix worker-owned implementation unless the exception policy above applies.

## Workflow

1. Read the plan document fully enough to understand purpose, progress, milestones, acceptance criteria, validation commands, recovery notes, and any required documentation.
2. Read any repo-specific agent instructions and docs that the plan or repository says are required before editing code or running commands.
3. Identify the next incomplete milestone. Do not skip ahead unless the plan says a later milestone is prerequisite.
4. Create a concise milestone brief for the implementation agent:
   - plan path and milestone name
   - exact scope and non-goals
   - required acceptance criteria
   - validation commands from the plan
   - files or modules likely involved
   - cleanup expectations, including removal of stale compatibility code when the plan requires it
   - instruction that the worker is not alone in the codebase and must not revert unrelated edits
5. Spawn one worker subagent for that milestone. Ask it to:
   - implement only that milestone
   - run the milestone's focused validation commands
   - run a simplify pass by using `$simplify` or the repository's simplification process on its own changes
   - report changed files, commands run, results, acceptance criteria satisfied, known gaps, anything surprising/unexpected/broken, and a concise ExecPlan update draft
6. While the worker runs, do non-implementation orchestration work only:
   - prepare a short verification checklist from the plan
   - identify validation commands
   - inspect repo docs required for validation
   - check current plan state
   Do not pre-edit downstream files, regenerate artifacts, patch tests, or "get ahead" on later milestones.
7. When the worker returns, review and integrate its changes using the platform's normal subagent change workflow. Inspect the diff before trusting it.
8. Verify the milestone yourself:
   - check every acceptance criterion for the milestone
   - run focused tests or lint commands needed to prove the milestone
   - inspect changed code for scope creep, compatibility branches, stale naming, and unremoved legacy code
9. If verification fails, send concrete feedback to the same implementation agent and wait for a revised result. Repeat review and verification until the milestone is complete. Do not patch the failure locally unless the Context Discipline exception policy applies.
10. When the milestone is complete, update the ExecPlan:
   - mark the milestone complete with date/time
   - record validation commands and results in Outcomes or Progress
   - record surprises, unexpected behavior, broken assumptions, cleanup decisions, or follow-up risks in the appropriate plan sections
11. Repeat from step 3 for the next incomplete milestone.

## Main-Agent Review Checklist

For each milestone, verify all of these before marking it complete:

- The implemented behavior matches the plan's acceptance criteria, not just the worker's summary.
- Focused validation commands passed, or any unrun command has a concrete reason documented.
- The worker ran a simplify pass and either applied cleanup or explained why no cleanup was needed.
- No unrelated user changes were reverted.
- Temporary compatibility layers are explicitly marked and scheduled for immediate removal when the plan requires a clean cutover.
- Any surprising, unexpected, or broken behavior is captured in the ExecPlan.
- The plan's progress state matches the codebase state.

## Feedback Loop

When sending feedback to the implementation agent, be specific and bounded. Include:

- the failed criterion or test
- file and line references when available
- the expected behavior
- the smallest acceptable correction
- whether additional simplification is required after the correction

Reuse the same implementation agent for corrections to its milestone unless the agent is unavailable or the task needs a clean-room second pass.

## Human Input Threshold

Stop for human input only when a decision cannot be inferred from the plan or repository context and proceeding would risk one of these:

- destructive operations or data loss
- shared production state changes
- externally visible actions
- a product/API compatibility decision not covered by the plan
- conflicting plan requirements that cannot both be satisfied

If blocked, summarize the exact decision needed, the options, and the recommended path.
