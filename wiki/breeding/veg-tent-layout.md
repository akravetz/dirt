---
title: Breeding Veg/Female Tent Layout - 3x3 Ebb-and-Flow SOG in 4x4 Tent
type: breeding
sources: []
related: [wiki/breeding/README.md, wiki/breeding/pheno-hunt-protocol.md, wiki/breeding/stabilization-strategy.md, wiki/breeding/bill-of-materials.md]
created: 2026-05-02
updated: 2026-05-02
---

# Breeding Veg/Female Tent Layout

Working layout for the repurposed 4 ft x 4 ft x 8 ft tent used to run high-count, short-cycle female/candidate generations for the SBxBS01 stabilization program.

The goal is not yield. The goal is population size, repeatability, easy culling, clean labeling, branch pollination, and fast reset between generations. The working design now favors a 3 ft x 3 ft flood table inside the 4 ft x 4 ft tent so there is usable edge space for plumbing, cords, sump routing, and service access.

## Locked decisions

| Area | Decision |
|---|---|
| Tent | 4 ft x 4 ft x 8 ft tent |
| System | Ebb-and-flow flood table |
| Tray | Botanicare 3 ft x 3 ft Core/ID flood tray inside the 4 ft x 4 ft tent |
| Stand | Fast Fit 3 ft x 3 ft tray stand |
| Plant count | Start 25 seedlings; cull to 16 final plant sites |
| Grid | Fixed 4 x 4 final coordinate grid |
| Media | 1.5 inch rockwool starter cubes transplanted into 6 inch x 6 inch rockwool final blocks |
| Reservoir | Reuse existing 30 gal AquaPot reservoir as an external nutrient reservoir |
| Drain strategy | Tray drains by gravity into a local 15 gal tote sump; Sicce Syncra Silent 2.0 returns solution to external reservoir |
| Siphon control | Air-gap siphon break: fill outlet stays above maximum tray flood height; no siphon/check valve planned |
| Tray fittings | Botanicare Ebb & Flow Fitting Kit; 1/2 inch low drain plus 3/4 inch overflow routed to sump |
| Pump control | Dedicated microcontroller manages fill/drain cycle and safety interlocks |
| First flood depth target | 1.5-2.0 inches, tuned after dry run and first crop data |
| Tray height target | Stand height ~25 inches; bottom-bar clearance ~18 inches |
| Monitoring | Reservoir pH/EC plus runoff/tray pH once the pH sensor arrives |

## Grid layout

Use fixed coordinates for every plant record, photo, cull note, pollination event, and seed lot.

```text
Back of tent

A1  A2  A3  A4
B1  B2  B3  B4
C1  C2  C3  C4
D1  D2  D3  D4

Front of tent
```

Coordinate labels are part of the breeding record. A plant whose identity becomes uncertain should not be used for breeding.

The 25-start seedling phase should use separate early labels before transplant. Only the 16 final plants that survive culling get assigned the final table coordinates.

## Workflow model

The intended cycle is:

1. Start approximately 25 seedlings when seed supply allows.
2. Germinate and label seedlings in 1.5 inch rockwool cubes.
3. Cull aggressively before transplant for weak vigor, malformed growth, no early purple signal, squat/off-target morphology, label uncertainty, or other disqualifiers.
4. Transplant the best 16 seedlings into 6 inch x 6 inch final blocks on the 4 x 4 grid.
5. Run a very short veg.
6. Cull again for off-target traits during late veg and early flower.
7. Flower the remaining candidates.
8. Pollinate selected branches only.
9. Harvest seed lots by known plant and pollen source.
10. Reset the tray and repeat.

For stabilization generations, population count matters more than finished flower yield. Plants should stay small and individually scorable.

## Media rationale

Rockwool was selected over coco/fabric pots for this table because it makes the experiment cleaner:

- more uniform root-zone volume between plants
- predictable flood behavior
- no loose media washing into the reservoir
- faster reset between generations
- cleaner plant-grid geometry
- easier to treat each plant site as a discrete experimental unit

