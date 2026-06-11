---
title: Environment — Nutrients & pH
type: environment
sources: [raw/chat-history/all-chat-summary.md, raw/chat-history/bible.md, raw/chat-history/memory.md]
related: [wiki/concepts/coco-coir.md, wiki/concepts/autopot.md, wiki/overview.md]
created: 2026-04-06
updated: 2026-06-10
---

# Nutrients & pH

## Nutrient Line
**Canna Coco A+B** — sole nutrient product for entire grow (veg and flower).

- Mix A first, stir, then add B. Never combine A and B undiluted — they'll precipitate calcium phosphate and drop out of solution.
- Canna A+B already formulated to account for coco's calcium and magnesium demands. **Skip CalMag** unless deficiency signs appear.
- Adjust pH **after** Canna is mixed in, not before. Canna shifts pH on its own; correcting tap first is wasted effort.

## EC Targets by Phase — Autopot Reservoir

These targets are for the **autopot reservoir** (continuous feed). Hand-feed EC runs ~20–30% higher because flush-through dilutes the effective root-zone concentration. The reservoir is what the plants sip from all day, so reservoir EC ≈ effective feed EC.

| Phase | Reservoir EC | TDS-3 ppm (500 scale) |
|-------|--------------|------------------------|
| Early Veg / post-topping (current) | 0.8–1.0 | 400–500 |
| Mid Veg (canopy filling) | 1.0–1.2 | 500–600 |
| Late Veg / pre-flip | 1.2–1.4 | 600–700 |
| Early/Mid Flower | 1.4–1.6 | 700–800 |
| Late Flower (taper) | 1.2–1.4 | 600–700 |
| Final flush | 0.0 | 0 (plain pH 5.8 water) |

**Recovery note:** after stress events (topping, LST, transplant), sit at the **low end** of the current band. Plants repairing tissue don't handle hot nutrients well.

**TDS-3 conversion:** `EC (mS/cm) = ppm / 500`. The TDS-3 (HM Digital) uses the NaCl / 500 scale; there's no toggle on the unit. See [EC concept](../concepts/ec.md).

**Denver tap background:** plain tap measures ~100–150 ppm (calcium from water treatment) before any nutrients. The target total is what the meter shows with Canna mixed in — don't subtract the background.

## Current Reservoir Correction

**2026-06-10 20:00 MDT:** reservoir EC was found well over 2.0 mS/cm, above the late-flower taper target. The entire Autopot reservoir was flushed/replaced with plain Denver tap water adjusted to pH 5.8, measuring roughly EC 0.3 after adjustment.

Plan: leave the plants on plain pH 5.8 / EC ~0.3 water for about 24 hours, then rebuild the reservoir to roughly EC 1.2 around 2026-06-11 20:00 MDT if plant posture and tray cycling remain acceptable. This is a corrective high-EC reset, not a final harvest flush.

## pH Management

**Target pH:** 5.8 (after nutrients added)
**Acceptable range:** 5.5–6.0

