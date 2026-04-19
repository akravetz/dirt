---
title: "Lights-Off-Aware Humidifier Control (feedforward on lights schedule)"
type: decision
sources: [var/logs/humidifier/2026-04-19.jsonl]
related: [wiki/hardware/humidifier-control.md, wiki/decisions/2026-04-19-drop-humidifier-safety-timers.md, wiki/decisions/2026-04-18-vpd-targeting.md, wiki/concepts/vpd.md]
created: 2026-04-19
updated: 2026-04-19
---

# Decision: Lights-Off-Aware Humidifier Control

**Date:** 2026-04-19
**Status:** Accepted
**Amends:** [2026-04-18 VPD-targeting decision](2026-04-18-vpd-targeting.md) — adds a schedule-driven feedforward path; setpoint definition unchanged.

## Context

After the [2026-04-18 switch to VPD targeting](2026-04-18-vpd-targeting.md), the first full day's observation (2026-04-18 night → 2026-04-19 morning) showed a systematic VPD collapse from ~11:00 pm local onward: VPD fell from 1.31 kPa to 0.64 kPa over ~80 min while RH climbed from 56% to 72%. The humidifier shut off correctly (at VPD 0.97), but VPD kept falling *after* shutoff — driven almost entirely by the tent cooling 75 → 67 °F as lights went off, which dropped saturation vapor pressure ~25%.

Three candidate fixes were weighed:

1. **Derivative (PD) control.** Use `dVPD/dt` to suppress turn-on during fast drops. Rejected: the disturbance is *scheduled and periodic* (same event at 23:00 local every day), which is the regime where feedforward strictly dominates derivative feedback. D would have a ~5 min smoothing lag on DHT22 noise and near-unit SNR for the signals that matter. Using the clock is both cheaper and more accurate.
2. **Lights-off aware feedforward.** Two complementary rules ("A + B") — a pre-lights-off cutoff window and a shifted night band. Selected.
3. **Dehumidifier on a second EP10.** The only way to actively raise night VPD. Deferred to roadmap; handled entirely in software first.

Measured steady-state overshoot after a clean shutoff is ~0.004 kPa and ~15 seconds (see 2026-04-19 14:55 UTC trace), confirming that the nighttime "overshoot" is not a control-loop lag but the disturbance itself. No derivative estimator is needed for the observed symptom.

## Decision

Add lights-schedule feedforward to the humidifier loop:

**A. Pre-lights-off prep window.** In the last `lights_off_prep_minutes` (default **30**) of lights-on, force the humidifier OFF regardless of VPD. Prevents dosing mist into air that's about to cool and crash VPD into damping-off territory.

**B. Lights-off band offset.** During the dark period, subtract `vpd_lights_off_offset_kpa` (default **−0.3 kPa**) from the stage's day band. The humidifier can't raise night VPD (single-direction actuator), so the offset lets the loop rest rather than chase a setpoint it can't hit. Preserves deadband width.

### Resulting bands

| Stage | Day band | Night band (offset −0.3) |
|---|---|---|
| veg | 0.8 – 1.2 | 0.5 – 0.9 |
| flower_early | 1.0 – 1.3 | 0.7 – 1.0 |
| flower_late | 1.2 – 1.5 | 0.9 – 1.2 |

Each night band sits inside the published industry range for dark-period VPD (0.2–0.4 kPa below day; School 1 per Pulse Grow, GrowSensor, Anden). The more conservative "day = night" school (ScynceLED, Gorilla Grow Tent) is **unreachable** without a dehumidifier — deferred.

### Schedule source

Lights times live on `growstate`: `lights_on_local` and `lights_off_local`, stored as tent-local `TIME` (`America/Denver`). User-mutable via SQL for V1; future UI. Timezone constant (`TENT_TZ`) lives in code — it's a physical property of the grow-space location, not a per-grow decision.

Default schedule seeded for this grow:

- `lights_on_local = 05:00`
- `lights_off_local = 23:00`

Matches standard **veg 18/6**. Flower flip (12/12) requires a manual UPDATE to `lights_on_local = 11:00` alongside setting `flower_start_date`.

### Migration

`growstate` existed pre-decision with germination + flower dates. Both columns added via idempotent `ALTER TABLE ADD COLUMN ... DEFAULT` executed in `init_db()` after `SQLModel.metadata.create_all`. Existing row auto-populated with the defaults; fresh installs get them from the model's `Field(default=...)`.

## Control Logic

Full pseudocode in [hardware/humidifier-control.md](../hardware/humidifier-control.md). Summary:

```
offset = 0 if lights.on else night_offset
turn_on_above  = hi_day + offset
turn_off_below = hi_day + offset - deadband
in_prep_window = lights.on and lights.minutes_until_off < prep_minutes

if stale_sensor:     off
elif in_prep_window: off                  # A
elif vpd > turn_on:  on                   # deadband-terminated
elif vpd < turn_off: off                  # B via shifted setpoint
```

## Consequences

- **Night-time VPD collapse is absorbed, not fought.** The loop rests in the −0.3 band instead of cycling against impossible setpoints.
- **Pre-lights-off mist dosing eliminated.** A turn-on at 22:30 no longer adds moisture that becomes overshoot at 23:15.
- **Schedule is data, not code.** DB-backed so future UI edits or stage flips propagate on the next poll without a restart or redeploy.
- **New state-change reason: `lights_off_prep`.** Observability events now include `lights_on`, `minutes_until_off`, `band_offset_kpa` so logs fully determine which rule fired.
- **Derivative control is off the roadmap** for this loop. Remaining unpredictable disturbances (door opens, HVAC kicks) are smaller-amplitude and self-correcting within the deadband.

## Not in Scope

- **Dehumidifier actuator.** Needed to reach "day = night" VPD (School 2 guidance). Deferred to roadmap.
- **C. Pre-lights-off *dry-up* window** (lift the upper edge for the last hour of lights-on). Rejected — A already prevents the cause, and C would deliberately stress plants during peak photosynthesis.
- **Per-stage prep windows / offsets.** One global value each until data argues otherwise.
- **Schedule per day-of-week** (e.g. staggered for perpetual harvest). Not relevant to this grow.
