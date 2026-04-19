---
title: "Multi-Actuator Tent Environment Control — Design Principles (future work)"
type: concept
sources: []
related: [wiki/hardware/humidifier-control.md, wiki/decisions/2026-04-19-lights-off-aware-humidifier.md, wiki/decisions/2026-04-18-vpd-targeting.md, wiki/concepts/vpd.md]
created: 2026-04-19
updated: 2026-04-19
---

# Multi-Actuator Tent Environment Control

**Status: design notes, not yet implemented.** Captured 2026-04-19 before the dehumidifier and PWM exhaust fan arrive. Revisit when both actuators are provisioned.

## What changes

Current loop is SISO — one actuator (Raydrop humidifier), one output (VPD). Targets the upper-band edge; can only push VPD down. See [hardware/humidifier-control.md](../hardware/humidifier-control.md).

Planned additions:
- **Dehumidifier on a second Kasa EP10** — bidirectional humidity control becomes possible (we can push VPD up at night too).
- **PWM exhaust fan** — modulated airflow instead of fixed speed. Primary authority: temperature. Secondary authority: humidity (coupled via air exchange).

Now we have three actuators and two physical outputs (T, RH), with the fan affecting both. This is a **MIMO system with interaction**, and it's where reaching for the wrong control paradigm can do real damage.

## Principle 1: Target outputs directly, not their scalar summary

VPD is a projection of (T, RH) into one number. Two different (T, RH) pairs can give the same VPD and be very different plant experiences — 85 °F / 40% RH and 75 °F / 55% RH both ≈ 1.2 kPa, but the first stresses plants via leaf temperature.

With bidirectional humidity control + temperature control, the setpoint should become a **2D region in (T, RH) space**. `STAGE_TARGETS` (in `dirt_shared.services.grow_state`) already has bands for all three metrics — we just aren't enforcing temp or RH yet. Enforce all three; think of the target as "stay inside this polygon" rather than "track this scalar."

## Principle 2: Actuator-output mapping by dominant authority

Assign each actuator to its strongest-effect output. Treat side effects as disturbances the other loops absorb.

| Output | Primary actuator | Direction | Notable side effect |
|---|---|---|---|
| Temperature | Fan (PWM) | ↑ fan = ↓ T | Also ↓ RH (usually — depends on room RH) |
| Humidity ↓ | Dehumidifier | ↓ RH | Slight ↑ T (condenser waste heat) |
| Humidity ↑ | Humidifier | ↑ RH | Slight ↓ T (evaporative cooling, small) |

Three things worth internalizing:

- **No heater.** Temperature is only controllable *downward* (via fan). Upward motion is a disturbance from lights. That's OK — the lights schedule is our "heater" and we know when it runs.
- **The fan couples into RH.** More fan → drier tent (room air is usually drier than tent air). Treat this as a *known-sign* disturbance to the humidity loop; most of the year it's beneficial on hot-humid days.
- **Dehumidifier puts out heat.** Extended runtime lifts T. The fan absorbs that — but flag it if fan duty rises in lockstep with dehumidifier runtime (diagnostic signal that one loop is fighting another).

## Principle 3: Hierarchy / cascade over true MIMO

Real HVAC systems almost universally use **cascaded SISO loops with priority** rather than LQR / MPC / matrix decoupling. Because:

- The actuator → output matrix is sparse.
- Plant physiology doesn't need tight tracking — it needs "stay inside the zone."
- Coupled MIMO controllers are hard to tune and much harder to diagnose when they misbehave.

Proposed hierarchy — one tick:

1. **Classify** tent state by (T, RH) relative to the stage zone: `in_zone`, `hot`, `cold`, `dry`, `humid`, `hot_humid`, `hot_dry`, `cold_humid`, `cold_dry`.
2. **Dispatch** per class. Each handler says "run actuator X at setting Y; leave others alone."
3. **Apply feedforward overrides** (lights-off prep, lights-on pre-ramp).

Per-class logic sketch:

- `hot_humid` — fan up (kills both problems). Dehumidifier only if fan alone isn't catching up.
- `hot_dry` — fan up (cool first). Humidifier *after* T is back in band. Raising RH into hot air risks damping-off when lights go off. T wins.
- `cold_humid` — dehumidifier on (waste heat helps). Fan down.
- `cold_dry` — nothing. No heater; wait for lights.
- `dry` — humidifier on.
- `humid` — dehumidifier on.
- `hot` / `cold` — fan only.
- `in_zone` — all actuators off except baseline fan floor.

