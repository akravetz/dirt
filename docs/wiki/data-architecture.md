# Wiki Data Architecture

Read before inspecting `var/sessions/`, `var/raw/`, or the `wiki/` → `var/outputs/` flow. Defines what each layer is, who writes it, and who reads it.

## Layers

```
sessions/   Interaction transcripts. Append-only JSONL, written by harness. Agent reads on demand.
raw/        Immutable source material. Never edited after ingestion.
wiki/       LLM-maintained knowledge base. Single source of truth for synthesized knowledge.
outputs/    Generated reports, summaries, exports. Derived from wiki, never primary.
```

## sessions/

Interaction transcripts, one JSONL file per day per channel. Written by the harness (`dirt-harness` user), read-only to the agent (`dirt-agent` user) via Linux group permissions. The agent may read these on demand (e.g., "what did we discuss yesterday?") but they are NOT loaded into context by default. See [ADR 005](../adrs/005-conversation-data-isolation.md) for the full access control model. Subfolders:

- `telegram/` — Telegram bot conversations (`YYYY-MM-DD.jsonl`)
- `voice/` — Voice interactions via Jabra speakerphone (`YYYY-MM-DD.jsonl`)

## raw/

Drop zone for incoming material. Subfolders:

- `photos/` — Daily/weekly plant photos
- `sensor-logs/` — Temperature, humidity, VPD, CO2, pH, EC readings
- `chat-history/` — Conversational notes, questions, observations
- `references/` — Grow guides, nutrient schedules, strain info, etc.

## wiki/

Agent-maintained knowledge base. All wiki files follow the conventions in [`conventions.md`](conventions.md). Subfolders:

- `daily/` — One file per day (`YYYY-MM-DD.md`). Canonical observation records.
- `plants/` — One file per plant (A–D). Timelines + current state, linking into dailies.
- `environment/` — Trend pages for temp/humidity/VPD/lighting/nutrients/etc.
- `hardware/` — One file per deployed system (sensors, cameras, controllers). Operational state, wiring, configuration.
- `concepts/` — Reference knowledge for both growing and technical domains (e.g., VPD, LST, EC metering, sensor placement).
- `decisions/` — Dated decision records (e.g., switching to flower, choosing a PTZ camera, defoliating).
- `breeding/` — Operating manual for the small breeding program (pollen handling, pheno-hunt protocol, cross procedure, isolation). Frontmatter `type: breeding`. Background on the breeder lives in `concepts/oregon-breeding-group.md`.
- `index.md` — Master catalog. Always up to date.
- `log.md` — Append-only activity log. Never edited, only appended.
- `overview.md` — High-level grow status + system status. Refreshed on each update.

## outputs/

Exports only. Do not edit wiki files here; generate from wiki.
