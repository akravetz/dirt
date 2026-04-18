---
title: "Humidifier Control via Kasa EP10 Smart Plug + python-kasa (supersedes 2026-04-14)"
type: decision
sources: []
related: [wiki/environment/humidity.md, wiki/hardware/humidifier-control.md, wiki/decisions/2026-04-14-humidifier-relay-control.md, wiki/concepts/vpd.md]
created: 2026-04-17
updated: 2026-04-17
---

# Decision: Humidifier Control via Kasa EP10 Smart Plug

**Date:** 2026-04-17
**Status:** Accepted
**Supersedes:** [2026-04-14 SSR/Arduino approach](2026-04-14-humidifier-relay-control.md)

## Context

The 2026-04-14 decision to control the Raydrop 4L humidifier via a G3MB-202P solid-state relay driven by the Arduino Nano was accepted but the hardware was never deployed. Installing a mains-switching SSR means a proper enclosure, strain relief, hot-side wiring, and physical space next to the tent for all of that. The activation energy for a one-person grow to do that safely is higher than it should be for a control surface that just needs to turn a plug on and off.

A WiFi smart plug is the same control topology (bang-bang gating of mains power to an unmodified humidifier) with the mains side already sealed in a UL-listed enclosure and a software API in place of a GPIO pin.

## Decision

Drive the Raydrop 4L humidifier through a **TP-Link Kasa Ultra Mini EP10 smart plug**, with an on-host Python service doing bang-bang / hysteresis control based on the tent DHT22 RH reading. Control the plug via the **[`python-kasa`](https://github.com/python-kasa/python-kasa)** library (async API, first-class EP10 support).

No microcontroller code changes. No mains wiring. No enclosure. No GPIO.

## Control Logic

Unchanged from the 2026-04-14 design — bang-bang with a deadband. PID is not appropriate for a binary actuator, an asymmetric transfer function (humidifier only adds moisture; drying is passive), or a relay with finite switch-cycle life. See the [hardware page](../hardware/humidifier-control.md) for the full loop.

Shape:

```
target   = 60%  RH    (mid-veg; phase-configurable)
deadband = ±3% RH     (on at 57%, off at 63%)

if rh < 57 and time_since_last_switch >= min_off_seconds: plug.turn_on()
elif rh > 63:                                             plug.turn_off()
# else: hold
```

Plus two operational guards:
- **Minimum off-time between switches** (~90s) to protect the plug's relay and to let the last humidifier pulse actually reach the sensor before the next decision.
- **Maximum on-time safety timeout** (~20 min continuous) — if reached, force OFF and surface an alert. Covers sensor dropouts, doors left open, plume failing to reach the sensor.

**Failsafe on stale/invalid RH reads:** force OFF. Preference is brief dryness over saturated-tent damping-off conditions.

## Rationale

- **No mains wiring.** The EP10 is a sealed, UL-listed consumer device. All high-voltage switching stays inside the plug. Eliminates the enclosure / strain-relief / fused-outlet checklist the SSR path required.
- **python-kasa is the canonical library** for this plug family (Kasa Ultra Mini EP10 is explicitly supported, including via the newer KLAP protocol). Async API slots cleanly into the existing service layout. No custom HTTP/cloud dependency — `python-kasa` talks to the plug directly over the LAN.
- **Bang-bang still wins over PID**: binary actuator, asymmetric transfer function, big dead time (plume travel + sensor lag), relay switch-life limits, and plants don't need ±1% precision. Same reasons as the 2026-04-14 decision; only the transport layer changes.
- **Control host moves off the Arduino** back to the main `dirt` host. The Nano no longer owns any actuator logic — it's a pure sensor node again. Setpoints live in the host-side service, which is simpler to evolve toward phase-aware targets.
- **Energy monitoring bonus**: the EP10 reports instantaneous wattage. That's a free "is the humidifier actually drawing power right now?" signal — useful for detecting a humidifier that's been unplugged, has run out of water, or has hit its internal safety shutoff while the plug still reports ON.

## What stays the same from 2026-04-14

- Target ~60% RH in veg, phase-configurable.
- Deadband ±3% (sized to exceed DHT22 noise floor).
- Failsafe OFF on stale sensor data.
- Raydrop 4L knob set to a moderate fixed output — dynamic control is gating, not level.
- Ingest/log plug state alongside the RH reading so cause-and-effect is reconstructable from the DB.

## What changes from 2026-04-14

| Aspect | Old (2026-04-14) | New (this decision) |
|---|---|---|
| Actuator | G3MB-202P SSR inside a DIY enclosure | Kasa Ultra Mini EP10 smart plug |
| Control host | Arduino Nano firmware | Python service on the `dirt` host |
| Transport | GPIO → SSR DC input pin | LAN → python-kasa → plug |
| Mains wiring | Custom (hot gated, neutral/ground pass-through, fused outlet) | None (sealed consumer device) |
| Enclosure | Required (project box, strain relief) | None |
| State observability | Serial field from Nano | `plug.is_on` + `plug.emeter_realtime` (wattage) from LAN |
| Setpoint source | Firmware constants | Python config |

## Open Items

- Decide where the service lives in the `src/dirt/` tree (own module under `services/` likely). Out of scope for this decision — the decision is about the topology, not the code layout.
- Log schema for humidifier on/off transitions — add a new metric/state table, or fold into `sensorreading` as a distinct metric (e.g. `humidifier_on` boolean-as-0/1)? Deferred.
- Phase table for setpoints (seedling / veg / flower / late flower) — TBD when flower approaches.

## Acceptance Criteria

- Humidifier cycles on/off through the EP10 based on DHT22 RH without manual intervention.
- RH stays within target band ±5% for 24h continuous.
- Plug state (and ideally wattage) logged alongside RH.
- Simulated sensor failure triggers failsafe OFF within the failsafe window.
- Maximum-on-time safety timeout observed under a "sensor stuck low" simulation.
