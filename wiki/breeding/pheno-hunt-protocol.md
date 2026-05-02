---
title: Phenotype Hunt Protocol
type: breeding
sources: []
related: [wiki/breeding/README.md, wiki/breeding/stabilization-strategy.md, wiki/breeding/cloning.md, wiki/concepts/anthocyanin.md, wiki/concepts/trichome-stages.md]
created: 2026-04-26
updated: 2026-05-02
---

# Phenotype Hunt Protocol

How we pick keeper female(s) from a pack of seeds. Applies to both the current-grow 4 plants (A/B/C/D), the planned 10-pack hunt in Phase 4, and later stabilization populations. For the current stabilization goal, see [stabilization-strategy.md](stabilization-strategy.md).

## The fundamental rule

**Take clones of every plant before flipping to 12/12.** A "keeper" is identified at harvest, weeks after the decision to flip is irrevocable. Without clones, the keeper is gone before you know she existed.

See [cloning.md](cloning.md) for the procedure. Take 2–3 clones per mother for redundancy.

## Selection axes (priority order)

This is *our* priority order, tuned to what BS01 was selected for and what we care about. Adjust per project as goals shift. For stabilization runs, the first pass is gate-based: no early purple, no trellis-friendly structure, herm tendency, or uncertain labels remove a plant from breeding consideration before scoring.

### 1. Color (anthocyanin expression) — primary

The reason BS01 exists. Genetic anthocyanin (purple expressed at warm ambient temps) is the strongest signal we can score, and the easiest.

**How to score:**
- Late veg: photograph stems and petioles under consistent light. Score 1–10 deepness of color.
- Flower week 3, 6, 9: photograph again, this time scoring calyxes specifically (not just leaves — leaf purple doesn't always predict bud purple).
- Distinguish from environmental purple — Denver's cool nights amplify color in late flower for *any* susceptible plant. Genetic phenos show purple at warm ambient temps from veg onward.

See [`concepts/anthocyanin.md`](../concepts/anthocyanin.md) for the genetic-vs-environmental distinction in detail.

### 2. Terpenes (aroma/flavor) — primary

Biggest determinant of how much you'll actually enjoy the smoke. Most subjective axis to score.

**How to score:**
- Stem rub at flower week 4, 6, 8 — pinch a leaf petiole, smell. Take a voice memo or note per plant ("gas-forward, hint of grape, slight skunk").
- Re-evaluate after dry/cure (terps shift dramatically) — week 1 after cure jar opens, then week 4.
- Score in random plant order; nose adapts within minutes. Take a coffee-bean break between plants.
- Common categories: gas/diesel, fruit (berry/citrus/tropical), floral/sweet, earthy/skunk, pine. Most phenos are 1–2 dominant + supporting.
- Don't try to find "the best" — find "the one I most want to smoke." This is your strain; subjective wins.

### 3. Structure (internodal distance, branching) — primary

For the 2026-05-02 stabilization target, longer internodes and sativa-leaning structure are preferred because they make the plant easier to spread through a trellis. This reverses the earlier yield-focused bias toward compact, bushy plants. Extreme stretch is still undesirable, but the target is open, trainable structure rather than squat density.

**How to score:**
- End-of-veg: measure internode distance (cm between nodes 4–8 on the main stem). Note branchiness visually.
- Flip + 3 weeks: measure stretch (height at flip vs height now — most stretch happens in this window).
- Flower week 9: final height. Bonus criteria: bud spacing (tight nugs vs spaced "popcorn").
- For the purple/sativa stabilization line: open structure + longer internodes + manageable stretch = wins. Squat, compact indica morphology is a cull unless the plant is otherwise exceptional.

### 4. Finish time — secondary tiebreaker

Earlier finish = more cycles per year + less time for pests/PM. Within a single F1 pack, expect ±2 weeks variance.

**How to score:**
- Check trichomes weekly with 60–100x loupe starting flower week 7.
- Note the date each plant hits "mostly cloudy + some amber" (or whatever your harvest preference is).
- Use as a tiebreaker between two phenos that scored similarly on color/terps/structure.

See [`concepts/trichome-stages.md`](../concepts/trichome-stages.md).

### 5. Vigor — secondary

Growth rate, robustness, recovery from training/transplant. High vigor = forgiving plant + faster cycles.

**How to score:**
- Days from germination to first true leaves.
- Week-over-week node count during veg.
- Recovery time from topping (if topping is part of the hunt).

### 6. Resilience (pest/PM/heat) — long-term, deferred

Mostly observational. Skip as a primary criterion in the first hunt — comes into play only across multiple grows when problems show up. Note in journal but don't weight it.

## Scoring rubric template

For each plant, maintain a row in a scoring spreadsheet (or per-plant page in `breeding/projects/<project>/`). Suggested columns:

| Plant | Color | Terps | Structure | Finish (days) | Vigor | Total | Notes |
|---|---|---|---|---|---|---|---|

Score each axis 1–10. For the current stabilization line, first apply hard gates (early purple, structure, no hermie, known labels), then total = weighted sum: `Color×3 + Structure×3 + Terps×2 + Vigor×1` (no Finish/Resilience until tiebreaker is needed). Adjust weights per project.

## Schedule

For a 10-plant hunt, this is the cadence:

| Week | Stage | Activity |
|---|---|---|
| 0 | Germination | Pop seeds, label by position |
| 2 | Early veg | First photos, document seedling vigor differences |
| 3–4 | Late veg | Take 2–3 clones per plant, label by mother |
| 4 | Flip prep | Final veg measurements (height, internode, structure) |
| 5 | Flip + 0 | Flip to 12/12; baseline photos |
| 7 | Flower wk 2 | First pre-flower observations, sex confirmation if regulars |
| 8 | Flower wk 3 | Stretch measured; first stem rubs |
| 11 | Flower wk 6 | Mid-flower photos, calyx color, mid-flower stem rubs |
| 14 | Flower wk 9 | Final stem rubs; trichome check; identify finish-order |
| 15+ | Harvest | Per plant; score and dry-cure separately |
| 17–18 | Post-cure | Final smell/taste evaluation; declare keeper(s) |

## How many keepers to keep

For a first hunt of 10 plants: aim to identify **1 primary keeper + 1 backup**. More than 2 keepers is space-burning — mothers cost veg space to maintain indefinitely. Less than 1 means the hunt produced nothing usable, which is rare from F1 stock if scoring is honest.

## What constitutes "the cross is on"

The keeper passes when she beats every other plant in the hunt on the *primary* axes (color, terps, structure) and is at least middle-of-pack on the secondaries. If no plant clearly wins, run a second 10-pack rather than forcing a mediocre keeper into a multi-year stabilization project.
