# Epic: Codex Migration

Status: planning
Priority: high
Created: 2026-04-28

## Goal

Move this repository's agent-facing workflow from Claude Code to Codex while preserving the operating manual, protected-file boundaries, skills, and multi-agent work patterns that currently make agent work safe and repeatable.

The first priority is mechanical and repo-wide: every `CLAUDE.md` operating manual becomes an `AGENTS.md` file, and every reference to those manuals is updated so Codex discovers the same guidance that Claude Code currently receives.

## Source References

- Codex `AGENTS.md` discovery: https://developers.openai.com/codex/guides/agents-md
- Codex hooks: https://developers.openai.com/codex/hooks
- Codex config reference: https://developers.openai.com/codex/config-reference
- Codex skills: https://developers.openai.com/codex/skills
- Codex subagents: https://developers.openai.com/codex/subagents
- Claude Code settings and hooks, for parity checks: https://code.claude.com/docs/en/settings and https://code.claude.com/docs/en/hooks

## Scope

### 1. Rename Agent Manuals

- Rename root `CLAUDE.md` to `AGENTS.md`.
- Rename nested manuals, currently:
  - `wiki/CLAUDE.md`
  - `apps/wake-word/CLAUDE.md`
- Update all repo references from `CLAUDE.md` to `AGENTS.md`, including docs, scripts, systemd `Documentation=` links, test comments, and generated prompt templates.
- Preserve nested manual semantics: Codex loads `AGENTS.md` from the repo root down to the current working directory, so nested manuals should remain near the work they govern.
- Decide whether any compatibility symlinks named `CLAUDE.md` should remain temporarily for Claude users, or whether this migration removes Claude support outright.

### 2. Migrate Hooks

- Replace `.claude/settings.json` hook configuration with Codex hook configuration in `.codex/config.toml` and/or `.codex/hooks.json`.
- Port `.claude/hooks/protect-invariants.sh` to Codex's `apply_patch` input shape.
- Port `.claude/hooks/protect-invariants-bash.sh` to Codex `PreToolUse` for `Bash`.
- Revisit hook decisions: Claude's `permissionDecision: "ask"` behavior does not directly preserve in Codex, where the documented blocking shape is `permissionDecision: "deny"` or legacy `decision: "block"`.
- Update invariant tests that currently assert `.claude/settings.json` protects web UI invariants.

### 3. Migrate Skills

- Keep repo skills in `.agents/skills`, which Codex discovers directly.
- Move or copy useful Claude skills from `.claude/skills` into `.agents/skills` after auditing frontmatter and behavior:
  - `unstuck`
  - `reference-builder`
  - `review-issue`
  - `close-issue`
  - `create-issue`
- Remove or rewrite Claude-specific fields and assumptions such as Claude-only tool permission syntax, Claude command invocation, and Claude subagent references.
- Keep the existing `.codex/skills -> ../.agents/skills` symlink only if it is still useful; Codex docs say repo skills are read from `.agents/skills`.

### 4. Migrate Config, Permissions, and Rules

- Add project-scoped `.codex/config.toml` for Codex settings that should be shared by the team.
- Translate relevant Claude permission and sandbox assumptions to Codex `approval_policy`, `sandbox_mode`, named permission profiles, and `.codex/rules/*.rules`.
- Decide which settings are personal and should stay out of the repo.
- Update docs that instruct agents to use Claude-specific commands, approval modes, or permission modes.

### 5. Migrate Subagent and Worktree Workflow

- Replace Claude-specific subagent references in docs and generator prompts with Codex subagent language.
- Decide whether manual worktrees stay under `.claude/worktrees`, move to `.codex/worktrees`, or move to a tool-neutral path such as `.agents/worktrees`.
- Update `scripts/worktree-port`, `docs/plans/orchestrator.md`, and `docs/plans/generator-prompts.md` once the target path is chosen.
- Convert any custom Claude subagents, if still needed, to Codex `.codex/agents/*.toml`.

### 6. Migrate MCP and Runtime Agent Integrations

- Inventory any user-level Claude MCP servers and decide which should be added to Codex `config.toml` under `[mcp_servers.*]`.
- Keep the application MCP server under `apps/mcp/`; it is product code, not just Claude configuration.
- Separately decide whether runtime integrations that shell out to `claude -p` or depend on `claude-agent-sdk` should remain Claude-based, move to Codex CLI, or move to an OpenAI API integration.

## Acceptance Criteria

1. No checked-in operating manual is named `CLAUDE.md`; all intended manuals are named `AGENTS.md`.
2. `rg -n "CLAUDE.md|\\.claude|claude -p|claude-agent-sdk|Claude Code"` has only deliberate historical references or runtime integrations explicitly called out in this epic.
3. Codex loads the root and nested `AGENTS.md` files from the expected directories.
4. Codex hooks protect the same invariant paths currently protected by Claude hooks:
   - `apps/tests/invariants/**`, except `apps/tests/invariants/contract_status.json`
   - `.githooks/**`
   - `web-ui/invariants/**`
   - `web-ui/src/api-client/generated/**`
5. The migrated hook behavior is tested directly, including Bash write attempts and patch attempts against protected files.
6. Repo skills needed for normal work are available through Codex from `.agents/skills`.
7. Docs, scripts, systemd units, and invariant tests refer to Codex/`AGENTS.md` conventions where appropriate.
8. Existing test and lint workflows still pass after the migration.

## Out of Scope

- Rewriting application code solely because it mentions Claude in user-facing product names, unless that code is part of the agent harness.
- Changing the public MCP server API under `apps/mcp/`.
- Removing historical notes from completed plans or verdicts unless they create active confusion for future agents.
- Replacing every Anthropic model reference in research docs that are intentionally about Anthropic or Pipecat Anthropic integrations.

## Open Questions

- Should `CLAUDE.md` compatibility symlinks remain for a transition period, or should the migration be Codex-only?
- Should worktrees move to `.codex/worktrees` or a tool-neutral `.agents/worktrees`?
- Should protected-path Codex hooks deny edits outright, or should they point agents to a human approval workflow outside the hook system?
- Which `.claude/skills` are still valuable enough to port, and which should be retired?
- Does the Telegram bot/runtime agent loop continue using Claude billing, or does that become a separate OpenAI/Codex migration epic?

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:codex-migration"`
