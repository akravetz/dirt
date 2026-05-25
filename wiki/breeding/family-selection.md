---
title: Progeny-Tested Family Selection
type: breeding
sources: []
related: [wiki/breeding/stabilization-strategy.md, wiki/breeding/veg-tent-layout.md, wiki/breeding/pheno-hunt-protocol.md, wiki/breeding/male-evaluation.md, wiki/breeding/cross-procedure.md]
created: 2026-05-02
updated: 2026-05-24
---

# Progeny-Tested Family Selection

Family selection is how F3/F4/F5 stabilization stays tractable in a small tent. The goal is not to make every possible cross. The goal is to create a few known family lots, test them honestly, advance the best one, and repeat.

A **family** is one known parent pair:

```text
F2-M1 x F2-F1 -> F3 family A
F2-M2 x F2-F1 -> F3 family B
F2-M1 x F2-F2 -> F3 family C
```

The family, not just the individual plant, is what gets judged. A beautiful F2 plant is useful only if its offspring keep producing the target.

The short rule:

```text
Select individual plants by phenotype.
Advance families by progeny performance.
```

That means a standout plant is a candidate parent, not proof that the line is stable. The test is whether that plant's seed lot throws a high percentage of dark-purple, sativa-leaning, trellis-friendly offspring.

## How families continue each generation

A family exists whenever the parents are known. The first SBxBS01 cross can already create separate F2 families:

```text
TA-M1 x A clone -> F2-A family
TA-M1 x D clone -> F2-D family
```

If the 16-site test is split 8 seeds from F2-A and 8 seeds from F2-D, judge the families by their hit rate:

| Family | Example result | Decision |
|---|---|---|
| F2-A | 5/8 on target, 0 herms | Advance as the main line |
| F2-D | 2/8 on target, 1 herm | Drop, unless one clone has an exceptional trait worth preserving as a backup |

If one F2 family clearly dominates, do not keep both families on equal footing just because both parents looked interesting. Pick the best male and female candidates inside the winning family and make the next generation:

```text
F2-A-M1 x F2-A-F1 -> F3-A1
```

That F3-A1 seed lot is now one family. The next run asks whether that family throws the target consistently. If it does, choose the best F3 plants inside it and make 1-4 F4 subfamilies:

```text
F3-A1-M1 x F3-A1-F1 -> F4-A1a
F3-A1-M2 x F3-A1-F1 -> F4-A1b
F3-A1-M1 x F3-A1-F2 -> F4-A1c
F3-A1-M2 x F3-A1-F2 -> F4-A1d
```

Then test those F4 subfamilies and advance the one with the best target percentage. The loop repeats at F5 and beyond: grow the current winning family, select the best candidates inside it, make a few known next-generation family lots, test those lots, and advance one winner.

With only 16 plant sites, keep the loop small:

```text
F2 test: 8 seeds from F2-A + 8 seeds from F2-D
F3 creation: best selected F2 parent pair(s) from the winning family
F3 test: 16 seeds from one F3 family, or 8 + 8 from two candidate F3 families
F4 creation: 1-4 known crosses from the best F3 candidates
F4 test: 4 x 4 family screen, 8 + 8 comparison, or 16-seed validation
```

Do not collapse the process into "best-looking plant every time" too early. That bottlenecks the line before the parents have been tested through offspring. Use one best pair only when the population gives one obvious pair or when space forces the choice.

## Default operating rule

For the 16-site 3x3 table / 4x4 tent model:

```text
Generation creation: make 2-4 family lots, not a full matrix.
Generation testing: test 1-4 families, depending on confidence.
Advancement: keep 1 winning family, with 1 backup only if space allows.
```

Avoid a full 4x4 breeding matrix as the default. Sixteen seed lots are too many to evaluate with only 16 final plant sites.

## Creating F3 families from F2

In the F2 run, start more seeds than can finish. After early culling and sexing, the final candidates may look something like:

```text
F2 males worth considering: 2-3
F2 females worth considering: 2-3
```

Make a small number of deliberate crosses.

