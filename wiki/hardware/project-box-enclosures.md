---
title: Hardware — Project Box Enclosures
type: hardware
sources: []
related: [wiki/hardware/reservoir-level.md, wiki/hardware/ac-infinity-fan-control.md, wiki/hardware/esp32-plant-nodes.md]
created: 2026-05-25
updated: 2026-05-25
---

# Project Box Enclosures

Practical enclosure guidance for moving grow-room electronics off breadboards
and into splash-resistant project boxes. Current targets: the reservoir level
node and the tent temperature/RH SHT45 node.

## Core Rules

- Drill project boxes yourself. Generic ABS/polycarbonate boxes usually ship
  blank; cable, sensor, and mounting holes are placed for the build.
- Use metric hardware where possible. Cable glands, vents, standoffs, and
  drill sizes are normally specified in millimeters.
- Seal electronics, ventilate sensors, strain-relieve every cable.
- Do not use a breadboard for permanent analog or humid grow-room installs.
- Do not rely on hot glue for waterproofing or strain relief.

## Current Scope

| Box | Location | Contents | Special requirement |
|---|---|---|---|
| Reservoir node | Outside tent, near reservoir, off the floor if possible | ESP32-C3, ADS1115, SEN0262, power/signal wiring | Keep probe vent dry but breathable; protect analog nodes from splash and residue. |
| Tent temp/RH node | Outside/edge of tent, with SHT45 exposed to tent air | ESP32-C3 or fan-control electronics plus SHT45 cable | Do not seal the SHT45 sensing element inside a closed box; it needs airflow. |

The ABS boxes on order are Amazon `B0895J3SWL` project boxes.

## Bill of Materials

### Tools

| Item | Recommendation | Purpose |
|---|---|---|
| Metric step drill bit | 4-32 mm or similar | Clean cable-gland and vent holes in ABS boxes. |
| Center punch or awl | Any small punch | Prevent the drill from wandering. |
| Deburring tool or countersink bit | Small hand deburrer is enough | Clean both sides of drilled holes so gaskets sit flat. |
| Calipers | Digital calipers | Measure cable outer diameter and connector pitch. |
| Drill | Low/medium speed | Drill enclosure holes without melting plastic. |

An imperial step-bit set will work, but metric is less error-prone because
gland mounting holes are specified in millimeters.

### Cable Entry and Strain Relief

| Item | Recommendation | Purpose |
|---|---|---|
| PG7 IP68 nylon cable glands | Clamp range around 3-6.5 mm | Small jacketed sensor/control cables. |
| PG9 IP68 nylon cable glands | Clamp range around 4-8 mm | Thicker jacketed cables. |
| Optional M12 breathable vent plug | Hydrophobic/PTFE style | Pressure equalization and humidity management in mostly sealed boxes. |
| 22 AWG 4-conductor stranded jacketed cable | Tinned copper preferred | Reservoir signal/power run through one gland. |
| Screw-down cable tie mounts | Prefer screw-down over adhesive-only | Internal secondary strain relief. |
| Small zip ties | Nylon | Tie cable to internal mount after it enters the box. |

Cable glands seal around round jacketed cable. They do not seal well around four
loose individual wires. For the reservoir node, run a short 4-conductor
jacketed cable through one gland, then terminate inside the box.

### Internal Mounting and Wiring

| Item | Recommendation | Purpose |
|---|---|---|
| Perma-proto or solderable breadboard | Adafruit Perma-Proto or equivalent | Permanent soldered circuit carrier. |
| M2.5 nylon standoff kit | Assorted heights | Mount boards above the box floor. |
| M2.5 stainless screws/nuts/washers | Match standoffs | Fasten boards and standoffs. |
| JST connector kit | Confirm pitch first | Removable low-voltage sensor/control connections. |
| Heat-shrink assortment | 2:1 or 3:1 | Insulate solder joints and connector transitions. |
| Optional WAGO 221 lever nuts | Small 2/3/5-port | Temporary low-voltage splices during layout. |
| Optional ferrule kit | Match wire gauge | Cleaner screw-terminal connections. |

Common JST pitches: JST-XH is 2.54 mm, JST-PH is 2.0 mm, JST-SH/Qwiic is
1.0 mm. Measure before buying keyed housings for existing cables.

