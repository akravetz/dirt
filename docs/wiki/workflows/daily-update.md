# Wiki Daily Update Workflow

Read before writing `wiki/daily/YYYY-MM-DD.md` (whether triggered manually or by the daily-report orchestrator).

Triggered automatically at 14:00 MDT by the `dirt-daily-report.timer` systemd unit (see [`scripts/daily_report`](../../../scripts/daily_report) and `apps/shared/src/dirt_shared/services/daily_report.py`). The orchestrator pans the main camera through the five presets, adds any configured extra tent overview photos such as the breeding tent, snapshots scoped sensors, then spawns a sub-agent (you, when invoked this way) with `cwd=wiki/`, the photo paths, and a windowed sensor JSON in the user prompt.

**Re-running for the same date is safe** — overwrite the daily file and re-apply the plant-page / log / overview / index updates from scratch; the orchestrator's marker file prevents accidental duplicate Telegram sends, but the wiki update itself is idempotent.

For manual / interactive runs, the user sends: photo(s) + sensor readings (and optionally notes/questions). Same workflow.

## Steps

1. **Create `wiki/daily/YYYY-MM-DD.md`:**
   - Full photo observations for each plant (color, structure, canopy, any issues)
   - Concise scoped tent updates for any extra tent photo/sensor sections, especially breeding when present
   - Sensor readings table (temp, RH, VPD, pH, EC, etc.)
   - Soil-moisture trend notes should emphasize relative movement; absolute calibrated percentages are rough context until probes are calibrated in-place
   - Stage-appropriate recommendations and action items
   - Any user questions answered in context
2. **Update each plant's page** (`wiki/plants/plant-{a,b,c,d}.md`):
   - Append one-line entry to Timeline
   - Rewrite Current State (1–2 sentences max, link to today's daily)
3. **Update relevant environment pages** with trend data.
4. **Append to `wiki/log.md`.**
5. **Rewrite `wiki/overview.md`** with current grow status, system status, active action items, next milestones.
6. **Refresh `wiki/index.md`** (add daily entry link, update any changed pages).
7. **Run `uv run scripts/lint.py`** — fix any reported issues before considering the update complete. See [`../lint.md`](../lint.md).
