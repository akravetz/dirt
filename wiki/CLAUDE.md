# wiki/CLAUDE.md — Grow Wiki operating manual

This is the operating manual for the grow wiki. Two audiences:

1. **`ask_wiki` sub-agent** (`src/dirt/tools/wiki.py`) — runs in `cwd=wiki/` and is told by its user prompt to read this file first. The "Sub-agent routing" section below is the fastest path to an answer.
2. **Human agents updating the wiki** (ingestion, daily updates, query filing) — the Workflows sections below are the standard operating procedure.

---

## Sub-agent routing (answer questions fast)

Answer from the smallest relevant file first. The table below tells you where to look for each question shape; read in the order given and stop as soon as you have the answer. Don't grep blindly, and don't read multiple large files when one section of `overview.md` would have answered it.

### Question type → file to read (in order)

| Question shape | File(s) |
|---|---|
| "what's next" / "what should I do" / "current plan" / "upcoming" | `overview.md` (Active Action Items + Upcoming Milestones) — **usually sufficient alone** |
| "how are the plants" / "current status" / per-plant status | `overview.md` (Plant Status table), then `plants/plant-[abcd].md` (Current State at top; Timeline below) |
| "how did X happen" / past observations | `daily/YYYY-MM-DD.md` (most recent first) |
| "why did we decide Y" / decision rationale | `decisions/YYYY-MM-DD-<slug>.md` |
| "what is VPD / LST / DLI / flushing / …" | `concepts/<topic>.md` |
| environment trends (temp, humidity, nutrients) | `environment/<topic>.md` |
| hardware (sensors, camera, voice, humidifier) | `hardware/<device>.md` |

### Don't

- **Don't `Read` `log.md`.** Append-only activity log, grows unboundedly, almost never answers a question directly. Grep only as a last resort.
- **Don't glob for files that don't exist.** Full top-level layout: `concepts/  daily/  decisions/  environment/  hardware/  plants/`, plus `index.md`, `log.md`, `overview.md`. There is no `schedule/`, `timeline/`, or `journal/`.
- **Don't read multiple full files when one section of `overview.md` answers the question.** Start there.

### Canonical sections in `overview.md`

Most "quick answer" questions resolve from these sections alone:

- **Setup** — strain, tent, light, nutrients, start date, grow day
- **Current Stage** — stage name + current-week activities
- **Plant Status** — per-plant node count, priority, current action
- **Environment (Last Reading)** — latest temp / humidity / VPD / pH / EC
- **Active Action Items** — what to do right now
- **Upcoming Milestones** — what's next

---

## Commands

- **Wiki lint**: `uv run scripts/lint.py` (run after every ingestion or daily update)
- **EXIF date extraction**: `uv run scripts/exif_date.py <file_or_directory>`

## Data Architecture

```
sessions/   Interaction transcripts. Append-only JSONL, written by harness. Agent reads on demand.
raw/        Immutable source material. Never edited after ingestion.
wiki/       LLM-maintained knowledge base. Single source of truth for synthesized knowledge.
outputs/    Generated reports, summaries, exports. Derived from wiki, never primary.
```

| Layer | Purpose | Who writes | Who reads |
|-------|---------|-----------|-----------|
| `sessions/` | Raw interaction transcripts | Harness (append-only) | Agent (on demand) |
| `raw/` | Source material (photos, sensor logs) | User / hardware | Agent (during ingestion) |
| `wiki/` | Curated knowledge | Agent | Agent + user |
| `outputs/` | Generated reports | Agent | User |

