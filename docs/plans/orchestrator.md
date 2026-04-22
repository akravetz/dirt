# Orchestrator Playbook — Phase 2 Dirt Webapp Rewrite

**Who this is for:** a future agent (or human) picking up the Phase-2 harness mid-flight and wanting to continue spawning generator + evaluator pairs without re-learning everything from scratch.

**Read first, in this order:**

1. This file end-to-end. It's the map.
2. [`docs/plans/webapp-rewrite.json`](webapp-rewrite.json) — the frozen plan; `features[].status` is the source of truth for what's done.
3. [`docs/plans/generator-prompts.md`](generator-prompts.md) — the full generator + evaluator prompt skeletons you'll fill in.
4. [`docs/harness-issues/worktree-isolation-silently-fails.md`](../harness-issues/worktree-isolation-silently-fails.md) — the Claude Code bug that drives the "manual worktree" pattern below. Don't skip this; the built-in `isolation: "worktree"` flag is NOT safe.
5. `CLAUDE.md` (repo root) — project overview, commit conventions, invariant test layout.

---

## Current state — how to read it

At any point the answer to "where are we?" is derivable from git + the plan JSON:

```bash
# What's in the plan?
jq -r '.features[] | [.id, .lane, .status, (.depends_on | join(","))] | @tsv' \
  docs/plans/webapp-rewrite.json | column -t -s $'\t'

# Which features have verdict files (evaluator ran)?
ls docs/plans/verdicts/ 2>/dev/null

# Which feature branches exist locally (some may be orphaned)?
git branch --list 'feat/*'

# Which worktrees are live?
git worktree list
```

A feature is truly **done** when all of these hold:

