---
title: Concept - Drying
type: concept
sources: []
related: [wiki/concepts/curing.md, wiki/concepts/trichome-stages.md, wiki/concepts/vpd.md, wiki/environment/temperature.md, wiki/environment/humidity.md, wiki/hardware/ac-infinity-fan-control.md]
created: 2026-05-28
updated: 2026-05-28
---

# Drying

Drying is the controlled removal of most of the plant's harvest moisture before the cure. The target is not "crispy flower." The target is flower that has reached a safe, stable moisture state while drying slowly enough for internal moisture to keep moving outward and gently enough to preserve volatile aroma compounds.

For automation, treat drying as a rate-control problem:

- **Primary endpoint:** flower water activity / equilibrium RH, confirmed by a sealed test.
- **Primary room control variable:** vapor-pressure driving force, expressed as air VPD, because temperature and RH together determine how hard the room pulls water out of the flower.
- **Preservation constraint:** keep temperature low and stable; heat accelerates volatile loss and cannabinoid conversion.
- **Microbial constraint:** do not let the room sit near saturation or allow dense buds to remain wet internally for too long.

In practical home-grow terms, the classic "60/60" target is a shorthand for this psychrometric balance: about **60°F / 60% RH**, dark, with indirect airflow. At that point air VPD is roughly **0.7 kPa**, which is a moderate drying force.

---

## Targets for This Grow

Preferred dry-room target:

| Parameter | Target | Guardrail |
|---|---:|---:|
| Air temperature | 60-64°F | 58-68°F |
| RH | 58-62% | 55-65% |
| Air VPD | 0.65-0.85 kPa | 0.55-1.00 kPa |
| Light | Dark | No direct light |
| Airflow | Gentle indirect exchange | No fan pointed at buds |
| Dry duration | 10-14 days expected | Dense tops may need longer |
| Sealed jar/bag test | 58-62% RH after 12-24 h | Re-dry if >65% |
| Water activity, if measured | 0.58-0.62 aw | Never store >0.65 aw |

The broad applied-literature range is usually **60-70°F and 55-65% RH**. We should aim cooler than the upper end because the quality goal is terpene preservation, not maximum throughput.

## What to Control

### Water Activity Is the Endpoint

Water activity (`aw`) is the product-side metric that matters for safety and storage. It measures free water available for microbial growth, not just total moisture. ASTM's dry-flower storage range is **0.55-0.65 aw**, and California's dried flower water-activity pass/fail limit is **<=0.65 aw**.

For our purposes:

- **0.58-0.62 aw**: ideal handoff to Grove Bags or jars.
- **0.63-0.65 aw**: usable but watch closely during early cure.
- **>0.65 aw**: too wet for sealed storage; return to drying.
- **<0.55 aw**: too dry for an active cure; smoke/storage only, with humidity packs used only for stabilization.

If we do not have a water-activity meter, sealed-container RH is the practical proxy: after 12-24 hours sealed with a calibrated mini hygrometer, equilibrium RH approximately equals `aw * 100`.

### VPD Controls Drying Rate

VPD is the drying force of the room. Low VPD means the room is too close to saturation and water leaves the flower too slowly. High VPD flash-dries the surface while the core remains wet, which can trap internal moisture and produce harsh, grassy flower.

Use VPD as the automation setpoint, but keep it bounded by temperature:

- **0.55-0.65 kPa:** slow/gentle. Useful early if the room is stable and airflow is good.
- **0.65-0.85 kPa:** target band for this crop.
- **0.85-1.00 kPa:** acceptable short-term correction if flower is drying too slowly.
- **>1.00 kPa:** surface-dry risk; reduce dehumidification or lower airflow.

RH alone is not enough because 60% RH at 60°F and 60% RH at 75°F are different drying environments. Dew point is useful for dehumidifier control and absolute-moisture tracking, but it is not the quality endpoint. Dew point plus temperature gives RH/VPD; VPD is the simpler room-rate signal.

### Temperature Caps Preservation Risk

Drying research and applied practice agree on one direction: higher temperature dries faster, but risks more chemical change and volatile loss. A controlled traditional benchmark used **16°C / 50% RH for 10 days**. Cornell hemp work notes conventional controlled drying around **15-20°C and 50-60% RH**, while newer high-temperature approaches improve throughput and microbial reduction at the cost of being a different process goal than premium smokable flower.

For this grow, do not use heat to solve drying unless the room is cold enough to approach saturation or stall. Use dehumidification and airflow first.

## Automation Strategy

Use a simple state machine instead of a PID that chases noisy hourly swings.

### Sensors

- SHT45 or equivalent dry-room air temperature/RH sensor at hanging-bud height.
- A second sensor near room intake/ambient if available.
- Mini hygrometers inside representative jars/bags for sealed tests.
- Optional water activity meter for batch release decisions.
- Optional scale weights for sample branches to track drying curve.

### Actuators

- Dehumidifier or lung-room dehumidifier.
- Exhaust fan / intake exchange.
- Circulation fan, pointed away from buds.
- AC or cool-room control if the dry room drifts warm.
- Humidifier only as a rescue tool for over-dry room air, never blowing onto flower.

### Control Logic