The tradeoff is lower buffering. Rockwool requires more disciplined pH/EC management than coco and must be conditioned correctly before transplant.

The 3 ft x 3 ft tray reduces final plant count from 25 to 16, but it removes the fit/stand problem created by trying to force a 4 ft x 4 ft tray and oversized commercial tray stand into a nominal 4 ft x 4 ft tent. The remaining tent margin is useful working space, not wasted space.

## Reservoir and drain layout

The external AquaPot reservoir will be used as a standard nutrient reservoir. The original bottom port can be capped if it is not useful for this build.

```text
30 gal reservoir outside tent
  -> Sicce Syncra Silent 1.5 fill pump
  -> fill line through tent port
  -> Botanicare 3x3 Core/ID flood tray
  -> tray drain fitting
  -> short gravity line into 15 gal tote sump
  -> Sicce Syncra Silent 2.0 sump pump
  -> return line back to reservoir
```

This solves the reservoir-height problem: the external reservoir top will sit higher than the tray drain outlet, so direct gravity return is not reliable. The tray only needs to gravity-drain into a lower local sump; the sump pump handles the lift back to the reservoir.

The fill line should discharge into the tray from above the maximum flood height. The outlet must not be submerged during normal operation. This open air gap is the siphon break: when the fill pump turns off, air enters the line and prevents the elevated reservoir from continuing to feed the tray. Do not rely on a check valve as the primary siphon control.

Use the Botanicare Ebb & Flow Fitting Kit for tray penetrations:

- 1/2 inch fitting as the low drain, routed to the 15 gal sump through a tunable ball valve.
- 3/4 inch fitting with extension as the overflow, set to the maximum flood height and routed to the 15 gal sump.

The fill line is separate from the tray bulkhead fittings and enters over the tray rim.

## Controller

A dedicated microcontroller will manage the flood-and-drain system instead of a standalone cycle timer.

Baseline controller responsibilities:

- turn the Sicce Syncra Silent 1.5 fill pump on/off for scheduled flood events
- stop fill when the cycle target is met, or immediately on tray high-water signal
- turn the Sicce Syncra Silent 2.0 sump pump on/off from sump level state
- prevent fill and sump return from fighting each other unless intentionally allowed during a test mode
- expose manual fill/drain/test commands
- log flood starts, stops, safety trips, and sensor states

The controller design is not finalized yet. Treat pump relays, float switches, high-water cutoff, and electrical enclosure selection as open BOM items until the firmware/hardware design is written.

## Sump

Use a generic 15 gal tote near or under the tray as the local sump. The larger tote gives real buffer for a 1.5-2.0 inch flood event and reduces overflow risk compared with a 5 gal bucket.

The sump should be able to hold a full tray drain event if the sump pump is delayed or fails. The sump pump can be timer-driven, but a float-switch-controlled sump pump is preferred because it removes timing guesswork. The extra sump volume does not replace high-water safety controls; it just makes the system less brittle.

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

Target tray height: the Fast Fit 3 ft x 3 ft stand is approximately 25 inches tall, with roughly 18 inches of bottom-bar clearance without casters.

This gives enough working room for a local sump and drain plumbing while preserving vertical space in the 8 ft tent for:

- stand and tray
- 6 inch rockwool blocks
- short SOG plants
- flower stretch
- light fixture and clearance

The specific stand should be verified against the selected tray and the final plumbing layout before purchase. Confirm the stand fits inside the tent at the intended height and that the sump can still be removed or serviced.

## Safeties

Minimum safeguards:

- tray overflow fitting set to maximum flood height
- fill-line air-gap siphon break with outlet above maximum flood height
- return line secured to the reservoir
- covered reservoir to prevent algae/debris
- local sump sized for a full drain event
- water alarm near the tent floor
- microcontroller pump control that prevents accidental continuous flooding

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
