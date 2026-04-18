---
title: "Closed-Loop Humidifier Control: Raydrop 4L + G3MB-202P SSR"
type: decision
sources: []
related: [wiki/environment/humidity.md, wiki/hardware/humidifier-control.md, wiki/concepts/vpd.md]
created: 2026-04-14
updated: 2026-04-14
---

# Decision: Closed-Loop Humidifier Control

**Date:** 2026-04-14
**Status:** ⚠️ **Superseded 2026-04-17 by [Humidifier Control via Kasa EP10 Smart Plug](2026-04-17-humidifier-kasa-ep10.md)**. The SSR approach was accepted but never deployed — installing mains-switching hardware safely is higher-friction than a WiFi smart plug that achieves the same topology with the mains side already sealed. The control algorithm (bang-bang with hysteresis) carries forward unchanged; only the actuator and control host changed. Kept for decision-trail history.

**Date (original):** 2026-04-14
**Status (original):** Accepted (hardware ordered, arrives 2026-04-15)

## Context

Humidity has been one of the most chronically off-target environmental parameters this grow:

- Extended stretches in the 70–76% range (ceiling of veg target 55–65%) — see [humidity log](../environment/humidity.md#trend-log).
- Periodic overshoots to 81–89% overnight (damping-off risk) when the humidifier was run hot.
- **2026-04-08 VPD swing incident:** turning the humidifier off dropped RH from 70% → 42% (VPD 0.89 → 2.03 kPa) before manual recovery. RH oscillations stress plants more than a steady suboptimal value.

The current workflow is manual: the grower eyeballs RH on the dashboard and twists the humidifier's potentiometer. This produces the oscillations above, scales poorly across the remaining 8–10 weeks of grow, and cannot respond while the grower is away.

## Decision

Drive the humidifier via a **solid-state relay controlled by humidity readings from the existing DHT22** (Arduino Nano tent-hub). Use a **bang-bang (hysteresis) controller** with a deadband to avoid relay chatter.

**Hardware:**
- **Humidifier:** Raydrop 4L ultrasonic — analog potentiometer knob (no digital control interface). Set the knob to a conservative fixed output; the relay provides all dynamic control by gating mains power.
- **Relay:** Omron **G3MB-202P** solid-state relay module (≤240VAC / 2A, zero-cross switching, opto-isolated DC control input).

**Control topology (initial):** Arduino Nano reads DHT22 → decides on/off via hysteresis → drives G3MB-202P input pin → SSR gates AC power to humidifier. Arduino already has the DHT22 loop running; adding a single GPIO + publishing state over serial is incremental.

**Alternative considered:** ESP32 tent-hub controller with HTTP setpoint from backend. Cleaner long-term (setpoints live server-side, control is network-visible), but deferred — the Arduino path is strictly simpler and gets closed-loop control online on Day 1. Revisit when more tent-level actuators are added (dehumidifier, heater, exhaust modulation).

## Control Logic

Bang-bang with deadband:

```
target = 60%   (mid-veg target; configurable per phase)
deadband = ±3% (turn on at 57%, off at 63%)

if RH < target - deadband: relay ON
if RH > target + deadband: relay OFF
else: hold current state (hysteresis — do nothing)
```

Phase-specific targets to be tabulated in `environment/humidity.md`. Deadband sized to exceed DHT22 noise floor (±2% per datasheet) and avoid minute-by-minute toggling.

**Fail-safe:** If DHT22 read fails for >N minutes, force relay OFF (better dry than damping-off on a stale reading).

## Rationale

- **Raydrop 4L has no digital interface** — only a pot knob. The relay-gating approach is the least-invasive way to add programmatic control without modifying the humidifier.
- **G3MB-202P** is the canonical Arduino/ESP-compatible SSR module: opto-isolated DC control (3–32V), zero-cross AC switching (reduces inrush noise and EMI), adequate current headroom for a 4L ultrasonic humidifier (~0.2–0.3A at 120V vs. the relay's 2A rating).
- **Arduino Nano host** leverages an already-running control loop. No new microcontroller to provision, flash, or secure.
- **Hysteresis over PID:** PID is overkill for an on/off actuator driving a slow-response environmental variable. Bang-bang with a sensible deadband is standard for HVAC-class loops.

## Safety / Operational Notes

- SSR switches **mains AC**. Must be installed in a proper enclosure with strain relief before deployment — not bare on the tent floor near standing water.
- Zero-cross switching means the SSR only turns on/off at AC zero-crossings. This limits EMI and inrush but is invisible at the control-loop timescale (30s+).
- G3MB-202P has no built-in fuse. Humidifier is low-current (~0.3A), but the circuit should still be on a fused outlet or add an inline fuse in the enclosure.
- Potentiometer knob on the humidifier should be set to a **moderate** fixed output (~50–60%), not max. If the relay fails closed and the humidifier runs continuously, a lower knob setting limits the overshoot rate.

## Acceptance Criteria

- Humidifier cycles on/off based on DHT22 RH reading without manual intervention.
- RH stays within target band ±5% for 24h+ continuous operation.
- Relay state visible in the dashboard / logged to DB alongside sensor readings.
- Fail-safe observed: simulated DHT22 failure forces relay OFF within N minutes.
- No damping-off overshoots and no VPD-spike-from-off events for the remainder of veg.

## Open Questions

- **Control host final home:** Arduino Nano for MVP. Migrate to a dedicated ESP32 tent-hub when exhaust fan / dehumidifier / heater join the control surface (likely at flower flip when RH targets tighten).
- **Setpoint source:** hardcoded in firmware for MVP. Phase-aware setpoints via server-side config come when control migrates off the Nano.
- **Logging:** relay state should be recorded per transition (or every cycle) and correlated with RH trend. Schema/ingest to be defined before deployment.