### Balanced 2x2

Use this when two males and two females all pass the gates.

```text
F2-M1 x F2-F1 -> F3-A
F2-M2 x F2-F1 -> F3-B
F2-M1 x F2-F2 -> F3-C
F2-M2 x F2-F2 -> F3-D
```

This is the default maximum. Four families is already enough for one small setup.

### One elite female, multiple males

Use this when one female is clearly superior and the male choice is uncertain.

```text
F2-M1 x F2-F1 -> F3-A
F2-M2 x F2-F1 -> F3-B
F2-M3 x F2-F1 -> F3-C
```

This tests male contribution against the same elite female.

### One elite male, multiple females

Use this when one male is clearly superior and the female choice is uncertain.

```text
F2-M1 x F2-F1 -> F3-A
F2-M1 x F2-F2 -> F3-B
F2-M1 x F2-F3 -> F3-C
```

This tests female contribution against the same elite male.

### One best pair

Use this only when the population gives one obvious best male and one obvious best female, or when space is too tight for comparison.

```text
F2-M1 x F2-F1 -> F3-A
```

This is simpler, but weaker. If the family disappoints, there is no same-generation comparison lot.

## Testing the families

With 16 final plant sites, there are two useful testing modes.

### Four-family screen

```text
4 seeds from F3-A
4 seeds from F3-B
4 seeds from F3-C
4 seeds from F3-D
= 16 plants
```

This is a light screen. It can identify obvious losers, but it cannot prove stability.

Use this immediately after making 3-4 families, when the goal is to decide which family deserves more space.

### Two-family comparison

```text
8 seeds from F3-A
8 seeds from F3-C
= 16 plants
```

This is the better default after the first screen. It gives enough signal to compare the best candidates more honestly.

### One-family validation

```text
16 seeds from F3-C
= 16 plants
```

Use this when one family is already clearly leading and the question is consistency, not exploration.

## How to decide what advances

Count the denominator for every family:

- seeds germinated
- seedlings culled before flip
- plants flowered
- on-target plants
- hermaphrodite/intersex failures
- off-target color failures
- off-target structure failures

Example screen:

| Family | Result | Decision |
|---|---|---|
| F3-A | 3/4 on target | Backup candidate |
| F3-B | 1/4 on target | Drop |
| F3-C | 4/4 on target | Advance / retest deeper |
| F3-D | 2/4 on target | Drop unless it has an exceptional trait |

Then focus on the winner:

```text
F3-C-M1 x F3-C-F1 -> F4-C1
F3-C-M2 x F3-C-F1 -> F4-C2
```

The next generation repeats the same pattern inside the winning family.

## F4/F5 repetition

For each later generation: grow the winning family, cull hard by the target gates, keep 1-2 best males and 1-2 best females, make 1-4 next-generation family lots, screen families, and advance one family.

As the line improves, shift space from exploration to validation:

```text
Early F3: 4 families x 4 plants
Promising F3/F4: 2 families x 8 plants
Leading F4/F5: 1 family x 16 plants
Production candidate: repeat tests and then feminized validation
```

## Practical defaults

Use these defaults unless the population strongly argues otherwise:

| Situation | Default action |
|---|---|
| First F2 selection has 2 good males and 2 good females | Make a 2x2: four F3 families |
| One female is clearly best | Test 2-3 males against her |
| One male is clearly best | Test him against 2-3 females |
| Only one parent pair is good | Make one family, but keep expectations modest |
| Four families exist and none has been tested | Run 4 seeds per family |
| Two families look best | Run 8 seeds per family |
| One family is clearly best | Run 16 seeds from that family |

## What not to do

- Do not bulk-mix pollen for stabilization work. It destroys family-level signal.
- Do not keep all families alive indefinitely. Space pressure will dilute selection.
- Do not call a 4-seed family screen stable. It is only a triage pass.
- Do not advance a family with hermaphrodite tendency, even if color is excellent.
- Do not use uncertain labels for breeding. Discard uncertain plants or seed lots.
