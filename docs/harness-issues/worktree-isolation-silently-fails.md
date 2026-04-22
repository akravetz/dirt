# Claude Code Agent tool: `isolation: "worktree"` silently fails

**Observed:** 2026-04-21 during Phase-2 webapp-rewrite harness pilot.
**Session UUID:** `0732f17b-944c-4edf-a3ae-43634eed017c`.
**Host:** `/home/akcom/code/dirt` on the Dirt homebox.
**Upstream status:** matches multiple open GitHub issues (links at the bottom).

**Action for future agent reading this file:** re-derive the evidence below from the session JSONL, then either comment on the canonical upstream issue (#39886) with this session's fingerprint, or — if that issue has since been closed-as-fixed — open a new issue against `anthropics/claude-code` using the draft at the bottom of this file.

Do **not** paste the full session JSONL into the issue. Extract only the specific Agent tool-input entries and task-notification completion payloads that demonstrate the bug. The session JSONL is user-scoped and may contain other project context.

---

## The bug, three surface manifestations

All three showed up in the same session, all to Agent calls with parameters that should have been identical w.r.t. isolation behaviour:

```js
Agent({
  subagent_type: "general-purpose",
  model: "opus",
  isolation: "worktree",
  run_in_background: true,
  prompt: "...",
})
```

### Mode A — `isolation` silently ignored; agent runs in main

- `Agent(...)` returns a success-launch ack as normal.
- A worktree directory **is** created at `.claude/worktrees/agent-<id>/` (visible in `git worktree list`).
- The agent's file writes land on the **orchestrator's** working tree (i.e. main repo), not on the worktree.
- The completion `<task-notification>` block is **missing the `<worktree>` sub-block** entirely. Compare to a successful spawn which returns:
  ```xml
  <worktree>
    <worktreePath>/home/akcom/code/dirt/.claude/worktrees/agent-<id></worktreePath>
    <worktreeBranch>worktree-agent-<id></worktreeBranch>
  </worktree>
  ```
- The created worktree directory stays empty: `HEAD == main HEAD`, `git log main..HEAD` is empty, `git status --porcelain` inside the worktree is empty.
- Main's working tree has uncommitted modifications whose file surface matches the agent's declared scope.

This is the same class of failure as upstream issue #39886 and the comment at #48811 — our surface manifestation is an **absent** `<worktree>` block rather than a literal `null` string inside a populated block, but the underlying symptom (worktree never populated, agent ran in main) is identical.

### Mode B — isolation works, but commits vanish

- `Agent(...)` returns success-launch ack.
- Worktree is created and populated with the agent's file writes.
- Completion notification contains a populated `<worktree>` block (path + branch both non-null).
- But `git reflog worktree-agent-<id>` shows only `branch: Created from origin/main` — no commits.
- Agent's files remain uncommitted in the worktree. The agent's transcript may claim a simplify-pass ran (implying an earlier commit cycle), but no commit exists on the branch.

Matches upstream issue #29110 ("worktree data loss").

### Mode C — stream watchdog kills mid-work

- Agent stalls with `Agent stalled: no progress for 600s (stream watchdog did not recover)`.
- Last stream fragment is a partial assistant message (ours was `"Now update contract_status.json:"`).
- Typically compounds with Mode A: the stalled agent's partial work is on main's working tree, uncommitted.

Orthogonal to the isolation bug but frequently observed together because both kill the orchestrator's wrap-up assumptions.

---

## Evidence paths

### Primary — session JSONL (persistent)

```
~/.claude/projects/-home-akcom-code-dirt/<session-uuid>.jsonl
```

The session for this incident is `0732f17b-944c-4edf-a3ae-43634eed017c.jsonl`. If a future agent is re-running the extraction in a different session, pick the most recently modified JSONL matching the session of interest.

### Secondary — sub-agent transcripts (preserved in `debug/subagents/`)

This session's sub-agent transcripts have been preserved in the repo at `debug/subagents/` (**gitignored**, so they're on disk only, not in history). Six files — three failure cases (Modes A, A+C, B) and three working controls — with a README explaining each.

Relevant files for this bug:

- [`debug/subagents/mocks-setup-afc3dc7e-mode-A-isolation-skipped.jsonl`](../../debug/subagents/mocks-setup-afc3dc7e-mode-A-isolation-skipped.jsonl) — Mode A (isolation silently skipped).
- [`debug/subagents/backend-auth-af9e23e7-mode-A-plus-C-stalled.jsonl`](../../debug/subagents/backend-auth-af9e23e7-mode-A-plus-C-stalled.jsonl) — Mode A + Mode C (600s watchdog stall).
- [`debug/subagents/frontend-login-a31b6703-mode-B-commits-lost.jsonl`](../../debug/subagents/frontend-login-a31b6703-mode-B-commits-lost.jsonl) — Mode B (worktree populated, commits vanished).

Working controls (to compare against):

