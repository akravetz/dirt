---
title: Concept — DLI & Light Management (Fold-650)
type: concept
sources: [raw/chat-history/all-chat-summary.md]
related: [wiki/concepts/vpd.md, wiki/environment/nutrients.md, wiki/concepts/coco-coir.md, wiki/concepts/damping-off.md, wiki/breeding/README.md]
created: 2026-04-07
updated: 2026-05-05
---

# DLI & Light Management

This page is the project reference for measuring and setting plant light in the
main Fold-650 tent and the breeding/propagation side workflows.

## Core Terms

**PPFD** — Photosynthetic Photon Flux Density. Instantaneous usable plant light
at canopy level, measured in **µmol/m²/s**. This is the number to read with a
PAR meter or Photone.

**DLI** — Daily Light Integral. Total usable plant light received over a full
photoperiod, measured in **mol/m²/day**.

**Formula:** `DLI = PPFD × light-hours × 0.0036`

PPFD is "how bright right now"; DLI is "how much light today."

## What Is DLI?

For the current 12/12 flower schedule:

| PPFD | Hours | DLI |
|------|-------|-----|
| 600 | 12 | 25.9 |
| 650 | 12 | 28.1 |
| 700 | 12 | 30.2 |
| 800 | 12 | 34.6 |

The 18→12 flip matters because the same PPFD delivers one-third less daily
light after the flip:

- `600 PPFD × 18 hr × 0.0036 = 38.9 DLI`
- `600 PPFD × 12 hr × 0.0036 = 25.9 DLI`

Do not compensate by instantly blasting the canopy. Early flower should be
ramped. The plant is transitioning hormonally, stretching, and still exposing
new tops to the SCROG plane.

## PPFD Targets by Stage

Use measured canopy PPFD instead of dimmer percentage as the source of truth.

| Stage | Target PPFD | Notes |
|-------|-------------|-------|
| Clone rooting | 75–150 | Low light; avoid heating the dome |
| Clone/mother stasis | 100–200 | Enough to hold healthy veg without fast growth |
| Seedling | 200–300 | Use 300–400 only if healthy and still reaching |
| Early veg | 300–450 | Ramp after roots establish |
| Late veg / SCROG fill | 450–600 | Keep canopy even |
| Flower week 1 | 600–700 average | Accept ~500–750 across the net; avoid >800 hotspots |
| Flower week 2 | 700–800 | Ramp only if leaf posture and VPD are stable |
| Flower week 3 / bud set | 750–850 | Stretch should be slowing |
| Mid flower | 800–950 | Practical no-CO2 ceiling for this closet |
| Late flower | 700–900 | Taper if tops show stress, bleaching, or foxtailing |

## DLI Targets by Stage

| Stage | Approximate DLI Target |
|-------|------------------------|
| Seedling | 12–20 |
| Early veg | 20–30 |
| Late veg | 30–40 |
| Flower week 1 | 26–30 |
| Flower week 2–3 | 30–37 |
| Mid flower | 35–41 |
| Late flower | 30–39 |

These are operating targets, not proof of health. The plant still wins: leaf
temperature, posture, stretch, tacoing, bleaching, and water uptake decide
whether the target is too aggressive.

## Seedling Stretch Diagnosis

Severe seedling stretch is usually a shared light/environment issue before it
is a genetics signal.

If every seedling in a lot stretches several inches before transplant, assume
the seedlings had too little usable light at canopy level, the light was too
far away, the dome diffused/blocked too much light, or they spent too long
after emergence before receiving strong light. Genetics can influence later
internode length, but do not score early etiolation as a breeding trait.

Corrective target for the SBxBS01 Track A seedlings:

- Start around **200–300 PPFD** at seedling canopy.
- If they still reach after 24–48 hours and leaves look healthy, move toward
  **300–400 PPFD**.
- If leaves curl, taco, bleach, or stall, back off.
- Add gentle airflow after transplant so stems strengthen.
- Keep coco moist but not saturated around buried stems.

Burying leggy stems during transplant is a valid rescue, but it increases the
importance of crown-zone airflow and moisture discipline. See
[Coco Coir Medium](coco-coir.md) and [Damping Off](damping-off.md).

