---
name: reference-builder
description: Build a local reference pack for a technical concept (framework, hosted API, or language idioms) so agents stop reverting to training-data patterns and start following current best practices. Use this skill whenever the user wants to "anchor" future agent work to a specific framework version (React 19, TanStack Router v1, Vue 4), a hosted API (Deepgram TTS, Gemini 3.1 Live, OpenAI Responses API), or a language/stylistic standard (modern idiomatic TypeScript, Python 3.15 idioms, modern React patterns). Also trigger when the user mentions hallucination problems with library versions, asks for documentation for a specific version, says things like "make sure Claude uses X" or "prevent training-data drift for Y," or references a newer library/API version and wants to avoid outdated patterns. The skill produces a local pack of reference docs AND wires an always-loaded pointer in CLAUDE.md — the pointer is what actually changes agent behavior.
---

# Reference Builder

Produces a local, progressively-disclosed reference pack for a specific technical concept, then wires an always-loaded pointer into the project's `CLAUDE.md` so future agent sessions consult the pack before writing code.

## Why this skill exists

LLMs have a measurable tendency to revert to training-data patterns when working with newer frameworks, APIs, or stylistic conventions. Vercel's public eval on Next.js 16 APIs found:

- No docs: 53% pass rate
- Plain skills (on-demand): 53% — same as no docs, because agents don't reliably recognize when to retrieve
- Skills with explicit triggering instructions: 79%
- AGENTS.md-style compressed index in the always-loaded system prompt: 100%

Source: https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals

**Load-bearing lesson:** the pointer in CLAUDE.md is what actually gets the pack read. The pack itself is just what the pointer points to. This skill produces both; skipping the CLAUDE.md step makes the skill useless.

## What it produces

A pack directory:

```
docs/references/<concept-slug>/        (falls back to .claude/knowledge/<concept-slug>/ if docs/ doesn't exist)
├── INDEX.md                           # entry point — always-read when pack is consulted
├── metadata.yaml                      # concept, mode, version, generated_at, sources
├── <topic-1>.md                       # one file per topic (3-10 typical)
├── <topic-2>.md
└── raw/                               # framework mode only: downloaded originals
```

And a block in the project's `CLAUDE.md`:

```markdown
## Framework/API References

Knowledge packs live in `docs/references/`. Before writing code that touches any of these concepts, read the linked `INDEX.md` first — the pack anchors to current practice and should override any conflicting training-data instincts.

- **<Concept Name>** — `docs/references/<slug>/INDEX.md`. Consult when <specific-when-to-consult>.
```

## Workflow

### Step 1 — Get the concept

The user provides a technical concept. If it's ambiguous (e.g. just "React" with no version), ask for a concrete name + version before proceeding. Examples of good inputs:

- `TanStack Router v1` (framework)
- `Deepgram TTS v3` (api)
- `modern idiomatic TypeScript` (idioms)

### Step 2 — Classify the mode, confirm with the user

Classify using these heuristics:

| Signal | Likely mode |
|---|---|
| Major library/framework name, often with version (React 19, Next.js 16, Vue 4, TanStack X, Svelte 5, Astro) | **framework** |
| Hosted service + product/endpoint (Deepgram TTS, Gemini Live, Stripe Terminal, Supabase Realtime, OpenAI Responses) | **api** |
| "modern idiomatic X", "X idioms", "best practices for X", language-name + version where the focus is style (Python 3.15 idioms, idiomatic Rust 2024, modern React patterns) | **idioms** |

State your classification and the sourcing approach in one sentence, then wait for confirmation. This is cheap and prevents wasted research time if you guessed wrong.

Example:
> I'd treat "TanStack Router v1" as **framework** mode — I'll pull the official docs tree and condense it into a pack. OK?

### Step 3 — Run the mode-specific workflow

Once the mode is confirmed, read the matching reference file and follow it:

- **framework** → [references/mode-framework.md](references/mode-framework.md)
- **api** → [references/mode-api.md](references/mode-api.md)
- **idioms** → [references/mode-idioms.md](references/mode-idioms.md)

All three modes produce the same output shape (defined in [references/pack-structure.md](references/pack-structure.md)) but source and condense differently.

### Step 4 — Write the pack

Create the pack directory. Default: `docs/references/<concept-slug>/`. If the project has no `docs/` directory, fall back to `.claude/knowledge/<concept-slug>/`. Slug rules: lowercase, hyphenated, version embedded (`tanstack-router-v1`, `deepgram-tts-v3`, `modern-idiomatic-typescript`).

Populate `INDEX.md`, topic files, and `metadata.yaml` per [references/pack-structure.md](references/pack-structure.md).

**Fresh overwrite on re-run.** If the slug directory already exists, remove it and regenerate. No merge logic.

### Step 5 — Wire the CLAUDE.md pointer

This step is what makes the skill work. Don't skip it.

Find the project's `CLAUDE.md` (usually repo root). Look for an existing `## Framework/API References` section:

- **Section exists, concept not listed** → append a new bullet.
- **Section exists, concept already listed** → replace that bullet (fresh overwrite).
- **Section doesn't exist** → add it. Place it near the top of CLAUDE.md, below the project overview but above deeper sections. Use the block template in [assets/claude-md-block.md](assets/claude-md-block.md).

Each bullet has three parts:
1. **Concept name** (bold)
2. Path to the pack's `INDEX.md` (relative to repo root)
3. A specific "Consult when..." phrase

The "Consult when..." phrase is the single most important sentence in the pack. Write it concretely — `when writing route definitions, loaders, or search-param handling` beats `when using TanStack Router`. Generic phrases get ignored by future agents scanning CLAUDE.md for relevance.

### Step 6 — Verify and report

1. `INDEX.md` exists and its Topics list references every topic file.
2. Every topic file has frontmatter and reads usefully in isolation.
3. `metadata.yaml` is populated.
4. `CLAUDE.md` has the pointer with a specific when-to-consult phrase.
5. Report to the user: the pack path, the concepts now wired in CLAUDE.md, and a one-line note on what to re-run to refresh.

## Design principles

**Progressive disclosure.** `INDEX.md` is the only file read every time the pack is consulted. Topic files load on demand. Keep `INDEX.md` under ~120 lines.

**Anti-hallucination framing in every file.** Every topic file opens with a short "retrieval-led reasoning" reminder — the pack is authoritative for this concept and overrides training-data instincts. This framing matters; it's what makes the pack work against the pull of training data.

**Cite sources at the point of use.** Every claim that could become stale gets a URL next to it. Users can audit; future agents can re-verify.

**Condense, don't dump.** Target ~80% compression vs. the source material (the Vercel number). Terse, high-density synthesis beats wholesale copies. Framework mode stores originals in `raw/` for reference, but topic files must be condensed.

**Fresh overwrite.** Re-running on the same slug replaces the pack. No merge, no diff, no stale detection. The user re-runs when they want the pack refreshed.

**The CLAUDE.md pointer is the whole point.** A pack without a pointer might as well not exist. A pointer without a pack is useless. Always produce both.
