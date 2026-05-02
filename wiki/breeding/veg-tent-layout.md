---
title: Breeding Veg/Female Tent Layout - 4x4 Ebb-and-Flow SOG
type: breeding
sources: []
related: [wiki/breeding/README.md, wiki/breeding/pheno-hunt-protocol.md, wiki/breeding/stabilization-strategy.md, wiki/breeding/bill-of-materials.md]
created: 2026-05-02
updated: 2026-05-02
---

# Breeding Veg/Female Tent Layout

Working layout for the repurposed 4 ft x 4 ft x 8 ft tent used to run high-count, short-cycle female/candidate generations for the SBxBS01 stabilization program.

The goal is not yield. The goal is population size, repeatability, easy culling, clean labeling, branch pollination, and fast reset between generations.

## Locked decisions

| Area | Decision |
|---|---|
| Tent | 4 ft x 4 ft x 8 ft tent |
| System | Ebb-and-flow flood table |
| Tray | 4 ft x 4 ft flood tray |
| Plant count | 25 final plant sites |
| Grid | Fixed 5 x 5 coordinate grid |
| Media | 1.5 inch rockwool starter cubes transplanted into 6 inch x 6 inch rockwool final blocks |
| Reservoir | Reuse existing 30 gal AquaPot reservoir as an external nutrient reservoir |
| Drain strategy | Tray drains by gravity into a local sump; sump pump returns solution to external reservoir |
| First flood depth target | 1.5-2.0 inches, tuned after dry run and first crop data |
| Tray height target | ~24 inches off the floor |
| Monitoring | Reservoir pH/EC plus runoff/tray pH once the pH sensor arrives |

## Grid layout

Use fixed coordinates for every plant record, photo, cull note, pollination event, and seed lot.

```text
Back of tent

A1  A2  A3  A4  A5
B1  B2  B3  B4  B5
C1  C2  C3  C4  C5
D1  D2  D3  D4  D5
E1  E2  E3  E4  E5

Front of tent
```

Coordinate labels are part of the breeding record. A plant whose identity becomes uncertain should not be used for breeding.

## Workflow model

The intended cycle is:

1. Germinate and label seedlings.
2. Start in 1.5 inch rockwool cubes.
3. Transplant selected seedlings into 6 inch x 6 inch final blocks.
4. Run a very short veg.
5. Cull aggressively for off-target traits before and during early flower.
6. Flower the remaining candidates.
7. Pollinate selected branches only.
8. Harvest seed lots by known plant and pollen source.
9. Reset the tray and repeat.

For stabilization generations, population count matters more than finished flower yield. Plants should stay small and individually scorable.

## Media rationale

Rockwool was selected over coco/fabric pots for this table because it makes the experiment cleaner:

- more uniform root-zone volume between plants
- predictable flood behavior
- no loose media washing into the reservoir
- faster reset between generations
- cleaner 5 x 5 plant-grid geometry
- easier to treat each plant site as a discrete experimental unit

The tradeoff is lower buffering. Rockwool requires more disciplined pH/EC management than coco and must be conditioned correctly before transplant.

## Reservoir and drain layout

The external AquaPot reservoir will be used as a standard nutrient reservoir. The original bottom port can be capped if it is not useful for this build.

```text
30 gal reservoir outside tent
  -> fill pump
  -> fill line through tent port
  -> 4x4 flood tray
  -> tray drain fitting
  -> short gravity line into local sump
  -> sump pump
  -> return line back to reservoir
```

This solves the reservoir-height problem: the external reservoir top will sit higher than the tray drain outlet, so direct gravity return is not reliable. The tray only needs to gravity-drain into a lower local sump; the sump pump handles the lift back to the reservoir.

## Sump

Use a 5-10 gal sump bucket or low tote near or under the tray. A 10 gal tote is preferred if the footprint works because it gives more buffer during a drain event and reduces splash risk.

The sump should be able to hold a full tray drain event if the sump pump is delayed or fails. The sump pump can be timer-driven, but a float-switch-controlled sump pump is preferred because it removes timing guesswork.

## Flood depth and tuning

Initial target flood height: 1.5-2.0 inches.

The goal is to wet the lower portion of each 6 inch rockwool block and let the block wick upward, not to submerge the full block. The final height and frequency should be tuned from:

- block weight/feel
- plant size
- reservoir pH/EC
- runoff or tray-drain pH/EC
- visible plant response

Initial schedule expectation:

| Stage | Starting flood frequency |
|---|---|
| Fresh transplant | 1 flood/day or every other day, depending on block moisture |
| Established veg | 1-2 floods/day |
| Early flower | 2-4 floods/day |
| Late flower / seed maturation | tune by dryback, likely 2-5 floods/day |

These are starting points only. The first run should calibrate the real schedule for the tent, light, humidity, and plant size.

## Tray height

Target tray height: ~24 inches off the floor.

This gives enough working room for a local sump and drain plumbing while preserving vertical space in the 8 ft tent for:

- stand and tray
- 6 inch rockwool blocks
- short SOG plants
- flower stretch
- light fixture and clearance

The stand must be built or selected for water weight. Plan for at least 300-500 lb capacity.

## Safeties

Minimum safeguards:

- tray overflow fitting set to maximum flood height
- fill-line siphon break near the tray
- return line secured to the reservoir
- covered reservoir to prevent algae/debris
- local sump sized for a full drain event
- water alarm near the tent floor
- pump/timer arrangement that prevents accidental continuous flooding

Preferred upgrades:

- high-water float switch in the tray to cut fill pump power
- float-switch-controlled sump pump
- low-water protection for the fill pump
- automated top-off after the basic table is proven

## Research anchors

External references used while choosing this direction:

- Oregon State Extension, "Hydro hints: Ebb and flow" - ebb-and-flow fundamentals.
- University of Minnesota Extension, "Small-scale hydroponics" - hydroponic system types and ebb-and-flow context.
- Oklahoma State Extension, "Soilless Growing Mediums" - mineral wool properties and hydroponic media comparison.
- Oklahoma State Extension, "Electrical Conductivity and pH Guide for Hydroponics" - reservoir pH/EC management.
- Grodan product/grow guides - rockwool conditioning and water-content/EC management.
