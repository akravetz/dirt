# Wiki Page Conventions

Read before creating a new wiki page. Defines frontmatter schema, file naming, and the no-duplication rule that keeps the wiki searchable.

## Frontmatter

All wiki pages use YAML frontmatter:

```yaml
---
title: <page title>
type: daily | plant | environment | hardware | concept | decision | index | overview | log | breeding
sources: [raw/photos/2026-04-06.jpg, raw/sensor-logs/2026-04-06.csv]  # raw files referenced
related: [wiki/plants/plant-a.md, wiki/environment/humidity.md]       # wiki pages linked
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

`index.md` and `log.md` are exempt from frontmatter (verified by `scripts/lint.py`'s frontmatter check).

## File naming

- Daily entries: `wiki/daily/YYYY-MM-DD.md`
- Concept pages: `wiki/concepts/<concept-name>.md`
- Decision pages: `wiki/decisions/YYYY-MM-DD-<decision-name>.md`
- Environment pages: `wiki/environment/<topic>.md` (e.g., `temperature.md`, `vpd.md`, `nutrients.md`)
- Hardware pages: `wiki/hardware/<system-name>.md` (e.g., `arduino-nano.md`, `ptz-camera.md`)
- Plant pages: `wiki/plants/plant-{a,b,c,d}.md` (canonical labels — see "Plant labeling" in `wiki/AGENTS.md`)

## NO DUPLICATION

Daily entries (`wiki/daily/`) are the **canonical record** of observations.

Plant, environment, and decision pages are **views** — they summarize and link into dailies. They do NOT duplicate observation data.

- A plant page's Timeline section has one-line entries like: `2026-04-06 — [Day 12: first pistils visible, minor tip burn](../daily/2026-04-06.md)`
- A plant page's Current State section has 1–2 sentences reflecting the latest daily.
- Environment pages track trends and notable events with links to source dailies.
- If something is recorded in a daily, don't re-record it elsewhere — link to it.
