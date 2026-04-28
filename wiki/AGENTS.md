# wiki/AGENTS.md — Grow Wiki operating manual

This is the operating manual for the grow wiki. Two audiences:

1. **`ask_wiki` sub-agent** (`apps/voice/src/dirt_voice/tools/wiki.py`) — runs in `cwd=wiki/` and is told by its user prompt to read this file first. The "Sub-agent routing" section below is the fastest path to an answer.
2. **Human-prompted agents updating the wiki** (ingestion, daily updates, query filing) — the doc map at the bottom links to the standard operating procedures.

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
| breeding program (pollen, pheno hunt, cross procedure, F1/F2 vocab) | `breeding/README.md` first; then specific page (`breeding/<topic>.md`) |

### Don't

- **Don't `Read` `log.md`.** Append-only activity log, grows unboundedly, almost never answers a question directly. Grep only as a last resort.
- **Don't glob for files that don't exist.** Full top-level layout: `breeding/  concepts/  daily/  decisions/  environment/  hardware/  plants/`, plus `index.md`, `log.md`, `overview.md`, `wake-word-experiments.md`. There is no `schedule/`, `timeline/`, or `journal/`.
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

## Plant labeling

Plants are labeled **A, B, C, D** — matching the physical pot labels. Canonical naming throughout the wiki and in all agent work.

- Plant files: `wiki/plants/plant-a.md`, `wiki/plants/plant-b.md`, `wiki/plants/plant-c.md`, `wiki/plants/plant-d.md`
- Early documentation (before 2026-04-06) used numeric labels (Plant 1/2/3/4). The mapping was: 1→A, 2→B, 3→C, 4→D. Do NOT use the numeric labels; use A/B/C/D exclusively.

## Commands

- **Wiki lint**: `uv run scripts/lint.py` (run after every ingestion or daily update)
- **EXIF date extraction**: `uv run scripts/exif_date.py <file_or_directory>`

---

## Doc map (for the human-prompted agent audience)

The sub-agent (audience #1 above) rarely needs anything below this line — questions resolve from the routing table. The deep-dive docs are for ingestion, daily-update, and query-filing operations.

| Doc | Read before |
|---|---|
| [`../docs/wiki/data-architecture.md`](../docs/wiki/data-architecture.md) | inspecting `var/sessions/`, `var/raw/`, or the `wiki/` → `var/outputs/` flow |
| [`../docs/wiki/conventions.md`](../docs/wiki/conventions.md) | creating a new wiki page (frontmatter schema, file naming, no-duplication rule) |
| [`../docs/wiki/workflows/ingestion.md`](../docs/wiki/workflows/ingestion.md) | processing new material from `var/raw/` into the wiki |
| [`../docs/wiki/workflows/daily-update.md`](../docs/wiki/workflows/daily-update.md) | writing `wiki/daily/YYYY-MM-DD.md` (manual or daily-report driven) |
| [`../docs/wiki/workflows/query-filing.md`](../docs/wiki/workflows/query-filing.md) | filing a chat answer into the wiki |
| [`../docs/wiki/lint.md`](../docs/wiki/lint.md) | running `scripts/lint.py` or interpreting its output |
