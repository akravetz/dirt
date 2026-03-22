---
name: create-issue
description: Create a GitHub issue on the Dirt project board with our standard template
disable-model-invocation: true
allowed-tools: Bash(gh *), Read, Grep, Glob
argument-hint: "<epic> <title>"
---

# Create GitHub Issue

Create a GitHub issue for the Dirt project and add it to the project board.

## Arguments

- `$1` — Epic slug (one of: webcam-live-feed, auth, sensor-monitoring, dashboard, mcp-server)
- Remaining arguments — Issue title

## Steps

1. Read the relevant epic README at `docs/epics/$1/README.md` for context.
2. Ask the user for any details not covered by the title (description, implementation notes, acceptance criteria). If the user already provided enough detail, proceed.
3. Create the issue using `gh issue create` with the template below.
4. Add the issue to the project board: `gh issue edit <number> --add-project "Dirt"`
5. Report the issue URL back to the user.

## Issue Template

```
gh issue create \
  --repo akravetz/dirt \
  --title "<title>" \
  --label "epic:<epic-slug>" \
  --body "$(cat <<'ISSUE_EOF'
## Description

<Clear explanation of what needs to happen and why>

## Implementation Notes

- <Specific guidance, file paths, approach>

## Done When

- [ ] <Measurable criterion 1>
- [ ] <Measurable criterion 2>

## Epic

<epic-slug> — [Epic README](../docs/epics/<epic-slug>/README.md)
ISSUE_EOF
)"
```

## Labeling

Always apply the `epic:<slug>` label to link the issue to its epic. Add additional labels as appropriate:
- `bug` — Something is broken
- `enhancement` — New feature or improvement
- `infra` — Tooling, CI, project setup

## Validation

Before creating, verify:
- The epic slug matches an existing epic directory
- The title is specific and actionable (start with a verb)
- No duplicate issue already exists: `gh issue list --repo akravetz/dirt --label "epic:<slug>" --state open`
