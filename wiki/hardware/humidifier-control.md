---
title: "Hardware — Humidifier Control (Raydrop 4L + Kasa EP10 smart plug)"
type: hardware
sources: []
related: [wiki/decisions/2026-04-17-humidifier-kasa-ep10.md, wiki/decisions/2026-04-26-govee-humidifier-pivot.md, wiki/environment/humidity.md, wiki/concepts/vpd.md]
created: 2026-04-14
updated: 2026-04-26
---

> **🔄 Hardware swap in progress (2026-04-26)** — A Govee H7142 Wi-Fi humidifier arrives 2026-04-28 and will replace the Raydrop + Kasa EP10 stack documented below (H7140 also en route 2026-04-27 as the de-risking backup). The MCU mist-intensity mod ([decision 2026-04-23](../decisions/2026-04-23-raydrop-mcu-mist-control.md)) was abandoned in favor of buying a smart humidifier off the shelf — see [pivot decision 2026-04-26](../decisions/2026-04-26-govee-humidifier-pivot.md). Until cutover, everything below is still live. After cutover, this page will be updated for the new actuator; the operational lessons (bang-bang oscillation, fan-coupling saturation, low-water latch, hard-water descale) generalize to any ultrasonic humidifier and stay relevant.
>
> Future-agent integration shape lives in [docs/references/govee-api/INDEX.md](../../docs/references/govee-api/INDEX.md).

# Humidifier Control

Closed-loop VPD control: tent SHT45 reading → VPD calc → Python service on the `dirt` host → WiFi command to Kasa EP10 smart plug → mains power to the Raydrop 4L humidifier.

(Sensor history: DHT22 → BME280 (2026-04-13, [decision](../decisions/2026-04-20-bme280-sensor-swap.md)) → SHT45 on the combined fan-controller ESP32-C3 (2026-04-23, [decision](../decisions/2026-04-22-sht45-tent-node-esp32.md)) after the BME280 was found to be reading +3.5 °F / +23 %RH off vs. a calibrated handheld. The control loop is sensor-agnostic; deadband was widened on 2026-04-23 after the SHT45 cutover exposed actuator overshoot — see "0.4 kPa deadband" below.)

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
- **Relay lifetime:** plug relays are mechanical — rated on the order of 10⁴–10⁵ cycles. The VPD deadband alone keeps switching low (a natural on-phase ends when the tent moistens past the turn-off edge, typically tens of minutes); no additional min-off or max-on guards are used.

## Network / Provisioning

- Onboard the plug using the Kasa mobile app (one-time; WiFi credentials baked into the plug).
- Assign the plug a **static DHCP reservation** on the LAN so the control service can reach it by a stable IP (or mDNS name if preferred).
- Note the plug's MAC + IP in this file once deployed.

## Control Library

