---
title: Concept — VPD (Vapor Pressure Deficit)
type: concept
sources: [raw/chat-history/bible.md]
related: [wiki/environment/temperature.md, wiki/environment/humidity.md, wiki/concepts/coco-coir.md, wiki/concepts/dli-light-management.md]
created: 2026-04-06
updated: 2026-04-07
---

# VPD — Vapor Pressure Deficit

VPD measures the difference between the amount of moisture the air holds and how much it *could* hold at saturation. Higher VPD = drier air relative to capacity = stronger transpiration pull.

**VPD = SVP − AVP**

Where:
- **SVP** (Saturation Vapor Pressure) = `0.6108 × exp(17.27 × T / (T + 237.3))` — T in °C, result in kPa
- **AVP** (Actual Vapor Pressure) = `SVP × (RH / 100)`
- **VPD** = SVP − AVP

Example at 25°C / 75% RH: SVP ≈ 3.17 kPa, AVP ≈ 2.38 kPa → VPD ≈ **0.79 kPa**

## Target Ranges by Stage

| Stage | VPD Target |
|-------|-----------|
| Seedling / Clone | 0.4–0.8 kPa |
| Vegetative | 0.8–1.2 kPa |
| Flowering | 1.2–1.6 kPa |
| Late Flower / Ripening | 1.0–1.3 kPa |

## Our Current Situation

RH is running **73–76%**, temps around **77°F (25°C)**. At 25°C / 75% RH, VPD ≈ **0.79 kPa** — just barely in range for veg, but on the low end.

As we move toward flower we'll need to get RH down significantly to reach the 1.2–1.6 kPa flowering window. At 25°C, hitting 1.2 kPa requires RH ≈ 62%; hitting 1.6 kPa requires RH ≈ 49%.

## Why Low VPD Is a Problem

- **Reduced transpiration** — stomata don't open fully; nutrient uptake slows
- **Poor calcium/magnesium transport** — Ca and Mg move via transpiration stream; low VPD = deficiency risk even with correct solution EC
- **Mold / mildew / botrytis risk** — stagnant humid air at canopy is ideal for fungal growth
- **Root rot conditions** — high ambient moisture combined with wet coco creates anaerobic risk around root zone

## How to Raise VPD in a Small Closet

1. **Dehumidifier** — most direct fix; size appropriately for the space
2. **Improve exhaust ventilation** — pull humid air out faster
3. **Oscillating fans** — improve air exchange at canopy, disrupt the humid boundary layer on leaves
4. **Slight temp increase** — raises SVP without changing AVP, increasing VPD (useful as a secondary lever)

## Leaf Temp vs. Air Temp

Leaf surface is typically **2–5°F cooler than air** due to evaporative cooling. This means actual VPD at the leaf surface is slightly *lower* than the air VPD calculation suggests. For precision VPD management, use an **IR thermometer** pointed at leaf surfaces and substitute leaf temp for T in the formula. For our purposes, air temp is a reasonable proxy.

## Interaction with Coco

Good VPD management is especially important in coco because the medium stays moist between waterings (or continuously in autopot mode). In soil, the medium drying out provides passive pressure to drive nutrient uptake. In coco, you're relying more on **transpiration pull** to move water and nutrients from root zone to leaf. Low VPD reduces this pull, leading to nutrient underperformance even with correct EC. See [Coco Coir](coco-coir.md) for medium notes.

## Interaction with Light Intensity

Higher light intensity drives more transpiration and stomatal opening, which naturally raises the plant's VPD demand. As we increase PPFD toward flower, VPD targets should be matched accordingly. See [DLI & Light Management](dli-light-management.md).
