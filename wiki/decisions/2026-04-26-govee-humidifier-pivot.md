---
title: "Pivot from Raydrop MCU Mod to Wi-Fi-Native Humidifier (Govee H7142)"
type: decision
sources: []
related:
  - wiki/decisions/2026-04-23-raydrop-mcu-mist-control.md
  - wiki/decisions/2026-04-17-humidifier-kasa-ep10.md
  - wiki/hardware/humidifier-control.md
  - docs/references/govee-api/INDEX.md
  - docs/epics/continuous-humidifier/README.md
created: 2026-04-26
updated: 2026-04-26
---

# Decision: Replace the Raydrop + Kasa stack with a Wi-Fi-native Govee H71xx humidifier (deployed: H7142)

**Date:** 2026-04-26
**Status:** Accepted. Hardware on order; H7142 arrives 2026-04-28 (H7140 also en route 2026-04-27 as the original-order backup, may be retained as spare or returned).
**Supersedes:** [2026-04-23 Raydrop MCU mist control](2026-04-23-raydrop-mcu-mist-control.md). The MCU-mod path is abandoned.

**Revision 2026-04-26 (same day).** Original order was the H7140 Smart Humidifier Lite (3 L, 8 Manual-mode levels). After fuller side-by-side comparison across the H71xx line later the same day, switched the deployment SKU to **H7142** (6 L cool-mist, 9 Manual-mode levels via API — one more level than H7140/H7143). Same API contract; only the SKU string changes. The H7140 remains en route as the de-risking backup. Per-SKU comparison table in [h714x-capabilities.md](../../docs/references/govee-api/h714x-capabilities.md). Decision body below preserves the H71xx line-level rationale.

## Context

The 2026-04-23 decision committed to opening up the Raydrop KC-RD03A and replacing its analog intensity potentiometer with an MCU-driven digipot or PWM line, then driving it from a host-side PI loop on VPD. The rationale was sound — three classes of operational failure (bang-bang overshoot oscillation, fan-coupling actuator saturation, and "hidden analog dial" gotcha) all trace back to the Raydrop being a single-speed actuator with a manually-set intensity cap.

Phase 4 prep work — the PI controller, ~45 unit + plant-in-loop tests, FOPDT fit, shadow-mode logging, analyzer/replay harness — landed on schedule and was running in shadow mode for ~36 h. **All of that work is sound and stays committed; it's just no longer needed for this hardware.**

Phase 1 (the open-up-and-probe investigation) ran into trouble:

1. **2026-04-25**: original spare Raydrop destroyed during disassembly.
2. **2026-04-26 evening**: replacement Raydrop on the bench. Probe session went deep but stalled. Established that the intensity pot is a 5 kΩ rheostat (only 2 of 3 terminals wired) but couldn't get a clean DC voltage sweep on the wiper — multiple ground-reference candidates failed (one suspected solder joint, others picked up from the wrong rail), and after suspecting the low-water sensor was gating the entire oscillator stage we didn't have the bench setup (board removed from base, water tank disconnected) to easily drive the unit into "running" state for live measurement. The user surfaced the right diagnosis (low-water cutoff suppressing the wiper signal) but the ergonomics of finishing the probe — re-mounting the board, defeating the water sensor with a jumper, redoing ground hunt — were no longer worth the cost relative to the alternative.

The deeper realization: a ~$50–60 humidifier with a Wi-Fi/HTTP API surface (the GoveeLife Smart Humidifier H71xx line: H7140 Lite ~$45, H7142 ~$60, H7143 Max ~$55) is a strictly better answer than rolling our own MCU-controlled mist intensity for a unit that resists reverse engineering. We were building bespoke hardware to compensate for a $5 cost-saving decision the Raydrop manufacturer made (no smart control), when an off-the-shelf product with the smart control we wanted exists at a similar price point.

## Decision

Deploy a **GoveeLife Smart Humidifier H7142** (6 L cool-mist ultrasonic) and integrate it via the **Govee Public API v2** (cloud HTTP, `openapi.api.govee.com`). Retire the Raydrop + Kasa EP10 stack from the live grow once the H7142 is provisioned and validated. (H7140 unit ordered earlier the same day as the de-risking backup; may be retained as spare or returned.)