**sessions/** — Interaction transcripts, one JSONL file per day per channel. Written by the harness (`dirt-harness` user), read-only to the agent (`dirt-agent` user) via Linux group permissions. The agent may read these on demand (e.g., "what did we discuss yesterday?") but they are NOT loaded into context by default. See ADR 005 for the full access control model. Subfolders:
- `telegram/` — Telegram bot conversations (`YYYY-MM-DD.jsonl`)
- `voice/` — Voice interactions via Jabra speakerphone (`YYYY-MM-DD.jsonl`)

**raw/** — Drop zone for incoming material. Subfolders:
- `photos/` — Daily/weekly plant photos
- `sensor-logs/` — Temperature, humidity, VPD, CO2, pH, EC readings
- `chat-history/` — Conversational notes, questions, observations
- `references/` — Grow guides, nutrient schedules, strain info, etc.

**wiki/** — Agent-maintained knowledge base. All wiki files follow the page conventions below. Subfolders:
- `daily/` — One file per day (YYYY-MM-DD.md). Canonical observation records.
- `plants/` — One file per plant. Timelines + current state, linking into dailies.
- `environment/` — Trend pages for temp/humidity/VPD/lighting/nutrients/etc.
- `hardware/` — One file per deployed system (sensors, cameras, controllers). Operational state, wiring, configuration.
- `concepts/` — Reference knowledge for both growing and technical domains (e.g., VPD, LST, EC metering, sensor placement).
- `decisions/` — Dated decision records (e.g., switching to flower, choosing a PTZ camera, defoliating).
- `index.md` — Master catalog. Always up to date.
- `log.md` — Append-only activity log. Never edited, only appended.
- `overview.md` — High-level grow status + system status. Refreshed on each update.

**outputs/** — Exports only. Do not edit wiki files here; generate from wiki.

## Page Conventions

All wiki pages use YAML frontmatter:

```yaml
---
title: <page title>
type: daily | plant | environment | hardware | concept | decision | index | overview | log
sources: [raw/photos/2026-04-06.jpg, raw/sensor-logs/2026-04-06.csv]  # raw files referenced
related: [wiki/plants/plant-1.md, wiki/environment/humidity.md]       # wiki pages linked
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

**File naming:**
- Daily entries: `wiki/daily/YYYY-MM-DD.md`
- Concept pages: `wiki/concepts/concept-name.md`
- Decision pages: `wiki/decisions/YYYY-MM-DD-decision-name.md`
- Environment pages: `wiki/environment/topic.md` (e.g., `temperature.md`, `vpd.md`, `nutrients.md`)
- Hardware pages: `wiki/hardware/system-name.md` (e.g., `arduino-nano.md`, `ptz-camera.md`)

## Key Principle: NO DUPLICATION

Daily entries (`wiki/daily/`) are the **canonical record** of observations.

Plant, environment, and decision pages are **views** — they summarize and link into dailies. They do NOT duplicate observation data.

- A plant page's Timeline section has one-line entries like: `2026-04-06 — [Day 12: first pistils visible, minor tip burn](../daily/2026-04-06.md)`
- A plant page's Current State section has 1-2 sentences reflecting the latest daily.
- Environment pages track trends and notable events with links to source dailies.
- If something is recorded in a daily, don't re-record it elsewhere — link to it.

## Ingestion Workflow

When new raw material arrives in `raw/`:

1. Read `wiki/index.md` to understand current state.
2. Identify what's new (compare raw/ contents vs. sources cited in existing wiki pages).
3. For each new day's material, create/update `wiki/daily/YYYY-MM-DD.md` with full observations, photo notes, sensor readings, and recommendations.
4. Update each relevant plant page: add one-line timeline entry + update Current State (1-2 sentences + link to daily). Do not duplicate observation detail.
5. Update relevant environment pages: note trends, flag anomalies, link to daily entries.
6. Append to `wiki/log.md` with what was ingested.
7. Refresh `wiki/index.md` and `wiki/overview.md`.
8. **Run `uv run scripts/lint.py`** — fix any reported issues before considering ingestion complete.

## Daily Update Workflow

Triggered automatically at 14:00 MDT by the `dirt-daily-report.timer` systemd unit (see [`scripts/daily_report`](../scripts/daily_report) and `src/dirt/services/daily_report.py`). The orchestrator pans the camera through the five presets, snapshots sensors, then spawns a sub-agent (you, when invoked this way) with the `cwd=wiki/`, the photo paths, and a windowed sensor JSON in the user prompt. **Re-running for the same date is safe — overwrite the daily file and re-apply the plant-page / log / overview / index updates from scratch; the orchestrator's marker file prevents accidental duplicate Telegram sends, but the wiki update itself is idempotent.**

For manual / interactive runs, the user sends: photo(s) + sensor readings (and optionally notes/questions). Same workflow.

1. Create `wiki/daily/YYYY-MM-DD.md`:
   - Full photo observations for each plant (color, structure, canopy, any issues)
   - Sensor readings table (temp, RH, VPD, pH, EC, etc.)
   - Stage-appropriate recommendations and action items
   - Any user questions answered in context
2. Update each plant's page (`wiki/plants/plant-N.md`):
   - Append one-line entry to Timeline
   - Rewrite Current State (1-2 sentences max, link to today's daily)
3. Update relevant environment pages with trend data.
4. Append to `wiki/log.md`.
5. Rewrite `wiki/overview.md` with current grow status, system status, active action items, next milestones.
6. Refresh `wiki/index.md` (add daily entry link, update any changed pages).
7. **Run `uv run scripts/lint.py`** — fix any reported issues before considering the update complete.

## Query Workflow

After answering a user question or providing advice, evaluate whether the response is "filing-worthy" — meaning it should be persisted into the wiki rather than lost in chat history.

**Filing-worthy responses include:**
- Diagnoses or assessments (e.g., "Plant C's light green color is likely nitrogen deficiency because...")
- Comparisons or analyses
- Decision rationales (why we chose X over Y)
- New concepts explained for the first time
- Synthesized insights from multiple sources

**NOT filing-worthy:**
- Simple factual answers ("water at 6pm")
- Confirmations or acknowledgments
- Routine status updates already captured in daily entries

**Filing destinations:**
- Diagnosis/observation about a plant -> append to the relevant daily entry + update the plant page's current state
- New growing concept explained -> create a `concepts/` page
- New technical concept relevant to the grow -> create a `concepts/` page
- Hardware deployed or reconfigured -> create/update a `hardware/` page
- Decision made with rationale (grow or infrastructure) -> create a `decisions/` page
- Comparison or deep analysis -> file in `outputs/` and link from relevant wiki pages

**After filing:**
1. Update `wiki/index.md` if a new page was created
2. Update `wiki/log.md` with a `## [DATE] query-filed | Title` entry
3. Add backlinks from related pages
4. Run the deterministic lint (`uv run scripts/lint.py`)

## Linting Workflow

### Deterministic lint (run after every ingestion or daily update)

Run `uv run scripts/lint.py`. It performs 6 checks and exits non-zero if any fail:

1. **Index sync** — Parses `wiki/index.md` for markdown links; globs all `.md` files in `wiki/`. Flags files missing from the index and index entries pointing to nonexistent files.
2. **Backlink checker** — For each `wiki/daily/*.md`, checks whether plants mentioned in that entry are linked from the corresponding plant's Timeline section. Also verifies that all plant timeline links resolve to real daily files.
3. **Photo coverage** — Reads EXIF `DateTimeOriginal` (tag 36867) from all JPEGs in `raw/photos/`. Flags photo dates with no matching daily entry, and daily entries with no matching photo.
4. **Timeline continuity** — Parses dates from `wiki/daily/YYYY-MM-DD.md` filenames, sorts them, and reports any gaps between first and last entry.
5. **Overview staleness** — Compares the `updated` field in `wiki/overview.md` frontmatter against the most recent daily filename. Flags if overview is older.
6. **Frontmatter validation** — Every `.md` in `wiki/` (except `index.md` and `log.md`) must have YAML frontmatter with `title`, `type`, `created`, and `updated`. Flags missing or malformed frontmatter.
7. **File length** — Flags wiki files over 200 lines as a warning ("consider splitting") and over 400 lines as a failure ("should be split"). `index.md` and `log.md` are exempt (they grow naturally). Long files are a signal that a page is covering too many topics and should be broken into linked sub-pages.

Fix all reported issues before considering any update complete.

### LLM lint (weekly or on-demand)

The deterministic script cannot catch semantic issues. Periodically perform a deeper review using LLM reasoning:

- **Contradiction detection** — Read all plant pages and cross-reference claims (e.g., plant height, node count, health status) for inconsistencies across entries. Surface contradictions in `wiki/log.md` for user review; do not silently resolve them.
- **Concept gap finder** — Scan recent daily entries and flag domain terms (LST, VPD, flushing, trichomes, etc.) with no concepts/ page.
- **Overview rewrite** — When `wiki/overview.md` is stale (flagged by lint check 5), synthesize a new overview by reading the most recent daily entries and plant pages.

## Plant Labeling

Plants are labeled **A, B, C, D** — matching the physical pot labels. This is the canonical naming system used throughout the wiki and in all agent work.

- Plant files: `wiki/plants/plant-a.md`, `wiki/plants/plant-b.md`, `wiki/plants/plant-c.md`, `wiki/plants/plant-d.md`
- Early documentation (before 2026-04-06) used numeric labels (Plant 1/2/3/4). The mapping was: 1->A, 2->B, 3->C, 4->D. Do NOT use the numeric labels; use A/B/C/D exclusively.
