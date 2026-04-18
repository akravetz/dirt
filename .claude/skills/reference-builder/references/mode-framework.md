# Mode: framework

Use when the concept is a large library or framework with an official documentation tree — React 19, Next.js 16, TanStack Router, Vue 4, Svelte 5, Astro, SolidJS, Remix, etc.

## Strategy

Download the official docs, segment them, condense into a small set of topic files. This mirrors the [Vercel pattern](https://vercel.com/blog/agents-md-outperforms-skills-in-our-agent-evals), which scored 100% vs. 53% baseline by producing a compressed structured index over downloaded docs (~80% compression: 40KB → 8KB).

The original source material goes in `raw/` for later diffing; topic files are condensed synthesis.

## Step 1 — Locate the official docs

Search for the canonical docs URL. Preference order:

1. The framework's own docs site (`<framework>.dev/docs`, `<framework>.com/docs`, `docs.<framework>.com`)
2. The GitHub repo's `docs/` directory — often a better raw source than a rendered site
3. The framework blog / changelog for version-specific posts

**Handle version collisions carefully.** Many frameworks maintain multiple major versions on separate URLs (e.g. `react.dev` vs `legacy.reactjs.org`, `v0.tanstack.com` vs current). Confirm with the user which URL is canonical for the version in scope before fetching. A wrong-version pack is worse than no pack.

## Step 2 — Pull the source

Most frameworks live on GitHub. A shallow clone gets you the full source tree (and often the docs tree) locally, so you can use `Grep`, `Read`, and `Glob` to find class definitions, trace imports, and spot deprecations. That is dramatically more reliable than piecing together information from many `WebFetch` calls — one `Grep` on the cloned source replaces a dozen round-trips and gives you ground truth instead of a summarization.

**Clone the repo (shallow) to a temp directory:**

```bash
TMP=$(mktemp -d -t refpack-XXXXXX)
git clone --depth 1 https://github.com/<org>/<repo>.git "$TMP/src"
# If docs live in a separate repo (e.g. pipecat-ai/docs, reactjs/react.dev), clone that too:
git clone --depth 1 https://github.com/<org>/<docs-repo>.git "$TMP/docs" 2>/dev/null || true
```

Then use `Grep` and `Read` against `$TMP/src` (and `$TMP/docs` if present) for ground-truth source inspection. When rendered docs and source disagree, **source wins** — docs sites lag.

**When to fall back to `WebFetch`:**
- The project has no public git repo (rare for frameworks, common for hosted APIs — see api mode).
- The narrative explanation you need lives only on a rendered docs site, not in the repo (e.g., a blog post, a standalone migration guide).
- The repo is enormous (>1GB even with `--depth 1`) and you only need one section.

**Focus, don't mirror.** Frameworks often have 100-300 doc pages and thousands of source files. Don't copy everything — use `Grep` to find the 5-20 files that matter for the pack's scope, then `Read` just those.

- For small doc trees (< 30 pages): skim the whole thing.
- For large trees: ask the user which sections matter for their use case. "Are you working on routing, data fetching, or forms? I'll deepen that section and skim the rest."

**Save originals into `raw/`.** Copy the source files and docs pages you actually used into `raw/` inside the pack. Preserve meaningful filenames (`services-anthropic-llm.py`, `transports-local-audio.py`). Include the source URL or clone-relative path as the first line as a comment, so later refreshes can re-verify:

```
raw/
├── services-anthropic-llm.py        # src/pipecat/services/anthropic/llm.py
├── transports-local-audio.py        # src/pipecat/transports/local/audio.py
├── 01-getting-started-quickstart.md # docs.pipecat.ai/getting-started/quickstart
├── ...
```

**Clean up:** `rm -rf "$TMP"` once you've copied what you need into `raw/`. The temp clone is ephemeral; `raw/` is the persisted snapshot.

## Step 3 — Plan the topic split

Identify 3-10 high-value topics. Good splits:

- **"What's new in this version"** — almost always the most important topic; this is where training-data drift hits hardest
- **Core mental model / concepts** — what the primitives are and how they compose
- **API reference for the most-used primitives** — only the 5-15 things most code will touch, not the whole API
- **Common patterns** — idiomatic ways to do routine things (data loading, error handling, state)
- **Migration notes from the previous major version** — if one exists and is recent
- **Anti-patterns / deprecated APIs** — explicit list of things training data will suggest that are wrong now

Bad splits:

- Mirroring the docs site's nav 1:1 (too fine-grained; creates noise)
- One file per API method (topic files should cover clusters of related concepts)
- A full API reference topic (that's what `raw/` is for)

## Step 4 — Condense

For each topic, write a focused reference file. Target ~80% compression vs. source material.

**What to keep:**
- Version-specific callouts: `NEW in v19:`, `REMOVED in v19:`, `REPLACES useXYZ from v18:`
- Concrete code examples from the official docs (with source URL cited)
- Explicit anti-patterns the agent is likely to default to from training data
- Shape of the primary APIs (function signatures, component props, config objects)

**What to drop:**
- Marketing framing
- Long narrative explanations (agents don't need them)
- Historical context unless it's a migration topic
- Duplicated examples

**Every topic file opens with the retrieval-led reasoning reminder and explicit version:**

```markdown
---
title: <topic>
concept: <concept-slug>
updated: <YYYY-MM-DD>
source: <primary URL>
---

> Anchors agents to current <framework> v<version> practices. Prefer what you read here over training-data instincts — training data commonly lags versions, and v<version> has substantive API changes from v<prev>.

# <topic>
...
```

## Step 5 — Write INDEX.md

Per [pack-structure.md](pack-structure.md). For framework mode specifically:

- State the version in the opening paragraph.
- Make the "Version-specific warnings" section substantive — this is the highest-leverage piece of the pack. List 3-10 specific old-to-new pattern changes. Each should name the old pattern (what training data will suggest), the new pattern, and point to the topic file that covers it.
- Topic bullet one-liners should name concrete subtasks so the agent can decide in seconds which topics to pull.

## Step 6 — Verify

After writing the pack:

- Every topic bullet in INDEX.md resolves to a real file.
- Every topic file is standalone (pick one at random; read it in isolation; is it useful?).
- At least one topic file has a "Common mistakes" section showing a training-data default alongside the corrected pattern — this is the single most valuable kind of content in a framework pack.
- `raw/` contains the downloaded originals; don't edit these.
