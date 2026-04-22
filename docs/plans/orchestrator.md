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

## Resuming specifically from where Session 0732f17b left off

At the time of writing this playbook (2026-04-21, session `0732f17b`), the state was:

### Done
- `frontend.app.shell` (pilot FE) — merged to main.
- `backend.grow.current` (pilot BE) — merged to main.
- `frontend.mocks.setup` — merged to main, status flipped, verdict reconciled.

### Reverted as trash (isolation bug casualties)
- `backend.auth` — agent stalled at 600s watchdog, isolation failed, ~60% complete partial work on main's working tree; reverted.
- `frontend.login` — agent's worktree populated but commits vanished (Mode B); reverted.

### Pending, unblocked, ordered by plan JSON list position
- `backend.auth` (top of BE list). Big feature: auth API + SPA static serving + Jinja handler removal. Plan JSON has detailed `implementation_notes`. Iteration budget suggestion: 18.
- `frontend.login` (top of FE list). Depends on `backend.auth`. With MSW now available (`frontend.mocks.setup` is done), this is the FIRST TRUE PARALLEL FE — it mocks `/api/auth/*` via MSW handlers in `web-ui/src/mocks/handlers.ts` and doesn't wait for BE. Visual criterion at `docs/plans/refs/login.png`. Iteration budget: 15.
- `backend.sensors.current`, `backend.sensors.history`, and eight other zero-dep BE features sit further down the list.

### Harness changes that landed in this session
- Evaluator prompt: off-limits diff is against **local main**, not origin/main.
- Plan JSON: visual acceptance entries accept optional `threshold_pct` override.
- Plan JSON: `frontend.mocks.setup` feature added + landed; MSW v2 reference pack at `docs/references/msw-v2/` anchors future FE agents away from v1 patterns.
- Plan JSON: `backend.auth` user_story + implementation_notes folded in the SPA static-serving swap.
- `web-ui/invariants/eslint.config.ts`: new `mocks` element-type + scoped boundaries.
- `apps/tests/invariants/test_webui_invariants_wired.py`: `_strip_line_comments` regex ordering fix.
- `docs/harness-issues/worktree-isolation-silently-fails.md` + `debug/subagents/` evidence corpus.
- This playbook.

### Recommended next move

**Resume with `backend.auth` + `frontend.login` as a parallel pair**, using the manual-worktree pattern documented above. The pair is already planned and the infrastructure to run them is in place:

```bash
# Step 0:
git worktree add /home/akcom/code/dirt/.claude/worktrees/backend.auth \
    -b feat/be/backend.auth main
git worktree add /home/akcom/code/dirt/.claude/worktrees/frontend.login \
    -b feat/fe/frontend.login main
```

Then spawn both generators in a single Agent-tool message with the skeleton from `docs/plans/generator-prompts.md`, `{{WORKTREE_PATH}}` populated, **no `isolation` flag**. Substitutions:

- BE: `{{FEATURE_ID}}=backend.auth`, `{{BRANCH}}=feat/be/backend.auth`, iteration budget 18.
- FE: `{{FEATURE_ID}}=frontend.login`, `{{BRANCH}}=feat/fe/frontend.login`, iteration budget 15, explicit reminder to consume MSW (`docs/references/msw-v2/INDEX.md` is mandatory pre-read).

Confirm with the user before spawning — backend.auth's blast radius is larger than anything done so far (it deletes Jinja, adds SPA static serving, modifies AuthMiddleware).

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

- **2026-04-21 — session `0732f17b-944c-4edf-a3ae-43634eed017c`**: Phase-2 pilot + harness shakedown. Landed: `frontend.app.shell`, `backend.grow.current`, `frontend.mocks.setup`. Surfaced: Claude Code `isolation: "worktree"` silent failure (see `docs/harness-issues/worktree-isolation-silently-fails.md`; evidence preserved at `debug/subagents/`). Reverted two in-flight generator runs poisoned by that bug (`backend.auth`, `frontend.login`). Switched harness to manual-worktree pattern documented in this file. Next: re-spawn `backend.auth` + `frontend.login` as the first true parallel pair under the new pattern.
