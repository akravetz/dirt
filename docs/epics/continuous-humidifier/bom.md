# Bill of Materials — Continuous Humidifier Intensity Control

Pre-ordered before Phase 1 investigation so that once the pot's signal type is known (Scenario A: DC voltage → digipot; Scenario B: PWM → direct GPIO) the hardware build can begin immediately.

## Procurement status (2026-04-23)

| State | Item | Source |
|---|---|---|
| ✅ In-hand | Heat-shrink tubing assortment | user stash |
| ✅ In-hand | E12 through-hole resistor kit | user stash |
| ✅ Ordered | Raydrop KC-RD03A spare | Amazon, arriving next-day |
| ✅ Ordered | MCP4131 digipots (1× each: 10 kΩ, 50 kΩ, 100 kΩ) | DigiKey, 2–3 day transit |
| ✅ Ordered | MCP4725 DAC breakout (#935), BSS138 level shifter (#757), headers + jumpers (#392 / #1957 / #1954) | Adafruit, 2–4 day transit |
| 🛒 To order | BOJACK 300-pc ceramic cap kit — ASIN B085RDTCCV ($9.99) | [Amazon](https://www.amazon.com/dp/B085RDTCCV) |

**Resume point for a fresh agent:** when all packages have arrived, start executing [`phase1-probe-checklist.md`](phase1-probe-checklist.md). The decision doc linked from the epic README has full rationale; you don't need to re-derive it. All four Phase-1→Phase-2 matrix rows are covered by what's already ordered — no further purchasing required based on the probe verdict.

## DigiKey (ordered — ~$2.24 in parts + shipping)

Through-hole digital potentiometers covering the three common pot resistances. DIP-8 → breadboard-friendly, no SMD soldering. Only the one matching the Raydrop's actual pot will be used; the other two sit in the parts drawer.

| Qty | Part | P/N | Unit | URL |
|---|---|---|---|---|
| 1 | Microchip MCP4131 — 10 kΩ SPI digipot, DIP-8 | **MCP4131-103E/P** | ~$0.69 | [DigiKey](https://www.digikey.com/en/products/detail/microchip-technology/MCP4131-103E-P/1874338) |
| 1 | Microchip MCP4131 — 50 kΩ SPI digipot, DIP-8 | **MCP4131-503E/P** | ~$0.96 | [DigiKey](https://www.digikey.com/en/products/detail/microchip-technology/MCP4131-503E-P/1874330) |
| 1 | Microchip MCP4131 — 100 kΩ SPI digipot, DIP-8 | **MCP4131-104E/P** | ~$0.69 | [DigiKey](https://www.digikey.com/en/products/detail/microchip-technology/MCP4131-104E-P/1874342) |

**Why MCP4131 specifically:** single-channel, 7-bit + wiper (128 steps — plenty for mist intensity), SPI from 2.7–5.5 V logic (3.3 V ESP32 is fine), VA/VB analog terminals rated to VDD so safe at 5 V on the Raydrop's control rail, active product line. The `MCP41010/41050/41100` series is an older equivalent — fall back to those if a 4131 variant is backordered.

## Amazon — Raydrop spare (ordered)

| Qty | Item | ASIN | ~Price | Notes |
|---|---|---|---|---|
| 1 | Raydrop humidifier (spare) | [B0CDL8XCJ5](https://www.amazon.com/dp/B0CDL8XCJ5) | $19.99 | Confirm model on bottom sticker of current unit before using the spare for Phase 1 probing — electronics may differ between Raydrop sizes. |

## Amazon — capacitor kit (to order)

| Qty | Item | ASIN | Price | URL |
|---|---|---|---|---|
| 1 | **BOJACK 10 Values 300 Pcs Ceramic Capacitor Assortment Kit** (0.1 / 0.15 / 0.22 / 0.33 / 0.47 / 0.68 / 1 / 2.2 / 4.7 / 10 µF, 30 pcs each, MLCC ±10 %) | **B085RDTCCV** | $9.99 | [Amazon](https://www.amazon.com/dp/B085RDTCCV) |

**Why this specific kit:**

- **Covers all three values we need**: 0.1 µF (digipot VDD bypass), 1 µF (RC filter for kHz-range PWM), 10 µF (RC filter for sub-100 Hz PWM).
- **All MLCC ceramic** including the 10 µF. For our RC-filter use case, MLCC is strictly better than electrolytic — no polarity, lower ESR, tighter tolerance, doesn't dry out over time. Electrolytic only wins for bulk filtering on high-ripple power rails, which isn't what we're doing.
- 300 pieces means this kit outlives the project many times over.

## Adafruit (ordered)

| Qty | Part | SKU | Price | Role in Phase 2 |
|---|---|---|---|---|
| 1 | MCP4725 12-bit DAC breakout (I²C) | [#935](https://www.adafruit.com/product/935) | $4.95 | Scenario-A fallback: use instead of MCP4131 if the pot drives an ADC expecting absolute voltage rather than a ratiometric divider. |
| 1 | BSS138 4-channel bidirectional level shifter | [#757](https://www.adafruit.com/product/757) | $3.95 | Use on the SPI (or DAC output) if the Raydrop's control side runs at 5 V — ESP32-C3 is 3.3 V only, not 5 V-tolerant. |
| 1 | 0.1" male header pin strip — 36-pin × 10 | [#392](https://www.adafruit.com/product/392) | $4.95 | Build-prep. |
| 1 | Premium M/M jumper wire bundle | [#1957](https://www.adafruit.com/product/1957) | $1.95 | Breadboarding. |
| 1 | Premium M/F jumper wire bundle | [#1954](https://www.adafruit.com/product/1954) | $1.95 | Breadboarding. |

## What we deliberately didn't order

- **Optoisolator breakout.** Ultrasonic humidifiers keep mains isolated from the low-voltage control board; mains-referenced voltage on the pot would be a genuine surprise. Only order if Phase 1 finds it.
- **Proto-PCB / perf board.** Breadboarding is fine until PI tuning is done. Move to perma-proto only if we're putting the circuit back inside the Raydrop case.
- **Oscilloscope.** HiLetgo LA + multimeter cover every likely case. See [phase1-probe-checklist.md](phase1-probe-checklist.md).

## Phase 1 → Phase 2 decision matrix

All listed parts are already on order; the matrix maps the probe verdict to which subset gets populated onto the breadboard.

| Phase 1 finding | Parts used in Phase 2 |
|---|---|
| Pot outputs smooth DC 0 → Vref, Raydrop at 3.3 V | One MCP4131 (matched resistance) + 1× 0.1 µF cap |
| Pot outputs smooth DC 0 → Vref, Raydrop at 5 V | One MCP4131 + BSS138 level shifter + 1× 0.1 µF |
| Pot sets PWM duty via RC into driver | ESP32 GPIO direct-drive, no IC; maybe 10 kΩ + 1 µF RC filter |
| Pot feeds ADC expecting absolute voltage | MCP4725 DAC breakout + 1× 0.1 µF |
| Encoded digital comms (unlikely) | Stop and re-plan — outside scoped alternatives |
