# Progress Tracking

This directory tracks feature development across PRs and conversations. Each file represents a feature or work stream.

## Format

Each progress file should include:
- **Goal**: What we're building
- **Status**: Not started / In progress / Complete
- **Completed**: What's been done (with PR refs if applicable)
- **Next steps**: What remains

## Current Features

- **[webapp-rewrite.md](webapp-rewrite.md)** — Phase 0 ✅ (workspace split) + Phase 1 design ✅ (API + data-model proposals, pg cutover, service modules, test rework). Next: translate `docs/proposals/API.md` → `contracts/webapp-v1.yaml`, write contract invariant + plan JSON, get sign-off, freeze. Then Phase 2 = parallel FE + BE generator agents.
- **[architectural-invariants.json](architectural-invariants.json)** — shared INDEX. Holds harness rules, references, acceptance-criteria type definitions, and pointers to the two lane files below. Read-only for lane agents. Format follows Anthropic's long-running harness pattern (JSON over Markdown, per-item `status`/`acceptance_criteria`/`session_log`, verifier promotes `needs_verification` → `complete`).
  - **[architectural-invariants-python.json](architectural-invariants-python.json)** — Python lane (9 items). Import-linter layers, deptry, no-env-outside-config, no-blocking-IO-in-async, no-raw-SQL, no-print, no-asyncio.run, Ruff rule-set audit, Hypothesis properties.
  - **[architectural-invariants-typescript.json](architectural-invariants-typescript.json)** — TypeScript lane (18 items, XX-02 gates the rest). Protected `web-ui/invariants/` directory + shims + Python meta-invariant, strict tsconfig, eslint-plugin-boundaries, no-restricted-imports/syntax, no-fetch-outside-api-client, no-useEffect-fetch, no-literal-route-to, custom vi.mock rule, localStorage/window ownership, top-level-singleton ban, knip, api-client drift test, TanStack Router plugin, Tailwind palette guard, no-inline-style.
  - Lanes can run in parallel — file surfaces are disjoint. Only cross-lane gate: XX-02 must land before any TS-\* starts.
- **[phase1-skeleton.md](phase1-skeleton.md)** — historical; earliest scaffolding notes (pre-workspace-split).