### Sealants, Adhesives, and Moisture Control

| Item | Recommendation | Use |
|---|---|---|
| Neutral-cure RTV silicone | Non-acetic; no vinegar smell | Optional sealing around glands or non-critical seams. |
| E6000 or 3M VHB tape | Optional | Light-duty mounts, labels, or cable tie bases. |
| Silicone conformal coating | Optional | Protect boards after debug is complete. |
| Desiccant packets | Small reusable packets | Keep sealed electronics boxes dry. |
| 90%+ isopropyl alcohol | Electronics cleanup | Clean boards after soldering or suspected splash exposure. |

Do not conformal-coat sensor elements, connectors, buttons, trim pots, USB
ports, or the pressure sensor vent. Do not use acetic-cure silicone near
electronics; the vinegar-smell cure chemistry is not what we want inside a
small electronics enclosure.

## Drilling Workflow

1. Lay out the box with the lid orientation marked.
2. Keep cable entries on the lower side when possible, so drip loops can form.
3. Mark hole centers with a center punch or awl.
4. Drill a small pilot hole if needed.
5. Use the metric step bit slowly with light pressure.
6. Stop one step before the expected gland size and test fit.
7. Enlarge one step at a time until the gland just fits.
8. Deburr both sides.
9. Install the gland with its gasket and locknut.

For plastic boxes, avoid high drill speed and hard pressure. Heat can melt the
plastic or make the bit grab.

## Strain Relief Pattern

Every cable should be strain-relieved twice:

1. The cable gland clamps the jacket at the enclosure wall.
2. An internal zip tie or clamp catches any remaining tug before it reaches a
   solder joint, JST header, screw terminal, or sensor board.

Route external cables with drip loops: the cable should dip below the box entry
before entering the gland, so water running along the cable drips off before it
reaches the enclosure.

## Reservoir Node Layout

Recommended layout:

- Gasketed ABS project box.
- One PG7/PG9 gland for a 4-conductor jacketed low-voltage cable.
- Separate gland for power if power enters as a separate cable.
- ESP32-C3, ADS1115, and SEN0262 mounted on perma-proto/standoffs.
- Screw-down internal cable tie mount after each gland.
- Desiccant packet inside.
- Box mounted off the floor, with drip loops on all cables.

Reservoir-specific cautions:

- Keep the hydrostatic probe's atmospheric vent dry and breathable.
- Do not seal the vent into a wet, airtight, humid pocket.
- Keep A0/SEN0262/ADS1115 analog wiring short, clean, and away from wet
  residue. The reservoir debug incident showed that the ADS1115's tightest
  gain setting can be sensitive to input-source behavior.

## SHT45 Temperature/RH Layout

The SHT45 needs airflow. Do not seal the sensing element inside a closed box or
it will read the stale microclimate inside the enclosure instead of tent air.

Good options:

- Put the controller/electronics inside the sealed project box, then run the
  SHT45 on a short cable outside the box.
- Put the SHT45 inside a small vented or louvered sensor cap.
- Use a downward-facing splash hood, fine mesh, or PTFE vent membrane if splash
  protection is needed.

Do not conformal-coat the SHT45 sensing element. If the SHT45 breakout has a
PTFE cap, preserve it and keep the board oriented so liquid water cannot pool
on the sensor.

## Minimum Cart

- Metric step bit, 4-32 mm.
- PG7 cable gland assortment.
- PG9 cable gland assortment.
- 22 AWG 4-conductor stranded jacketed cable.
- M2.5 nylon standoff kit.
- M2.5 stainless screw/nut/washer kit.
- Adafruit Perma-Proto boards or equivalent solderable breadboards.
- Neutral-cure RTV silicone.
- Heat-shrink assortment.
- Small zip ties and screw-down cable tie mounts.
- Desiccant packets.
- 90%+ isopropyl alcohol.
- Optional M12 breathable vent plugs.
- Optional silicone conformal coating.

## Open Questions Before Ordering Connectors

- Confirm the outer diameter of each cable that will pass through a gland.
- Confirm the JST connector pitch already used on each sensor cable.
- Decide whether any box needs a removable external connector; glands are
  simpler, but panel connectors make service easier.
- Decide final box placement so cable entries can be drilled on the side that
  naturally supports drip loops.
