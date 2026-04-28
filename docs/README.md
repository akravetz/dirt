# Dirt Documentation

Index for the progressive-disclosure docs tree. The root `AGENTS.md` points here for everything except the most universal context. Each entry below has a triggering description — read the linked doc *before* doing the listed activity.

## Operations

| Doc | Read before |
|---|---|
| [commands.md](commands.md) | running anything (dev, test, lint, firmware, web-ui, web-api auth, PTZ, voice, daily report). The exhaustive command surface. |
| [database.md](database.md) | writing SQL, editing `apps/shared/src/dirt_shared/models/`, or running `atlas migrate`. Schema cheat sheet, query patterns, Atlas workflow, backup/rollback. |
| [observability.md](observability.md) | calling `log_event()`, debugging across logs, writing tests that touch `var/logs/` or `var/sessions/`, or adding a new log stream. Full stream registry + retention + correlation. |

## Grow context

| Doc | Read before |
|---|---|
| [grow-state.md](grow-state.md) | writing code that branches on stage (veg / flower_early / flower_late) or that needs the current germination/flower-flip date. |

## Framework anchors

| Doc | Read before |
|---|---|
| [references/INDEX.md](references/INDEX.md) | writing code that touches Pipecat, TanStack Router, Tailwind v4, Govee API, Atlas, MSW v2, Wandb, RunPod, Claude Agent SDK, Deepgram, or modern TS idioms. Each pack has its own deep-dive `INDEX.md` plus topic files. |

## Architecture & process

| Directory | Purpose |
|---|---|
| [adrs/](adrs/) | Architecture Decision Records ([Nygard format](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions)). Read before proposing alternatives to settled choices. Numbered sequentially, never reused. |
| [epics/](epics/) | Epic and issue context — major features, scope, in-flight work. Read the relevant epic README before starting work in that area. Issues tracked on the [GitHub project board](https://github.com/users/akravetz/projects/1/views/1) — find issues for an epic with `gh issue list --repo akravetz/dirt --label "epic:<slug>"`. |
| [progress/](progress/) | Feature progress tracking between PRs. Update after completing work. |
| [rules/](rules/) | Codebase rules and conventions. Read before making changes in affected areas. |
| [proposals/](proposals/) | Design proposals not yet promoted to ADRs (or that informed multiple ADRs). |

## Wiki (the grow knowledge base)

The `wiki/` directory at the repo root is a separate progressive-disclosure tree maintained by the daily-report agent. For any wiki work — ingestion, daily updates, page conventions, linting, query filing, plant labeling — start at [`../wiki/AGENTS.md`](../wiki/AGENTS.md).