[`python-kasa`](https://github.com/python-kasa/python-kasa) — async API, explicit EP10 support, talks directly to the plug over the LAN. No TP-Link cloud dependency. Also usable from its CLI (`kasa` command) for out-of-band testing. Real call-site: `apps/hwd/src/dirt_hwd/services/humidifier.py`.

## Known Issues

### KLAP v2 authentication (firmware 1.1.1 Build 250908)

Our plug ships with KLAP `Login version: 2`, and stock `python-kasa` (0.10.2) fails the second-stage handshake with "Device response did not match our challenge" even with correct TP-Link Cloud credentials. Fix is in [python-kasa PR #1580](https://github.com/python-kasa/python-kasa/pull/1580) (approved, not yet merged). We pin to the contributor's branch in `pyproject.toml`:

```toml
"python-kasa @ git+https://github.com/ZeliardM/python-kasa.git@feature/new-klap"
```

Once PR #1580 merges and releases, swap back to a pinned version.

### Provisioning note

"Remote Control" must be **enabled** in the Kasa app for LAN KLAP auth to work. It's nominally a cloud-relay toggle, but the plug's KLAP credentials are only valid once it's bound to a TP-Link Cloud account.

### Red LED on the Raydrop = low-water sensor latch

**First observed 2026-04-23 10:00 MDT:** plug ON continuously 1h 30m+, VPD above upper band and *not* falling, tent RH drifting down despite the loop commanding mist. Physical check: unit LED red (normally green), no visible mist. Unplug/replug (bypass Kasa briefly, then reconnect) cleared it — immediately began misting.

**Model & root cause:** Raydrop **KC-RD03A** ([manual](https://manuals.plus/raydrop/kc-rd03a-cool-mist-humidifiers-manual)). The low-water float sensor latches the "empty" state even with water in the tank; controller red-lights and disables the ultrasonic until a power cycle drops the latch. Trigger is mineral scale or biofilm on the float stem and/or the ultrasonic atomizer disc — same substrate fouls both. No thermal cutout and no other documented red-LED state. **Confirmed 2026-04-23:** physically cleaning the atomizer disc resolved today's latch, matching the scale/biofilm hypothesis.

**Detection (automated, 2026-04-23):** `HumidifierLoopService` runs a stuck-actuator watchdog via `update_stuck_state` — each tick advances a `StuckState` tracking the current continuous-ON streak and the VPD at streak start. When elapsed-on ≥ `humidifier_stuck_alert_after_s` (default 1200 s = 20 min) and VPD dropped less than `humidifier_stuck_min_vpd_drop_kpa` (default 0.15 kPa), a `suspected_stuck` event lands in the `humidifier` stream and a Telegram alert fires with start/now VPD and a "check red LED / water level / misting" prompt. Fires once per streak — suppressed until the plug transitions OFF.

**Recovery:** unplug Raydrop from the Kasa, plug directly into wall for ~10 s, reconnect through the Kasa. Loop sees misting resume within the next cycle.

**Prevention:** distilled or RO water only (tap water is the root cause of both float sticking and transducer fouling — one problem, not two). Weekly 1:1 white-vinegar descale of the base (float + piezo disc), 15–20 min, rinse, air dry.

### BME280 drift (resolved-by-transition 2026-04-23)

**Resolved** by retiring the Arduino Nano + BME280 for the ESP32-C3 + SHT45 combined fan-controller board (see [fan control + tent sensor](ac-infinity-fan-control.md), [decision 2026-04-22](../decisions/2026-04-22-sht45-tent-node-esp32.md)). Handheld hygrometer side-by-side with both sensors on 2026-04-23 00:15 MDT: **69 °F / 49 %RH**; SHT45: **69.6 °F / 53 %**; BME280: **72.5 °F / 73 %** — BME280 was off by +3.5 °F and +23 %RH, much larger than the prior "stuck-state" pattern.

**Historical-data caveat.** All `source=arduino` tent readings prior to 2026-04-23 00:22 MDT are biased high on RH / low on VPD by an unquantified amount. The humidifier VPD loop has been under-humidifying for some time — tent was drier than wiki/daily-reports indicated. Current-grow trend claims based on pre-cutover sensor data should be read against this caveat.

## Control Logic (deployed)

Bang-bang with hysteresis, targeting the **upper edge** of the stage-appropriate VPD band. The humidifier only pushes VPD down (adds moisture), so the upper edge is the right setpoint: kick on when VPD climbs past it, kick off once it falls back below by a small deadband.

Stage → VPD band lookup comes from `dirt.services.grow_state.STAGE_TARGETS`:

| Stage | VPD band (kPa) | Upper edge (turn-on threshold) |
|---|---|---|
| `veg` | 0.8 – 1.2 | 1.2 |
| `flower_early` (days 0–20 of 12/12) | 1.0 – 1.3 | 1.3 |
| `flower_late` (day 21+ of 12/12) | 1.2 – 1.5 | 1.5 |

Lights schedule comes from `growstate.lights_on_local` / `growstate.lights_off_local`, interpreted in `growstate.timezone` (default `America/Denver`). Defaults: veg 18/6 → (05:00, 23:00). Flip via SQL when the photoperiod changes; the loop picks it up on the next poll.

```
deadband          = 0.4   # kPa  (vpd_deadband_kpa)
night_offset      = -0.3  # kPa  (vpd_lights_off_offset_kpa)  — dark-period band shift
prep_minutes      = 5     # min  (lights_off_prep_minutes)    — pre-lights-off cutoff
FAILSAFE_STALE_S  = 300   # 5 min without fresh VPD → force OFF

loop every ~30s:
    stage                = current_stage()
    lights               = lights_state()        # (on: bool, minutes_until_off: float)
    offset               = 0 if lights.on else night_offset
    lo_day, hi_day       = current_targets()["vpd_kpa"]
    turn_on_above        = hi_day + offset
    turn_off_below       = hi_day + offset - deadband
    in_prep_window       = lights.on and lights.minutes_until_off < prep_minutes

    vpd, ts              = latest vpd_kpa reading

    if vpd is None or (now - ts) > FAILSAFE_STALE_S:
        plug.off(); continue

    if in_prep_window:
        plug.off()                   # A: don't dose mist pre-lights-off
        continue

    if vpd > turn_on_above and not plug.is_on:
        plug.on()
    elif vpd < turn_off_below and plug.is_on:
        plug.off()
    # else: hold — the deadband is intentional
```

**Why these choices:**

- **VPD, not RH.** RH at a fixed setpoint mis-targets the plant: when temperature falls at night, the same RH produces a much lower VPD (e.g. 60% RH at 63°F = 0.46 kPa, seedling range). VPD collapses this into one number that's correct across the day/night swing. See [concepts/vpd.md](../concepts/vpd.md).
- **Upper-edge setpoint.** The humidifier only adds moisture; there's nothing to do when VPD is already in or below the band. Acting only at the dry edge keeps the duty cycle low and the relay count manageable.
- **Bang-bang, not PID.** Binary actuator. Big dead time. Asymmetric transfer function (can add moisture, can't actively remove). Plants don't need ±0.05 kPa.
- **0.4 kPa deadband.** Originally 0.1 kPa (sized to DHT22 noise floor and kept through the BME280 swap). Widened to 0.3 kPa on 2026-04-23 after the SHT45 cutover exposed severe bang-bang flapping: the Raydrop running for one minute drops VPD ~0.45 kPa (from ~1.35 to ~0.87 in veg-ambient conditions), overshooting the 0.1 kPa deadband by 4× every cycle and clicking the plug relay every 60 s at lights-on. Widened again to 0.4 kPa later on 2026-04-23 after the UI showed 128 cycles/24h — at the low end of the EP10's 10⁴–10⁵-cycle relay rating, that's ~2.5 months of life in the worst case. 0.4 kPa stretches the natural off-phase from ~5–10 min toward ~15–20 min without any hardware change. Not sensor-noise-sized anymore — it's actuator-overshoot-sized. The proper long-term fix is the two-actuator fan+humidifier loop (see [fan control](ac-infinity-fan-control.md) "Future integration"), which lets the fan counteract the humidifier's overshoot and tighten the band back up.
- **Feedforward, not derivative.** The dominant disturbance (lights on/off) is scheduled and periodic, so we use the clock to anticipate it rather than estimating `dVPD/dt`. Derivative on sensor noise would have a 5 min smoothing lag and near-unit SNR for the signals we care about. See [decisions/2026-04-19-lights-off-aware-humidifier.md](../decisions/2026-04-19-lights-off-aware-humidifier.md).
- **−0.3 kPa night offset, not percentage.** Preserves deadband width across stages (a percentage factor compresses the band below sensor noise). Falls inside the published "0.2–0.4 kPa below day" range (Pulse Grow, GrowSensor, Anden).
- **5 min prep window.** Sized to one tent-fan-volume turnover so the humidifier isn't actively misting at the lights transition. **Originally 30 min** (Apr 19); tightened to 5 min on 2026-04-27 after Govee H7142 data showed RH clears 63%→43% within 5 minutes of OFF. The legacy 30-min margin had been left over from the Raydrop era and was leaving VPD ~0.4 kPa above the veg upper band for ~25 min/day with no observable benefit (no residual mist rise, dew-point stayed 50–55°F vs 70–75°F ambient at lights-off — ~20°F condensation margin). Same value applies symmetrically pre-lights-on (humidifier resumes 5 min before lights, not 30).
- **No max-on safety, no min-off guard.** The Raydrop has its own low-water cutoff, so a stuck-high VPD reading self-limits when the reservoir runs dry. Min-off was redundant with the deadband (hysteresis already prevents chatter). Earlier versions fought the safety timers — ops learning 2026-04-19: max-on at 20 min terminated on-phases before the deadband could, turning the safety into the primary (and poorly-tuned) controller. See [decisions/2026-04-19-drop-humidifier-safety-timers.md](../decisions/2026-04-19-drop-humidifier-safety-timers.md).
- **Failsafe OFF on stale reads** — prefer brief dryness over a damping-off tent.
- **Stage band + lights schedule re-read every tick** — a veg→flower flip or a photoperiod change in the DB takes effect on the next poll with no restart.

## Coupling with fan exhaust rate

The humidifier competes directly with the tent exhaust fan — a coupling invisible in the BME280 era (bogus +23 %RH kept the loop from seriously demanding humidity) but immediately observable after the SHT45 cutover. 2026-04-23: at fan 30 % + mid-dial Raydrop, VPD tracked setpoint and the humidifier oscillated gently. Bumping fan to 40 % tipped the balance — exhaust exceeded the Raydrop's dialed-down emission rate, the plug pinned ON continuously, VPD *climbed* 1.20 → 1.50 kPa over 1h 40m. User turned the Raydrop dial up and RH recovered.

**Implications:** (1) The Raydrop potentiometer is a hidden input to the control stack — its setting caps the max mist rate the loop can ask for, and software has no visibility into it. (2) Fan speed is part of the humidity-control surface even though nothing in the loop models it. **Diagnostic:** humidifier stuck ON >30 min with VPD still rising ⇒ physical actuator saturation, not a loop bug. Dial up the Raydrop or dial down the fan.

## State Logging

Two streams, each serving a different consumer:

- **`sensorreading.humidifier_on`** — 0/1 every poll (~30s), `source="kasa"`, `location="tent"`. Written even when no state change occurred, so the web UI's time-series graphs show a continuous step function alongside `vpd_kpa`.
- **`logs/humidifier/YYYY-MM-DD.jsonl`** — state-change events with full context (reason, VPD at decision time, VPD-reading age, stage, and the upper/lower band edges in effect). Short-retention operational stream for incident review.

State-change reasons: `vpd_above_upper_band`, `vpd_below_upper_band`, `failsafe_stale_sensor`, `lights_off_prep`. Each event also carries `lights_on`, `minutes_until_off`, and `band_offset_kpa` so a log line fully determines which rule fired. Manual overrides via the Kasa app or `uv run kasa --host 192.168.1.220 on/off` are NOT tagged — the loop just observes the new state on its next poll and records it.

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
- Veg→flower flip (via a `grow_state.flower_start_date` write) shifts the upper-edge setpoint on the next poll without a service restart.

## Future work

### Continuous humidifier intensity control

**Scoped and tracked** per [decision 2026-04-23](../decisions/2026-04-23-raydrop-mcu-mist-control.md) and [epic: continuous-humidifier](../../docs/epics/continuous-humidifier/README.md). Replaces the Raydrop's analog potentiometer with MCU-driven intensity + a PI control loop, in place of today's bang-bang Kasa-plug control. Collapses the actuator-overshoot deadband, the fan-coupling saturation failure mode, and the "turn the dial" operational gotcha. Phase 1 (open-and-probe investigation) is the gate on Phases 2–4.

For a conceptual walkthrough of *why* PI, what FOPDT means, and how IMC maps a plant model to gains, see [`concepts/control-theory-primer.md`](../concepts/control-theory-primer.md).

**Phase 4 prep landed 2026-04-25** — pure-function PI controller (`apps/hwd/src/dirt_hwd/services/humidifier_pi.py`), 29 property tests + 16 plant-in-loop tests (FOPDT-simulator + parametrized plant bracket), shadow-mode logging on a new `humidifier_shadow` stream, and an analyzer + replay harness at `debug/humidifier-shadow/analyze.py` that reads the shadow stream and reports reasons / divergence / PI math health / RH ceiling patterns / FOPDT refit / current-controller replay against historical inputs. Stage humidity bands updated late 2026-04-25 to mold-prevention envelopes (veg=(40,70), flower_early=(40,60), flower_late=(35,55)) — the previous (45,55) values were internally inconsistent with the VPD targets and caused the rh_ceiling guard to fire constantly. Full state for resumption: [`docs/epics/continuous-humidifier/README.md`](../../docs/epics/continuous-humidifier/README.md) (per-tick `u_pct`, `plug_on_shadow` vs `plug_on_actual`, setpoint, error, P/I split, integrator, reason). No actuator action; bang-bang above still drives the plug. Conservative starting gains (Kc=8, Ki=0.01) at the low end of the [FOPDT-fit bracket](../../docs/epics/continuous-humidifier/fopdt-fit-findings.md); refined under shadow data + a graduated step test in Phase 2/3 acceptance. New `rh_ceiling` envelope guard forces u=0 when RH ≥ stage_rh_max — addresses the "VPD looks fine because tent went cold and humid" failure mode that scalar VPD alone can't catch.