Key invariant: **at most one net move per output per tick.** That's what keeps the loops decoupled without fancy math.

## Principle 4: Feedforward compounds

Predictable disturbances get compensated *before* they arrive. Derivative feedback is strictly dominated here because our dominant disturbance is scheduled (lights). See [decisions/2026-04-19-lights-off-aware-humidifier.md](../decisions/2026-04-19-lights-off-aware-humidifier.md) for the first iteration.

With bidirectional actuators, more feedforward moves become available:

- **Pre-lights-on fan ramp** — start bringing fan up 15 min before lights-on to pre-cool against the incoming heat load.
- **Pre-lights-off dehumidifier burst** — run dehumidifier for the last 30–45 min of lights-on. Pulls RH down so the thermal crash lands mid-band at night instead of bottom. Replaces today's passive "force humidifier off" rule with something *active*.
- **Post-lights-on fan floor** — fan minimum lifted during the first hour of lights-on (both T and RH ramping).

Each is a few lines once the schedule-aware plumbing is in place (which it already is — `lights_state()` in `grow_state.py`).

## Failure modes to design against

1. **Actuators fighting.** Humidifier and dehumidifier on simultaneously burns power and oscillates RH. Design constraint: single mutex. They can never both be on; explicit "both off" gap on state transitions.

2. **Dehumidifier saturation masquerading as an RH problem.** Dehumidifiers have reservoir tanks that fill. When full, they silently stop dehumidifying but keep drawing idle power. Read wattage via Kasa (should be ~300 W running, ~0 W saturated) and treat `plug_on AND wattage ≈ 0` as a reservoir-full alarm. Same pattern as the Raydrop's low-water cutoff.

3. **Fan noise floor.** Exhaust has a *minimum* duty cycle for fresh-air / CO2 refresh and to keep the carbon filter doing work. Control variable must be `baseline_fan_pwm + control_output`, clipped to `[baseline, max]`.

4. **Dehumidifier cycle limit.** Compressor-based dehumidifiers have minimum off-time requirements (~5 min) to let the refrigerant equalize. Unlike the humidifier relay, this is a hardware constraint we *should* respect. Don't drop the `min_off` idea entirely for the dehumidifier.

5. **Room-air coupling.** The fan's effect on tent RH depends on makeup-air RH. In a humid summer, "fan up" may *raise* tent RH. Worth a sanity check once we have a room DHT22 to compare against.

## Proposed implementation shape

A new service replacing `humidifier.py` — `apps/hwd/src/dirt_hwd/services/environment.py`:

```
loop every ~30s:
    T, RH, VPD = latest readings
    stage      = current_stage()
    lights     = lights_state()
    zone       = STAGE_TARGETS[stage]
    class_     = classify(T, RH, zone)

    plan       = DISPATCH[class_](T, RH, zone)   # dict: {fan_pwm, hum_on, dehum_on}
    plan       = apply_feedforward(plan, lights) # lights-off prep, pre-lights-on ramp
    plan       = enforce_invariants(plan)        # mutex, baseline fan, min_off

    commit(plan)                                 # atomic: all three actuators in one tick
    log_event("env_control", event="tick", class_=class_, **plan, ...)
```

Every class transition logged with full context; that log becomes the tuning signal. Look at:
- How often we land in each class.
- How long we spend there.
- Whether any class is ever entered (dead code = wrong classification logic).
- How often feedforward overrides fired.

Class boundaries and feedforward offsets become the knobs you adjust — not PID gains.

## When to implement

All of the above waits on hardware:

1. Dehumidifier procured, plugged into a second Kasa EP10 (requires DHCP reservation, firmware check for KLAP v2).
2. PWM fan control wired through the ESP32 or a dedicated driver.
3. Room DHT22 (for makeup-air context) — optional but nice.

Migration path from today's loop: keep `humidifier.py` running until `environment.py` is tested end-to-end. Don't partial-port. The value is in the unified state machine; half-implementation is worse than the current single-loop design.

## Explicitly out of scope

- **PID / LQR / MPC.** Discrete state-machine dispatch is sufficient.
- **Derivative estimation on VPD noise.** Rejected 2026-04-19 — feedforward on the known lights schedule strictly dominates.
- **Ripening-tail VPD targeting** (late flower 1.5+). Not in scope until the grow reaches that stage.
- **Auto-tuning / adaptive gains.** Manual tuning is fine for a problem this small.
