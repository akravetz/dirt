# Wiki Ingestion Workflow

Read before processing new material from `var/raw/` into the wiki.

When new raw material arrives in `raw/`:

1. Read `wiki/index.md` to understand current state.
2. Identify what's new — compare `var/raw/` contents vs. `sources` cited in existing wiki pages.
3. For each new day's material, create/update `wiki/daily/YYYY-MM-DD.md` with full observations, photo notes, sensor readings, and recommendations.
4. Update each relevant plant page: add one-line timeline entry + update Current State (1–2 sentences + link to daily). **Do not duplicate observation detail** — see the no-duplication rule in [`../conventions.md`](../conventions.md).
5. Update relevant environment pages: note trends, flag anomalies, link to daily entries.
6. Append to `wiki/log.md` with what was ingested.
7. Refresh `wiki/index.md` and `wiki/overview.md`.
8. **Run `uv run scripts/lint.py`** — fix any reported issues before considering ingestion complete. See [`../lint.md`](../lint.md) for what the lint checks.
