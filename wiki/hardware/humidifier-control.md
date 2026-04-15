---
title: "Hardware — Humidifier Control (Raydrop 4L + G3MB-202P SSR)"
type: hardware
sources: []
related: [wiki/decisions/2026-04-14-humidifier-relay-control.md, wiki/environment/humidity.md, wiki/concepts/vpd.md]
created: 2026-04-14
updated: 2026-04-14
---

# Humidifier Control

Closed-loop humidity control: DHT22 reading → Arduino Nano decision → G3MB-202P SSR → Raydrop 4L humidifier mains power.

## Deployment Status

| Component | Status | Notes |
|-----------|--------|-------|
| Raydrop 4L humidifier | ⏳ **Arrives 2026-04-15** | Replaces current ad-hoc humidifier |
| G3MB-202P SSR module | ⏳ **Arrives 2026-04-15** | 2A zero-cross SSR |
| Arduino Nano firmware update | ❌ Not started | Add hysteresis loop + GPIO drive |
| Enclosure for SSR + mains wiring | ❌ Not yet sourced | Required before deployment |
| Relay state logging | ❌ Not designed | Schema/endpoint TBD |

See [decision record](../decisions/2026-04-14-humidifier-relay-control.md) for rationale.

## Hardware

### Raydrop 4L Ultrasonic Humidifier

- **Control interface:** analog potentiometer (mist intensity). No digital / WiFi / BLE control.
- **Power:** 120VAC wall plug.
- **Approach:** knob set to a fixed moderate output (~50–60%). Dynamic control via mains gating from the SSR, not by driving the knob.

### G3MB-202P Solid-State Relay Module

| Parameter | Rating |
|-----------|--------|
| Control (input) | 3–32 VDC, opto-isolated |
| Load (output) | 100–240 VAC, ≤2A resistive |
| Switching type | Zero-cross (reduces inrush / EMI) |
| Isolation | Optocoupler between DC control and AC load |
| Form factor | PCB module with screw terminals for AC, header pin for DC control |

**Current margin:** a 4L ultrasonic humidifier draws ~0.2–0.3A at 120V — well within the 2A rating.

**No built-in fuse.** Add an inline fuse in the enclosure or plug into a fused outlet strip.

## Wiring (planned)

```
AC side (inside enclosure):
  Wall plug (hot) ──────┬── SSR AC IN
                        └── (neutral passes through uninterrupted to outlet)
  SSR AC OUT ───────── Outlet hot (to humidifier plug)
  Wall plug (neutral) ─ Outlet neutral
  Wall plug (ground) ── Outlet ground (pass-through)

DC control side:
  Arduino Nano GPIO (TBD) ── SSR input "+"
  Arduino Nano GND ──────── SSR input "−"
```

The relay gates **only the hot conductor**; neutral and ground pass through unbroken. Enclosure must be rated for mains wiring (plastic project box with strain relief, or a proper outlet box).

## Control Firmware (planned)

Extension of the existing Arduino Nano DHT22 loop. Pseudocode:

```cpp
const float TARGET_RH = 60.0;
const float DEADBAND  = 3.0;    // ±3% around target
const unsigned long MIN_CYCLE_MS = 60000; // minimum 60s between state changes
const unsigned long FAILSAFE_MS  = 300000; // 5 min stale reading → force OFF

void controlLoop() {
    float rh = readDHT22_RH();
    if (rh is NaN or stale > FAILSAFE_MS) {
        setRelay(OFF);
        return;
    }
    unsigned long now = millis();
    if (now - lastStateChange < MIN_CYCLE_MS) return;  // anti-chatter

    if (rh < TARGET_RH - DEADBAND && !relayState) setRelay(ON);
    else if (rh > TARGET_RH + DEADBAND && relayState) setRelay(OFF);
}
```

**Setpoint** is hardcoded per phase in firmware for MVP. Future: server-side setpoint table keyed on grow phase.

**State publishing:** relay state should be serialized alongside the DHT22 reading in the existing serial output the dirt backend already parses. New field, e.g. `humidifier: on|off`.

## Safety

- **Mains voltage** — SSR and its wiring are live. Install in a closed enclosure with strain relief before powering. Never probe live AC terminals.
- **Water proximity** — tent contains a humidifier, moisture, and occasional drips. Mount the SSR enclosure outside the tent or well above the canopy/reservoir splash zone. Use a drip loop on any cable entering the enclosure.
- **Thermal** — G3MB-202P has modest thermal headroom at its rated 2A; at ~0.3A load there is no practical heat concern, but do not obstruct the module.
- **Fail behavior** — firmware failsafe forces relay OFF on stale sensor data. Preference is "dry air from a stuck-off humidifier" over "saturated tent from a stuck-on humidifier" (damping-off + mold are worse than a dry spell).

## Acceptance (from decision record)

- Humidifier cycles on/off based on DHT22 readings without manual intervention.
- RH stays within target band ±5% for 24h continuous.
- Relay state logged alongside RH.
- Simulated sensor failure triggers failsafe OFF.
