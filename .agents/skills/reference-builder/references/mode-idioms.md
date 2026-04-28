# Mode: idioms

Use when the concept is a language/ecosystem style guide or a version-specific set of practices. Examples: "modern idiomatic TypeScript", "Python 3.15 idioms", "modern React patterns", "idiomatic Rust 2024", "modern Go style".

## Strategy

No single doc tree to download; instead, harvest the best opinionated sources in the community and synthesize into prescriptive topic files. Triangulate multiple authoritative voices per claim — idioms are opinions, and an idioms pack without consensus is just one person's taste.

Idioms packs differ from framework packs in one important way: **they are prescriptive, not descriptive.** "Prefer X over Y" beats "X is one approach."

## Step 1 — Find authoritative sources

For each language/ecosystem, search for:

1. **Official release notes** for the version if one is specified — Python 3.15 What's New, TypeScript 5.x release posts, Rust edition guides
2. **Widely-cited voices** in the community — examples (non-exhaustive):
   - TypeScript: matklad, TkDodo, Dan Vanderkam (Effective TypeScript), Matt Pocock (total-typescript)
   - Python: PEP index, Hynek Schlawack, Real Python deep-dives, Raymond Hettinger talks
   - Rust: matklad, Without Boats, Rust blog, Jon Gjengset
   - React: react.dev, Dan Abramov's posts, TkDodo
   - Go: Dave Cheney, Go blog, Effective Go
   - Node/Bun: the runtimes' own docs, the Node/Bun team blogs
3. **Official linter / formatter config** as a source of truth — ruff (Python), biome (JS/TS), clippy (Rust), gofmt / golangci-lint (Go). What the tool enforces is codified community consensus.
4. **Recent "modern X" blog posts** from known voices — filter by recency (within the last 12-18 months ideally)

**Triangulate.** For each prescription in the pack, ensure at least 2-3 authoritative voices back it. If only one voice supports a claim, either mark it as opinionated or drop it.

## Step 2 — Organize by pattern, not by source

Topic splits that work well for idioms:

- **"Prefer X over Y"** — concrete substitutions (TypeScript: `satisfies` over type assertions; discriminated unions over enums; branded types over nominal hacks). This is the meat of an idioms pack.
- **"Use the version-specific feature"** — what's new in this version that replaces an older pattern. Python 3.15: `match` statements over chained `isinstance`. TypeScript 5.x: `const` type parameters, `using` declarations.
- **"Anti-patterns"** — explicit things not to do, with training-data-era examples. TypeScript: `enum`, `namespace`, `any` casts, class-based components for everything. Python: mutable default args, `import *`, `%`-formatting.
- **"Project scaffolding"** — file layout, dependency choices, build tooling. TS: biome over eslint+prettier in greenfield; Node: ESM-only; Python: uv + ruff over pip + black + flake8.
- **"Type / signature style"** — how to shape public APIs, what to export, how to name things.

Pick 3-6 topics. Keep them prescriptive — each topic should have clear "do / don't" content.

## Step 3 — Be opinionated; cite sources

Idioms packs without opinions are useless. Pick a lane per topic and state it clearly. **Every prescription gets a URL to the voice that codified it.** This lets the user audit the taste embedded in the pack and lets future agents understand the authority behind a claim.

Example of tight idioms writing:

```markdown
## Prefer `satisfies` over type assertions

For typed object literals where you want inference of the specific literal types but also want to check the shape, use `satisfies` (TS 4.9+) rather than `as` or a separate type annotation.

```ts
// Good
const routes = {
  home: "/",
  about: "/about",
} satisfies Record<string, `/${string}`>;

// Bad — widens the value types
const routes: Record<string, string> = { home: "/", about: "/about" };

// Bad — `as` skips the check
const routes = { home: "/", about: "/about" } as Record<string, string>;
```

Source: Matt Pocock, "satisfies operator" — https://www.totaltypescript.com/tips/satisfies
```

## Step 4 — Write topic files and INDEX.md

Per [pack-structure.md](pack-structure.md). For idioms mode:

- INDEX.md's "When to consult this pack" should trigger on `writing new <language> code`, `refactoring <language> code`, `choosing libraries or tooling for <language>`.
- The "Version-specific warnings" section should list the training-data defaults that are wrong now: "training data often uses `any`; use `unknown` and narrow"; "training data often uses `enum`; use discriminated unions or `as const` objects"; etc.
- No `raw/` directory — idioms mode is pure synthesis.

## Step 5 — Verify

- Every topic has clear do/don't pairs with code examples.
- Every prescription cites a URL (the voice or tool that backs it).
- INDEX.md "Version-specific warnings" lists at least 3-5 training-data defaults that should be overridden.
- No prescription depends on a single source — triangulate or mark opinion.