The H7142 exposes (via API discovery, see [govee-api reference pack](../../docs/references/govee-api/INDEX.md)) — capability shape shared with the rest of the H71xx line:

- **Power** (`powerSwitch` on/off)
- **Work mode** (Manual / Custom / Auto), with Manual offering **9 discrete mist intensity levels** on H7142 (vs 8 on H7140/H7143) and Auto running an internal closed loop against an RH setpoint
- **Humidity setpoint** (40–80% RH, used in Auto mode — we don't use Auto)
- **Low-water event** (`lackWaterEvent`) — surfaced via `/device/state`, replaces our home-grown stuck-actuator watchdog for the empty-tank case
- Plus nightlight controls + UVC light + aroma diffuser we won't use

This collapses one sub-project and replaces another:
- The Raydrop hardware mod (Phases 1–3 of the [continuous-humidifier epic](../../docs/epics/continuous-humidifier/README.md)) — abandoned. No more probing, no MCU firmware, no digipot.
- **The PI controller, plant-in-loop tests, FOPDT fit, shadow logging, and analyzer/replay harness all stay live** — the H7142 just becomes the actuator at the dispatch boundary. `u_pct ∈ [0, 100]` quantizes to one of 9 discrete Manual-mode levels with a small hysteresis dead-zone at boundaries. FOPDT plant needs re-fitting against H7142 mist rate (graduated step test, originally planned for Phase 4 acceptance — same methodology, new actuator).
- The stuck-actuator watchdog for "tank empty" — replaced by the device's own `lackWaterEvent`.

**Integration shape:** drive the H7142 in **Manual mode** (`workMode = {workMode: Manual, modeValue: 1..9}`), commanded by the existing host-side PI controller on VPD error. VPD-targeting is settled per [decision 2026-04-18](2026-04-18-vpd-targeting.md) and remains the design — the H7142 is just a different actuator at the dispatch boundary. The device's built-in Auto mode (RH setpoint + internal closed loop) is RH-only and would walk back the VPD decision, so we don't use it. See [h714x-capabilities.md](../../docs/references/govee-api/h714x-capabilities.md) for the dispatch shape.

## Alternatives Considered

| Option | Why rejected |
|---|---|
| Continue the Raydrop MCU mod | The probe session demonstrated the cost of finishing is non-trivial (defeat low-water sensor, redo ground hunt, identify driver IC, build digipot, write firmware, test). For a unit that costs $40 and a path that's $45 with the API surface ready out of the box, the ratio isn't there. The Phase 4 PI work was the most uncertain part and it landed cleanly — the remaining work was all the bench/firmware path, which is exactly what the Govee unit eliminates. |
| Different Wi-Fi humidifier (Levoit, Vornado, Honeywell smart line) | Govee Public API is documented, has a working Home Assistant integration that proves the H71xx line specifically works, and the user already has a Govee account. No other vendor in this price class has a similarly-documented public API for humidifiers. |
| Govee H7140 (Lite, 3 L) — the original order | Same API contract as the H7142, but only 8 Manual-mode levels (vs the H7142's 9) and a 3 L tank that would force daily refills in flower-stage demand. Not a deal-breaker, just strictly worse on the two axes that matter (granularity + refill cadence). H7140 is still en route as the de-risking backup. |
| Govee H7143 (Max, 7 L, cool + warm mist) | Bigger tank than H7142 (7 L vs 6 L) is a marginal win, but only 8 Manual-mode levels (vs H7142's 9). Warm mist is irrelevant in a 70-75°F tent. Probably second-best pick if the H7142 has supply issues; not enough difference to prefer it over what's available now. |
| LAN-controllable humidifier (SwitchBot Smart Humidifier, Tuya/SmartLife with LocalTuya, Matter humidifier) | Three meaningful alternatives. **SwitchBot Smart Humidifier** (BLE local, 3.5 L, ~$50) was the first-choice "escape cloud" option but is no longer available on Amazon. **Tuya/SmartLife humidifiers** (LocalTuya HA integration, $30–80) require ~30 min one-time local-key extraction setup and granularity is typically only 3 levels — same or worse than Govee. **SwitchBot Evaporative (Matter, 4.5 L, $240)** is the price ceiling and uses evaporative not ultrasonic physics (different control dynamics). The cloud-dependency cost on Govee is bounded — failsafe-OFF on cloud unreachability + Telegram alert keeps the worst case at "tent gets a little dry during a multi-hour outage." Not worth $200 of premium nor LocalTuya setup tax to escape that. |
| Roll the same digipot mod into a fresh Raydrop after probing succeeds | Defers a known-good-already solution to chase a path that's already been hard. The MCU work was justifiable when the alternative was "no smart control"; once "buy smart control off the shelf for the same $40" became visible, the ROI flipped. |
| Stick with bang-bang on the Kasa EP10 forever | Has known operational failures (oscillation, fan coupling, dial gotcha) we already wrote a decision against. Kicking the can. |

## Consequences

### Wins

- **Single round-trip to add intensity control.** No firmware to write, no soldering, no PCB to modify, no second hardware probe session.
- **Built-in low-water detection.** The `lackWaterEvent` capability removes the need for our home-grown stuck-actuator watchdog. Telegram alerts wire directly to the event.
- **9 discrete intensity levels, software-addressable.** The PI controller's continuous output (`u_pct ∈ [0, 100]`) quantizes to one of 9 levels at the dispatch boundary. Resolution loss is well within the FOPDT plant time constants (τ ≈ 130 s) — far below the noise floor that would actually matter for VPD tracking.
- **Removes the "operator-set physical dial" failure mode.** The H7142 has no analog dial.
- **All Phase 4 prep work carries over.** PI controller, plant-in-loop tests, shadow logging, analyzer/replay harness — they stay live, just point at a different actuator. The graduated step test originally planned for Phase 4 acceptance becomes the H7142 plant-fit step.

### Losses

- **Cloud dependency.** Every command flows through `openapi.api.govee.com`. Internet outage = no humidifier control. Govee outage = no humidifier control. The Kasa EP10 talked LAN-locally; this is a regression on local autonomy. The existing failsafe-stale-sensor logic in `HumidifierLoopService` covers this gracefully (defaults to OFF on lost signal); add a Telegram alert on extended unreachability.
- **Rate limits.** Govee enforces 10K calls/account/day and ~10 changes/min/device. Comfortable for the 30 s loop with "only POST when the level changes," disqualifying for tighter polling. See [rate-limits.md](../../docs/references/govee-api/rate-limits.md).
- **Quantization dead-zone needed.** Naïvely rounding `u_pct → level` could induce limit cycles between adjacent levels (level 4 ↔ level 5 every tick when `u_pct` sits near the boundary). Add small hysteresis at each boundary. Cheap, one property test.
- **FOPDT plant needs refitting.** The H7142's mist rate isn't the Raydrop's. Run the graduated-step procedure against the H7142 once provisioned; refit τ and K_per_pct from the result; update `_SHADOW_PI_*` constants in `humidifier.py`. Same methodology that was already in the Phase 4 acceptance plan.
- **Net new cloud vendor in the loop.** One more SaaS dependency, one more account/key/quota. Govee's API is documented but smaller-scale than Kasa and has been known to ship breaking firmware capability changes.

### What stays unchanged

- The control loop's outer shape: read VPD per tick, target the stage band's upper edge, force OFF outside the lights window with prep margin, fail-safe OFF on stale sensor.
- The lights schedule + stage targets + grow-state-driven setpoint logic.
- The `humidifier` observability stream — same fields, source field changes from `kasa` to `govee`.
- The Telegram alerting envelope — `lackWaterEvent` plugs into the same alert pipeline.
- The Kasa EP10 hardware. We can keep the plug for unrelated future use (e.g. dehumidifier, when it arrives) or sell it.

## Rollout

1. **Hardware arrival (H7140 backup 2026-04-27, H7142 primary 2026-04-28)**: provision the H7142 via the Govee Home app (one-time onboarding to user's Wi-Fi + Govee account). The H7140 stays in the box as a known-good fallback unless the H7142 has issues.
2. **API key**: already obtained from the Govee Home app (`Profile → About Us → Apply for API Key`). Stash in `.env` as `GOVEE_API_KEY`.
3. **Discovery sanity check**: hit `POST /user/devices`, log the H7142's full capability list, verify against [h714x-capabilities.md](../../docs/references/govee-api/h714x-capabilities.md) and update that doc if anything has shifted in the live discovery response. **Specifically verify the `workMode` Manual-mode `modeValue` range** — the 9-level claim throughout this decision and the reference pack came from the H7142 user manual ("9 levels of mist via the Govee Home App"), but the API can drift from the app's UI (the H7140's manual says "low/med/high" but its API exposes 8 levels). If the H7142's API actually exposes 8 levels (or any other count), it's not a blocker — just update the dispatch quantization (`u_pct → level 1..N`), the step-test sample points (currently 2/5/8 assumes 1-9), and re-publish [h714x-capabilities.md](../../docs/references/govee-api/h714x-capabilities.md) with the verified count. Also confirm the H7142's full capability list in case the UVC light or aroma-pad features expose extra `toggle`/`mode` capabilities not yet documented (we'll ignore them, but they should appear in the doc for completeness).
4. **Bench script** in `debug/govee/` to: power-cycle the device via API, set Auto + a 55% setpoint, verify it actually misted, read state back, confirm `lackWaterEvent` triggers when the tank is drained. Throwaway code; not committed long-term.
5. **Production client**: add `apps/shared/src/dirt_shared/services/govee.py` mirroring the surface of the existing kasa client. Async methods for `set_power`, `set_work_mode(level)`, `get_state`.
6. **Graduated step test**: with the H7142 provisioned and unit running in Manual mode, hold each level (2, then 5, then 8 — three points across the 1-9 range, ~20 min each) in lights-on steady state. Capture VPD response in the shadow stream. Refit FOPDT (`debug/humidifier-shadow/analyze.py --section fopdt`); derive new IMC gains; update `_SHADOW_PI_*` constants in `humidifier.py`. Sanity check against the 2026-04-26 Raydrop fit (lights-on τ ≈ 133 s) — H7142 likely lands in a similar range but K_per_pct will differ.
7. **Loop swap**: promote shadow controller to authoritative. Replace `HumidifierLoopService`'s Kasa-plug actuation with the Govee Manual-mode dispatch. Add quantization (`u_pct → level 1..9`) with hysteresis dead-zones at boundaries. Sub-threshold cutoff sends `powerSwitch = 0` (same logic as today's plug-off). Keep all surrounding logic (stage targets, lights window, failsafe-stale-sensor, RH-ceiling envelope, observability stream) unchanged. Update the stuck-actuator watchdog trigger from `plug ON + VPD not falling` → `level > 0 + VPD not falling`, and wire `lackWaterEvent` to the existing Telegram alert path (replacing the home-grown empty-tank heuristic).
8. **Soak**: run authoritative for 48–72h. Compare VPD tracking against the bang-bang baseline; verify dead-zone tuning with the analyzer's `replay` section.
9. **Decommission Raydrop + Kasa**: physically remove from tent, document the swap on `wiki/hardware/humidifier-control.md`. Cancel the spare-pot order if it hasn't shipped.

## Not in Scope

- **Using the H7142's Auto mode.** It's RH-only and walks back the 2026-04-18 VPD-targeting decision. Documented in the reference pack as a capability the device exposes; not a path we take.
- **Dehumidifier integration.** Same as before — separate decision when the unit arrives.
- **Pulling the Raydrop entirely from the wiki.** Keep the page (and the failure-mode write-up under "Red LED") as historical context — the operational lessons (bang-bang oscillation under fan exhaust, low-water latch under hard water) generalize beyond this specific actuator.
- **Migrating the Kasa EP10 anywhere else.** Sits on the shelf for now; we'll find a use or sell it later.
- **Negotiating a higher Govee API quota.** The 10K/day ceiling is several × what we'll consume.
