---
title: Pheno-Split Flip Strategy — Tuck Sativas, Hold for ~60% Coverage
type: decision
sources: []
related: [wiki/concepts/scrog.md, wiki/concepts/plant-training-methods.md, wiki/concepts/lst.md, wiki/breeding/cloning.md, wiki/breeding/timeline.md, wiki/decisions/2026-04-26-breeding-program-launch.md]
created: 2026-04-26
updated: 2026-04-26
---

# Pheno-Split Flip Strategy

The 4-plant grow has split into two morphological groups that fill the SCROG net at very different rates. This decision records *when* and *how* we flip to 12/12 given that split, and what to do for the next 1–3 weeks.

## The split (Day 43 observation)

| Group | Plants | Morphology | Net status |
|---|---|---|---|
| Sativa-leaning | **A, D** | longer internodes, less bushy, vertical | already at the net, starting to fill |
| Indica-leaning | **B, C** | tighter internodes, bushier, lateral | barely reaching the net |

Net coverage estimate from user inspection: **~40% overall**, but unevenly distributed — A and D account for the bulk of the filled squares.

**Notable:** the sativa-leaning pair (A, D) is also the *primary keeper* pair — both are the strong purple/anthocyanin contenders (per [`decisions/2026-04-01-anthocyanin-priority.md`](2026-04-01-anthocyanin-priority.md)). The plants we most need to slow down via aggressive tucking are the same plants whose flower expression we most want to evaluate. That's fine — tucking trains lateral fill without compromising final yield or quality of evaluation; it just means *every* tuck pass on A and D matters more than a tuck on a backup plant would.

## Decision

**Flip target: ~2026-05-10 → 2026-05-17**, gated on **~60% net coverage with all four plants reaching the net plane**, not on a calendar date.

For the next 1–3 weeks:

1. **Tuck the sativas hard.** Bend the tallest growth horizontally back under the net. The point of the SCROG net is exactly this: convert vertical reach into lateral fill. Don't let them keep stretching upward past the net plane.
2. **Encourage the indicas.** Let them keep climbing toward the net. Light step-up window is open (Apr 25–27 per current `overview.md`); use it. Do not tuck indicas — they need to *reach* the net first.
3. **Re-evaluate every 3 days.** When all four are at the net plane and coverage hits ~60%, flip.

## Why ~60% coverage (not 70%, not 90%)

The widely-cited "flip at 70% coverage" rule is a generic SCROG target. It's too high for *this* grow because:

- **Mixed phenos = mixed stretch.** Sativa-leaning plants will stretch 2–3× during flower; indica-leaning closer to 1.5–2×. With plants in both groups under the same net, post-stretch fill from the sativa side will overshoot the net while the indica side just catches up. Flipping at 60% leaves room for that asymmetry without trapping sativa growth above the net.
- **Indicas are still ramping.** If we wait for indicas to hit 70% on their own, sativas will already be 18"+ above the net — overgrown, hard to recover from, and shading everything below.
- **Pheno hunt mode, not yield mode.** This grow's purpose is selecting keepers for the F2 cross (per [breeding-program-launch](2026-04-26-breeding-program-launch.md)), not maximum gram-per-watt. Even fill matters more for evaluation than absolute coverage.

## Why not flip now (at 40%)

- Indica-leaning plants would arrive at the net during stretch, not before. Their canopy never settles into a SCROG plane — they end up under the dominant sativa colas, light-starved.
- Wastes ~2 weeks of available veg time that the indicas demonstrably need.
- See [`concepts/scrog.md`](../concepts/scrog.md): "too early = wasted veg time; too late = overgrown net pre-flip."

## Why not wait until 70%+

- Sativas would overgrow the net. Tucking can't keep up with a 2× stretch on already-tall plants.
- Pushes the F2 cross timeline. The breeding [timeline](../breeding/timeline.md) anchors on a ~2026-05-15 flip; slipping that 2+ weeks ripples into the male-pollen / keeper-clone window.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Sativas stretch past net during 1–3 wk hold despite tucking | Aggressive daily inspection + LST tie-down; cut the tallest tip if necessary (super-cropping) |
| Indicas don't reach net by mid-May despite priority | Accept lower yield from the laggards — they're still pheno candidates regardless of canopy fill, and clones (per [breeding/cloning.md](../breeding/cloning.md)) preserve them as F2 cross candidates if their flower expression turns out to be the keeper |
| Tucking damages a sativa branch | Tape/tie if needed; cannabis recovers from supercropping in ~3–5 days |
| Reservoir/VPD/temp instability (per current `overview.md`) compounds with extended veg | Address those issues this week regardless — the flip is gated on canopy, not on environment, but unhealthy environment slows fill rate |

## Implications for the breeding program

**Clone timing:** clones must be taken **before flip**. Per [breeding/timeline.md](../breeding/timeline.md) Phase 0, take 2 cuttings per plant (8 total) ~7–10 days before the flip date. With flip targeted 2026-05-10 → 2026-05-17, clone-taking window is **~2026-05-03 → 2026-05-10**.

**Pollen window unchanged.** Track A regulars are already targeted for germination this week (per breeding program launch). The 1–2 week shift in flip date doesn't move the male-pollen-collection schedule because the pollen freezer holds for 18–24 months — the cross can happen any time after pollen is banked, regardless of when this grow flowered.

## Open items

- [x] ~~Assign each plant (A, B, C, D) to indica-leaning or sativa-leaning group at next inspection.~~ Confirmed 2026-04-26: A & D sativa-leaning, B & C indica-leaning. Plant pages updated.
- [ ] Daily coverage % estimate added to daily reports starting 2026-04-27.
- [ ] First sativa tuck pass on A and D: today or tomorrow.
- [x] ~~Confirm flip target in [breeding/timeline.md](../breeding/timeline.md) Phase 0/1.~~ Updated 2026-04-26.

## Supersedes

- The implicit "flip at ~Day 56–60" calendar assumption from prior planning. Coverage gate replaces the calendar gate.
- The "weeks 6–8 install net" estimate in [`concepts/scrog.md`](../concepts/scrog.md) is already obsolete (net was installed early on Day 35 — 2026-04-18). This decision adds the *flip* gate on top of that already-revised plan.
