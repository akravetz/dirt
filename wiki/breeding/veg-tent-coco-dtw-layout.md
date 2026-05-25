---
title: Breeding Veg/Female Tent Layout - Coco Drain-to-Waste Alternative
type: breeding
sources: []
related: [wiki/breeding/README.md, wiki/breeding/veg-tent-layout.md, wiki/breeding/family-selection.md, wiki/breeding/bill-of-materials.md, wiki/concepts/coco-coir.md]
created: 2026-05-25
updated: 2026-05-25
---

# Breeding Veg/Female Tent Layout - Coco Drain-to-Waste Alternative

Alternative working layout for the repurposed 4 ft x 4 ft x 8 ft breeding
tent. This keeps the 16-site pheno-hunt model from
[veg-tent-layout.md](veg-tent-layout.md), but replaces the rockwool
ebb-and-flow table with small coco pots on a drain-to-waste tray.

Status: **proposed / likely direction**, not locked. The original
ebb-and-flow proposal remains valid; this page exists so the two systems can be
compared without overwriting the earlier plan.

The goal is not yield. The goal is population size, repeatability, easy
culling, clean labels, branch pollination, and fast reset between generations.
Coco drain-to-waste favors fewer hard-plumbing failure modes and easier human
servicing over the very clean shared-table behavior of flood-and-drain
rockwool.

## Working design

| Area | Proposed direction |
|---|---|
| Tent | 4 ft x 4 ft x 8 ft tent |
| System | Coco drain-to-waste with automated pressure-compensating drip |
| Plant count | Start ~25 seedlings; cull to 16 final plant sites |
| Grid | Fixed 4 x 4 coordinate grid, same A1-D4 model as the flood-table plan |
| Media | Coco/perlite, likely 60/40 or similar high-air mix |
| Pots | 1 gal rigid square plastic nursery pots for the first run |
| Irrigation | Reservoir -> pressure pump -> filter -> regulator/gauge as needed -> PC emitters -> stakes/halo |
| Emitters | Two low-flow pressure-compensating emitters per pot as the default starting point |
| Tray | Shared low-profile drain tray or low flood table used only for runoff capture |
| Drainage | Tray drains to covered waste tote or shallow condensate pump; no recirculation |
| Human work priority | Easy pot removal, easy culling, easy cleaning, minimal hidden plumbing state |

## Grid layout

Use the same fixed coordinate model as the flood-table plan.

```text
Back of tent

A1  A2  A3  A4
B1  B2  B3  B4
C1  C2  C3  C4
D1  D2  D3  D4

Front of tent
```

Coordinate labels are part of the breeding record. A plant whose identity
becomes uncertain should not be used for breeding.

The 25-start seedling phase should use separate early labels before transplant.
Only the 16 final plants that survive culling get assigned the final table
coordinates.

## Why this may beat flood-and-drain for this tent

Coco drain-to-waste has more irrigation tubing at the plant sites, but the
overall system is simpler to reason about:

- no flood-depth tuning
- no tray-fill event moving 8-12 gal at once
- no sump-return loop
- no recirculating reservoir chemistry
- no shared root-zone runoff returning to the reservoir
- easier removal of one plant after a cull
- easier per-plant inspection and runoff sampling
- lower tray/stand height possible, preserving flower stretch room

The tradeoff is recurring waste management. Runoff must go somewhere, and the
runoff path must be kept clean enough that pots never sit in standing nutrient
solution.

## Comparison with ebb-and-flow rockwool

