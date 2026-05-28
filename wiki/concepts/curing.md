---
title: Concept - Curing
type: concept
sources: []
related: [wiki/concepts/drying.md, wiki/concepts/flushing.md, wiki/concepts/trichome-stages.md, wiki/concepts/vpd.md]
created: 2026-05-25
updated: 2026-05-28
---

# Curing

Curing is the post-dry equalization and aging step. It is not a way to finish drying wet cannabis. The dry has already removed most of the water; curing lets remaining moisture redistribute through the buds, reduces raw green harshness, and protects aroma before long-term storage.

For this grow, the cure should be treated as a product-stability problem, not a live-plant environment problem.

- **Primary target:** flower water activity (`aw`) or sealed-container equilibrium RH.
- **Practical target:** **58-62% RH** inside the sealed container.
- **Safety ceiling:** **0.65 aw / 65% equilibrium RH**. Above this, return to drying.
- **Temperature goal:** cool and stable, preferably **60-65°F**, never warm storage.
- **Light goal:** dark.
- **Default container:** Grove Bags / TerpLoc-style bags for the main cure, with glass jars as the higher-control fallback.

## What Actually Matters

### Water Activity Is the Cure Metric

Water activity measures the free water available for microbial growth and chemical reactions. It is not the same as total moisture content. ASTM's acceptable range for dry cannabis flower is **0.55-0.65 aw**, and state testing programs commonly use **0.65 aw** as the pass/fail ceiling.

In a sealed container at equilibrium, `aw` maps closely to RH:

| Flower aw | Container RH | Interpretation |
|---:|---:|---|
| 0.50-0.54 | 50-54% | Too dry for a meaningful cure |
| 0.55-0.57 | 55-57% | Stable but slightly dry |
| 0.58-0.62 | 58-62% | Target cure window |
| 0.63-0.65 | 63-65% | Wet edge; monitor closely |
| >0.65 | >65% | Mold-risk handoff error; dry further |

If a water-activity meter is available, use it as the release metric. If not, use calibrated mini hygrometers in representative jars/bags and let the sealed test equilibrate for 12-24 hours.

### Temperature Preserves Chemistry

Cool storage slows cannabinoid degradation, terpene loss, and oxidation. Storage research repeatedly points in the same direction: light and warmth accelerate THC loss and CBN formation, while cool/dark storage preserves chemistry better.

Room temperature is acceptable for a normal 4-8 week cure if it is stable and below about 70°F. For long-term keeper samples, glass jars in cool/dark storage are preferred.

### VPD Is Secondary During Cure

VPD is useful in drying because the room is actively pulling moisture from exposed plant material. In a sealed jar or Grove Bag, the important measurement is the container's equilibrium RH / flower `aw`.

Use VPD only if curing in an active room or if running a controlled dry-cure chamber. In that case, VPD is a rate-control variable for moisture migration. It is not the final release criterion.

### Dew Point Is a Guardrail

Dew point helps prevent condensation and explains room moisture load, but it is not the cure target. A sealed container can be at the correct RH/aw across several cool temperatures. The main dew-point rule is simple: avoid temperature swings that cause condensation inside bags or jars.

## Default Method: Grove Bags

Use Grove Bags for the main cure after the flower has already passed the dry handoff.

### Equipment

- Grove Bags or equivalent TerpLoc-style curing bags
- Mini hygrometers, at least one per plant or representative bag
- Optional water-activity meter
- Optional pin moisture meter
- Clean tray or rack for correction drying
- Labels: plant, harvest date, dry-end date, bag date, dry-test RH or `aw`

### Bagging Readiness

Before bagging:

- Small stems snap rather than fold.
- Buds feel dry outside but still springy, not brittle.
- A sealed jar test stabilizes at **58-62% RH** after 12-24 hours.
- If using a pin moisture meter, Grove's guidance is **10-12% moisture content**.
- No ammonia, sour, compost, or wet-hay odor.

Do not bag wet flower. If the sealed test reads over 65% RH, dry longer.

### Loading Bags

1. Trim before bagging unless intentionally doing a loose post-dry trim later.
2. Fill bags about **75% full**, leaving about **25% headspace**.
3. Do not compress buds and do not squeeze air out.
4. Put a hygrometer in at least one representative bag per batch.
5. Zip fully. Heat seal bags intended for long cure or long-term storage.
6. Store cool and dark.

## First Two Weeks

The first two weeks are the correction window. Watch representative bag or jar RH without opening unless an action is needed.

| Reading | Action |
|---|---|
| 58-62% RH | Ideal. Leave sealed. |
| 63-65% RH | Wet edge. Inspect daily; open briefly or return to tray if it keeps rising. |
| 66-70% RH | Too wet. Remove and air on a clean tray until back in range. |
| >70% RH | High mold risk. Remove, dry further, and inspect carefully. |
| <55% RH | Too dry for active cure. Stabilize for storage; do not expect full cure recovery. |

If a container smells like ammonia, sour compost, or wet hay, the buds were sealed too wet. Remove them, dry further, and inspect for mold. Moldy cannabis should be discarded, not salvaged for consumption.

## Cure Length

- Minimum useful cure: **2-4 weeks**
- Preferred target for this grow: **6-8 weeks**
- Long cure: **2-3 months** for dense flower or keeper evaluation samples

