---
title: "Hardware — Humidifier Control (Raydrop 4L + Kasa EP10 smart plug)"
type: hardware
sources: []
related: [wiki/decisions/2026-04-17-humidifier-kasa-ep10.md, wiki/environment/humidity.md, wiki/concepts/vpd.md]
created: 2026-04-14
updated: 2026-04-18
---

# Humidifier Control

Closed-loop VPD control: tent DHT22 reading → VPD calc → Python service on the `dirt` host → WiFi command to Kasa EP10 smart plug → mains power to the Raydrop 4L humidifier.

The loop targets **VPD** against the current stage's upper band (from `dirt.services.grow_state.current_targets()`), not a fixed RH. Night behavior is free — cooler air drops VPD on its own, so the humidifier shuts off during lights-off without needing a schedule. See [decision 2026-04-18](../decisions/2026-04-18-vpd-targeting.md) for the switch from fixed-RH control.

Superseded the SSR-on-Arduino approach — see [decision 2026-04-17](../decisions/2026-04-17-humidifier-kasa-ep10.md). No mains wiring, no custom enclosure, no GPIO.

## Deployment Status

| Component | Status | Notes |
|-----------|--------|-------|
| Raydrop 4L humidifier | ✅ In tent | Knob set to a moderate fixed output (~50–60%) |
| Kasa Ultra Mini EP10 smart plug | ✅ Provisioned | Alias `dirt-humidifier`; DHCP-reserved `192.168.1.220`; MAC `10:5A:95:8B:E8:B7`; firmware `1.1.1 Build 250908` |
| `python-kasa` integration | ✅ Working | Pinned to [PR #1580 fork branch](https://github.com/ZeliardM/python-kasa/tree/feature/new-klap) until KLAP v2 support lands upstream — stock python-kasa fails auth on this firmware (see "Known Issues" below) |
| Control service | ✅ Deployed 2026-04-18 | `src/dirt/services/humidifier.py`, run from the FastAPI lifespan alongside capture / archive / serial |
| Plug state logging | ✅ | `humidifier_on` (0/1) written to `sensorreading` every poll; state transitions emitted to `logs/humidifier/` stream with reason + VPD |
| Energy monitoring | ❌ Not exposed | This EP10 firmware does not publish an `Energy` module — only `is_on` is readable. Good-enough: control loop uses VPD, not wattage |

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

## Known Issues

### KLAP v2 authentication (firmware 1.1.1 Build 250908)

Our plug ships with KLAP `Login version: 2`, and stock `python-kasa` (0.10.2) fails the second-stage handshake with "Device response did not match our challenge" even with correct TP-Link Cloud credentials. Fix is in [python-kasa PR #1580](https://github.com/python-kasa/python-kasa/pull/1580) (approved, not yet merged). We pin to the contributor's branch in `pyproject.toml`:

```toml
"python-kasa @ git+https://github.com/ZeliardM/python-kasa.git@feature/new-klap"
```

Once PR #1580 merges and releases, swap back to a pinned version.

### Provisioning note

"Remote Control" must be **enabled** in the Kasa app for LAN KLAP auth to work. It's nominally a cloud-relay toggle, but the plug's KLAP credentials are only valid once it's bound to a TP-Link Cloud account.

## Control Logic (deployed)

Bang-bang with hysteresis + relay-protection guards, targeting the **upper edge** of the stage-appropriate VPD band. The humidifier only pushes VPD down (adds moisture), so the upper edge is the right setpoint: kick on when VPD climbs past it, kick off once it falls back below by a small deadband.

Stage → VPD band lookup comes from `dirt.services.grow_state.STAGE_TARGETS`:

| Stage | VPD band (kPa) | Upper edge (turn-on threshold) |
|---|---|---|
| `veg` | 0.8 – 1.2 | 1.2 |
| `flower_early` (days 0–20 of 12/12) | 1.0 – 1.3 | 1.3 |
| `flower_late` (day 21+ of 12/12) | 1.2 – 1.5 | 1.5 |

```
deadband          = 0.1  # kPa  (vpd_deadband_kpa in config)
MIN_OFF_SECONDS   = 90   # relay protection + let the last pulse settle
MAX_ON_SECONDS    = 1200 # 20 min — safety timeout
FAILSAFE_STALE_S  = 300  # 5 min without fresh VPD → force OFF

loop every ~30s:
    stage                = current_stage()        # veg / flower_early / flower_late
    lo, hi               = current_targets()["vpd_kpa"]
    turn_on_above        = hi
    turn_off_below       = hi - deadband
    vpd, ts              = latest vpd_kpa reading

    if vpd is None or (now - ts) > FAILSAFE_STALE_S:
        plug.off()
        continue

    if plug.is_on and (now - turned_on_at) > MAX_ON_SECONDS:
        plug.off()
        alert("humidifier max-on timeout")
        continue

    if vpd > turn_on_above and (now - last_switch) >= MIN_OFF_SECONDS and not plug.is_on:
        plug.on()
    elif vpd < turn_off_below and plug.is_on:
        plug.off()
    # else: hold — the deadband is intentional
```

**Why these choices:**

- **VPD, not RH.** RH at a fixed setpoint mis-targets the plant: when temperature falls at night, the same RH produces a much lower VPD (e.g. 60% RH at 63°F = 0.46 kPa, seedling range). VPD collapses this into one number that's correct across the day/night swing. See [concepts/vpd.md](../concepts/vpd.md).
- **Upper-edge setpoint.** The humidifier only adds moisture; there's nothing to do when VPD is already in or below the band. Acting only at the dry edge keeps the duty cycle low and the relay count manageable.
- **Bang-bang, not PID.** Binary actuator. Big dead time. Asymmetric transfer function (can add moisture, can't actively remove). Relay switch-cycle budget. Plants don't need ±0.05 kPa.
- **0.1 kPa deadband** ≈ the noise floor of the derived VPD signal given DHT22 ±0.5°C / ±2% RH.
- **Failsafe OFF on stale reads** — prefer brief dryness over a damping-off tent.
- **Stage band re-read every tick** — a veg→flower flip in the DB (via a future UI) takes effect on the next poll with no restart.

## State Logging

Two streams, each serving a different consumer:

- **`sensorreading.humidifier_on`** — 0/1 every poll (~30s), `source="kasa"`, `location="tent"`. Written even when no state change occurred, so the web UI's time-series graphs show a continuous step function alongside `vpd_kpa`.
- **`logs/humidifier/YYYY-MM-DD.jsonl`** — state-change events with full context (reason, VPD at decision time, VPD-reading age, stage, and the upper/lower band edges in effect). Short-retention operational stream for incident review.

State-change reasons: `vpd_above_upper_band`, `vpd_below_upper_band`, `failsafe_stale_sensor`, `max_on_timeout`. Manual overrides via the Kasa app or `uv run kasa --host 192.168.1.220 on/off` are NOT tagged — the loop just observes the new state on its next poll and records it.

Wattage field is absent because this firmware doesn't expose an Energy module.

## Safety / Operational Notes

- **No mains wiring to do.** The EP10 is a sealed consumer device; all high-voltage switching is internal.
- **Plug placement:** keep the plug outside the tent's splash zone. A short extension cord into the tent is fine; the plug itself should be in dry air.
- **Humidifier knob:** set to ~50–60% output, not max. If the plug ever fails closed (rare but possible — relays can weld), a lower knob setting limits the overshoot rate before a human notices.
- **Empty-reservoir behavior:** the Raydrop has its own low-water cutoff. Combined with the EP10's wattage reporting (~0 W even when `is_on`), the control service can detect "humidifier plugged in but not actually running" and surface it.
- **Fail-safe priority:** stuck-off is safer than stuck-on. Damping-off and mold are worse than a dry spell. The loop defaults to OFF on any ambiguity.

## Acceptance

- Humidifier cycles on/off through the EP10 based on tent VPD without manual intervention.
- VPD stays inside the active stage band for 24h continuous across the day/night swing.
- Plug state logged alongside VPD; state-change events carry the band edges that were active at decision time.
- Simulated sensor failure triggers failsafe OFF within the failsafe window.
- Max-on-time safety timeout observed under a "sensor stuck high-VPD" simulation.
- Veg→flower flip (via a `grow_state.flower_start_date` write) shifts the upper-edge setpoint on the next poll without a service restart.
