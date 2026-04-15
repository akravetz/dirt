---
title: Concept — DLI & Light Management (Fold-650)
type: concept
sources: []
related: [wiki/concepts/vpd.md, wiki/environment/nutrients.md]
created: 2026-04-07
updated: 2026-04-07
---

# DLI & Light Management

## What Is DLI?

**Daily Light Integral (DLI)** is the total amount of photosynthetically active light a plant receives over a full day, measured in **mol/m²/d**.

**Formula:** `DLI = PPFD × hours × 0.0036`

Where PPFD (Photosynthetic Photon Flux Density) is measured in µmol/m²/s at canopy level.

**How to measure PPFD:** The **Photone app** (phone camera) gives a reasonable estimate for LED grows. Take readings at canopy level, multiple points across the footprint, and average them.

## PPFD Targets by Stage

| Stage | PPFD Target (µmol/m²/s) |
|-------|------------------------|
| Seedling / Clone | 100–300 |
| Early Veg | 250–400 |
| Late Veg | 400–600 |
| Early Flower | 600–800 |
| Mid Flower | 800–1,000 |
| Late Flower | 700–900 |

## DLI Targets by Stage

| Stage | DLI Target (mol/m²/d) |
|-------|----------------------|
| Seedling | 5–10 |
| Early Veg | 15–20 |
| Late Veg | 25–35 |
| Early Flower | 20–25 (drops at flip due to 18→12hr) |
| Mid Flower | 30–40 |
| Late Flower | 35–45 |

## The 18→12 Flip Math

Switching from an 18hr to 12hr photoperiod cuts DLI by **33%** even at the same PPFD. To maintain the same DLI at flip, you need to increase PPFD by **50%**.

**Example:** 600 PPFD × 18hr × 0.0036 = **38.9 DLI**. To hit ~38.9 DLI in 12hr: 38.9 / (12 × 0.0036) = **~900 PPFD** required.

In practice, early flower DLI targets are lower than late veg (plants are adjusting to the new cycle), so a full 50% PPFD increase isn't necessary — but a significant jump is appropriate.

## Our Light Ramp Plan — Fold-650

| Phase | Dimmer Setting | Notes |
|-------|---------------|-------|
| Post-transplant / Early Veg (now) | 30% | Establishment; conservative to avoid stress |
| Week 3–4 veg (current) | 40–50% | Ramp gradually over ~1 week |
| Week 5–6 veg (pre-SCROG) | 60–70% | Canopy filling out; higher demand |
| At flip to flower | 80–90% | Compensate for 18→12 DLI drop |
| Mid flower | 100% | If plants handle it and VPD is managed |

**Ramp protocol:** Increase by ~10% every 2–3 days. Watch for **light stress symptoms**:
- Leaf taco-ing (edges curling up) — back off 10%
- Bleaching or tip whitening — too much; reduce and move light up
- No symptoms + healthy growth = safe to continue ramping

## Without Supplemental CO2

At ambient CO2 (~420 ppm), photosynthesis saturates around **800–1,000 PPFD**. Above that, more light does not produce more photosynthesis — it just generates heat and oxidative stress. Our closet without CO2 supplementation means the **practical ceiling is ~900 PPFD**. Pushing to 100% dimmer is only worth it if plants are large, canopy is dense, and VPD is well-managed.

With supplemental CO2 (1,200–1,500 ppm), the saturation point rises to ~1,500 PPFD and DLI targets increase significantly — not relevant to this grow currently.

## Interaction with VPD

Higher PPFD drives more stomatal opening and transpiration, which increases the plant's VPD demand. If VPD is too low when ramping light, the stomata close and photosynthesis stalls regardless of intensity. Always **match VPD target to your current light stage** — see [VPD](vpd.md) for current situation and targets.

## Interaction with Nutrients

Higher light intensity = faster growth = higher nutrient demand. As PPFD ramps through veg, expect to increase EC accordingly. Do not ramp light and nutrients simultaneously — change one variable at a time, allow 2–3 days to observe the plant's response before changing the other.
