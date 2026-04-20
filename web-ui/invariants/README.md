# web-ui/invariants/ — HUMAN-OWNED

This directory holds the **source of truth** for every architectural invariant
that applies to `web-ui/` (TypeScript / React / TanStack Router / Tailwind v4).
It is the TypeScript-side mirror of `apps/tests/invariants/` on the Python
side, and it is subject to the same discipline:

> **You MUST NOT modify any file under `web-ui/invariants/**` to make a
> failing lint / typecheck pass.** Invariants encode architecturally load-bearing
> rules. If a rule fires on your code, fix the code — do not downgrade, disable,
> or carve a hole in the rule.

The Claude Code hook at `.claude/hooks/protect-invariants.sh` prompts before
any Edit/Write to this directory; the Python meta-invariant
`apps/tests/invariants/test_webui_invariants_wired.py` asserts that the
editable shims at `web-ui/eslint.config.ts` and `web-ui/tsconfig.json` still
wire through the protected files, tamper-evident against downgrades-by-override.

## Layout

- `eslint.config.ts`   — flat ESLint config; exported as `Linter.Config[]`.
- `tsconfig.base.json` — strict compilerOptions; the root shim `extends` this.
- `knip.json`          — unused-exports/files/deps config.
- `rules/`             — custom ESLint rules (TypeScript, flat-config inline plugin pattern).

## Editing protocol

1. If a rule is too narrow/broad: edit it here and commit with message
   `invariant(TS-XX): <reason>` — human review required.
2. If a legitimate app-specific override is needed (new path alias, new
   feature slice): edit the **shim** at `web-ui/eslint.config.ts` or
   `web-ui/tsconfig.json`, not this directory. App-specific overrides must
   not downgrade severity of any rule resolved by the meta-invariant's
   `KNOWN_SENTINELS` list.
3. Never use `eslint-disable` / `@ts-ignore` inside this directory.

## Adding a new invariant

Each TS-XX item in `docs/progress/architectural-invariants-typescript.json`
adds one rule here and appends one sentinel to `KNOWN_SENTINELS` in the
meta-invariant test, so `eslint --print-config` / `tsc --showConfig` keep
asserting the rule resolves at severity=error / the flag is set.
