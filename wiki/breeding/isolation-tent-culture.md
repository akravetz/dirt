---
title: Isolation Tent Culture — Pots, Watering, Drip Assist
type: breeding
sources: []
related: [wiki/breeding/isolation.md, wiki/breeding/bill-of-materials.md, wiki/breeding/male-evaluation.md, wiki/breeding/cross-procedure.md, wiki/breeding/cloning.md]
created: 2026-05-02
updated: 2026-05-16
---

# Isolation Tent Culture

This page covers how to grow and water plants inside the 2x2 isolation tent. Pollen containment, hygiene, and room phases live in [isolation.md](isolation.md).

The 2x2 is a containment and pollination space, not a production tent. Keep water management simple, removable, and easy to clean.

## Default potting

- **Males:** 1-gal fabric pots, coco/perlite, hand-watered.
- **Seed mother / keeper clone:** 2-gal fabric pot, coco/perlite, hand-watered.
- **Runoff control:** individual saucers or one shallow boot tray under pots; remove standing runoff.
- **Automation:** hand-water first. If upgrading, use the removable drip-assist setup below rather than a recirculating or flood system.

Why:

- 1-gal males have enough root volume for evaluation and pollen production without crowding the 2x2.
- 0.5-gal male pots would work for very short runs, but dry too quickly in coco/fabric and add watering risk.
- 2-gal seed mothers have more buffer through the 6-8 week seed-maturation window without turning the tent into a yield-focused grow.
- Coco/perlite keeps active breeding plants on the same nutrient language as the main grow.
- No flood table or recirculating system means fewer parts to clean after pollen work.

Soil is reserved for clone stasis on the separate shelf, not active male/seed production in the isolation tent.

## Drip-Assist Upgrade

If hand-watering becomes annoying, the first automation step is a simple drain-to-waste top-drip assist:

```text
5 gal reservoir
-> Sicce Syncra Silent 1.5 submersible pump
-> 1/2 inch main line
-> inline filter
-> tee with bypass valve returning excess flow to reservoir
-> Rain Bird free-flow 6-port manifold
-> six equal-length 1/4 inch lines
-> inline valve per plant
-> open stake or simple halo at each pot
```

Use the **free-flow** manifold, not fixed 2 GPH ports. Free-flow matches a low-pressure submersible pump better, while inline valves and measuring-cup calibration handle balancing. The Syncra Silent 1.5 is expected to be sufficient for this job because it is roughly 357-358 GPH with about 6 ft maximum head; it is still not a pressure-compensating irrigation pump.

Required safeguards:

- keep the system removable and easy to sanitize
- use equal-length 1/4 inch lines from manifold to pots
- add a bypass return so the pump is not forced entirely through tiny lines
- add an anti-siphon hole or keep the reservoir below drip outlets
- catch runoff in saucers or a boot tray and remove standing runoff
- calibrate every line into measuring cups before feeding plants

Initial calibration: test 5, 10, and 20 second pulses, measure each outlet, adjust the bypass and inline valves, then connect to pots. Recheck output after any nutrient change or line cleaning.

## Pump Control

Permanent control target: **Shelly Plus Plug US** controlling the Sicce pump from an existing outlet, with `dirt-hwd` owning irrigation schedules and issuing short pump pulses. The important safety requirement is device-side auto-off: the command should turn the plug on with an auto-off duration in seconds, so a service crash or missed follow-up command does not leave the pump running.

Temporary test controller: an existing **Kasa EP10** may be used for supervised calibration and first-water tests while the Shelly plug is in transit. Do not leave Kasa-driven irrigation unattended unless a separate physical or device-side shutoff is in place; the Kasa path depends on the controlling service or operator sending the off command.

Operating rules:

- plug the pump controller into a GFCI-protected outlet or GFCI power strip
- keep the smart plug outside the splash zone and above reservoir height when practical
- add a drip loop on the pump cord before it reaches the plug
- default to missed irrigation over continuous pumping; fail-off is safer than fail-on
- first real pulses stay supervised until measured output, runoff capture, and leak alarms are proven