1. Calculate dry-room VPD from air temperature and RH.
2. Hold temperature below 68°F whenever practical.
3. If VPD <0.55 kPa for more than 30-60 minutes, increase moisture removal or air exchange.
4. If VPD >1.00 kPa for more than 30-60 minutes, reduce dehumidification/exhaust or add lung-room humidity.
5. If RH exceeds 65% while temperature is falling, prioritize dehumidification because condensation/mold risk is rising.
6. Keep circulation fan indirect and constant enough to avoid stagnant pockets.
7. Do not terminate drying from room metrics alone. Terminate from sealed test or water activity.

## Drying Workflow

1. Harvest whole branches where practical, especially dense tops, to slow the dry and improve moisture equalization.
2. Remove large fan leaves if they are wet, crowded, or blocking airflow.
3. Hang branches in the dark with space between them.
4. Set room target to 60-64°F, 58-62% RH, indirect airflow.
5. Check daily for mold, hay/ammonia odor, and surface overdrying.
6. Begin sealed-test sampling around day 7-10.
7. When small stems snap and buds feel springy rather than wet, trim a representative sample and seal it with a hygrometer for 12-24 hours.
8. If the sealed test stabilizes at 58-62% RH, move the batch to cure.
9. If the sealed test is 63-65%, either dry a little longer or start cure with close first-week monitoring.
10. If the sealed test is >65%, continue drying and inspect dense buds carefully.

## Readiness Cues

Use physical cues only as a screening tool:

- Small stems snap rather than fold.
- Larger stems may still bend slightly.
- Bud exteriors are dry to the touch but not brittle.
- Buds spring back when lightly compressed.
- No ammonia, sour, compost, or wet-hay odor.
- Sealed test lands in range.

The sealed test matters more than stem snap. Stem snap varies with branch size, cultivar structure, and how much stem remains attached.

## Failure Modes

| Symptom | Likely Cause | Action |
|---|---|---|
| Outside crispy, inside wet | VPD too high / direct airflow | Reduce air movement and drying force; let sealed tests guide |
| Drying takes >16 days and RH often >65% | VPD too low / stagnant air | Increase dehumidification, exhaust, or spacing |
| Hay smell during dry | Too warm, too fast, or still metabolically wet | Lower temp, keep moderate VPD, do not jar early |
| Ammonia/sour smell in sealed test | Flower too wet / anaerobic activity | Remove from container, dry further, inspect for mold |
| Buds feel brittle and jar RH <55% | Over-dried | Stabilize with 58-62% pack; do not expect full cure recovery |
| Visible mold | Contaminated unsafe flower | Discard affected material; inspect adjacent flowers |

## Why This Is Not the Same as Live-Plant VPD

Live-plant VPD describes transpiration through stomata. Dry-room VPD describes moisture removal from dead plant material. The math is similar, but the biological process is different:

- There is no active transpiration control by the plant after harvest.
- The flower's internal moisture and structure set the product-side vapor pressure.
- Air VPD controls drying rate; flower `aw` controls cure/storage readiness.

So the dry room can use VPD for automation, but the cure handoff should use water activity or equilibrium RH.

## Sources

- [Das et al. 2022, Postharvest Operations of Cannabis and Their Effect on Cannabinoid Content](https://www.mdpi.com/2306-5354/9/8/364) - review of cannabis drying, curing, storage, water activity, equilibrium moisture content, and process effects.
- [Baek, Grab, and Chen 2025, Postharvest Drying and Curing Affect Cannabinoid Contents and Microbial Levels in Industrial Hemp](https://www.mdpi.com/2223-7747/14/3/414) - controlled comparison of drying methods; notes conventional drying around 15-20°C and 50-60% RH, plus curing effects on moisture and microbial levels.
- [Uziel et al. 2024, Solid-State Microwave Drying for Medical Cannabis Inflorescences](https://journals.sagepub.com/doi/10.1089/can.2022.0051) - traditional control benchmark of 16°C / 50% RH for 10 days; elevated drying temperatures reduced time but increased terpene loss at high temperature.
- [ASTM: Two Cannabis Standards You Should Know About](https://www.astm.org/news/two-cannabis-standards-you-should-know-about) - water activity as the critical moisture metric; dry flower range 0.55-0.65 aw.
- [ASTM D8196](https://store.astm.org/d8196-20.html) - water-activity testing as a quality-control step for cannabis flower storage safety and quality.
- [California Code of Regulations, Section 15717](https://regulations.justia.com/states/california/title-4/division-19/chapter-6/article-5/section-15717/) - dried flower water activity passes if it does not exceed 0.65 aw.
- [Cannabis Research Coalition: The Science of Post-Harvest Handling](https://www.cannabisrc.org/post/the-science-of-post-harvest-handling) - applied VPD/EMC framing; recommends around 0.8 kPa drying VPD for a balanced rate.
- [Leafly: Drying and Curing Cannabis](https://www.leafly.com/learn/growing/harvesting-marijuana/drying-curing-cannabis) - applied home-grow guidance: 60-70°F, 55-65% RH, slow dry/cure, dark storage, and ammonia warning.
- [New York Office of Cannabis Management: Medical Home Cultivation Guide](https://cannabis.ny.gov/system/files/documents/2022/10/medical-home-cultivation-guide-.pdf) - home-cultivation drying/curing cues, ventilation/mold warnings, and mold disposal guidance.
