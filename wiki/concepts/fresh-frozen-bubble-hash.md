---
title: Concept - Fresh Frozen Bubble Hash
type: concept
sources: []
related: [wiki/concepts/trimming.md, wiki/concepts/dry-sift-hash.md, wiki/concepts/anthocyanin.md, wiki/concepts/drying.md, wiki/concepts/curing.md]
created: 2026-05-28
updated: 2026-05-28
---

# Fresh Frozen Bubble Hash

Fresh frozen bubble hash is a solventless extraction method that freezes fresh cannabis material immediately after harvest, then uses ice water, cold temperature, gentle agitation, and micron bags to separate trichome heads from plant tissue. It is also called ice water hash; when made from fresh frozen material, it is often the starting point for "live" hash or live hash rosin.

For this crop, fresh frozen bubble hash is the **best terpene-preservation experiment** for sugar leaves and popcorn buds. It is not the best method for preserving the visible purple color. Purple anthocyanins are water-soluble, so the wash water may turn pink/purple while the collected trichome hash stays cream, tan, blonde, or light brown unless the resin heads themselves carry pigment.

## Why Use It

- No hydrocarbon or alcohol solvent.
- Cold process limits heat-driven terpene loss.
- Good use for fresh sugar trim and popcorn buds that would otherwise need drying.
- Micron fractions separate different resin-head sizes and qualities.
- Higher-quality fractions may be kept as full-melt hash or later pressed into rosin.

The process is still contamination-sensitive. The hard part is not separating trichomes; it is drying the wet hash quickly and safely without mold.

## Color Reality

Bubble hash separates trichome heads and intentionally leaves plant tissue behind. That is why high-quality bubble hash is usually lighter and cleaner than leafy hash.

For purple material:

- Purple wash water usually means anthocyanins left the plant tissue.
- Purple water does not guarantee purple hash.
- Purple hash is possible if pigment is in trichome stalks/heads or if some pigmented plant particulate remains.
- Cleaner full-melt fractions are less likely to preserve the purple leaf color.

So the workflow should optimize quality first and document color as an observation, not force purple contamination into the hash.

## Starting Material

Use:

- Fresh sugar trim frozen immediately after harvest.
- Fresh popcorn buds frozen immediately after harvest.
- Small resinous flower that is not needed for jar/bag flower.
- Separate plant-labeled lots if comparing A/D purple expression.

Avoid:

- Moldy or suspect material.
- Trim that sat wet and warm.
- Fan leaves with little visible resin.
- Material that thawed and refroze repeatedly.

Freeze material loose in bags or trays so it does not become one dense block. Keep it frozen until the wash starts.

## Equipment

- Food-safe buckets or a small wash vessel.
- Ice and cold filtered water.
- Bubble bags / hash bags. A common stack is 220, 160, 120, 90, 73, 45, and 25 micron.
- Work bag for plant material.
- Gentle paddle or hand agitation tool.
- Cold spoon or collection card.
- 25 micron pressing/drying screen.
- Parchment paper.
- Freeze dryer if available, otherwise microplane/air-dry workflow in a cold clean space.
- Labels for each plant, wash number, and micron fraction.

## Workflow

1. Harvest and trim the selected material.
2. Freeze immediately and keep frozen until processing.
3. Pre-chill water, bags, tools, and workspace.
4. Layer bags from smallest micron at the bottom to largest/work bag at the top.
5. Combine frozen material, ice, and cold water.
6. Let material cold-soak briefly so trichomes become brittle.
7. Agitate gently for the first wash.
8. Drain through the bag stack without forcing plant pulp through screens.
9. Collect each micron fraction separately.
10. Rinse collected hash with cold clean water if needed to clear foam/debris.
11. Repeat for additional washes, keeping wash numbers separate.
12. Dry the collected wet hash immediately.
13. Store dry hash cold, dark, sealed, and labeled.

The first wash should be gentle and short. Later washes can be longer or more forceful, but they should be labeled as lower grades because plant contamination rises with agitation.

## Micron Fractions

Fraction quality varies by cultivar and trichome size, so treat this as a starting map:

| Bag | Expected Role |
|---:|---|
| 220 | Work bag / plant-material catch |
| 160 | Large heads plus contaminants; often cooking grade |
| 120 | Good resin in some cultivars; inspect carefully |
| 90 | Often premium/full-melt candidate |
| 73 | Often premium/full-melt candidate |
| 45 | Smaller heads; can be strong but may include more stalks/fines |
| 25 | Fine material; often lower melt but useful |

Keep 90 and 73 separate at first. Do not combine fractions until after drying and evaluation.

## Drying Hash