- [`debug/subagents/control-frontend-app-shell-respawn-a3a047f9-isolated-ok.jsonl`](../../debug/subagents/control-frontend-app-shell-respawn-a3a047f9-isolated-ok.jsonl)
- [`debug/subagents/control-pilot-backend-grow-current-a249f474-isolated-ok.jsonl`](../../debug/subagents/control-pilot-backend-grow-current-a249f474-isolated-ok.jsonl)
- [`debug/subagents/control-pilot-frontend-app-shell-ad3d50d9-isolated-ok.jsonl`](../../debug/subagents/control-pilot-frontend-app-shell-ad3d50d9-isolated-ok.jsonl)

See [`debug/subagents/README.md`](../../debug/subagents/README.md) for per-file descriptions and quick-triage commands (what did the sub-agent `pwd` see, where did its Write/Edit file-paths resolve to, where did the stall land).

### Tertiary — `/tmp` output files (original symlinks; volatile)

```
/tmp/claude-<uid>/-home-akcom-code-dirt/<project-ctx>/tasks/<task-id>.output
```

These are symlinks into `~/.claude/projects/-home-akcom-code-dirt/<session-uuid>/subagents/agent-<task-id>.jsonl`. The symlinks themselves don't survive `/tmp` wipes on reboot; the targets do, until `~/.claude/projects/` is pruned by ops or Claude Code itself. For this session we've captured independent copies in `debug/subagents/` (above) so the evidence survives either vector.

---

## Extraction recipes

All recipes assume you've located the session JSONL:

```bash
SESSION=$(ls -t ~/.claude/projects/-home-akcom-code-dirt/*.jsonl | head -1)
echo "using $SESSION"
```

### Recipe 1 — list every Agent tool invocation + its parameters

```bash
python3 <<PY
import json, os
SESSION = os.environ["SESSION"]
with open(SESSION) as f:
    for i, line in enumerate(f, 1):
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if obj.get("type") != "assistant":
            continue
        for item in (obj.get("message", {}).get("content") or []):
            if item.get("type") == "tool_use" and item.get("name") == "Agent":
                inp = item.get("input", {})
                print(json.dumps({
                    "line": i,
                    "description": inp.get("description"),
                    "isolation": inp.get("isolation"),
                    "run_in_background": inp.get("run_in_background"),
                    "subagent_type": inp.get("subagent_type"),
                    "model": inp.get("model"),
                }))
PY
```

**Expected for this bug report:** every generator spawn shows `isolation: "worktree"`. That proves the flag was *sent*; the bug is that it was *ignored*.

### Recipe 2 — flag completion notifications that lack `<worktree>` block

```bash
python3 <<PY
import json, os, re
SESSION = os.environ["SESSION"]
with open(SESSION) as f:
    for line in f:
        if "<task-notification>" not in line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        content = obj.get("message", {}).get("content", "")
        text = content if isinstance(content, str) else json.dumps(content)
        tid = re.search(r"<task-id>(.*?)</task-id>", text)
        status = re.search(r"<status>(.*?)</status>", text)
        has_wt = "<worktree>" in text
        print(f"task={(tid.group(1) if tid else '?')[:10]}  status={status.group(1) if status else '?'}  has_worktree_block={has_wt}")
PY
```

Any row with `status=completed` and `has_worktree_block=False` is a Mode A failure.

### Recipe 3 — verify Mode A by inspecting the orphaned worktree + main's working tree

For a suspected-failed agent id (from recipe 2):

```bash
AID=<first-8-chars-of-agentId>  # e.g. afc3dc7e
WT=/home/akcom/code/dirt/.claude/worktrees/agent-$AID
if [ -d "$WT" ]; then
  echo "worktree dir exists: $WT"
  echo "  HEAD:          $(cd "$WT" && git rev-parse HEAD)"
  echo "  ahead of main: $(cd "$WT" && git log --oneline main..HEAD | wc -l) commits"
  echo "  uncommitted:   $(cd "$WT" && git status --porcelain | wc -l) entries"
else
  echo "worktree dir was already cleaned; nothing to inspect"
fi
echo; echo "main's working tree (run from /home/akcom/code/dirt):"
(cd /home/akcom/code/dirt && git status --porcelain | head -20)
```

**Mode A signature:** worktree dir exists but is empty (0 commits ahead, 0 uncommitted), AND main has a substantive set of uncommitted modifications matching the agent's declared feature scope.

### Recipe 4 — verify Mode B by inspecting branch reflog

For a suspected-Mode-B agent:

```bash
AID=<first-8-chars>
git reflog worktree-agent-$AID --date=iso 2>&1 | head -10
```

**Mode B signature:** reflog shows only `branch: Created from origin/main` with no subsequent commit entries, even though the worktree on disk contains meaningful file changes.

---

## Related upstream issues

Before opening anything new, review these and **prefer commenting with a new-session fingerprint over duplicating**:

