---
title: Concept — EC (Electrical Conductivity)
type: concept
sources: []
related: [wiki/environment/nutrients.md, wiki/concepts/nutrient-burn.md, wiki/concepts/ph-lockout.md, wiki/concepts/coco-coir.md]
created: 2026-04-12
updated: 2026-04-15
---

# EC — Electrical Conductivity

EC (Electrical Conductivity) measures the total dissolved salt concentration in a nutrient solution. It is the primary metric for managing nutrient strength in coco coir grows. Higher EC = more nutrients (and more risk of burn). Lower EC = less nutrients (and risk of deficiency).

## Units and Conversion

| Unit | Description | Conversion |
|------|-------------|------------|
| EC (mS/cm) | Millisiemens per centimeter | Base unit |
| ppm (500 scale) | Parts per million | ppm = EC × 500 |
| ppm (700 scale) | Parts per million (Hanna/EU) | ppm = EC × 700 |
| TDS | Total Dissolved Solids | Usually same as ppm |

**This grow uses a TDS-3 meter** which reads in ppm (500 scale). HM Digital ships all their pocket TDS meters (TDS-3, TDS-4, COM-100) with the NaCl conversion factor baked in — there is no toggle on the unit. To convert: EC = ppm ÷ 500.

Example: 920 ppm ÷ 500 = EC 1.84.

## Targets by Stage (Canna Coco A+B, Autopot reservoir)

These are **autopot reservoir** targets (continuous feed). Hand-feed EC runs ~20–30% higher than reservoir EC because flush-through dilutes the effective root-zone concentration. Reservoir EC ≈ what the plants are actually drinking.

| Stage | Target EC | Target ppm (500) | Notes |
|-------|-----------|-------------------|-------|
| Seedling | 0.4–0.6 | 200–300 | Very dilute; coco has some buffered nutrients |
| Early veg / post-topping | 0.8–1.0 | 400–500 | **Current target.** Lean low during wound recovery. |
| Mid veg | 1.0–1.2 | 500–600 | Canopy filling the SCROG |
| Late veg | 1.2–1.4 | 600–700 | Pre-flower ramp |
| Early/Mid flower | 1.4–1.6 | 700–800 | Peak nutrient demand |
| Late flower | 1.2–1.4 | 600–700 | Taper |
| Final flush | 0.0 | 0 | Plain pH 5.8 water |

## How to Measure

1. **Input EC:** Measure the nutrient solution after mixing (before watering)
2. **Runoff EC:** Collect tray runoff after watering; measure its EC
3. **Compare:** Runoff EC significantly higher than input = salt buildup in the root zone

## Key Principles

- **Always water to 10–20% runoff** in coco — this prevents salt accumulation
- **Runoff EC > input EC** is normal (coco releases buffered salts); a large gap (>0.5 EC) suggests buildup
- **Coco is inert but buffered** — fresh coco exchanges calcium/magnesium for sodium/potassium; this is why calmag is sometimes needed in early runs
- **Denver tap water** contributes some baseline EC (~0.2–0.3) before adding nutrients

## EC and Other Metrics

- **EC too high → nutrient burn** — brown tips/edges, especially on upper canopy. See [Nutrient Burn](nutrient-burn.md).
- **EC normal but symptoms → pH lockout** — nutrients are present but unavailable due to pH drift. See [pH Lockout](ph-lockout.md).
- **EC and VPD interact** — high VPD (dry air) increases transpiration rate, concentrating salts at the root zone. In high VPD conditions, run slightly lower EC. See [VPD](vpd.md).

## Current Situation

**Apr 11 reading: 920 ppm (EC ~1.84)** — too high for early veg (target 0.8–1.0 / 400–500 ppm). This is the #2 action item: dilute the nutrient solution before next watering. See [Nutrients & pH](../environment/nutrients.md).