## Main Tent Flower Ramp

Current main tent context: Fold-650 LED, 4x4 SCROG, 12/12 schedule, no
supplemental CO2.

For flower week 1, set the canopy by Photone/PAR reading:

- **Target average:** 600–700 PPFD
- **Good enough range across the net:** 500–750 PPFD
- **Avoid this week:** hotspots above ~800 PPFD, especially on tall A/D tops

Ramp over the next two weeks only if the environment supports it. VPD, root
zone oxygen, and airflow must keep up with light intensity.

## Without Supplemental CO2

At ambient CO2, the practical home-grow ceiling is roughly **900–1,000 PPFD**.
Above that, more light often turns into heat and oxidative stress instead of
more useful photosynthesis unless temperature, VPD, airflow, nutrition, and CO2
are all deliberately managed.

With supplemental CO2, the ceiling can move much higher. That is not the current
system, so do not use CO2-enriched PPFD targets for this grow.

## Measuring with Photone

Photone with a diffuser is good enough for grow-room decisions. Treat it as a
practical field meter, roughly **±10%** when configured and used correctly, not
as a calibrated lab instrument.

Protocol:

1. Select the correct light source, usually **Full Spectrum LED** for the
   Fold-650.
2. Select the exact diffuser type in the app: paper diffuser vs Photone
   diffuser accessory.
3. Measure at canopy height, phone level, sensor/diffuser facing upward.
4. Do not shade the sensor with a hand, arm, head, or phone case lip.
5. Take multiple readings across the SCROG or seedling tray.
6. Use the average plus the low/high spread; do not tune from a single hotspot.
7. Record notes as **Photone PPFD**, not absolute reference PPFD.

For this project, Photone is accurate enough to distinguish the decisions that
matter: 70 vs 250 PPFD for seedlings, 500 vs 700 PPFD in week 1 flower, or a
900+ PPFD hotspot on a tall top.

## Meter Trust Levels

| Tool | Use | Trust level |
|------|-----|-------------|
| Photone + proper diffuser | Daily setup and canopy mapping | Good practical meter; setup-sensitive |
| Budget PAR meter | Cross-checking and repeatability | Useful if cheap/returnable; verify against plant response |
| Apogee-class quantum meter | Reference measurements and calibration | Best instrument class; expensive |

Budget meters are useful if they report PPFD directly and are cheap enough to
treat as a practical tool. Be cautious if a listing lacks accuracy, calibration,
cosine-response, spectral-response, drift, and support/recalibration specs.

## Interaction with VPD

Higher PPFD drives more stomatal opening and transpiration, which increases the
plant's VPD demand. If VPD is too low when ramping light, the stomata close and
photosynthesis stalls regardless of intensity. If VPD is too high, the plant can
dry faster than the roots can support. Always match the light ramp to the
current VPD target. See [VPD](vpd.md).

## Interaction with Nutrients

Higher light intensity can raise growth rate and nutrient demand. In coco, the
plant will show light/nutrient/water mismatches quickly. Avoid changing light
and EC aggressively at the same time; change one major variable, wait 2–3 days,
then evaluate.

## External References

- Photone common mistakes and accuracy guidance:
  <https://growlightmeter.com/guides/common-mistakes/>
- Photone App Store listing and diffuser requirement:
  <https://apps.apple.com/us/app/photone-grow-light-meter/id1450079523>
- Cannabis early-flower PPFD ranges:
  <https://growguide.app/blog/cannabis-flowering-stages-week-by-week-pictures/>
- Flowering PPFD ramp guidance:
  <https://weedinsight.com/ppfd-for-flowering/>
- General PPFD/DLI stage ranges:
  <https://growpilot.guide/seo/growing-guide/634-calculate-and-apply-ppfd-correctly>
- VIVOSUN PPFD/distance guide:
  <https://vivosun.com/growing_guide/how-far-away-should-lights-be/>
- Seedling stretch / leggy seedling troubleshooting:
  <https://blog-fruit-vegetable-ipm.extension.umn.edu/2020/04/troubleshooting-seedling-issues.html>
