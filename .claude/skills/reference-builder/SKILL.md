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

### Step 3 — Delegate the build to a subagent

**This step is what keeps the main conversation's context clean.** The research and writing phase involves reading hundreds of lines of source code, cloning repos, and drafting long topic files — none of which the user needs to see. Do NOT do this work inline. Spawn a subagent to perform it and relay only its summary.

Use the `Agent` tool with `subagent_type: "general-purpose"`. The subagent has no memory of this conversation, so the prompt must be fully self-contained.

**Before spawning**, determine and embed in the prompt:

- The skill's base directory — at skill invocation time you were told `Base directory for this skill: <SKILL_BASE_DIR>`. Use that absolute path. The subagent will read the skill's mode and pack-structure references from there.
- The concept's slug (lowercase, hyphenated, version embedded): `tanstack-router-v1`, `deepgram-tts-v3`, `modern-idiomatic-typescript`.
- The mode (`framework` / `api` / `idioms`) the user confirmed.
- The repo root and project `CLAUDE.md` absolute path. Fall back to `.claude/knowledge/<slug>/` if no `docs/` directory exists at the repo root.
- A first-draft `Consult when…` phrase for the CLAUDE.md bullet. The subagent may refine it, but having one in the prompt anchors the "name concrete file paths / function names / subtasks" expectation — generic phrases are the single most common failure mode.

**Prompt template** (fill in the angle-bracketed placeholders):

```
You are executing the build phase of the reference-builder skill. The main
conversation has already scoped the concept and confirmed the mode — your job
is to do the research, condense it into a pack, and wire a pointer into
CLAUDE.md. Work autonomously; the user will not see your intermediate tool
calls, only your final report.

Inputs:
  Concept: <Concept Name + version>
  Slug:    <slug>
  Mode:    <framework | api | idioms>
  Pack target directory: <absolute path, e.g. /repo/docs/references/<slug>/>
  Project CLAUDE.md:     <absolute path>
  First-draft "Consult when…" phrase: <phrase>

Read these files first, in order, and follow them:
  1. <SKILL_BASE_DIR>/references/mode-<mode>.md  — sourcing + condensation strategy for this mode
  2. <SKILL_BASE_DIR>/references/pack-structure.md — required pack layout + INDEX.md / topic file / metadata.yaml templates
  3. <SKILL_BASE_DIR>/assets/claude-md-block.md   — CLAUDE.md block template

Then execute end-to-end:
  - Source material per the mode instructions (shallow git clone to /tmp, WebFetch, etc.). Clean up temp dirs when done.
  - Write INDEX.md, 3-10 topic files, and metadata.yaml into the pack target directory. Framework mode additionally populates raw/ with the actual source files you used, filename-preserved.
  - Wire the pointer into CLAUDE.md: append to the existing `## Framework/API References` section, replace the bullet if the concept is already listed, or create the section if missing (place it near the top, below the project overview). Refine the "Consult when…" phrase to name concrete file paths / function names / subtasks.
  - If the pack directory already exists, delete it first and regenerate (fresh overwrite; no merge).

Verify before reporting:
  - Every topic bullet in INDEX.md resolves to a real file.
  - Every topic file has frontmatter with title/concept/updated/source.
  - metadata.yaml is populated with `claude_md_pointer.consult_when` reflecting what you wrote.
  - CLAUDE.md has the new/updated bullet.

Report back in under 250 words, structured as:
  - Pack path
  - Topic filenames (one per line)
  - The CLAUDE.md bullet you wrote, verbatim
  - Any non-obvious decisions you made (version chosen, topic scope, skipped sections, WebFetch fallbacks)
  - Anything that failed, was skipped, or should be re-run

Do NOT paste topic file contents, source-file contents, or long narration into your report. The report must be scannable in 30 seconds — everything else lives in the pack itself.
```

### Step 4 — Relay the summary and do a lightweight verify

When the subagent returns:

1. **Sanity-check the pack exists.** One `Glob` for `<pack-dir>/*.md` and one `Glob` on CLAUDE.md for the new bullet is enough. Do NOT re-read the topic files — they exist for future agents, not for revalidation now. If the subagent claimed work it didn't do, the Globs will expose it.
2. **Relay to the user.** Pack path, concepts now wired in CLAUDE.md, a one-line note on how to refresh (`re-run /reference-builder with the same concept`), and any caveats the subagent surfaced.
3. **Do NOT reprint the pack contents or the subagent's tool trace.** The whole point of delegation is that the main conversation stays short.

## Design principles

**Progressive disclosure.** `INDEX.md` is the only file read every time the pack is consulted. Topic files load on demand. Keep `INDEX.md` under ~120 lines.

**Anti-hallucination framing in every file.** Every topic file opens with a short "retrieval-led reasoning" reminder — the pack is authoritative for this concept and overrides training-data instincts. This framing matters; it's what makes the pack work against the pull of training data.

**Cite sources at the point of use.** Every claim that could become stale gets a URL next to it. Users can audit; future agents can re-verify.

**Condense, don't dump.** Target ~80% compression vs. the source material (the Vercel number). Terse, high-density synthesis beats wholesale copies. Framework mode stores originals in `raw/` for reference, but topic files must be condensed.

**Fresh overwrite.** Re-running on the same slug replaces the pack. No merge, no diff, no stale detection. The user re-runs when they want the pack refreshed.

**The CLAUDE.md pointer is the whole point.** A pack without a pointer might as well not exist. A pointer without a pack is useless. Always produce both.

**Delegate the build; keep the main conversation clean.** Steps 1-2 (classify, confirm) must run in the main conversation because they need the user's judgment. Steps 3+ (source ingestion, condensation, pack writing, CLAUDE.md wiring) must NOT — they pull hundreds of lines of source and generate thousands of lines of output, which bloats the caller's context window for zero user benefit. Always spawn a subagent for the build phase and relay only its summary. The only exception is if the subagent tooling is unavailable in the current environment; in that case say so and ask the user whether to proceed inline.
