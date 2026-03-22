---
name: close-issue
description: Close a GitHub issue with a summary comment. If the work included UI changes, capture and attach a screenshot via Playwright MCP.
disable-model-invocation: false
allowed-tools: Bash(gh *), mcp__playwright__browser_navigate, mcp__playwright__browser_fill_form, mcp__playwright__browser_click, mcp__playwright__browser_take_screenshot, mcp__playwright__browser_snapshot, Read, Grep, Glob
argument-hint: "<issue-number>"
---

# Close GitHub Issue

Close a GitHub issue with a summary of what was done. If the work involved UI changes, attach a screenshot.

## Arguments

- `$1` — GitHub issue number

## Steps

### 1. Determine if UI changes were made

Check if the work touched any of these:
- `src/dirt/templates/` — HTML templates
- `src/dirt/api/feed.py` or other endpoints returning HTML
- Static assets (CSS, JS)
- Any user-facing page behavior

If yes, proceed to step 2. If no, skip to step 3.

### 2. Capture screenshot (UI changes only)

1. Ensure the server is running (`uv run python main.py` in background if needed).
2. Use Playwright MCP to navigate to the affected page:
   - Navigate to `http://localhost:8000`
   - Log in with credentials from `.env` (default: admin/changeme)
   - Navigate to the page that changed
3. Take a screenshot: `mcp__playwright__browser_take_screenshot` with a descriptive filename.
4. Upload as a GitHub release asset:
   ```bash
   # Create the assets release if it doesn't exist
   gh release create assets --repo akravetz/dirt --title "Assets" --notes "Image assets for issues" 2>/dev/null || true
   # Upload (--clobber overwrites if name exists)
   gh release upload assets --repo akravetz/dirt <screenshot-file> --clobber
   ```
5. Get the URL: `https://github.com/akravetz/dirt/releases/download/assets/<filename>`

### 3. Post closing comment

```bash
gh issue comment <number> --repo akravetz/dirt --body "$(cat <<'BODY'
## Done

<Brief summary of what was implemented>

![Screenshot description](https://github.com/akravetz/dirt/releases/download/assets/<filename>)

BODY
)"
```

Omit the image line if no UI changes were made.

### 4. Close the issue

```bash
gh issue close <number> --repo akravetz/dirt
```

## Why screenshots matter

Screenshots provide visual evidence that UI work is complete and correct. For a private repo, images must be hosted via GitHub release assets — `raw.githubusercontent.com` returns 404 for unauthenticated requests to private repos.