**Critical Denver note:** Denver tap water pH runs 8.5–8.8 (due to the city's Lead Reduction Program). GH pH Down is **required at every reservoir fill**. Canna A+B's buffering does NOT eliminate this need.

**Chloramines:** Denver water uses chloramines (not free chlorine). These do NOT off-gas — cannot be treated by letting water sit. Use as-is after pH adjustment.

## Incident Log

| Date | Event | Resolution |
|------|-------|------------|
| 2026-04-05 | ⚠️ Plant A foliar burn — yellowing upper leaves from nutrient solution spill | Identified as localized salt damage (foliar burn), NOT systemic deficiency. No intervention; monitor new growth → [2026-04-05 daily](../daily/2026-04-05.md) |
| 2026-04-05 | ⚠️ Plant C lighter green + edge spotting on older leaves | pH verification needed — ensure watering at exactly 5.8 → [2026-04-05 daily](../daily/2026-04-05.md) |
| 2026-04-08 | ⚠️ Plant C worsening — brown/rust spots on multiple leaves; stress-induced purple on stems/petioles | Most likely pH lockout. Required: measure runoff pH and EC; flush with plain pH 5.8 water if runoff pH outside 5.5–6.2 → [2026-04-08 daily](../daily/2026-04-08.md) |
| 2026-04-11 | ⚠️ Nutrient solution measured at 920 ppm (EC ~1.84) — above early veg target of 0.8–1.0 EC | Dilute next feed to EC 0.8–1.0. TDS-3 factor confirmed 0.5 (NaCl / 500 scale) on 2026-04-15 — 920 ppm is correct at EC 1.84 → [2026-04-11 daily](../daily/2026-04-11.md) |
| 2026-05-17 | ⚠️ Plant A local low-pH tray/runoff — pH 4.8 with rough lower-leaf chlorosis/necrosis and stunting concern; reservoir was normal at pH 5.8 / EC 1.4 | Working diagnosis: localized low-pH lockout/root-zone acidification, not hot reservoir feed. Plant A received 8 cups pH 5.8 / EC 1.2 top flush; post-flush runoff EC ~1.1. Recheck A tray/runoff pH+EC before disturbing and compare B/C/D trays → [2026-05-17 daily](../daily/2026-05-17.md) |
| 2026-05-27 | ⚠️ Plant A comparison extraction — A pH 5.78 / EC 4.4 versus healthy D pH 5.97 / EC 3.0; A coco visibly wetter and drying back slowly after valve closure | Current diagnosis shifts away from active low-pH lockout and toward high root-zone EC/salt concentration plus wet/slower cycling in A. A valve remains closed after tray/stand cleaning; wait for dryback before any controlled weak pH 5.8 top rinse, and do not adjust the whole reservoir based on A alone → [2026-05-27 daily](../daily/2026-05-27.md) |
| 2026-05-31 | ⚠️ Plant A post-dryback weak top rinse/feed — plant looked healthier with small dark-green growth tips; live rough moisture was stable near 35.7% after the large dryback | Runoff pH 6.2 and EC about 40% above input. This does not support active low-pH lockout or a severe salt dump; stop further rinsing, remove runoff, leave the valve closed 12-24h, then reopen Autopot only as a monitored test if tray/pot conditions stay clean → [2026-05-31 daily](../daily/2026-05-31.md) |
| 2026-06-04 | ⚠️ Plant A additional runoff after diagnostic top rinse — plant looked fine; no heavy, sour, or stagnant pot/tray signs; runoff pH looked fine; TDS measured >1000 ppm on the 500 scale, equivalent to EC >2.0 | Interpreted as residual soluble salts still washing through after top rinse, not an active pH problem. Reconnect Plant A to the Autopot as a watched test, remove runoff, and do not perform another top flush unless the plant declines or repeated checks show persistent high EC; if needed, flush drain-to-waste with light feed EC 0.4-0.6 / 200-300 ppm on the 500 scale → [2026-06-04 daily](../daily/2026-06-04.md) |
| 2026-06-10 | ⚠️ Whole Autopot reservoir EC found too high, well over 2.0 mS/cm, during evening service | Entire reservoir flushed/replaced at 20:00 MDT with plain tap water adjusted to pH 5.8 and EC ~0.3. Let plants drink plain water for ~24h, then rebuild nutrient solution to roughly EC 1.2 if posture and tray cycling remain acceptable → [2026-06-10 daily](../daily/2026-06-10.md) |

## pH Correction History
- **2026-03-28** — pH misconception corrected: Canna A+B buffering does NOT eliminate need for pH Down in Denver water. pH Down required every fill.

## Equipment
- **pH Down:** GH pH Down (primary)
- **pH Meter:** Apera Instruments AI311 Premium Series PH60 Waterproof pH Pocket Tester Kit (±0.01 pH accuracy, replaceable probe, waterproof) — [Amazon B01ENFOIQE](https://www.amazon.com/dp/B01ENFOIQE)
- **EC Meter:** TDS-3 EC meter
