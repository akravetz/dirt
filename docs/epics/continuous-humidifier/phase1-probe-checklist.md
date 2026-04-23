# Raydrop KC-RD03A — Phase 1 Probe Checklist

Walkthrough for the open-up-and-characterize session that gates this epic (see [README.md](README.md) alongside). Final findings land in the [decision doc](../../../wiki/decisions/2026-04-23-raydrop-mcu-mist-control.md) as a revision block. Photos + LA capture files go to `debug/raydrop-re/` (gitignored scratch) — only this checklist and the recorded verdict are tracked.

**Goal:** identify whether the intensity potentiometer's output is DC voltage, PWM, or encoded comms — enough information to pick the Phase 2 replacement (digipot vs ESP32 PWM vs something else). **Stop gate:** if the circuit is outside these three cases, update the decision doc and reassess before proceeding.

## Prerequisites

- Spare Raydrop KC-RD03A on the shelf (this probe session risks the unit — $40 insurance).
- Multimeter with DC volts range.
- HiLetgo USB Logic Analyzer (FX2 8-channel, 24 MHz). Same one used for the fan-PWM RE — `debug/fan-pwm/` is the reference workflow.
- sigrok-cli + PulseView installed (already on `homebox` from the fan work).
- Something to take photos with — the PCB layout + chip markings go in this directory.
- Philips + small flathead screwdriver set. A guitar pick or plastic spudger for clamshell prying.

## Safety

- **UNPLUG THE RAYDROP BEFORE OPENING.** No exceptions. The driver board steps up to drive the piezo — high-impedance spikes are present even with the unit "off."
- **Drain the tank and dry the base** before inverting. Water + open electronics do not mix.
- When you re-energize for probing, plug into a **wall strip that's easy to cut**, not through the Kasa plug — we don't want the existing VPD loop flipping power state mid-probe. Better: temporarily disable the humidifier loop (`systemctl --user stop dirt-hwd`) while probing, and bring it back when done.
- **Share the Raydrop's GND with the LA's GND** as your first connection every time. Floating-ground probes give noise or worse.
- Don't probe near the transformer / large inductor on the driver side of the board.

## Step 0 — Disassembly + photography

1. Unplug. Drain tank. Wipe base dry.
2. Invert and remove the base screws (usually 4, hidden under rubber feet — peel a foot with the spudger).
3. Separate the clamshell gently. There's often a ribbon cable between halves; don't yank it.
4. **Photograph:**
   - Full PCB top-down, in focus, centered.
   - Close-up of the ultrasonic driver IC with readable markings (rotate under a desk lamp if needed).
   - Close-up of the intensity potentiometer from above — you need to see its 3 pins and any printed value (e.g. "103" = 10 kΩ, "503" = 50 kΩ, "104" = 100 kΩ).
   - Any other ICs on the board with chip markings.
5. Save photos to this directory (`debug/raydrop-re/photos/`) named `board-top.jpg`, `driver-ic.jpg`, `pot.jpg`, etc.
6. Note the pot value (resistance code) in the observations log at the bottom of this file.

## Step 1 — Multimeter DC sweep (should answer the question in 2 minutes)

With the unit **unplugged**, identify the pot's 3 pins:

- Most pots: outer two pins = the full resistive track; middle pin = wiper.
- Look on the back of the PCB for the pot's silkscreen designator and any exposed test points.

Now **plug the Raydrop in** (direct wall, not through Kasa). Turn the unit ON. Set the intensity knob to minimum.

Probe sequence (all measurements vs a known GND — use a black-wire ground clip to a large ground plane or the barrel jack's shield; verify it's actually GND with the DMM first):

| Pin | Expected | Action |
|---|---|---|
| Outer A | Either 0 V (= GND) or Vref (constant, e.g. 3.3 / 5 / 9 V). | Note the voltage. |
| Outer B | The other of {GND, Vref}. | Note the voltage. |
| Wiper (middle) | Somewhere between the two outers. | Note the voltage at min-knob. |

Now **sweep the knob slowly end-to-end** while watching the wiper pin:

- **Smoothly varying 0 → Vref → 0 (or 0 → Vref)** = **DC analog**. **Stop here.** Record the Vref value and the pot resistance. Proceed to Phase 2 with a digipot matched to Vref and pot value (MCP4131 drop-in for 10 kΩ, MCP41050 for 50 kΩ, MCP41100 for 100 kΩ).
- **Bouncing or averaging to some mid-value that doesn't change smoothly** = **probably PWM fed through an RC**. Proceed to Step 2.
- **Stuck at one value regardless of knob position** = something wrong with probe placement, or the pot isn't what's setting intensity (maybe it's behind a microcontroller that reads the pot via ADC and then commands via PWM/SPI — rare on this class of unit, but note it and proceed to Step 2 to look for activity on nearby pins).

Record results in the observations log at the bottom.

## Step 2 — Logic analyzer on the wiper (only if Step 1 was inconclusive)

Turn the Raydrop OFF before clipping. Connect:

- LA GND → Raydrop GND (established in Step 1).
- LA D0 → pot wiper.
- (Optional) LA D1 → outer A, D2 → outer B — these probably won't show activity but rule them out.

Turn Raydrop back ON, knob at a fixed middle position.

```bash
# From the repo root, with the LA plugged in:
cd debug/raydrop-re
sigrok-cli --driver fx2lafw --config samplerate=4m \
  --channels D0,D1,D2 \
  --samples 4000000 \
  --output-file pot-middle.sr
```

That's 4 MHz sample rate × 4 M samples = 1-second capture. Then repeat with the knob at min and max:

```bash
# knob at min
sigrok-cli ... --output-file pot-min.sr
# knob at max
sigrok-cli ... --output-file pot-max.sr
```

Open each in PulseView. Expected outcomes:

- **Edges visible, regular PWM pattern, duty cycle changes with knob** = **PWM case.** Note: frequency, duty-cycle range across knob sweep. **Stop here.** Proceed to Phase 2 with direct ESP32 PWM driving the same line (via LEDC — mirrors the fan driver exactly, `firmware/fan_controller` has the pattern).
- **No edges, stays HIGH or LOW regardless** = signal is DC but the multimeter read was misleading. Re-probe with DMM, maybe averaging a cleaner signal. Not a PWM case.
- **Regular edges but not obviously duty-modulated** = could be an oscillator whose *frequency* sets intensity, or encoded digital comms. Drop a note in the observations log and flag for further probing.

## Step 3 — Identify the driver IC

Read the chip markings (from the Step 0 photo if needed). Search:

- [LCSC](https://www.lcsc.com/) part search
- [OctoPart](https://octopart.com/)
- [Google "<part number> datasheet"](https://www.google.com/search?q=ultrasonic+humidifier+driver+datasheet)

Common ultrasonic driver ICs for sub-$50 units: **CS1710**, **HY2201**, **NE555 timer** (sometimes drives a transformer directly), **LMC555**, or a generic Chinese clone. Datasheet gives the intensity-input pin name (e.g. DUTY, CV, FREQ_ADJ) and confirms whether it expects DC voltage or PWM.

Write the IC part number to the observations log.

## Observations log (fill in during the session)

```
Date: _____________
Duration (min): _____________

=== Board photos ===
[list file names]

=== Pot identification ===
Silkscreen designator:  _____________
Resistance code on body: _____________   (e.g. "103" = 10 kΩ)
3-pin orientation:       _____________
Outer A measured:        _____ V
Outer B measured:        _____ V
Wiper @ min knob:        _____ V
Wiper @ mid knob:        _____ V
Wiper @ max knob:        _____ V
Sweep behavior:          [smoothly varying / bouncing / stuck / other]

=== Verdict (Step 1) ===
[ ] DC analog     — Vref = _____ V,  pot = _____ Ω  → digipot MCP41xxx
[ ] PWM suspected — proceed to Step 2
[ ] Stuck / weird — proceed to Step 2 for nearby-pin survey

=== Logic analyzer (if Step 2 ran) ===
Capture files:           [pot-min.sr, pot-mid.sr, pot-max.sr, ...]
Carrier frequency:       _____ Hz
Duty cycle @ min knob:   _____ %
Duty cycle @ mid knob:   _____ %
Duty cycle @ max knob:   _____ %

=== Verdict (Step 2) ===
[ ] PWM — direct ESP32 LEDC drive at _____ Hz
[ ] DC  — re-probe with DMM; use digipot
[ ] Encoded comms — reverse-engineer separately

=== Driver IC ===
Markings:                _____________
Datasheet URL:           _____________
Intensity input pin:     _____________
Expected signal:         [DC / PWM / other]

=== Phase 2 recommendation ===
[ ] Digipot MCP4131/MCP41050/MCP41100 on SPI (DC replacement)
[ ] ESP32 GPIO direct PWM via LEDC (PWM replacement)
[ ] Other: _____________

=== Follow-ups / gotchas ===
[notes]
```

After filling this in, paste the verdict into the [decision doc](../../../wiki/decisions/2026-04-23-raydrop-mcu-mist-control.md) as a "Phase 1 findings" revision block, and the epic can move from "planning" to "in-progress." `debug/raydrop-re/` stays as scratch for photos + `.sr` capture files — gitignored by design per `CLAUDE.md` (`debug/` is the agent sandbox).
