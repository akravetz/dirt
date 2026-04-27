---
title: Breeding Nomenclature — F1, F2, BX, S1, IBL
type: breeding
sources: []
related: [wiki/breeding/README.md, wiki/concepts/oregon-breeding-group.md]
created: 2026-04-26
updated: 2026-04-26
---

# Breeding Nomenclature

Shared vocabulary so generation labels in our project log mean the same thing every time. Cannabis breeders use these letters loosely; this page pins them down for *our* program.

## The terms

| Term | Definition | What it means here |
|---|---|---|
| **P** (Parent) | Original parent lines used in a cross | Sirius Black (SB) and BS01 are P generation for the breeder. We never see them as plants — we see their first offspring. |
| **F1** | First filial — direct offspring of two distinct parent lines (P × P) | Every seed in our SBxBS01 packs (feminized or regular) is F1. F1 from two distinct lines tends to be uniform-ish with hybrid vigor. |
| **F2** | Cross of two F1 siblings (F1 × F1) | What our first cross produces. **Maximum genetic segregation.** Wide variance is the feature. |
| **F3, F4, …** | Successive sibling crosses from selected F2/F3 plants | Stabilization over generations. Each generation reduces variance if you select consistently. |
| **S1** | Selfed — pollinating a plant with its own pollen (via reversal, e.g. colloidal silver) | Not part of our current plan. Useful for locking traits but requires chemical reversal of a female to make pollen. |
| **BX** (Backcross) | Crossing offspring back to one of the original parents (e.g. F1 × P) | Not directly available to us — we don't have the original SB and BS01 plants. *Could* loosely apply if we cross an F2 keeper back to one of our retained F1 mothers. |
| **BX1, BX2** | Successive backcrosses to the same parent | Concentrates that parent's genetics. BX3 is generally considered "stabilized to that parent." |
| **IBL** (Inbred Line) | Multiple generations of selfing/sibcrossing to fix traits — typically 4–6+ gens | The endpoint of stabilization. *Not* what we're targeting in the first cycle. |

## How this maps to our program

The breeder did the SB × BS01 cross. We received F1 seeds.

```
P:    Sirius Black ──┐
                     ├── F1 (every seed in every pack)
P:    BS01     ──────┘

F1 × F1 (sibcross our male × our female keeper) ──► F2  ← our first cross produces this

F2 × F2 (selecting and recrossing F2 keepers) ─────► F3  ← future cycle, optional
```

So the seeds we eventually harvest from our first cross are correctly labeled **F2**, not "F1 of our cross." The breeder's F1 is our F1 too — we're continuing their generation count, not restarting it.

## Why F2 is the interesting generation

F1 hybrids look fairly uniform because both parents contribute one allele at every locus, so most F1s are heterozygous and express the dominant phenotype. F2 is where Mendelian segregation kicks in:

- **Recessive traits** (hidden in F1 because they need two copies) surface in ~25% of F2s.
- **Hybrid vigor** (the "1+1=3" effect from F1) typically diminishes in F2 — sometimes called the "F2 dip."
- **Trait variance is maximum.** Plants will lean toward the SB parent, lean toward the BS01 parent, or recombine in novel ways.

This is exactly what you want when pheno-hunting for *new* expressions. It is also why F2 is unstable — every plant is different, and a "keeper F2" is a single individual, not a stable line. To turn that individual into a stable line takes F3, F4, F5+ of selection.

## Labeling conventions for our project log

When recording a cross or a generation in the breeding project log, use this format:

```
SBxBS01-F1-A      ← Plant A from the current grow (an F1)
SBxBS01-F1-M03    ← Male #3 from the regular pack (also F1)
SBxBS01-F2-2026   ← The F2 seeds we harvest from our first cross
SBxBS01-F2-K1     ← Keeper #1 selected from the F2 grow
```

Pack/source codes can suffix when there's ambiguity (e.g. `SBxBS45-F1-A` if/when we add a second BS line).

## Common misuse to avoid

- **"F1" used as a marketing term for "any seed"** — common in the cannabis industry but technically wrong. Many "F1" packs are actually F2 or unstable hybrids. Trust the breeder's word about what's in the pack and label our generations correctly regardless.
- **"F1 hybrid" vs "F1"** — these mean the same thing. The "hybrid" is implied because F1 is by definition a cross of two different parent lines.
- **"True F1" vs "fake F1"** — sometimes used to distinguish a cross of two genuinely distinct *stable* parent lines (true F1) from a cross of two unstable hybrids (which is really F2 or worse). For our purposes: SB and BS01 were both selected by the breeder over many generations, so SBxBS01 *is* a true F1.