| Dimension | Coco drain-to-waste | Ebb-and-flow rockwool |
|---|---|---|
| Setup complexity | Moderate; feed pump, filter, manifold, emitters, runoff tray | Higher; flood tray, fill pump, drain, sump, return pump, overflow, siphon controls |
| Operating complexity | Irrigation automation is straightforward; runoff handling is the chore | Fewer daily waste chores, but reservoir/root-zone drift needs tighter discipline |
| Failure mode | Clogged emitter or runoff backup usually affects one/few plants first | Fill/drain/siphon failures can affect the whole table quickly |
| Chemistry | Fresh feed enters; runoff leaves | Shared recirculating solution changes over time |
| Plant isolation | Strong; each pot is a discrete root zone | Weaker; shared tray and reservoir |
| Culling | Easy to remove one pot | Easy to remove one block, but roots can mat across tray if not controlled |
| Uniformity | Good if emitters are calibrated; pot packing matters | Excellent once flood behavior is tuned |
| Forgiveness | Higher; coco buffers more than rockwool | Lower; rockwool requires tighter pH/EC and water-content control |
| Reset | Empty pots/media and clean tray | Remove blocks and clean tray; less loose media |
| Vertical space | Can be very low profile | Often needs a taller stand if gravity/sump layout drives the design |

## Pots

Default first-run pot:

```text
1 gal rigid square plastic nursery pot
```

Why:

- small enough for a 4 x 4 grid inside a 3 ft x 3 ft tray footprint
- adequate for fast-flip, small-plant pheno hunting under frequent fertigation
- easy to label
- easy to lift and remove during culls
- easy to clean or replace between runs
- less likely than fabric to wick runoff back from the tray
- more dimensionally uniform than round fabric pots

Fabric pots are acceptable for coco drain-to-waste, but they are not the best
default for this breeding table. They air-prune well and are common in
yield-oriented coco grows, but they add side evaporation, salt crusting on the
pot wall, less rigid handling, harder cleaning, and more risk of roots knitting
into fabric or runoff-contact surfaces.

If the first run dries too aggressively or seed maturation needs more root
buffer, consider a 1.5-2 gal square plastic pot only if its footprint still
works in the 4 x 4 grid. Avoid starting with 3 gal pots; that shifts the table
toward yield production instead of fast-cycle selection.

## Irrigation model

The permanent version should use pressure-capable drip hardware, not a simple
open-flow manifold that depends on perfectly equal line lengths.

Typical layout:

```text
30 gal reservoir
  -> pressure-capable pump
  -> 150-200 mesh filter
  -> pressure gauge
  -> pressure regulator if the pump output requires it
  -> 1/2 inch mainline or PVC header
  -> pressure-compensating emitters
  -> 1/4 inch lines to each pot
  -> stakes, halos, or drip rings
```

Pressure-compensating emitter systems are usually called **PC drip**. The
emitter meters flow at a rated output, such as 0.5, 1, or 2 GPH, as long as the
system is inside the emitter's operating pressure range.

Open-flow systems are usually called **open drip**, **free-flow drip**, or
**non-pressure-compensating drip**. In those systems, water takes the easiest
path, so equal line lengths and cup calibration matter much more.

For 16 sites, a practical starting point is:

```text
16 plants
2 x 0.5 GPH PC emitters per plant
32 emitters total
```

At two 0.5 GPH emitters per plant, each plant receives about 63 ml/min at rated
flow. A five-second pulse is too short to be a useful irrigation event; it is
only about 5 ml/plant. Irrigation windows should be calibrated in tens of
seconds to minutes, then adjusted by pot weight, runoff, plant response, and
stage.

The system does not need constant pressure all day. Normal operation is:

```text
pump off: lines stay full, pressure near zero
pump on: pressure rises, PC emitters flow
pump off: pressure bleeds down through emitters, flow stops
```

Keep lines primed so irrigation events do not waste time refilling dry tubing
and purging air. During setup, put every emitter into measuring cups and run the
system for a fixed interval to compare real volumes.

Likely hardware families:

- pressure pump: SEAFLO 33-Series or Shurflo/Pentair 2088-style diaphragm pump
- PC emitters: Netafim PC drippers, DIG PC stakes, FloraFlex low-flow emitters
- multi-outlet PC bubbler option: FloraFlex QDPS Multi Flow or Rivulis/Jain Octa-Bubbler
- filter: 150-200 mesh screen/disc filter from Rain Bird, DIG, Netafim, Amiad, FloraFlex, or similar
- regulator/gauge: Senninger, Rain Bird, DIG, Netafim, Tempo, Hunter, or similar

