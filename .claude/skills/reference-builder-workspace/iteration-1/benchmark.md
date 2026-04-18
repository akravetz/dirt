# Skill Benchmark: reference-builder — Iteration 1

**Date**: 2026-04-17
**Model**: claude-opus-4-7 (subagents)
**Runs per configuration**: 1 per eval (3 evals, with-skill + baseline each)

## Run contamination caveat

The 6 subagents were launched with `isolation: "worktree"`, but analysis of the outputs shows the isolation was only partial. Symptoms:

- Eval 2 baseline produced a pack with a file list identical to the with-skill output. Its own narrative said it "filled in the five missing sibling files the INDEX promised" — meaning it saw the with-skill pack already partially on disk.
- Eval 1 with-skill noted the pack dir "already existed with a prior, differently-structured version" and overwrote it (fresh-overwrite rule). That prior version was the baseline's output.
- Eval 3 was cleanly isolated (its notification included a worktree path).

Baselines for evals 1 and 2 cannot be treated as independent signal. The with-skill outputs are clean artifacts and were evaluated on merit. Eval 3's baseline is the one clean head-to-head.

## Summary (with contamination caveat)

| Metric | With Skill | Baseline | Delta |
|---|---|---|---|
| Pass rate — eval 1 (framework) | 10/10 (100%) | 4/10 (40%) | +60 pp |
| Pass rate — eval 2 (api) ⚠ contaminated | 10/10 (100%) | 10/10 (100%) ⚠ | n/a |
| Pass rate — eval 3 (idioms) — clean | 10/10 (100%) | 6/10 (60%) | +40 pp |
| Mean (excluding contaminated) | 100% | 50% | +50 pp |
| Wall time (s) | 419 / 447 / 613 | 457 / 551 / 877 | — |
| Tokens | 97k / 81k / 125k | 77k / 86k / 97k | — |

## Per-eval breakdown

### Eval 1 — Framework (TanStack Router v1)
- **With skill: 10/10** — Pack matches skill contract exactly: INDEX.md with 10-item version-warnings section, 5 topic files + `raw/` with 27 downloaded originals, metadata.yaml, CLAUDE.md pointer with specific consult-when phrase.
- **Baseline: 4/10** — Reasonable pack (7 topic files including anti-patterns.md with 14 WRONG/RIGHT pairs), but used README.md as entry, no INDEX.md, no metadata.yaml, no raw/. Lost structural contract points.

### Eval 2 — API (Deepgram TTS → Aura-2)
- **With skill: 10/10** — Agent correctly identified that "v3" is a user misnomer (Deepgram versioned voice models, not API surface). Pack slugged `deepgram-tts-aura-2`. `wire-format-rest.md` pins all hallucination-prone details verbatim with per-claim URLs. INDEX warnings call out `voice_id`, nested `voice.*`, `model` in body, WS `"chunk"`/`"partial"` — all the real failure modes.
- **Baseline: 10/10 (contaminated)** — File list and CLAUDE.md content match the with-skill run. Not independent signal.

### Eval 3 — Idioms (modern TypeScript) — clean
- **With skill: 10/10** — Structure matches contract. Every prescription in satisfies-over-assertions.md cites a URL; that single file triangulates Matt Pocock, Axel Rauschmayer, Dan Vanderkam. Agent explicitly described triangulation discipline.
- **Baseline: 6/10** — Substantial pack (11 topic files, ~2000 lines), technically correct, but deviates from skill contract: README.md entry (not INDEX.md), slug `modern-typescript` (not `modern-idiomatic-typescript`), no `mode: idioms` frontmatter, no structured version-warnings section, no per-prescription URL citation, no triangulation discipline.

## Observations

1. **The skill contract is doing real work.** Even Eval 3's clean baseline — which produced a longer, substantive pack — lost on structural contract items the skill enforces: INDEX.md as entry, `mode:` frontmatter, structured version-warnings section, per-prescription URL citation, triangulation discipline.
2. **The wire-format-airtight requirement of api mode had the highest qualitative payoff.** The Deepgram with-skill output pinned query-param vs body-field location — the exact failure mode the user cited.
3. **The Vercel bet paid off.** All three with-skill runs appended a substantive "Consult when…" bullet to CLAUDE.md. After the three merged into the real CLAUDE.md, the section reads as a coherent anti-drift harness.

## Iteration 2 candidates (isolation fix)

If re-running:
- Spawn serially (baselines first, then with-skills), or
- Give each run a unique scratch root (e.g. `/tmp/dirt-eval-<id>/`) and have the skill target it instead of `docs/references/`, then copy to the workspace.
