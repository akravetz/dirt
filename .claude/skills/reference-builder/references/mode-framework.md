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

## Step 2 — Pull the docs

Use `WebFetch` to pull the docs index page, then iterate through the linked pages.

**Focus, don't mirror.** Framework docs often have 100-300 pages. Don't mirror the whole tree.

- For small trees (< 30 pages): fetch the whole thing.
- For large trees: ask the user which sections matter for their use case, then focus there. "Are you working on routing, data fetching, or forms? I'll deepen that section and skim the rest."

Save originals into `raw/` in the pack directory. Preserve the source URL structure in filenames:

```
raw/
├── 01-getting-started-installation.md
├── 01-getting-started-project-structure.md
├── 02-routing-defining-routes.md
├── ...
```

One file per fetched page. Include the source URL as the first line of each raw file, as a comment, so later refreshes can re-fetch.

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
