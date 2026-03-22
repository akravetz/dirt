---
name: review-issue
description: Poll a GitHub issue for feedback comments, propose changes, implement on approval, post screenshots, and loop until the user signals completion.
disable-model-invocation: false
allowed-tools: Bash(gh *), Bash(uv *), Bash(kill *), Bash(lsof *), Bash(sleep *), Bash(curl *), Bash(timeout *), Read, Edit, Write, Grep, Glob, Agent, mcp__playwright__browser_navigate, mcp__playwright__browser_fill_form, mcp__playwright__browser_click, mcp__playwright__browser_take_screenshot, mcp__playwright__browser_snapshot, mcp__playwright__browser_wait_for
argument-hint: "<issue-number>"
---

# Review Issue — Feedback Loop

Poll a GitHub issue for new comments, process feedback, propose changes, implement on approval, post screenshots, and repeat until the user signals completion.

## Arguments

- `$1` — GitHub issue number to monitor

## The Loop

Each cycle has two phases:

### Phase 1: Feedback → Proposal

1. **Poll for new comments** using the polling script below. Track the last-seen comment ID.
2. **Read the comment.** If it contains a completion signal (`looks good`, `lgtm`, `approved`, `ship it`), post a closing comment and exit the loop.
3. **Analyze the feedback.** Read any referenced files, understand what change is being requested.
4. **Propose changes.** Post a comment on the issue describing:
   - What you plan to change (files, approach)
   - Why this addresses the feedback
   - Format: `## Proposed Changes\n- bullet points`
5. **Poll for approval.** Wait for the next comment. If the user approves (any affirmative response), proceed to Phase 2. If they redirect, revise the proposal.

### Phase 2: Implement → Verify → Screenshot

1. **Implement** the approved changes.
2. **Run tests:** `uv run pytest -v`. If tests fail, fix and re-run.
3. **Run lint:** `uv run ruff check src/ tests/ && uv run ruff format src/ tests/`
4. **Take a screenshot** if UI was changed:
   - Start server if needed (`uv run python main.py` in background)
   - Use Playwright MCP: navigate, log in (admin/changeme), screenshot the affected page
   - Upload screenshot: `gh release upload assets --repo akravetz/dirt <file> --clobber`
5. **Post result comment** on the issue:
   - What was changed (brief summary)
   - Screenshot (if UI change): `![description](https://github.com/akravetz/dirt/releases/download/assets/<file>)`
   - Test status: "X tests passing"
6. **Return to Phase 1** — poll for the next comment.

## Polling Script

To poll for new comments, run this in a loop:

```bash
# Get comments after a specific comment ID
LAST_ID=0  # or the ID of the last comment you processed
while true; do
    COMMENT=$(gh api repos/akravetz/dirt/issues/$ISSUE/comments \
        --jq "[.[] | select(.id > $LAST_ID) | select(.user.login != \"github-actions[bot]\")] | first // empty")
    if [ -n "$COMMENT" ]; then
        echo "$COMMENT"
        break
    fi
    sleep 5
done
```

Filter out bot comments and your own comments (check `user.login`). Only process comments from the issue author or collaborators.

## Completion Signals

Exit the loop when a comment contains any of these (case-insensitive):
- `looks good`
- `lgtm`
- `approved`
- `ship it`
- `close this`

On completion, offer to commit and push the changes.

## Important

- **Never implement without approval.** Always post a proposal and wait for the user to approve before writing code.
- **Always run tests** after implementing changes.
- **Always include a screenshot** when UI changes are made.
- **Track comment IDs** to avoid processing the same comment twice.
