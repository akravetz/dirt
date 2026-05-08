# Epics

Epics track major features from planning through completion. Each epic is a directory with a README providing context, scope, and acceptance criteria. Issues are tracked on the [GitHub project board](https://github.com/users/akravetz/projects/1/views/1).

## Structure

```
epics/
  epic-slug/
    README.md    # Goal, scope, acceptance criteria, how to find issues
```

Issues live in GitHub, labeled `epic:<slug>`. To find all issues for an epic:

```bash
gh issue list --repo akravetz/dirt --label "epic:<slug>"
```

## Epic README Format

```markdown
# Epic: Short Title

Status: planning | in-progress | blocked | complete
Priority: high | medium | low
Created: YYYY-MM-DD

## Goal
One paragraph describing what this epic achieves and why.

## Scope
- What's included in this epic

## Acceptance Criteria
- Measurable criterion 1
- Measurable criterion 2

## Issues
Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:<slug>"`
```

## Creating Issues

Use the `/create-issue` skill: `/create-issue <epic-slug> <title>`

This creates a GitHub issue with our standard template and the correct epic label.

## Current Epics

| Epic | Status | Priority |
|------|--------|----------|
| [webcam-live-feed](webcam-live-feed/README.md) | complete | high |
| [auth](auth/README.md) | complete | medium |
| [sensor-monitoring](sensor-monitoring/README.md) | blocked (hardware) | high |
| [dashboard](dashboard/README.md) | planning | medium |
| [mcp-server](mcp-server/README.md) | planning | medium |
| [testing-boundaries](testing-boundaries/README.md) | complete | high |
| [sensor-hardware](sensor-hardware/README.md) | planning | high |
| [ptz-camera](ptz-camera/README.md) | planning | high |
| [live-audio](live-audio/README.md) | planning | medium |
| [telegram-bot](telegram-bot/README.md) | planning | high |
| [codex-migration](codex-migration/README.md) | planning | high |
| [typed-boundary-contracts](typed-boundary-contracts/README.md) | planning | high |

## Rules for Agents

1. **Before starting work**, read the relevant epic README for context.
2. **Find your assigned issue** with `gh issue list --repo akravetz/dirt --label "epic:<slug>"`.
3. **One task per session** — complete it fully before moving to the next.
4. **Update the issue** when done — close it with `gh issue close <number>`.
