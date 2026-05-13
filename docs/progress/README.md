# Progress Tracking

This directory tracks feature development across PRs and conversations. Each file represents a feature or work stream.

## Format

Each progress file should include:
- **Goal**: What we're building
- **Status**: Not started / In progress / Complete
- **Completed**: What's been done (with PR refs if applicable)
- **Next steps**: What remains

## Current Features

- **[webapp-rewrite.md](webapp-rewrite.md)** — Phase 0 ✅ (workspace split) + Phase 1 design ✅ (API + data-model proposals, pg cutover, service modules) + architectural-invariant hardening ✅ (PY-01..09, TS-01..16, XX-01/02 in `apps/tests/invariants/` and `web-ui/invariants/`) + Phase 1 contract freeze ✅ (`contracts/webapp-v1.yaml`, generated Pydantic + TS clients, legacy contract invariant now retired, `docs/plans/webapp-rewrite.json` with 29 features; tag `contract-frozen-2026-04-20`). Next 🟢: Phase 2 = parallel FE + BE generator agents.
