---
title: "Hardware — Humidifier Control (Govee H7142 + PI controller)"
type: hardware
sources: []
related: [wiki/decisions/2026-04-26-govee-humidifier-pivot.md, wiki/decisions/2026-04-27-h7142-deployed.md, wiki/environment/humidity.md, wiki/concepts/vpd.md, docs/references/govee-api/INDEX.md]
created: 2026-04-14
updated: 2026-04-27
---

# Humidifier Control

Closed-loop VPD control: tent SHT45 reading → VPD calc → PI controller in `dirt-hwd` → discrete Manual-mode mist level via Govee Public API v2 → **GoveeLife H7142** Wi-Fi humidifier (6 L cool-mist ultrasonic).

The H7142 was deployed 2026-04-27, replacing the Raydrop 4L + Kasa EP10 stack. The Raydrop had no software-readable intensity control — every overshoot, fan-coupling saturation event, and "stuck red LED" incident traced back to a $5-cost-saving design decision in a unit that didn't expose the dial. The H7142 exposes 9 discrete intensity levels via API at a similar price point. See [pivot decision 2026-04-26](../decisions/2026-04-26-govee-humidifier-pivot.md) and [deployment decision 2026-04-27](../decisions/2026-04-27-h7142-deployed.md). The Raydrop + Kasa stack was unplugged the same day.

The loop targets **VPD** against the current stage's upper band (from `dirt.services.grow_state.current_targets()`), not a fixed RH. Night behavior is free — cooler air drops VPD on its own, so the humidifier shuts off during lights-off without needing a schedule. See [decision 2026-04-18](../decisions/2026-04-18-vpd-targeting.md) for the switch from fixed-RH control.

## Deployment Status

| Component | Status | Notes |
|-----------|--------|-------|
| GoveeLife H7142 humidifier | ✅ In tent | LAN IP `192.168.1.247` (DHCP-reserved); MAC `14:38:60:74:F4:DD:B9:46`; SKU `H7142`; account name `dirt-humidifier` |
| Govee Public API v2 | ✅ Working | `https://openapi.api.govee.com/router/api/v1/`; cloud-only, no LAN fallback for H71xx line |
| API key | ✅ Provisioned | `GOVEE_API_KEY` in `.env`; account-wide; rotate via Govee Home app |
| Control service | ✅ Deployed 2026-04-27 | `apps/hwd/src/dirt_hwd/services/humidifier.py`; runs in `dirt-hwd` lifespan |
| PI controller | ✅ Authoritative | `apps/hwd/src/dirt_hwd/services/humidifier_pi.py` (was shadow-mode 2026-04-25 → 2026-04-27) |
| Quantizer | ✅ Authoritative | `apps/hwd/src/dirt_hwd/services/humidifier_dispatch.py` — u_pct → Manual-mode level (1..9) with hysteresis |
| Plug state logging | ✅ | `humidifier_on` (0/1) + `humidifier_mist_level` (0..9) written every poll; transitions emitted to `logs/humidifier/` stream |
| `lackWaterEvent` watchdog | ✅ | Tank-empty alarm surfaced via `/device/state` → Telegram alert (rising-edge-deduped) |
| Ineffective-actuator watchdog | ✅ | Replaces Raydrop "red LED" check — fires when VPD doesn't drop after sustained mist commands |
| Raydrop 4L + Kasa EP10 | ⛔ Retired 2026-04-27 | Unplugged. Kasa EP10 (alias `dirt-humidifier`, MAC `10:5A:95:8B:E8:B7`, IP `192.168.1.220`) deprovisioned from the loop |

## Hardware

### GoveeLife Smart Humidifier H7142

