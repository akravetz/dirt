---
title: Govee API — H71xx Humidifier Line Capability Map (deployed: H7142)
parent: docs/references/govee-api/INDEX.md
deployed_sku: H7142
updated: 2026-04-26
---

# Govee H71xx Humidifier Line — Capability Map

The Govee H71xx ultrasonic humidifier line shares one API capability shape (`workMode` STRUCT + `lackWaterEvent` + `humidity` range + on/off + nightlight). **Per-SKU differences are limited to**: tank size, mist intensity granularity (8 vs 9 discrete Manual-mode levels), warm-mist support, and a handful of secondary features (UVC light, aroma pad). Code written against any one SKU should work against another with only the SKU string changing — but always run `POST /user/devices` against the actual physical device to confirm the live capability list before relying on any specific instance name.

## Our deployment: **H7142** (6 L cool-mist, 9 Manual-mode levels)

The dirt grow tent runs the **GoveeLife Smart Humidifier H7142**, chosen 2026-04-26 over the H7140 (3 L Lite) and H7143 (7 L Max) in this line. Picked for the combination of:

- **9 mist levels via API** (one more than the H7140/H7143's 8) — the most granular dispatch available in the Govee humidifier line at consumer prices
- **6 L tank** — middle ground between the H7140 (3 L → daily refill) and H7143 (7 L → twice-weekly refill); roughly 3-day refill cadence in flower-stage demand
- **Same API contract as the rest of the line** — the reference pack applies unchanged
- **Cool mist only** — what we want; warm mist (H7143) is irrelevant in a tent already at 70-75°F

History: ordered an H7140 first (arriving 2026-04-27 as a backup; was the cheapest path to "Govee humidifier in the tent" while we were still de-risking the pivot off the Raydrop). Upgraded the order to H7142 the same day after a fuller granularity/tank comparison across the line. The H7140 unit may end up retained as a spare or returned.

## Per-SKU comparison (H71xx line, 2026-04 snapshot)

| | H7140 (Lite) | **H7142 (deployed)** | H7143 (Max) |
|---|---|---|---|
| Tank | 3 L | **6 L** | 7 L |
| Mist type | Cool | Cool | Cool + Warm |
| **Manual-mode API levels** | 8 | **9** | 8 |
| On-device button cycle | 3 levels | Auto + 3 levels | Auto + 3 levels |
| Auto-mode RH range | 40–80% | 40–80% (default 60%) | 40–80% |
| Max output | ~200 ml/h | 300 ml/h | 650 ml/h (warm) |
| Runtime on low | ~30 h | 60 h | 70 h |
| Aroma diffuser pad | ❌ | ✅ | ❌ |
| UVC sterilization light | ❌ | ✅ | ❌ |
| RGB nightlight | ✅ | ✅ | ✅ |

The H7142's "kitchen-sink" extras (aroma pad, UVC light) are firmware capabilities we ignore — additional `toggle`/`mode` capabilities will appear in the discovery response, just don't bind to them.

## Shared capability list (verified for H7140 per disforw/goveelife issue #6, **expected to apply to H7142 with one extra Manual-level value and additional UVC/aroma capabilities**)

Always verify against your specific device's live discovery response — Govee can ship capability changes via firmware update without warning, and the H7142's full list hasn't been captured here yet from a live device. Re-discover at runtime and update this doc once the H7142 is provisioned 2026-04-28.

> **⚠ The "9 Manual-mode levels" claim is from marketing, not from a live API discovery.** The H7142 user manual states "9 levels of mist via the Govee Home App," but the API can drift from the app UI — the H7140's manual says "low/med/high" but its API exposes 8 levels. **Run discovery against the physical H7142 once provisioned and confirm the actual `workMode.parameters.fields.modeValue.range` value.** If the API exposes 8 levels (or any other count), update the level count throughout this doc and the dispatch quantization in `humidifier.py` to match. Not a blocker — the controller and tests don't hard-code the level count.

| # | type | instance | dataType | What it does | Send to control |
|---|---|---|---|---|---|
| 1 | `devices.capabilities.on_off` | `powerSwitch` | ENUM | Master on/off | `value: 1` (on) / `value: 0` (off) |
| 2 | `devices.capabilities.work_mode` | `workMode` | STRUCT | Mode + mode-specific level | See "Work modes" below |
| 3 | `devices.capabilities.range` | `humidity` | INTEGER | Auto-mode RH setpoint, **40–80%** | `value: 55` for 55% RH target |
| 4 | `devices.capabilities.toggle` | `nightlightToggle` | ENUM | Nightlight on/off | `value: 1` / `value: 0` |
| 5 | `devices.capabilities.range` | `brightness` | INTEGER | Nightlight brightness, **1–100** | `value: 50` |
| 6 | `devices.capabilities.color_setting` | `colorRgb` | INTEGER | Nightlight RGB packed as 24-bit int (`R<<16 \| G<<8 \| B`), **0–16777215** | `value: 16711680` (red) |
| 7 | `devices.capabilities.mode` | `nightlightScene` | ENUM | Preset scene: Forest / Ocean / Wetland / Leisurely / Sleep | `value: <enum from discovery>` |
| 8 | `devices.capabilities.event` | `lackWaterEvent` | EVENT (read-only) | Fires when the tank is empty (alarm type 51, single state `"lack"`) | n/a — read via `POST /device/state` |

**H7142 likely adds** (un-confirmed pending live discovery; H7142 user manual lists these as features):
- A `toggle` for **UVC sterilization light** on/off
- Possibly a `mode` capability for **aroma pad** behavior (or it may be passive — just toggleable nightlight rotation)

**Discover and confirm before relying on any of those.** If the H7142's Manual-mode `modeValue` range turns out to be `1..8` instead of `1..9` (firmware can drift between SKU advertised in marketing and what the API actually exposes), nothing breaks — the dispatch quantization just rounds to one fewer level.

## Work modes — the one to actually understand

`workMode` is a STRUCT capability. The value is `{workMode: <int>, modeValue: <int>}`:

| `workMode` value | Mode name | What `modeValue` means |
|---|---|---|
| 1 | **Manual** | Mist intensity level. **8 discrete levels (1–8) on H7140/H7143; 9 discrete levels (1–9) on H7142.** This is the humidifier-as-actuator option — closest analogue to the Raydrop's analog dial, but software-readable + software-writable. |
| 2 | **Custom** | A preset slot (1–N) that the user has saved in the Govee Home app. We won't use this. |
| 3 | **Auto** | Target RH setpoint. The device runs its own internal closed loop against the `humidity` capability's setpoint and decides when to mist on its own. |

The exact enum mapping (does `workMode: 1` map to "Manual" or "Custom"?) **must be confirmed against the actual discovery response** — the Govee docs and the community integrations disagree on the numbering for some SKUs. Run discovery, log `parameters.fields[*].options` for the `workMode` field, and trust that.

## How we use this device — Manual mode + our VPD PI loop

We drive the H7142 in **Manual mode**, with the intensity level (`modeValue` ∈ 1..9) commanded by the existing host-side PI controller on VPD error (`apps/hwd/src/dirt_hwd/services/humidifier_pi.py`). VPD-based control is settled per [decision 2026-04-18](../../../wiki/decisions/2026-04-18-vpd-targeting.md) and is the whole reason the controller, plant-in-loop tests, FOPDT fit, shadow logging, and analyzer/replay harness exist — the H7142 is just a different actuator at the dispatch boundary.

**Per-tick loop:**
1. Read VPD, derive setpoint from stage band + lights-off offset (unchanged from current code)
2. PI controller outputs `u_pct ∈ [0, 100]` (unchanged)
3. **Dispatch boundary** (new): quantize `u_pct → discrete Manual-mode level 1..9`. Cutoff: if `u_pct < sub_threshold`, send `powerSwitch = 0` (don't run the ultrasonic at useless levels — same logic as today's Kasa cutoff)
4. If the level changed since last tick: `POST /device/control` with `workMode = {workMode: <Manual>, modeValue: <level>}` (and `powerSwitch = 1` if it was off)
5. Otherwise: no API call. Hold.

The Auto-mode + RH-setpoint shape exists on the device but **we don't use it** — it's RH-only and the temperature swing across the day/night cycle gives the wrong VPD at a fixed RH (the exact failure mode the 2026-04-18 decision moved us off). Documenting the capability for completeness only.

### What needs re-tuning vs the abandoned Raydrop work

- **FOPDT plant model** — the H7142's mist rate (~300 ml/h max) ≠ Raydrop's. τ and K_per_pct will be different. Run the graduated step test (planned for Phase 4 acceptance under the Raydrop path) against the H7142 instead — hold each Manual level for ~20 min in lights-on steady state, refit FOPDT against the result, derive new IMC gains. Use levels 2, 5, 8 as the three sample points (low/mid/high across the 1-9 range). The methodology and the analyzer's `fopdt` section work unchanged; only the input data source changes from "shadow stream against Kasa actuation" to "shadow stream against H7142 Manual-mode actuation."
- **Quantization dead-zone at level boundaries** — to prevent limit-cycle chatter between adjacent levels (e.g. ticking 4↔5 every loop), add a small hysteresis around each rounding boundary. Cheap fix; covered by a property test.
- **Anti-windup integrator clamp** — unchanged. The clamp limit (50%) is still the right shape; only the units of the output change.

### What's unchanged from the shadow controller

- VPD setpoint logic, stage targets, lights-off offset, lights-on prep window, RH-ceiling envelope guard, failsafe-stale-sensor → OFF
- The `humidifier_shadow` stream's per-tick fields (`u_pct`, `error`, P/I split, integrator, reason)
- The analyzer's `reasons`/`pi`/`ceiling`/`replay` sections
- Property tests on monotonicity, saturation, anti-windup
- Plant-in-loop tests against the FOPDT simulator (parametrize against the new fit when it lands)

### Rate-limit budget

With 30 s ticks and `POST /device/control` only when the level actually changes, expected steady-state traffic is well under both quotas (10K/account/day, ~10/min/device). See [rate-limits.md](rate-limits.md) for the math.

## State to read back

In `POST /device/state` you'll get all the writable capabilities echoed plus `lackWaterEvent` when the tank is empty. The two we actually care about for ops:

- `state.value` of `powerSwitch` → did our `on/off` actually take?
- `state.value.workMode` and `state.value.modeValue` of `workMode` → confirm we're in the mode we think
- `state.value` of `humidity` → confirm the setpoint (only relevant if we ever use Auto mode, which we don't)
- Presence of `lackWaterEvent` in the response → tank empty, surface to Telegram

Don't poll this aggressively — see [rate-limits.md](rate-limits.md). Once per humidifier loop tick (30s) is the upper end of what's reasonable.