- [#39886 — `isolation: "worktree"` silently fails — agent runs in main repo](https://github.com/anthropics/claude-code/issues/39886) — closest match to Mode A. Previously closed as a duplicate of an earlier canonical issue.
- [#48811 — worktree isolation flag ignored for concurrent background agents](https://github.com/anthropics/claude-code/issues/48811) — same failure; the [comment at issuecomment-4255951128](https://github.com/anthropics/claude-code/issues/48811#issuecomment-4255951128) identifies `worktreePath: null` as the canonical fingerprint and recommends three harness-side fixes (sync worktree creation + verification, fail-fast on null, pre-op CWD check).
- [#33045 — `isolation: "worktree"` has no effect for team agents](https://github.com/anthropics/claude-code/issues/33045) — team-agent variant.
- [#37549 — `isolation: "worktree"` + `team_name` silently fails](https://github.com/anthropics/claude-code/issues/37549) — parameter-combo variant.
- [#29110 — Spawned agents: worktree data loss, plan mode loop](https://github.com/anthropics/claude-code/issues/29110) — matches Mode B.
- [#45645 — Worktree cleanup leaves stale git config](https://github.com/anthropics/claude-code/issues/45645) — unrelated but explains the long-lived `locked` orphan worktree entries in `git worktree list` from earlier sessions.

The canonical match is **#39886**. If it's still open, comment there with this session's evidence. If it has been closed-as-fixed and the behaviour is still reproducible, open a new issue referencing it.

---

## Draft GitHub issue body

Use this as a starting point. Fill in the `<< >>` placeholders with live data from the extraction recipes.

```markdown
### `isolation: "worktree"` silently ignored — `<worktree>` sub-block absent from completion notification

Observed in Claude Code (version `<<fill from `claude --version`>>`) during a session that spawned several background `Agent` calls with `isolation: "worktree"`. In a subset of spawns the flag was silently ignored: the agent ran in the orchestrator's working tree (main repo). The same parameters produced correct isolation for the other spawns in the same session. No error was raised.

### Fingerprint

The completion notification (`<task-notification>`) lacks the `<worktree>` sub-block that isolated spawns return.

Working case (isolation succeeded):
```xml
<worktree>
  <worktreePath>/home/.../.claude/worktrees/agent-<id></worktreePath>
  <worktreeBranch>worktree-agent-<id></worktreeBranch>
</worktree>
```

Failing case (isolation skipped — block absent):
```xml
<!-- no <worktree> block emitted; compare to the working spawn above in the same session -->
```

This is the same class of failure as #39886 and the analysis at #48811 (comment 4255951128). Our surface manifestation is an **absent** block rather than a literal `null` inside a populated block, but the underlying symptom (worktree never populated, agent ran in main repo) is identical.

### Reproduction context

- Version: `<<claude --version>>`
- Session UUID: `<<session uuid>>`
- Generator spawns: `N=<<total>>`, of which `K=<<failed>>` exhibited the absent-`<worktree>` block pattern. An additional spawn exhibited the Mode B variant described in #29110 (worktree populated but branch reflog empty).
- Repro cadence: intermittent; not tied to parallel vs. solo spawns — we saw one solo failure and one in-pair failure in the same session.

### Evidence

[Attach or paste the trimmed output of Recipes 1–3 from the harness-issues doc in the project repo.]

Key observations from the session JSONL:
- Every generator spawn was called with `isolation: "worktree"` (verified via tool-use entries in the session transcript).
- The failed spawns' completion notifications contain **no** `<worktree>` block.
- Their worktree directories at `.claude/worktrees/agent-<id>` were present but empty (HEAD == main, 0 commits, 0 uncommitted).
- The orchestrator's main working tree had substantive uncommitted modifications whose file surface matched the agents' declared scope — the agents' writes landed on main, not on the worktree.

### What I'd like

The three-layer fix 0xbrainkid proposes in #48811:
1. Synchronous worktree creation + `git worktree list` verification before the agent starts.
2. Fail-fast on null/absent `worktreePath` — return an error instead of silently skipping isolation.
3. Pre-operation CWD validation inside the agent — halt if `pwd` isn't the declared worktree path.

Any of (1) or (2) alone would prevent the whole failure mode: agents would either run in a real worktree or fail loudly at spawn time, instead of silently writing to main.
```

---

## Instructions for the future agent

1. Identify the session to report on. If the user pointed you at a specific session, use that. Otherwise pick the most recently modified `.jsonl` under `~/.claude/projects/-home-akcom-code-dirt/`.
2. Run Recipes 1–3 against that session. Save trimmed outputs for the issue body.
3. Check `git worktree list` and `git log main..<worktree-branch>` for every worktree-agent-* branch referenced in the session's task notifications. Record which isolated correctly vs. which exhibited Mode A or Mode B.
4. Cross-reference the related issues list above. If #39886 is still open, **comment there** rather than opening a duplicate. Use the draft body as the seed for your comment.
5. If #39886 is closed-as-fixed and behaviour still reproduces, open a new issue using the draft; link #39886 with "reported closed as fixed, reproducing on `<version>` in session `<uuid>`."
6. Run `claude --version` and fill that into the issue.
7. Do **not** paste the full session JSONL. Paste only the Agent input JSON + completion notification for the specific spawns that demonstrate the bug. Redact prompt contents if they contain user-specific secrets (unlikely for this bug's repros, but check).
8. After filing, append a line to this file under a new `## Filings` section: `- YYYY-MM-DD — <link to issue or comment> — <version reproduced on>`. Commit that change.
