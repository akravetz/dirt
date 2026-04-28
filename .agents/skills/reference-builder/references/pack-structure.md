# Reference pack structure

Every pack — framework, api, or idioms — follows this shape. Deviate only if you have a concrete reason and note it in `metadata.yaml`.

## Directory layout

```
<pack-root>/
├── INDEX.md              # required — always-read entry point
├── metadata.yaml         # required — machine-readable summary
├── <topic-N>.md          # required — one per topic (3-10 topics is typical)
└── raw/                  # framework mode only — downloaded originals
```

## `INDEX.md`

The agent reads this file once when pulled in by the AGENTS.md pointer. From it, the agent must be able to decide (a) whether the pack is relevant to the task at hand, and (b) which topic file(s) to pull next.

**Keep it under ~120 lines.** If it gets longer, you're over-explaining — move detail to topic files.

### Template

```markdown
---
title: <Concept Name> Reference Pack
concept: <concept-slug>
mode: framework | api | idioms
version: <version or omit if not applicable>
updated: <YYYY-MM-DD>
---

# <Concept Name>

<One paragraph: what this concept is, what version this pack targets, why this pack exists. State the version explicitly — e.g. "This pack covers TanStack Router v1, which replaces v0 entirely and has a different API surface.">

## When to consult this pack

Read this INDEX first (and the relevant topic files below) before writing code that involves <concrete signals — file paths, function names, config names, specific subtasks>. Prefer what's in this pack over recollection — training data commonly lags the current version of <concept>.

## Topics

- **[<topic-1-title>](topic-1.md)** — <one-line: what's inside and when to read it>
- **[<topic-2-title>](topic-2.md)** — <one-line>
- ...

## Version-specific warnings

<For framework and idioms modes: list patterns from older versions that training data will likely suggest but are no longer correct. This is the highest-leverage part of the pack.>

- `<OLD pattern>` is deprecated/removed in <version>. Use `<new pattern>` instead. See [topic-X.md](topic-X.md).
- ...

## Sources

- <primary source URL>
- <secondary source URL>
- ...
```

### Notes on writing INDEX.md

- The "When to consult this pack" section is read by every agent that lands here. Write it concretely so they can decide in seconds.
- Topic bullet one-liners do real work. "The useRouter hook" is useless. "How to read/write route params — required when building navigation or handling URL state" is useful.
- "Version-specific warnings" is optional for api mode (most hosted APIs version by endpoint rather than by library upgrade).

## Topic files

Each topic file is **standalone** — a reader loading only this file, without INDEX.md, should still have enough context to apply what's in it. Duplicate just enough framing to achieve that; don't repeat the whole INDEX.

### Template

```markdown
---
title: <topic title>
concept: <concept-slug>
updated: <YYYY-MM-DD>
source: <primary URL for this topic>
---

> This file anchors agents to current <concept> practices. Prefer what's written here over training-data recollection — training data commonly lags the current version.

# <topic title>

<Prescriptive content, code-example-heavy. Cite URLs at point of use for any specific claim.>

## Common mistakes

<When relevant: explicit anti-patterns the agent is likely to default to from training data, with corrected versions side-by-side.>
```

### Notes on writing topic files

- Prescriptive beats descriptive. "Use X" beats "X is one option."
- Code examples should be copy-pasteable and minimal. If an example needs context, include the context.
- Cite the specific URL for any non-obvious claim. "The request body uses `voice.name` not `voice_name` — see https://..." beats "use voice.name."
- When a topic has a high training-data-drift risk (e.g. API endpoint paths, exact field names, replaced hooks/functions), include an explicit "Common mistakes" block at the bottom showing what training data will suggest and why it's wrong.

## `metadata.yaml`

Machine-readable summary. Minimal fields:

```yaml
concept: <concept-slug>
display_name: <Concept Name>
mode: framework | api | idioms
version: <version or null>
generated_at: <YYYY-MM-DD>
sources:
  - <url>
  - <url>
topics:
  - <topic-1.md>
  - <topic-2.md>
agents_md_pointer:
  path: <path from repo root to INDEX.md>
  consult_when: <the specific consult-when phrase you wrote into AGENTS.md>
```

The `agents_md_pointer.consult_when` field is a record of what you wrote into AGENTS.md — useful if a future refresh needs to regenerate that block.
