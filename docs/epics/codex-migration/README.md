# Epic: Codex Migration

Status: done
Priority: high
Created: 2026-04-28

## Goal

Move this repository's agent-facing workflow from Claude Code to Codex while preserving the operating manuals, protected-file boundaries, useful skills, and worktree conventions that keep agent work repeatable.

The highest-priority deliverable is the operating manual rename: every active `CLAUDE.md` becomes `AGENTS.md`, and references are updated so Codex discovers the same guidance Claude Code currently receives.

## Source References

- Codex `AGENTS.md` discovery: https://developers.openai.com/codex/guides/agents-md
- Codex hooks: https://developers.openai.com/codex/hooks
- Codex config reference: https://developers.openai.com/codex/config-reference
- Codex skills: https://developers.openai.com/codex/skills
- Codex subagents: https://developers.openai.com/codex/subagents
- Claude Code settings and hooks, for parity checks: https://code.claude.com/docs/en/settings and https://code.claude.com/docs/en/hooks

## Migration Principles

- Codex-only: do not keep `CLAUDE.md` compatibility symlinks.
- Minimal Codex config: only port shared settings that Codex actually needs, primarily hooks.
- Run Codex in yolo mode for normal work; do not spend migration effort recreating Claude permission modes, sandbox profiles, or command allow lists.
- Keep agent-owned temporary state under `.agents/`, not `.claude/` or `.codex/`, unless Codex requires a specific path.
- Keep product code separate from harness migration. The app's MCP server remains product code; user-level MCP client config is not part of this migration because we do not use MCP clients here.

## Scope

### 1. Rename Agent Manuals

- Rename root `CLAUDE.md` to `AGENTS.md`.
- Rename nested manuals:
  - `wiki/CLAUDE.md` -> `wiki/AGENTS.md`
  - `apps/wake-word/CLAUDE.md` -> `apps/wake-word/AGENTS.md`
- Update references from `CLAUDE.md` to `AGENTS.md` in active docs, scripts, systemd `Documentation=` links, tests, and comments.
- Preserve nested manual placement. Codex reads `AGENTS.md` from the repo root down to the current working directory, so nested manuals stay near the work they govern.
- Remove Claude compatibility manual files rather than leaving symlinks.

### 2. Migrate Protected-Path Hooks

- Replace `.claude/settings.json` with minimal Codex hook config in `.codex/config.toml` and/or `.codex/hooks.json`.
- Enable Codex hooks with `[features].codex_hooks = true`.
- Move hook scripts from `.claude/hooks/` to `.codex/hooks/`. These scripts are not vendor-neutral because they parse Codex tool input and emit Codex hook output.
- Port the Bash protected-path hook to Codex `PreToolUse` for `Bash`.
- Port the Edit/Write protected-path hook to Codex `PreToolUse` for `apply_patch`, using `tool_input.command` rather than Claude's `tool_input.file_path`.
- Protect the same paths:
  - `apps/tests/invariants/**`
  - `.githooks/**`
  - `web-ui/invariants/**`
  - `web-ui/src/api-client/generated/**`

#### Hook Decision Model

Codex does not currently support Claude-style `permissionDecision: "ask"` from `PreToolUse`. The Codex hooks docs explicitly say `permissionDecision: "allow"` and `"ask"` are parsed but not supported yet and fail open.

The safe v1 behavior is therefore:

- Return `permissionDecision: "deny"` for protected writes.
- Include a clear reason telling the agent to stop and ask the user for an explicit migration/human-owned-file exception.
- Do not rely on hooks to surface a one-click approval prompt while running in yolo mode.

Codex does have a `PermissionRequest` hook that can allow, deny, or decline to decide when Codex is already about to ask for approval. That does not solve protected-path prompting in yolo mode because no approval request is generated for the hook to intercept.

### 3. Simplify Harness Invariants

`apps/tests/invariants/test_webui_invariants_wired.py` currently does more than test TypeScript config wiring. It also asserts that `.claude/settings.json` contains `web-ui/invariants`, so the human-owned TypeScript invariant directory is protected by the Claude hook layer.

Remove that hook-config assertion during the migration instead of porting it to Codex. A pytest that reads agent harness settings is too indirect, and Codex/Claude settings changes already require explicit user intent in normal work. The invariant should stay focused on product-adjacent TypeScript wiring: protected config exists, shims import or extend it, and live ESLint/TypeScript resolution keeps the intended sentinel rules enabled.

Migration work:

