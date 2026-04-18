---
title: "Hardware — Humidifier Control (Raydrop 4L + Kasa EP10 smart plug)"
type: hardware
sources: []
related: [wiki/decisions/2026-04-17-humidifier-kasa-ep10.md, wiki/environment/humidity.md, wiki/concepts/vpd.md]
created: 2026-04-14
updated: 2026-04-17
---

# Humidifier Control

Closed-loop humidity control: tent DHT22 reading → Python service on the `dirt` host → WiFi command to Kasa EP10 smart plug → mains power to the Raydrop 4L humidifier.

Superseded the SSR-on-Arduino approach — see [decision 2026-04-17](../decisions/2026-04-17-humidifier-kasa-ep10.md). No mains wiring, no custom enclosure, no GPIO.

## Deployment Status

| Component | Status | Notes |
|-----------|--------|-------|
| Raydrop 4L humidifier | ✅ In tent | Knob set to a moderate fixed output (~50–60%) |
| Kasa Ultra Mini EP10 smart plug | ⏳ On hand, not yet provisioned | Needs Kasa-app onboarding + static LAN IP |
| `python-kasa` integration | ❌ Not started | Canonical library, supports EP10 incl. newer KLAP protocol |
| Control service | ❌ Not started | Lives on `dirt` host; reads RH from DB / Nano stream, commands plug |
| Plug state logging | ❌ Not started | On/off transitions + optional wattage persisted alongside RH |

## Hardware

### Raydrop 4L Ultrasonic Humidifier

- **Control interface:** analog potentiometer knob for mist intensity. No digital / WiFi / BLE control.
- **Power:** 120 VAC wall plug.
- **Strategy:** knob set once to a moderate output (~50–60%). Dynamic control is purely ON/OFF gating of mains power via the Kasa plug — never by driving the knob.

### TP-Link Kasa Ultra Mini EP10 Smart Plug

- **Switching:** internal relay; UL-listed sealed consumer device — all mains switching stays inside the plug.
- **Connectivity:** 2.4 GHz WiFi. Controlled over LAN (not via TP-Link cloud).
- **Protocol:** modern Kasa plugs use the KLAP protocol; `python-kasa` handles both legacy Kasa and KLAP transparently.
- **Energy monitoring:** reports instantaneous wattage. Useful as a ground-truth signal — a humidifier that's been unplugged, has run dry, or has hit its own safety cutout will read ~0 W even when the plug is ON.
- **Relay lifetime:** plug relays are mechanical — rated on the order of 10⁴–10⁵ cycles. The control loop deliberately limits switching (wide hysteresis band + minimum off-time) to stay comfortably under that.

## Network / Provisioning

- Onboard the plug using the Kasa mobile app (one-time; WiFi credentials baked into the plug).
- Assign the plug a **static DHCP reservation** on the LAN so the control service can reach it by a stable IP (or mDNS name if preferred).
- Note the plug's MAC + IP in this file once deployed.

## Control Library

[`python-kasa`](https://github.com/python-kasa/python-kasa) — async API, explicit EP10 support, talks directly to the plug over the LAN. No TP-Link cloud dependency.

Sketch (not final code):

```python
from kasa import SmartPlug
plug = SmartPlug("192.168.1.XX")
await plug.update()
await plug.turn_on()
await plug.turn_off()
is_on = plug.is_on
watts = plug.emeter_realtime.power  # real-time wattage
```

`python-kasa` is also usable from its CLI (`kasa` command) for out-of-band testing.

## Control Logic (idea, not yet implemented)

Bang-bang with hysteresis + relay-protection guards. Concrete service wiring is deferred — this section is the algorithmic shape only.

```
target            = 60.0  # %RH  (mid-veg; phase-configurable later)
deadband          =  3.0  # %RH
TURN_ON_BELOW     = target - deadband   # 57%
TURN_OFF_ABOVE    = target + deadband   # 63%
MIN_OFF_SECONDS   = 90    # relay protection + let the last pulse settle
MAX_ON_SECONDS    = 1200  # 20 min — safety timeout
FAILSAFE_STALE_S  = 300   # 5 min without fresh RH → force OFF

loop every ~30s:
    rh, ts = latest DHT22 reading
    if rh is None or (now - ts) > FAILSAFE_STALE_S:
        plug.off()
        continue

    if plug.is_on and (now - turned_on_at) > MAX_ON_SECONDS:
        plug.off()
        alert("humidifier max-on timeout")
        continue

    if rh < TURN_ON_BELOW and (now - last_switch) >= MIN_OFF_SECONDS and not plug.is_on:
        plug.on()
    elif rh > TURN_OFF_ABOVE and plug.is_on:
        plug.off()
    # else: hold — the deadband is intentional
```

**Why these choices (recap):**

- Bang-bang, not PID. Binary actuator. Big dead time. Asymmetric transfer function (can add moisture, can't actively remove). Relay switch-cycle budget. Plants don't need ±1% RH.
- 3% deadband exceeds DHT22 noise floor (±2% per datasheet).
- Failsafe OFF on stale reads — prefer brief dryness over a damping-off tent.

## State Logging

On every state change, persist a row so the loop's behavior is reconstructable from the DB:

- Timestamp
- New state (`on` / `off`)
- Reason (`rh_below_threshold`, `rh_above_threshold`, `failsafe_stale_sensor`, `max_on_timeout`, `manual`)
- Current RH reading
- Optional: plug wattage at the moment of the change

Schema choice (new table vs. folding into `sensorreading` as a 0/1 metric) is an open question in the decision record.

## Safety / Operational Notes

- **No mains wiring to do.** The EP10 is a sealed consumer device; all high-voltage switching is internal.
- **Plug placement:** keep the plug outside the tent's splash zone. A short extension cord into the tent is fine; the plug itself should be in dry air.
- **Humidifier knob:** set to ~50–60% output, not max. If the plug ever fails closed (rare but possible — relays can weld), a lower knob setting limits the overshoot rate before a human notices.
- **Empty-reservoir behavior:** the Raydrop has its own low-water cutoff. Combined with the EP10's wattage reporting (~0 W even when `is_on`), the control service can detect "humidifier plugged in but not actually running" and surface it.
- **Fail-safe priority:** stuck-off is safer than stuck-on. Damping-off and mold are worse than a dry spell. The loop defaults to OFF on any ambiguity.

## Acceptance (from decision record)

- Humidifier cycles on/off through the EP10 based on DHT22 readings without manual intervention.
- RH stays within target band ±5% for 24h continuous.
- Plug state (and ideally wattage) logged alongside RH.
- Simulated sensor failure triggers failsafe OFF within the failsafe window.
- Max-on-time safety timeout observed under a "sensor stuck low" simulation.