Keep a small working jar once the cure is underway. Repeatedly opening the main cure bags adds oxygen, loses aroma, and defeats part of the low-handling benefit.

## When to Use Jars Instead

Glass jars are the higher-control fallback.

Use jars when:

- The dry endpoint is uncertain.
- A Grove Bag reads high RH and needs active correction.
- The batch is small.
- You want daily smell/texture inspection.
- A bag zipper or heat seal is questionable.
- The sample is especially valuable for keeper evaluation.
- Long-term storage beyond the main cure is the goal.

Jar process:

1. Fill jars 70-75%; do not compress.
2. Add calibrated hygrometers.
3. During week 1, open briefly once or twice daily if RH is in range; leave open longer only when RH is high.
4. During weeks 2-4, burp every few days if RH remains stable.
5. After RH is stable in the target range, minimize openings.

## Automation Notes

For a scientific cure workflow, measure the product, not just the room.

Recommended logging:

- `plant_id`
- `harvest_date`
- `dry_start_date`
- `dry_end_date`
- `container_type`
- `container_weight_empty`
- `flower_weight`
- `sealed_test_rh_pct`
- `sealed_test_temp_f`
- `water_activity_aw` if available
- `container_rh_pct`
- `container_temp_f`
- `odor_notes`
- `correction_action`

Control rules:

- Do not allow any sealed container above 65% RH without action.
- Do not open stable 58-62% bags just to "burp" them.
- If using Grove Bags, treat bag RH as a spot-check, not as a closed-loop actuator.
- If using jars, burping is manual moisture/oxygen exchange during the early cure; stop once stable.
- For long-term storage, prioritize cool/dark/stable over continued burping.

## Long-Term Storage

After the active cure:

1. Keep bulk flower sealed, cool, dark, and stable.
2. Use a small working jar for daily access.
3. For keeper samples or storage beyond several months, prefer glass jars with 58% or 62% humidity packs.
4. Avoid warm rooms, sunlight, and repeated temperature swings.
5. Do not store above 65% RH or 0.65 aw.

Grove Bags are acceptable for bulk cured flower if the zipper/heat seal is trustworthy and the bags are not opened repeatedly. Glass is more inert and easier to inspect, so it remains the preferred long-term option for important keeper samples.

## Process Summary

1. Dry flower to the correct handoff point.
2. Confirm with a 12-24 hour sealed RH test or water-activity reading.
3. Start cure only around **58-62% RH / 0.58-0.62 aw**.
4. Use Grove Bags for the main cure; use jars when higher control is needed.
5. Watch the first two weeks closely.
6. Cure 6-8 weeks for this grow.
7. Move daily-use flower to a small working jar and keep bulk sealed.

## Sources

- [ASTM: Two Cannabis Standards You Should Know About](https://www.astm.org/news/two-cannabis-standards-you-should-know-about) - water activity as the critical dry-flower moisture metric; acceptable dry cannabis flower range 0.55-0.65 aw.
- [ASTM D8196](https://store.astm.org/d8196-20.html) - water-activity testing as a quality-control step for cannabis flower storage safety and quality.
- [California Code of Regulations, Section 15717](https://regulations.justia.com/states/california/title-4/division-19/chapter-6/article-5/section-15717/) - dried flower water activity passes if it does not exceed 0.65 aw.
- [Cannabis Science and Technology: Impact of Water Activity on Cannabis Flower](https://www.cannabissciencetech.com/view/impact-of-water-activity-on-the-chemical-composition-and-smoking-quality-of-cannabis-flower-the-science-of-smokability-phase-i-results) - 0.45, 0.65, and 0.85 aw comparison; 0.65 aw associated with higher terpene content and less irritation than over-dried 0.45 aw samples.
- [Baek, Grab, and Chen 2025, Postharvest Drying and Curing Affect Cannabinoid Contents and Microbial Levels in Industrial Hemp](https://www.mdpi.com/2223-7747/14/3/414) - curing increased moisture 3.3-13.6% in sealed containers; curing method was not a major driver in that study.
- [Das et al. 2022, Postharvest Operations of Cannabis and Their Effect on Cannabinoid Content](https://www.mdpi.com/2306-5354/9/8/364) - review of drying, curing, water activity, equilibrium moisture content, storage, and postharvest effects.
- [Grove Bags FAQ](https://grovebags.com/pages/faqs) - manufacturer guidance: bags are for curing/storing, not drying wet flower; 10-12% moisture; 25% headspace; 58-62% RH.
- [Leafly: Drying and Curing Cannabis](https://www.leafly.com/learn/growing/harvesting-marijuana/drying-curing-cannabis) - applied jar cure guidance, 55-65% RH, burping, ammonia warning, and cool/dark storage.
- [New York Office of Cannabis Management: Medical Home Cultivation Guide](https://cannabis.ny.gov/system/files/documents/2022/10/medical-home-cultivation-guide-.pdf) - home-cultivation curing cues, mold warnings, airtight storage, and disposal guidance for moldy cannabis.
- [Zamengo et al. 2019, The Role of Time and Storage Conditions on Hashish and Marijuana Composition](https://www.sciencedirect.com/science/article/pii/S0379073818308818) - four-year storage study showing THC degradation and CBN formation depend on time, light, and temperature.