Wet hash is highly mold-prone. Drying is the critical control point.

Preferred:

- Freeze dry promptly, then jar cold.

Fallback:

1. Spread hash thin on 25 micron screen/parchment.
2. Freeze until firm.
3. Microplane or sieve into a fine powder.
4. Air dry in a cold, clean, low-humidity space with indirect airflow.
5. Do not jar until fully dry and sandy.

Do not leave wet patties in a jar. Do not assume cold alone prevents mold.

## Fresh Frozen vs Dried Material

| Input | Strength | Weakness |
|---|---|---|
| Fresh frozen | Best chance at live aroma, lighter color, less dried-flower oxidation | Requires immediate freezer space and careful drying |
| Dried/cured trim | Easier storage, simpler scheduling | More oxidized aroma/color; needs rehydration care; more brittle plant contamination |

For this harvest, freeze the best sugar trim/popcorn lots immediately and decide later whether to wash all of them. Freezing preserves optionality.

## Automation and Logging

Recommended fields:

- `plant_id`
- `material_type`: sugar trim, popcorn, smalls
- `fresh_weight_g`
- `freeze_datetime`
- `wash_datetime`
- `water_temp_f`
- `room_temp_f`
- `wash_number`
- `agitation_duration_min`
- `agitation_style`
- `bag_micron`
- `wet_hash_weight_g`
- `dry_hash_weight_g`
- `drying_method`: freeze dryer or air dry
- `drying_duration_h`
- `visual_color`
- `melt_grade`
- `aroma_notes`
- `purple_water_observed`: yes/no

Useful experiment: wash A and D purple trim separately, keep 90/73/45 fractions separate, and compare color and aroma against plant-matched dry sift.

## Failure Modes

| Symptom | Likely Cause | Action |
|---|---|---|
| Green water/hash | Too much agitation, too warm, plant material breaking down | Shorter/gentler wash, colder process, discard lower grade if harsh |
| Purple water but tan hash | Anthocyanins dissolved into water | Expected; document it, do not force contamination |
| Greasy/sticky hash during collection | Workspace too warm | Chill tools/room; work faster |
| Hash smells musty | Incomplete drying | Discard suspect material; dry future batches thinner/faster |
| Low yield | Genetics/material not a washer, immature heads, too gentle | Save as dry sift/edible input or run additional labeled washes |
| Fractions all dirty | Material thawed or was over-agitated | Improve freezing, cold chain, and wash handling |

## Decision Rules

- Use fresh frozen bubble hash for the best terpene-preserving solventless experiment.
- Use dry sift if purple visual preservation is the main goal.
- Freeze selected trim/popcorn immediately; process later.
- Keep plant, wash number, and micron fraction separate.
- Dry hash fully before storage.
- Discard moldy or suspect material rather than extracting it.

## Sources

- [Processing and extraction methods of medicinal cannabis: a narrative review](https://pmc.ncbi.nlm.nih.gov/articles/PMC8290527/) - describes water extraction/bubble hash as ice-water agitation followed by screen filtration and collection of separated trichomes.
- [A Clinical Framework for Evaluating Cannabis Product Quality and Safety](https://journals.sagepub.com/doi/10.1089/can.2021.0137) - classifies bubble hash/ice water hash as a solventless concentrate and describes collection of trichomes after ice-water agitation and screen filtration.
- [When Cannabis sativa L. Turns Purple: Biosynthesis and Accumulation of Anthocyanins](https://www.mdpi.com/2076-3921/12/7/1393) - cannabis anthocyanin review tying purple tissues to anthocyanin accumulation.
- [Factors affecting the stability of anthocyanins and strategies for improving their stability](https://pmc.ncbi.nlm.nih.gov/articles/PMC11497485/) - anthocyanins are water-soluble pigments affected by pH, temperature, light, oxygen, and related conditions.
- [The Press Club: Why Is My Water Purple with Anthocyanins When Washing Hash?](https://thepressclub.co/blogs/tips-tricks/why-is-ice-water-purple-anthocyanins-when-washing-hash) - applied bubble-hash color interpretation; purple water is usually water-soluble anthocyanin, while high-grade hash may not retain much color.
- [Weedmaps: Ice Water Hash](https://weedmaps.com/learn/dictionary/ice-hash) - applied equipment/process overview for ice water hash.
- [The Cannigma: What Is Bubble Hash?](https://cannigma.com/plant/what-is-bubble-hash/) - applied explanation of cold-water separation, trichome brittleness, and water-insoluble resin.
- [Trimleaf: Bubble Hash Guide](https://trimleaf.com/blogs/guides/bubble-hash-the-definitive-guide) - applied micron-bag workflow and quality grading.
