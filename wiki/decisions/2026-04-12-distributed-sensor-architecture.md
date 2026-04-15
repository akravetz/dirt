---
title: "Distributed Sensor Architecture: ESP32-C3 Per-Plant Nodes + Arduino Nano Tent Hub"
type: decision
sources: []
related: [wiki/decisions/2026-03-16-medium-and-training.md]
created: 2026-04-12
updated: 2026-04-12
---

# Decision: Distributed Sensor Architecture

**Date:** 2026-04-12
**Status:** Accepted

## Context

The original plan was a single Arduino Nano outside the tent reading all sensors, with long cable runs inside for each sensor. With 4 capacitive soil moisture sensors (one per plant), plus CO2, reservoir level, and DHT22, this meant 8+ wires threading through tent ports. The tent needs to be accessible for frequent plant work (topping, LST, SCROG net install, defoliation), and dense cabling makes that difficult.

## Decision

Split into a two-tier architecture:

1. **Per-plant nodes (ESP32-C3 SuperMini x4)** — inside the tent, one per plant. Each reads a capacitive soil moisture sensor and reports over WiFi. Powered via USB-C. Wiring is local (6" from sensor to board).

2. **Tent-level hub (Arduino Nano)** — outside the tent, reads tent-wide sensors (DHT22, MH-Z19B CO2, XKC-Y25-T12V reservoir level) over USB serial. Cable runs are minimal since these sensors mount on/near the tent exterior or reservoir.

## Alternatives Considered

| Option | Pros | Cons |
|--------|------|------|
| Single Arduino, long cable runs | Simple firmware, one device | 8+ cables across tent, hard to access plants, analog signal degradation over distance |
| ESP32 per plant, battery powered | Zero cables inside tent | Battery management overhead, TP4056 modules, periodic recharging |
| ESP32 per plant, USB-C powered | Short local wiring, WiFi, reliable power | 4 thin USB-C cables inside tent (acceptable) |
| Single ESP32 replacing Nano | One fewer device type | Still needs long cable runs for per-plant sensors |

## Rationale

- USB-C powered ESP32s eliminate battery management while keeping wiring minimal (4 thin cables vs 8+ sensor wires)
- WiFi eliminates analog signal degradation over long cable runs
- ESP32-C3 SuperMini chosen: cheapest, lowest power, RISC-V single-core is sufficient for reading one analog sensor and POSTing JSON
- Arduino Nano stays for tent-level sensors — firmware already exists, no WiFi needed for short USB cable
- RSHTECH 10-port powered USB hub centralizes all connections on the monitoring host
