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
- **[phase1-skeleton.md](phase1-skeleton.md)** — historical; earliest scaffolding notes (pre-workspace-split).
