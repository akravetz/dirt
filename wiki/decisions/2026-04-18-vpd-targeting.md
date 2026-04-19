---
title: "Humidifier Control Targets VPD, Not Fixed RH (stage-dynamic)"
type: decision
sources: []
related: [wiki/hardware/humidifier-control.md, wiki/environment/humidity.md, wiki/concepts/vpd.md, wiki/decisions/2026-04-17-humidifier-kasa-ep10.md]
created: 2026-04-18
updated: 2026-04-18
---

# Decision: VPD-Targeted Humidifier Control (stage-dynamic)

**Date:** 2026-04-18
**Status:** Accepted
**Supersedes (control-logic portion only):** [2026-04-17 Kasa EP10 decision](2026-04-17-humidifier-kasa-ep10.md) — hardware, actuator, and safety guards carry over unchanged; only the setpoint definition changes.

## Context

The closed-loop humidifier deployed 2026-04-18 targeted a fixed 60% RH with a ±3% deadband. First full day of operation surfaced the problem:

- Day period (lights on, tent ~75°F): RH ~59%, VPD ~1.3 kPa — healthy veg.
- Overnight (lights off, tent ~63°F): RH ~77%, VPD **0.46 kPa** — seedling range; damping-off territory.

Root cause: VPD is a function of temperature *and* RH. Holding a constant RH across a day/night temperature swing produces a very different VPD morning vs. overnight. At the same 60% RH, 75°F gives ~1.2 kPa; 63°F gives ~0.76 kPa. Under a strict fixed-RH loop the humidifier keeps topping off through a cool night, driving VPD well below the plant's comfort band.

Separately, the controller's hardcoded 60% setpoint was veg-specific. Phase-appropriate RH shifts as the grow progresses (flower wants drier air for bud density / mold prevention), so a single number couldn't serve the whole grow either.

## Decision

Control the humidifier against **VPD**, not RH, and pull the target band from **stage-dynamic lookups** stored in `dirt.services.grow_state.STAGE_TARGETS`:

| Stage | VPD band (kPa) | Upper edge |
|---|---|---|
| `veg` | 0.8 – 1.2 | 1.2 |
| `flower_early` (days 0–20 of 12/12) | 1.0 – 1.3 | 1.3 |
| `flower_late` (day 21+ of 12/12) | 1.2 – 1.5 | 1.5 |

The humidifier is a single-direction actuator (adds moisture → drops VPD). Targeting the upper edge with a 0.1 kPa deadband matches that asymmetry: kick on when VPD climbs past the band's dry edge, kick off once it falls back below by the deadband. Nothing to do when VPD is already in or below the band.

The DB singleton `grow_state` holds `germination_date` and `flower_start_date`; the flower-start flip drives the `flower_early` / `flower_late` transition without a service restart. Stage targets themselves live in code (hardcoded horticultural constants — change rarely and via PR), while grow identity lives in DB (user-mutable via the future UI).

## Control Logic

```
loop every ~30s:
    lo, hi = current_targets()["vpd_kpa"]   # stage-dynamic
    turn_on_above  = hi
    turn_off_below = hi - 0.1               # vpd_deadband_kpa
    # ... + stale-sensor failsafe, min-off, max-on guards from 2026-04-17
```

Full pseudocode and logging contract: [hardware/humidifier-control.md](../hardware/humidifier-control.md).

## Consequences

- **Day/night swing handled for free.** As tent temperature falls at night, VPD drops on its own and the loop naturally stops running — no schedule, no lights-on/lights-off branch in the controller.
- **Phase transitions are automatic.** Setting `grow_state.flower_start_date` via the future UI shifts the setpoint on the next poll.
- **Source of truth unified.** Claudia's voice status tool (`src/dirt/tools/sensors.py`) reads the same `STAGE_TARGETS` dict, so "out of range" flagging and humidifier control stay in lockstep.
- **RH-based settings retired.** `humidity_target_pct` and `humidity_deadband_pct` removed from config; replaced by `vpd_deadband_kpa = 0.1`. All hardware/safety settings from 2026-04-17 (min-off 90s, max-on 20 min, stale-sensor 5 min) unchanged.
- **Ripening tail not yet modeled.** Some flower guides push VPD toward 1.5–1.6 and RH to 35–40% in the final ~2 weeks; current `flower_late` band stops at 1.5. Revisit if late-flower runs ever land consistently below the band in 2026.

## Not in Scope

- Dehumidifier actuator — we still can't push VPD *up* when it drifts too low. Logged as observability only.
- Temperature control — tent heater / AC remain on the roadmap; the voice status tool flags out-of-band temperature, but the humidifier loop is purely VPD.
- Historical preservation — flipping back from flower to veg overwrites `flower_start_date` rather than keeping history. V1 tradeoff; event-log promotion is cheap later if needed.
