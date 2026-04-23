# Bill of Materials — Continuous Humidifier Intensity Control

Pre-ordered before Phase 1 investigation so that once the pot's signal type is known (Scenario A: DC voltage → digipot; Scenario B: PWM → direct GPIO) the hardware build can begin immediately.

**Approx total: $60–80** across three vendors. All SKUs verified in stock 2026-04-23.

## DigiKey (one order, ~$11 with shipping)

Through-hole digital potentiometers to cover whatever resistance the Raydrop's pot turns out to be. Buy 2× each variant so we have a spare of the one we actually use. DIP-8 → breadboard-friendly, no SMD soldering.

| Qty | Part | P/N | Unit | URL |
|---|---|---|---|---|
| 2 | Microchip MCP4131 — 10 kΩ SPI digipot, DIP-8 | **MCP4131-103E/P** | ~$0.69 | [DigiKey](https://www.digikey.com/en/products/detail/microchip-technology/MCP4131-103E-P/1874338) |
| 2 | Microchip MCP4131 — 50 kΩ SPI digipot, DIP-8 | **MCP4131-503E/P** | ~$0.96 | [DigiKey](https://www.digikey.com/en/products/detail/microchip-technology/MCP4131-503E-P/1874330) |
| 2 | Microchip MCP4131 — 100 kΩ SPI digipot, DIP-8 | **MCP4131-104E/P** | ~$0.69 | [DigiKey](https://www.digikey.com/en/products/detail/microchip-technology/MCP4131-104E-P/1874342) |

**Why MCP4131 specifically:** single-channel, 7-bit + wiper (128 steps — plenty for mist intensity), SPI from 2.7–5.5 V logic (3.3 V ESP32 is fine), VA/VB analog terminals rated to VDD so safe at 5 V on the Raydrop's control rail, active product line (not discontinued). The `MCP41010/41050/41100` series is an older equivalent — only fall back to those if a 4131 variant is backordered at checkout.

## Adafruit (one order, ~$20)

| Qty | Part | SKU | Price | URL |
|---|---|---|---|---|
| 1 | MCP4725 12-bit DAC breakout (I²C) | **#935** | $4.95 | [Adafruit](https://www.adafruit.com/product/935) |
| 1 | BSS138 4-channel bidirectional level shifter | **#757** | $3.95 | [Adafruit](https://www.adafruit.com/product/757) |
| 1 | 0.1" male header pin strip — 36-pin × 10 | **#392** | $4.95 | [Adafruit](https://www.adafruit.com/product/392) |
| 1 | Premium M/M jumper wire bundle (20× 6") | **#1957** | $1.95 | [Adafruit](https://www.adafruit.com/product/1957) |
| 1 | Premium M/F jumper wire bundle (20× 6") | **#1954** | $1.95 | [Adafruit](https://www.adafruit.com/product/1954) |

- **MCP4725 DAC** is the Scenario-A fallback: if the Raydrop's pot is feeding an ADC that expects an absolute voltage (not a ratiometric divider), use the DAC instead of a digipot. Adafruit library support is mature.
- **BSS138 level shifter**: defense in depth. ESP32-C3 is 3.3 V only, not 5 V-tolerant. If the Raydrop's control side turns out to be 5 V, this sits between them. Cheap insurance.
- **Jumpers / headers**: supplement whatever's left from the fan-controller build. Skip if the existing stash has spare.

## Amazon (next-day, ~$30–50)

| Qty | Item | ASIN / search | ~Price | Notes |
|---|---|---|---|---|
| 1 | Raydrop KC-RD03A humidifier (spare) | [B0CDL8XCJ5](https://www.amazon.com/dp/B0CDL8XCJ5) | $19.99 | 1.0 L model per the [KC-RD03A manual](https://manuals.plus/raydrop/kc-rd03a-cool-mist-humidifiers-manual). The wiki's "Raydrop 4L" reference may not match this SKU exactly — verify the model number on your current unit (bottom-plate sticker) before ordering the spare so both units have the same driver circuit. |
| 1 | E12 through-hole resistor assortment (1/4 W, 10 Ω–1 MΩ) | search `E12 resistor kit 1/4W` | ~$10 | Covers RC filter values + pull-ups. Generic kits from EEE-TEE / ELEGOO / ELPA are fine. |
| 1 | Ceramic + electrolytic cap kit (0.1 µF–10 µF assortment) | search `ceramic capacitor kit` | ~$10 | For the Scenario-B RC filter. 10 kΩ + 1 µF (≈16 Hz cutoff) is the default starting point; have 10 µF on hand in case PWM turns out to be <100 Hz. |
| 1 | Heat-shrink tubing assortment | search `heat shrink tubing kit` | ~$8 | Insulate pigtails going back into the Raydrop case. |

## Order strategy

**Scenario coverage at ~$70–80 total:**

- **DigiKey** (~$11 with ground shipping, 2–3 day transit): the three MCP4131 variants. Covers Scenario A for any of the three common pot resistances.
- **Adafruit** (~$20 + ~$10 shipping): DAC breakout + level shifter + headers/jumpers. Covers Scenario A fallback (DAC) and the 5 V bridging case.
- **Amazon** (~$40–50, next-day): Raydrop spare + passives + heat-shrink. Covers Scenario B (RC filter parts), build prep, and the magic-smoke insurance policy.

Scenario B (direct ESP32 PWM through RC filter) needs only the Amazon passives and existing jumper wire — no specialty IC. So if Phase 1 reveals PWM, the DigiKey digipots and the Adafruit DAC sit on the shelf for a future project.

## What to skip for now

- **Optoisolator breakout.** Ultrasonic humidifiers keep the mains-side isolated from the low-voltage control board; opto isolation is belt-and-suspenders. Only order if Phase 1 finds mains-referenced voltages on the pot (which would be surprising).
- **Proto-PCB / perf board.** Breadboarding is fine until the PI loop is tuned. Move to a perma-proto only if the final circuit is going back inside the Raydrop case.
- **Oscilloscope.** Logic analyzer + multimeter cover every likely case. See [phase1-probe-checklist.md](phase1-probe-checklist.md).

## Caveats

- **Stock at click-time.** Verify each SKU is in stock when you place the order. The MCP4131 family is long-established and active but chip-availability oscillates.
- **Raydrop model confirmation.** The wiki's historical "Raydrop 4L" descriptor may not match the `KC-RD03A` model number (which is a 1.0 L unit per the manual). **Check the sticker on the bottom of your current unit and order a spare of the same model** — the electronics inside will be similar across sizes but the driver IC may differ enough that Phase 1 findings don't transfer.