- Rename the test and comments from Claude-specific language to Codex/harness language.
- Delete the `.claude/settings.json` assertion from `test_webui_invariants_wired.py`.
- Keep the existing ESLint and TypeScript shim/sentinel checks.
- Do not add a replacement pytest that checks Codex hook configuration.

### 4. Migrate Skills

- Move the useful Claude skills directly into `.agents/skills`, then fix them up as needed.
- Keep:
  - `.claude/skills/unstuck` -> `.agents/skills/unstuck`
  - `.claude/skills/reference-builder` -> `.agents/skills/reference-builder`
- Remove the Claude skills we do not want to keep:
  - `.claude/skills/review-issue`
  - `.claude/skills/close-issue`
  - `.claude/skills/create-issue`
  - `.claude/skills/skill-creator`, unless there is a specific local reason to keep it instead of Codex's bundled skill creator.
- Audit retained skills for Claude-only fields and assumptions.
- Remove `.codex/skills -> ../.agents/skills`. Codex reads repository skills from `.agents/skills` directly.

### 5. Minimal Codex Config

- Add only the project-level Codex config needed for shared behavior:
  - hook enablement
  - hook declarations, if not using `.codex/hooks.json`
- Do not port Claude permission allow/ask/deny lists.
- Do not build Codex rules or sandbox profiles unless a concrete failure shows yolo mode plus hooks is insufficient.
- Update docs that tell agents to use Claude-specific commands, permission modes, or approval flows.

### 6. Worktrees and Legacy Plans

- Move manual agent worktrees to `.agents/worktrees`.
- Add `.agents/worktrees/` to `.gitignore`.
- Update `scripts/worktree-port` and any active docs that still reference `.claude/worktrees`.
- Remove `docs/plans/` and anything in it as legacy Claude-era planning cruft.
- Do not migrate the old generator/orchestrator docs unless a currently active workflow still depends on them.

### 7. Runtime Claude Integrations

- Do not include runtime `claude -p`, `claude-agent-sdk`, Telegram bot, or Anthropic model migration in this epic.
- Track runtime agent migration as a separate Codex/OpenAI epic if we decide to move those systems.
- Leave the application MCP server under `apps/mcp/` alone; it is product code, not Claude harness config.
- Do not add Codex MCP client config as part of this epic because we do not currently use MCP clients.

## Acceptance Criteria

1. No active checked-in operating manual is named `CLAUDE.md`; intended manuals are named `AGENTS.md`.
2. Root, wiki, and wake-word Codex guidance loads from the expected `AGENTS.md` files.
3. Active references in docs, scripts, systemd units, comments, and tests use `AGENTS.md` and Codex terminology where appropriate.
4. `.claude/` project harness config is removed after any still-useful hooks and skills are migrated.
5. `.codex/skills` symlink is removed.
6. `.agents/skills` contains the retained skills: `simplify`, `unstuck`, and `reference-builder`.
7. `.agents/worktrees/` is gitignored and active worktree docs/scripts point there.
8. `docs/plans/` is removed if no active workflow depends on it.
9. Codex hooks are enabled and block protected writes to the same paths the Claude hooks protected.
10. Hook behavior is tested directly for Bash and `apply_patch` protected-write attempts.
11. The `.claude/settings.json` assertion is removed from `test_webui_invariants_wired.py`; no replacement pytest checks Codex hook wiring.
12. Existing test and lint workflows still pass after the migration.

## Out of Scope

- Keeping Claude Code compatibility files.
- Recreating Claude permission/sandbox behavior in Codex.
- Migrating user-level MCP client settings.
- Changing the public MCP server API under `apps/mcp/`.
- Migrating runtime Claude integrations such as Telegram bot agent loops or `claude-agent-sdk`.
- Rewriting historical notes solely because they mention Claude, unless they confuse active agent instructions.
- Replacing Anthropic model references in reference docs that are intentionally about Anthropic or Pipecat Anthropic integrations.

## Decisions

- No `CLAUDE.md` compatibility symlinks.
- Worktrees move to `.agents/worktrees`.
- Hook scripts move to `.codex/hooks`.
- Retain only `unstuck` and `reference-builder` from `.claude/skills`.
- Remove `.codex/skills` symlink.
- Minimal Codex settings: hooks only unless later evidence says otherwise.
- Runtime Claude migration is a separate epic.

## Open Questions

- Resolved 2026-04-28: protected writes use hard deny plus an explicit human-exception instruction, because Codex `PreToolUse` does not currently support `ask`.

## Issues

Find issues for this epic: `gh issue list --repo akravetz/dirt --label "epic:codex-migration"`
