---
title: "Lights-Off-Aware Humidifier Control (feedforward on lights schedule)"
type: decision
sources: [var/logs/humidifier/2026-04-19.jsonl]
related: [wiki/hardware/humidifier-control.md, wiki/decisions/2026-04-19-drop-humidifier-safety-timers.md, wiki/decisions/2026-04-18-vpd-targeting.md, wiki/concepts/vpd.md]
created: 2026-04-19
updated: 2026-04-27
---

# Decision: Lights-Off-Aware Humidifier Control

**Date:** 2026-04-19
**Status:** Accepted (prep window tightened 30 → 5 min on 2026-04-27 — see [Update](#2026-04-27-update-prep-window-tightened-to-5-min) below)
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

## 2026-04-27 update — prep window tightened to 5 min

Eight days of operation under the original 30-min prep window (and after the [2026-04-26 pivot](2026-04-26-govee-humidifier-pivot.md) from the Raydrop to a Govee H7142) showed the margin was overspec'd. Two consecutive nights (2026-04-25, 2026-04-26) of minute-resolution `sensorreading` data around 22:15–23:30 MDT:

| t (rel to lights-off) | RH | VPD | source |
|---|---|---|---|
| −30 min (humidifier OFF, was ON) | 63% | 0.99 kPa | last "wet" reading before prep window |
| −25 min (5 min into prep) | 43% | 1.58 kPa | RH already past dry edge |
| −20 to 0 min | 42–46% | 1.55–1.65 kPa | sits well above veg upper band (1.2) |
| 0 min (lights off) | 45% | 1.54 kPa | thermal crash starts |
| +14 min (deep dark) | 52% | 1.25 kPa | back inside veg band |

Findings:

- **No residual ultrasonic rise.** RH dropped monotonically the moment the plug opened — the original "absorb residual air-mass rise" justification (written for the Raydrop, [hardware/humidifier-control.md](../hardware/humidifier-control.md)) doesn't apply to the H7142. Observed clearance: **5 min from 63% → 43% RH** (a 4 pp/min initial slope).
- **Cost was real and daily.** VPD sat at 1.55–1.65 kPa for ~25 min before lights-off — ~0.4 kPa above the veg upper band (1.2). Plants experienced 25 min/day of avoidable end-of-photoperiod stress.
- **Dew-point margin is plentiful.** Throughout the prep window dew point was 50–55°F vs ambient 70–75°F — ~20°F gap. Even letting RH stay at 63% into lights-off would still leave a ~10°F condensation margin. No mold/condensation risk identified.

**Decision:** lower `lights_off_prep_minutes` default from 30 → 5 (in `apps/shared/src/dirt_shared/config.py`). 5 min sized to one tent-fan-volume turnover so the humidifier isn't actively misting at the lights transition — the actual physical concern, vs. the discredited residual-mist argument. Same value applies symmetrically pre-lights-on (the loop now resumes at 04:55 instead of 04:30).

**Not changed:** rule A's *existence* (still want a buffer before lights-off), rule B (−0.3 kPa night offset), the schedule source on `growstate`, the observability events (`lights_off_prep` reason, `minutes_until_off` field). The cutoff just fires later in the photoperiod now.

**Next-night verification:** check `var/logs/humidifier/` and minute-binned tent VPD for 2026-04-27 22:55 → 23:30 — expect VPD to peak ~1.55 kPa for ~5 min (vs. ~25 min previously) and to fall back inside the veg band by ~23:15 as before. If a humidifier cycle ends *during* the 22:55 → 23:00 window with RH > 65%, the 5-min margin is too tight and we walk it back to ~10 min — bias should be toward "let air clear" if data disagrees.