- `features[id=X].status == "done"` in the plan JSON.
- A verdict file `docs/plans/verdicts/X.json` exists with `"overall": "pass"` (allow for `orchestrator_reconciled_at` fields when the evaluator's verdict was deferred on a human-owned-file criterion).
- The commits land on `main` (cherry-picked from the feature branch).
- `docs/plans/notes/X.md` exists (generator's NOTES, captured at merge time).

If any of those diverge, you've got unfinished orchestrator bookkeeping — fix that before spawning anything new.

---

## Decision: which feature(s) next?

The plan JSON's `depends_on` graph drives sequencing. Pick from "top of each lane's pending list" unless there's a specific reason to pair differently. **Top-of-lane pending** = first entry in `features[]` with `status == "pending"` and every `depends_on` already `done`.

```bash
# Suggest next candidates (not automated — manual review):
jq -r '.features[] | select(.status=="pending") | [.id, .lane, (.depends_on | join(","))] | @tsv' \
  docs/plans/webapp-rewrite.json | head -10
```

Confirm with the user before spawning, especially when:

- A feature has `removes_legacy` entries — those delete currently-working routes, which can break `main` until the replacement lands.
- Two features touch the same files (usually they don't because the plan's file assignments are disjoint — but worth checking with `jq`).
- A feature's `implementation_notes` names symbols you can't locate in the codebase — the plan may have drifted. See `docs/plans/webapp-rewrite.json`'s recent commits for examples of drift fixes.

---

## Harness pattern — manual worktrees + first-call `cd` guard

**Do not use `isolation: "worktree"` on Agent tool calls.** It silently fails ~30% of the time in recent observations (see `docs/harness-issues/worktree-isolation-silently-fails.md`). Instead:

### Step 0 — pre-create the worktree (orchestrator bash)

```bash
FEATURE_ID=<e.g. backend.sensors.current>
LANE=<backend|frontend>
BRANCH=feat/${LANE:0:2}/$FEATURE_ID   # feat/be/... or feat/fe/...
WT=/home/akcom/code/dirt/.claude/worktrees/$FEATURE_ID

git worktree add "$WT" -b "$BRANCH" main

# Fresh worktrees don't share node_modules (gitignored). Three FE
# invariants (test_typescript_dead_code, test_webui_invariants_wired
# x2) shell out to pnpm exec {biome,tsc,eslint} and fail env-level
# without node_modules. Install once per new worktree so pre-commit
# stays green for the generator's first commit.
(cd "$WT/web-ui" && pnpm install --frozen-lockfile) &
wait
```

One worktree per feature; two worktrees for a parallel BE+FE pair. Branch name `feat/<lane-prefix>/<feature_id>` matches the plan JSON's `lanes.*.worktree_branch_prefix` convention.

### Step 1 — spawn the generator(s)

Single Agent tool message, one call per pair member, all `run_in_background: true`. The prompt fills in the `docs/plans/generator-prompts.md` skeleton with the feature-specific substitutions, **including `{{WORKTREE_PATH}}` set to the absolute path from Step 0**. The shared skeleton's opening block tells the generator to `cd {{WORKTREE_PATH}}` as its first tool call and to abort with "STUCK: worktree mismatch" if `pwd` doesn't match.

Typical spawn parameters:

```
subagent_type: general-purpose
model: opus
run_in_background: true
# do NOT pass isolation
prompt: <filled-in generator skeleton + lane block>
```

### Step 2 — wait for completion notifications

They arrive asynchronously. Each notification's `<task-notification>` carries `<status>`, a summary, and — critically for the pre-Agent-tool-fix version of the harness — a `<worktree>` sub-block if the tool believed it created one. With manual worktrees we ignore that block entirely.

### Step 3 — per-spawn post-completion verification (orchestrator bash)

```bash
# What landed on the branch?
git log main..$BRANCH --oneline

# Anything uncommitted in the worktree?
git -C "$WT" status --porcelain

# Anything on MAIN's working tree that shouldn't be there?
cd /home/akcom/code/dirt && git status --porcelain | grep -v '^ M wiki/hardware/'
```

Interpret:

- Commits on the branch + clean worktree + clean main → generator wrapped up normally. Proceed to evaluator.
- Commits on the branch + uncommitted residue in the worktree → generator did work but didn't commit the tail (often simplify-pass artifacts or NOTES). Containerize: commit the residue on-branch if it's correct, or discard. Then evaluator.
- No commits, uncommitted residue in the worktree → agent exited mid-flow; the `cd` guard held. Triage: commit as-is if reviewable, or re-spawn with feedback, or discard.
- Anything on main's working tree matching the feature's scope → the `cd` guard FAILED (the generator bypassed step 1's instruction). This is a serious deviation — containerize to a proper feature branch by hand, and flag the failure in the next spawn's prompt.
- Watchdog stall ("no progress for 600s") → the agent's stream died; same triage as "no commits + residue" but with additional "agent may have been mid-edit" caveat.

### Step 4 — spawn the evaluator

Evaluators are read-only; they don't need their own worktree. Spawn them with the target worktree path as `{{WORKTREE_PATH}}` so the cold-context evaluator knows where to `cd` for diff inspection + test runs.

```
subagent_type: general-purpose
model: opus
run_in_background: true
# do NOT pass isolation
prompt: <filled-in evaluator skeleton + lane block>
```

The evaluator emits a verdict to `docs/plans/verdicts/<feature_id>.json` (absolute path) and echoes it as the last fenced ```json``` block of stdout. See the Evaluator prompt section of `docs/plans/generator-prompts.md`.

### Step 5 — route the verdict

Read the verdict file:

- `"overall": "pass"` → cherry-pick the branch onto main, flip `status: "done"` in plan JSON, commit the status flip + verdict file together, push.
- `"overall": "fail"` + `escalation.to == "generator"` → re-spawn the generator with `suggested_feedback_for_generator` prepended to the original prompt. Use a fresh worktree (delete the old one).
- `"overall": "fail"` + `escalation.to == "planner"` → a criterion is blocked on an edit the generator can't make (typically a `web-ui/invariants/**` or `apps/tests/invariants/**` change). You (orchestrator/human) make the edit, commit it, then either re-run the evaluator or reconcile the verdict file manually (preserve the original `evaluated_at` timestamp, add `orchestrator_reconciled_at`, update the specific criterion's status + evidence, update `overall`).
- `"overall": "fail"` + `escalation.to == "human"` → stop. An off-limits was touched, or a hard-fail condition hit. Surface to the user before any remediation.

### Step 6 — cleanup after merge

```bash
# After successful cherry-pick + status flip:
git worktree remove -f "$WT"
git branch -D "$BRANCH"
```

Known quirk (upstream bug #45645): stale `.claude/worktrees/agent-<hash>/` dirs from the Agent tool's earlier isolation-broken era may accumulate as `locked` entries. They don't block work but you can force-remove periodically:

```bash
for wt in $(git worktree list --porcelain | awk '/^worktree / && / \/.claude\/worktrees\/agent-/ {print $2}'); do
  git worktree remove -f -f "$wt" 2>/dev/null
done
```

---

## Committing orchestrator work

Orchestrator commits have their own style — they're not feature commits. Use `docs(plans):`, `invariant(...):`, or `docs(harness-issues):` prefixes depending on what's being committed. Representative examples in the recent git log:

```bash
git log --oneline -15 | grep -E '(docs\(plans\)|invariant|docs\(harness-issues\))' | head
```

Pre-commit hooks run on every commit (ruff/biome/eslint/pytest invariants); if they modify files, recover with `git add -A` + re-commit, never `--no-verify`.

---

## Current state (as of the latest Session log entry)

Read the ## Session log section at the bottom of this file for the most recent entry; its "next move" line is the fastest resume path. The paragraphs above (harness pattern, wrap-up protocol, etc.) are stable across sessions and don't need re-reading every time.

---

## Session-persistence checklist

When you finish a session (especially one where you did something unusual or landed an ADR-adjacent decision), update this file under a new `## Session log` heading at the end, one entry per session, with:

- Session UUID (from `~/.claude/projects/-home-akcom-code-dirt/`).
- Date.
- One-sentence summary of what moved.
- Any harness-level surprises discovered — link to the `docs/harness-issues/` file if one was written.
- Pointer to the next-move state at session end.

This file is the baton. Keep it current so the next agent can pick up without re-reading the whole history.

## Session log

- **2026-04-21 — session `0732f17b-944c-4edf-a3ae-43634eed017c`**: Phase-2 pilot + harness shakedown. Landed: `frontend.app.shell`, `backend.grow.current`, `frontend.mocks.setup`, `backend.auth`, `frontend.login`, **`backend.sensors.current`**, **`frontend.e2e.setup`**. Surfaced: Claude Code `isolation: "worktree"` silent failure (see `docs/harness-issues/worktree-isolation-silently-fails.md`; evidence preserved at `debug/subagents/`). Switched harness to manual-worktree pattern with a cd-first guard; pattern held 4/4 on this session's pairs (`backend.auth`+`frontend.login` re-spawn, then `backend.sensors.current`+`frontend.e2e.setup`). Introduced the `/simplify` 7-step mandatory wrap-up checklist with the explicit "returning control is NOT your exit signal" callout — VALIDATED end-to-end on the sensors + e2e pair (both agents did all 7 steps cleanly, no manual orchestrator wrap-up needed). Landed the `contract_status.json` carve-out in `.claude/hooks/protect-invariants*.sh`; exercised on `backend.sensors.current` without a human-ask prompt. Adopted the implementer-writes-tests model for FE: `frontend.e2e.setup` delivers Playwright infra + `tests/e2e/app-shell.spec.ts` as the bootstrap spec; generator/evaluator prompts updated for `kind: "e2e"` (implementer writes .spec.ts; evaluator runs it AND audits coverage per plan description). Added `scripts/worktree-port` + wired into vite + playwright configs + package.json — each worktree gets its own deterministic dev port, no manual env-overrides. **Next move**: next BE/FE pair is **`backend.sensors.history`** (zero deps; thin wrapper reusing `ReadingsService._BUCKET_SQL`) and **`frontend.dashboard.gauges`** (first FE feature under the new `kind: "e2e"` pattern — depends on `backend.sensors.current` which now exists on main AND `frontend.mocks.setup` + `frontend.e2e.setup` which both landed this session). Gauges is the real test of the implementer-writes-tests + evaluator-coverage-audit model; the generator authors `web-ui/tests/e2e/dashboard-gauges.spec.ts` itself. Note re cherry-picking: `--allow-empty` simplify commits are dropped by default during cherry-pick — either use `git cherry-pick --allow-empty` per range OR accept that main's log shows the feat+notes pair (the branch itself retains the empty simplify commit as a positive signal).
