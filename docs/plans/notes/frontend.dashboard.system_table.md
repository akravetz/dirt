# frontend.dashboard.system_table — generator notes

## Status: DONE (orchestrator-reconciled)

Feature committed by orchestrator after the generator exited on the
/simplify "returning control to the caller" handoff without making
the feat commit. Third occurrence of this exit pattern under the new
/simplify-in-feat runbook — 4/5 solo runs under the new runbook were
clean; this one broke. Possibly correlated with /simplify producing a
richer review (more real edits) making the handoff feel more
"review-final" to the model's exit heuristic.

## What's done

- `web-ui/src/ui/SystemTable.tsx` — 8-row device table. Each row
  renders the device name + a status badge with accessible indicator
  (textContent + aria-label). No color-only status signaling.
- `web-ui/src/routes/index.tsx` — SystemTable composed below
  PlantsStrip on the dashboard.
- `web-ui/src/mocks/handlers.ts` — `http.get("/api/system/devices", …)`
  returning 8 rows covering the status taxonomy (ok / listening /
  warn / offline).
- `web-ui/tests/e2e/dashboard-system-table.spec.ts` — 2 test blocks:
  8-row count, per-row status text match.

## Simplify pass (applied inline by the generator, committed by orchestrator)

- SystemTable.tsx: narrowed component props to `SystemTableRow {name, status}`;
  dropped dead fields (kind, last_seen, note) + the typo-laden
  `DeviceStatusKindKind` alias; removed redundant `data-status` attr.
- dashboard-system-table.spec.ts: removed dead `isAllowedStatus` type
  guard + `AllowedStatus` type; dropped `data-status` assertion;
  collapsed scoped-locator duplication.

## Acceptance

- `pnpm lint`, `pnpm typecheck`, `pnpm build` — all green.
- `pnpm test:e2e` — not re-run here; will run on main after cherry-pick.

## Harness observation

Same /simplify-handoff pattern that drove the structural fix in
commit 3a06109 is still firing intermittently. The WRAPUP_SENTINEL
forcing function works when the agent reaches W6, but the exit
happens BEFORE the feat commit even lands — the agent doesn't
traverse the runbook far enough for the sentinel to matter. Going
to propose the next hardening: tell agents explicitly that
`/simplify`'s output is a tool result (information) and that the
expected VERY NEXT tool call is Bash, specifically `git status +
git diff + git add + git commit`.