## Drain tray options

The tray should collect runoff without raising the plants more than necessary.
Preserving vertical space matters because these plants will still stretch after
a fast flip.

Preferred first concept:

```text
low-profile 3x3 drain tray on or near the tent floor
small pot risers/elevators so pots do not sit in runoff
tray drain to covered waste tote or shallow condensate pump
```

Common approaches:

| Tray approach | Notes |
|---|---|
| Shared low-rise tray | Best simple version; one tray captures all runoff |
| Standard flood tray used as drain tray | Works, but sidewalls are taller than needed |
| Individual FloraFlex/Bucket Company-style platforms | Good per-plant drainage, but adds 16 drain interfaces and more tubing |
| DIY sloped tray/table | Flexible, but more fabrication and more chances for leaks |

Avoid a tall 25 inch flood-table stand unless gravity drainage to a large tote
is more important than canopy height. If a low tray cannot gravity-drain, a
shallow condensate pump is probably a better tradeoff than raising the whole
garden.

## Runoff and waste handling

Drain-to-waste means runoff leaves the root zone and is discarded. That is a
major reason the chemistry is simpler than recirculating hydro, but it creates
the main human chore.

Starting targets:

- irrigate often enough that coco stays evenly moist, not soil-dry
- tune toward modest runoff once plants are established
- measure occasional runoff pH/EC to catch root-zone drift
- keep the tray clean enough that old runoff does not stagnate
- size the waste tote for worst-case unattended runoff, not just average runoff

For early seedlings and just-transplanted plants, do not chase runoff at every
event if the pot is not colonized yet. Once roots are established, runoff
becomes the confirmation that the root zone is being refreshed.

## Human workflow

The non-automatable work should be easy:

1. Mix reservoir feed.
2. Check reservoir pH/EC.
3. Verify waste tote capacity.
4. Inspect emitters visually during or after a feed.
5. Lift/check representative pots.
6. Pull occasional runoff samples.
7. Cull weak/off-target plants by lifting the whole pot out.
8. Clean tray and reset between generations.

Compared with flood-and-drain, this shifts work away from plumbing/siphon/sump
debugging and toward routine feed/runoff housekeeping.

## Open decisions

- exact tray: low-rise 3x3 drain tray vs standard flood tray used as drain tray
- drainage: gravity to waste tote vs shallow condensate pump
- pot: exact 1 gal square plastic model and footprint
- emitter: 0.5 GPH x2 per plant vs 1 GPH x1-2 per plant
- feed header: 1/2 inch poly mainline vs PVC manifold
- runoff measurement: shared tray sampling only vs occasional per-plant saucer/cup checks
- whether the bill of materials should pivot from flood-and-drain to this design

## Research anchors

External references used while sketching this alternative:

- FloraFlex PotPro platform drainage guidance:
  <https://www.floraflex.com/pages/faq-platforms-drainage>
- FloraFlex low-flow emitter / bubbler product family:
  <https://www.floraflex.com/>
- Netafim pressure-compensating drippers:
  <https://www.netafimusa.com/agriculture/products/product-offering/on-line-drippers/pressure-compensating-drippers/>
- DIG pressure-compensating drip stakes:
  <https://www.digcorp.com/homeowner-drip-irrigation-products/pressure-compensating-dripper-on-stake/>
- SEAFLO 33-Series diaphragm pumps:
  <https://www.seaflousa.com/product/33-series-diaphragm-water-pumps/>
- Pentair Shurflo 2088 diaphragm pumps:
  <https://www.pentair.com/en-us/flow/shurflo/shurflo-products/shurflo-agricultural-industrial-applications/agricultural-industrial-pumps/2088-series-diaphragm-pumps.html>
- Botanicare Low Tide trays:
  <https://www.botanicare.com/products/low-tide-trays/>
- Coco For Cannabis high-frequency fertigation:
  <https://www.cocoforcannabis.com/principles-fertigation-feed-water-cannabis-coco/>
