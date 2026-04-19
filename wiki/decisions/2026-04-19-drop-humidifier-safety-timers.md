---
title: "Drop Humidifier Max-On and Min-Off Timers"
type: decision
sources: [var/logs/humidifier/2026-04-19.jsonl]
related: [wiki/hardware/humidifier-control.md, wiki/decisions/2026-04-18-vpd-targeting.md, wiki/decisions/2026-04-17-humidifier-kasa-ep10.md]
created: 2026-04-19
updated: 2026-04-19
---

# Decision: Drop `humidifier_max_on_seconds` and `humidifier_min_off_seconds`

**Date:** 2026-04-19
**Status:** Accepted
**Amends:** [2026-04-17 Kasa EP10 decision](2026-04-17-humidifier-kasa-ep10.md) — removes two of the three safety guards established there; stale-sensor failsafe is retained.

## Context

First full day of VPD-targeted control (see [2026-04-18](2026-04-18-vpd-targeting.md)) produced a pathological pattern under high-VPD load, visible in `var/logs/humidifier/2026-04-19.jsonl` from 13:34 UTC onward:

| UTC | Event | VPD kPa | Reason |
|---|---|---|---|
| 13:34 | on | 2.24 | `vpd_above_upper_band` |
| 13:54 | off | 1.65 | `max_on_timeout` |
| 13:56 | on | 1.64 | `vpd_above_upper_band` |
| 14:16 | off | 1.36 | `max_on_timeout` |
| 14:17 | on | 1.61 | `vpd_above_upper_band` |
| 14:37 | off | 1.22 | `max_on_timeout` |
| 14:39 | on | 1.23 | `vpd_above_upper_band` |
| 14:55 | off | 1.09 | `vpd_below_upper_band` |

Four consecutive on-phases terminated on the 20-minute `max_on_timeout` safety, not on the hysteresis deadband. The 90-second `min_off` was too short for VPD to recover meaningfully, so the loop immediately re-armed and repeated. Net effect:

- `max_on` became the *primary* termination criterion, displacing the deadband as the actual setpoint. The tuned value (`hi - deadband = 1.1 kPa`) was never reached — effective setpoint was "whatever VPD is 20 min after turn-on under current load," which is non-deterministic.
- Relay cycle budget burned ~3× faster than the hysteresis design intended (multiple on/off transitions per hour instead of one long run per saturation cycle).
- Log noise: safety trips and control decisions were indistinguishable in the JSONL stream.
- Masked the real diagnosis: "humidifier is out of authority for current conditions" (knob setting, exhaust rate, or reservoir draw) looked like normal cycling.

## Decision

Remove both guards from `apps/hwd/src/dirt_hwd/services/humidifier.py` and from `apps/shared/src/dirt_shared/config.py`:

- `humidifier_max_on_seconds` — deleted.
- `humidifier_min_off_seconds` — deleted.

Keep `humidifier_failsafe_stale_seconds = 300` (stale-sensor → force OFF). That's the only remaining safety.

The `min_off` guard was redundant with the deadband: hysteresis already prevents chatter because the turn-on and turn-off edges are 0.1 kPa apart. VPD doesn't swing 0.1 kPa in <90s under normal conditions, so `min_off` never fired during control, only during `max_on` oscillation.

## Why this is safe without a max-on

The Raydrop 4L has its own built-in low-water cutoff. A stuck-high VPD reading that pins the humidifier on eventually drains the reservoir (a few hours at the current ~50% knob setting), and the humidifier's internal safety stops producing mist. The EP10 stays closed, but mist output goes to zero — functionally equivalent to the max-on trip, just self-limited by physics instead of a timer.

Relay cycle count is dominated by the *number* of on/off transitions, not continuous-on duration. Removing these timers *reduces* cycles, not increases them.

## Consequences

- **Setpoint is now actually the setpoint.** On-phases terminate at `hi - 0.1 kPa`, deterministic across tent load.
- **Fewer relay cycles.** Single long on-phase per saturation cycle, as the hysteresis design originally intended.
- **Cleaner log stream.** State-change reasons reduce to `vpd_above_upper_band`, `vpd_below_upper_band`, `failsafe_stale_sensor`.
- **"Out of authority" failures now surface as long continuous-on periods** (hours) rather than a machine-gun of safety trips. If this is observed, the right response is a mechanical intervention (knob up, reduce exhaust, refill reservoir), not a controller tune.
- **No shared-code impact.** No tests referenced the removed settings; no env / systemd overrides existed.

## Not in Scope

- Adding an "out of authority" alert (continuous on > N minutes → warning) — deferred; current log cadence is already a decent signal if you look.
- Revisiting deadband width — 0.1 kPa remains appropriate given DHT22 noise floor.
- Any change to the stale-sensor failsafe.