- **Capacity:** 6 L cool-mist ultrasonic.
- **Control interface:** Wi-Fi via Govee Public API v2 (cloud-only — no LAN fallback for the H71xx line, confirmed 2026-04-27).
- **Power:** 120 VAC wall plug. No smart plug between wall and humidifier — smart control is native.
- **Capability list (live discovery, 2026-04-27):**
  - `powerSwitch` (on/off, ENUM 0/1)
  - `workMode` (STRUCT `{workMode, modeValue}`; Manual=1 / Custom=2 / Auto=3)
  - `humidity` (INTEGER 40–70%, used in Auto only — we don't use Auto)
  - `lackWaterEvent` (event-only, fires when tank empty; alarmType 51, single state `lack=1`)
- **9 Manual-mode mist levels** confirmed via API (one more than the H7140/H7143). The marketing claim and the API match — verified 2026-04-27. Quantizer maps `u_pct ∈ [0, 100]` from the PI controller into one of these 9 buckets with hysteresis at level boundaries.
- **No UVC, no aroma pad, no nightlight** capabilities exposed by the API. The H7142 marketing copy implies these as features — the API doesn't surface them. We don't use them anyway.
- **Cloud-only constraint:** every control / state read is an HTTP round-trip through `openapi.api.govee.com`. State polls counted against a 10K/account/day quota; we poll once per 30 s loop tick → 2,880 calls/day, well under the budget. See [docs/references/govee-api/rate-limits.md](../../docs/references/govee-api/rate-limits.md).

History: DHT22 → BME280 (2026-04-13) → SHT45 ESP32-C3 fan-controller (2026-04-23) for the *sensor*; Arduino-SSR → Kasa EP10 + Raydrop (2026-04-17) → H7142 native (2026-04-27) for the *actuator*. The control loop is sensor- and actuator-agnostic at module boundaries — the PI controller and quantizer don't know which device they're driving.

## Network / Provisioning

- Onboard the H7142 using the Govee Home app (one-time; account binds the device).
- Apply for an API key in the Govee Home app: **Profile → About Us → Apply for API Key** (24h email turnaround). The key is account-wide.
- Set `GOVEE_API_KEY` and (optionally) `GOVEE_HUMIDIFIER_MAC` in `.env`. Empty MAC → loop discovers by SKU at startup.
- DHCP-reserve the H7142's LAN IP for orderly network maps; control doesn't actually use the LAN.

## Control Library

Custom thin client at [`apps/shared/src/dirt_shared/services/govee.py`](../../apps/shared/src/dirt_shared/services/govee.py). Wraps `httpx.AsyncClient` with envelope handling, error mapping (`GoveeError` / `GoveeRateLimitError`), and a `StateSnapshot` parser. No retries — the loop is the retry boundary. Wire format anchored to [`docs/references/govee-api/`](../../docs/references/govee-api/).

## Control Logic (deployed)

**PI control on VPD with feedforward lights gating.** Continuous `u_pct ∈ [0, 100]` from the PI module, quantized to a discrete H7142 Manual-mode level (1..9) with hysteresis at boundaries. The PI controller has been live since 2026-04-25 in shadow mode — it became authoritative on 2026-04-27 when the H7142 cutover let us replace the Kasa bang-bang as the actuator.

```
loop every ~30s:
    stage           = current_stage()
    lights          = lights_state()       # (on, minutes_until_off, minutes_until_on)
    vpd_lo, vpd_hi  = current_targets()["vpd_kpa"]
    rh_lo, rh_hi    = current_targets()["humidity_pct"]   # mold-prevention envelope

    vpd, vpd_ts     = latest vpd_kpa reading
    rh              = latest humidity_pct reading

    # 1. PI: u_pct = clamp(Kc*err + Ki*∫err·dt, 0, 100)
    pi_out = pi_compute(cfg, state, PIInput(vpd, vpd_ts, rh, ...))
    # 2. Quantize: u_pct → discrete level 1..9 (or OFF)
    target = quantize(disp_cfg, disp_state, pi_out.u, pi_out.plug_on)
    # 3. Read live device state (online, power, mode_value, lack_water)
    snap = govee.get_state(sku, mac)
    # 4. Diff (current device, target) → minimal API calls
    diff = plan_dispatch(snap.power_on, snap.mode_value, target.target_level)
    # 5. Dispatch (interleaved with 200ms sleep on the boot tick)
    if diff.set_power_on is not None: govee.set_power(...)
    if diff.interleave: await sleep(0.2)
    if diff.set_level is not None: govee.set_manual_level(...)
```

### PI controller

Pure-function module at `humidifier_pi.py`. Guards in priority order:

1. **Failsafe — stale or missing VPD** → u=0 (force off; prefer brief dryness over runaway mist)
2. **Outside lights window** → u=0 (don't run during dark period; humidifier off `lights_off - 5min` through `lights_on - 5min`)
3. **RH ceiling** → u=0 (mold-prevention envelope; force off when RH ≥ stage upper RH cap regardless of what VPD says)
4. **PI active** — `error = vpd - setpoint`, where setpoint = stage VPD upper band (with `-0.3 kPa` night offset during dark period)

Sub-threshold cutoff with hysteresis converts `u_pct` to the binary `plug_on` gate that the quantizer reads. Anti-windup integrator clamp at ±50 %u keeps the integrator bounded under sustained saturation. Conservative starting gains: `Kc=8.0`, `Ki=0.01` — sourced from a Raydrop FOPDT fit and not yet refit for the H7142. Step-test refit is week-1 work.

### Quantizer (dispatch boundary)

Pure-function module at `humidifier_dispatch.py`. Maps `u_pct → modeValue ∈ {1..9}` with `bucket_width = 100/9 ≈ 11.11%`. Hysteresis at every boundary (default 3 percentage points) — once at level N, `u_pct` has to walk past `boundary ± hyst` before stepping. Prevents 4↔5 chatter at steady state.

### Dispatch state machine

The loop diffs the **live device state** (not our last-commanded value) against the target, so a divergence — user toggled via the Govee app, dropped command, network blip — self-heals on the next tick. Five cases:

| Current | Target | API calls |
|---|---|---|
| OFF | OFF | none |
| ON at N | OFF | `set_power(off)` |
| OFF | level N (≠ device's last level) | `set_power(on)` → 200ms → `set_manual_level(N)` |
| OFF | level N (= device's last level) | `set_power(on)` only — H7142 preserves workMode across power cycles |
| ON at N | level N | none (~99% of ticks at steady state) |
| ON at N | level M | `set_manual_level(M)` |

The 200ms inline pause on the boot tick exists because the H7142 occasionally drops a closer-spaced second command (verified empirically). 200ms is generous for the cloud round-trip.

### Stage band reference

Stage → VPD band lookup comes from `dirt.services.grow_state.STAGE_TARGETS`:

| Stage | VPD band (kPa) | Setpoint (PI) |
|---|---|---|
| `veg` | 0.7 – 1.0 | 1.0 (lights-on); 0.7 (lights-off, with -0.3 kPa night offset) |
| `flower_early` (days 0–20 of 12/12) | 1.0 – 1.3 | 1.3 / 1.0 |
| `flower_late` (day 21+ of 12/12) | 1.2 – 1.5 | 1.5 / 1.2 |

RH ceiling envelope (mold prevention): `veg=(40,70)`, `flower_early=(40,60)`, `flower_late=(35,55)`.

Lights schedule comes from `growstate.lights_on_local` / `growstate.lights_off_local`, interpreted in `growstate.timezone` (default `America/Denver`). Defaults: veg 18/6 → (05:00, 23:00). Flip via SQL when the photoperiod changes; the loop picks it up on the next tick.

**Why these choices:**

- **VPD, not RH.** RH at a fixed setpoint mis-targets the plant: when temperature falls at night, the same RH produces a much lower VPD. VPD collapses this into one number that's correct across the day/night swing. See [concepts/vpd.md](../concepts/vpd.md).
- **Upper-edge setpoint.** The humidifier only adds moisture; there's nothing to do when VPD is already in or below the band. Acting only at the dry edge keeps the duty cycle low.
- **PI, not bang-bang.** Continuous-intensity actuator (9 levels). Big dead time. Asymmetric transfer function (can add moisture, can't actively remove). PI gives smooth response without the relay-cycling problem the bang-bang had on the Kasa. The 0.4 kPa deadband in the old loop was actuator-overshoot-sized — the PI eliminates it by ramping intensity instead of slamming the plug on/off.
- **Feedforward, not derivative.** Dominant disturbance (lights on/off) is scheduled and periodic — use the clock to anticipate it. Derivative on sensor noise has 5-min smoothing lag and near-unit SNR for the signals we care about.
- **−0.3 kPa night offset.** Falls inside the published "0.2–0.4 kPa below day" range (Pulse Grow, GrowSensor, Anden). Preserves band width across stages.
- **5 min prep window.** Sized to one tent-fan-volume turnover so the humidifier isn't actively misting at the lights transition. Symmetric pre-lights-off and pre-lights-on.
- **Live-state diffing.** Source of truth is what the device reports, not what we last commanded. Divergence self-heals.
- **No max-on / min-off guard.** PI integrator clamp (anti-windup) is the right tool for that — bounding u, not the plug.
- **Failsafe OFF on stale reads** — prefer brief dryness over runaway mist.

## State Logging

Three streams feed three consumers:

- **`sensorreading`** (DB):
  - `humidifier_on` (0/1) every poll, `source="govee"`, `location="tent"`
  - `humidifier_mist_level` (0..9) every poll — actuator commanded level
- **`logs/humidifier/YYYY-MM-DD.jsonl`** — operational state-change events:
  - `state_change` (power transitions, with new level/u_pct/reason/VPD/band/lights context)
  - `level_change` (level transitions while powered, with from/to and u_pct)
  - `lack_water` / `lack_water_cleared` (rising/falling edges of lackWaterEvent)
  - `device_offline` / `device_online` (Govee cloud reachability transitions)
  - `suspected_ineffective` (commanded mist for ≥20 min, VPD didn't drop ≥0.15 kPa)
  - `rate_limited` (HTTP/code 429 from Govee — quiet log; next tick retries)
  - `error` (any other exception in the tick body)
  - `skip_offline` (per-tick when device offline; PI ran but no actuation)
- **`logs/humidifier_shadow/YYYY-MM-DD.jsonl`** — per-tick PI raw output (u_pct, P/I split, integrator, error, setpoint, reason) for diagnostic replay against the analyzer at `debug/humidifier-shadow/analyze.py`. Promoted from "what would PI do" (2026-04-25 to 2026-04-27) to "what PI is actually emitting before quantization" — same fields, different role.

State-change reasons (from PI): `pi_active`, `failsafe_stale_sensor`, `outside_lights_window`, `rh_ceiling`. Each event also carries `lights_on`, `minutes_until_off`, and the active stage band so a log line fully determines which rule fired. Manual overrides via the Govee Home app are observed on the next state read and dispatched against (the loop will revert them within 30 s if they conflict with the PI's current target).

## Known Issues

### Tank empty (`lackWaterEvent`)

The H7142 surfaces tank-empty as an `event`-typed capability — `/device/state` includes a `lackWaterEvent` capability **only while the event is active**. Loop tracks the rising and falling edges, fires a single Telegram alert per refill cycle, and emits `lack_water` / `lack_water_cleared` log events. Replaces the Raydrop "red LED latch" check entirely.

Refill the 6 L tank — the H7142 resumes misting on its own once water clears the float sensor. No power-cycle dance needed.

### Ineffective actuator (still possible)

The `lackWaterEvent` only catches the empty-tank case. Other failure modes — atomization plate fouled by mineral scale, mist landing on the room not the canopy, firmware glitch — show up as "we keep commanding mist but VPD doesn't drop." Watchdog at `humidifier.py:update_ineffective_state` fires when commanded level ≥ 1 for ≥ `ineffective_alert_after_s` (default 1200 s = 20 min) with VPD drop < `ineffective_min_vpd_drop_kpa` (default 0.15 kPa). One Telegram alert per streak.

**Prevention:** distilled or RO water only. Weekly 1:1 white-vinegar descale of the base + atomization disc, 15–20 min, rinse, air dry.

### Govee cloud reachability

API is cloud-only. If `openapi.api.govee.com` is unreachable (ISP outage, Govee maintenance), the loop:
- Logs `error` events (failed control or state calls)
- Emits `device_offline` when the H7142's `online` state flips false (it goes offline ~1 min after losing Govee cloud sync, even if the LAN side is fine)
- Skips dispatch while offline; PI continues to compute u_pct for shadow logging

No LAN fallback exists for the H71xx humidifier line — confirmed via Govee API docs and live testing 2026-04-27.

### BME280 drift (resolved-by-transition 2026-04-23)

**Resolved** by retiring the Arduino Nano + BME280 for the ESP32-C3 + SHT45 combined fan-controller board (see [fan control + tent sensor](ac-infinity-fan-control.md), [decision 2026-04-22](../decisions/2026-04-22-sht45-tent-node-esp32.md)). All `source=arduino` tent readings prior to 2026-04-23 00:22 MDT are biased high on RH / low on VPD by an unquantified amount. Current-grow trend claims based on pre-cutover sensor data should be read against this caveat.

## Coupling with fan exhaust rate

Pre-H7142 observation: at fan 30 % + Raydrop dial mid, VPD tracked setpoint and the bang-bang oscillated gently. Bumping fan to 40 % tipped the balance — exhaust exceeded the Raydrop's max emission rate, the plug pinned ON, VPD climbed 1.20 → 1.50 kPa over 1h 40m. Raydrop dial was a hidden input.

**Post-H7142:** the dial is gone — the H7142 has 9 levels of mist, all software-readable + writable. The PI integrator can ramp through them in response to error. Fan-vs-humidifier saturation is still possible (the H7142 max output is 300 ml/h cool-mist; if the fan is at 100% the loop will saturate at level 9), but the watchdog catches it (`suspected_ineffective` after 20 min). Saturation now triggers an alert instead of silently failing.

## Safety / Operational Notes

- **No mains wiring to do.** H7142 is a sealed consumer device; smart control is native.
- **Plug placement:** the H7142 itself plugs into a wall outlet outside the tent's splash zone. A short cord into the tent is fine.
- **Fail-safe priority:** stuck-off is safer than stuck-on. Damping-off and mold are worse than a dry spell. The PI defaults to `u=0` on any ambiguity (stale sensor, outside-window, RH ceiling, transport error).

## Acceptance

- H7142 cycles through Manual-mode levels via Govee API based on tent VPD without manual intervention.
- VPD stays inside the active stage band for 24h continuous across the day/night swing (re-verify post-step-test refit; conservative gains may track a bit slowly initially).
- Plug state + commanded level logged alongside VPD; transition events carry the band edges that were active at decision time.
- Simulated sensor failure triggers failsafe `u=0` within the failsafe window (300 s default).
- Veg→flower flip (via a `grow_state.flower_start_date` write) shifts the upper-edge setpoint on the next poll without a service restart.
- `lackWaterEvent` rising edge fires exactly one Telegram alert per refill cycle.

## Future work

### FOPDT refit for H7142

Step-test the H7142 to derive new IMC gains. Hold each of `{level 2, 5, 8}` for ~20 min in lights-on steady state, capture the shadow-stream traces, refit FOPDT against the result, derive `(Kc, Ki)`. Methodology unchanged from the abandoned Raydrop FOPDT plan (see [docs/epics/continuous-humidifier/fopdt-fit-findings.md](../../docs/epics/continuous-humidifier/fopdt-fit-findings.md)) — only the input data source changes from "shadow stream against Kasa actuation" to "shadow stream against H7142 Manual-mode actuation."

### Hysteresis tuning

3% half-band at level boundaries is a default — may be too tight or too loose against the H7142's actual mist-rate granularity. Watch `level_change` event cadence; aim for < 5 transitions per hour at steady state.
