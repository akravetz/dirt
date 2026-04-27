---
title: Govee API — Gotchas & Failure Modes
parent: docs/references/govee-api/INDEX.md
updated: 2026-04-26
---

# Things that will bite you

## Cloud-only — no LAN fallback for humidifiers

Unlike Kasa (which has a documented LAN protocol and `python-kasa` talks to plugs over the local network), the Govee humidifier API is **strictly cloud**. Every command flows: `dirt-hwd` → Internet → `openapi.api.govee.com` → Govee cloud → back over the Internet → tent humidifier on local Wi-Fi.

Implications:

- **WAN outage = no humidifier control.** A residential Internet outage at the wrong time of the grow window can leave the tent humidity-uncontrolled for hours.
- **Govee outage = no humidifier control.** Same risk, smaller surface but harder to diagnose since the path is opaque.
- **Latency floor is ~hundreds of ms.** Fine for a 30 s tick. Disqualifying for any ms-scale control. We're nowhere near that, but if a future use case wants tight loops, this device isn't the answer.

A subset of Govee **lighting** products supports LAN UDP control. Humidifiers (every H71xx including our H7142) do not. There is no roadmap commitment to add it.

**Mitigation:** the humidifier loop's existing failsafe-stale-sensor branch covers this — if we can't reach the device cloud or get fresh state back, the loop should default to "humidifier off" rather than "stuck in last commanded state." Pair with a Telegram alert on extended unreachability.

## Capability discovery is the only honest source of truth

Marketing copy on the Govee product page lists features in plain English. The Govee Home app exposes a smaller subset. The API capability discovery returns the actual surface that's wired up in firmware. **These three sets do not always agree.**

Always run `POST /user/devices` against your specific device, log the full `capabilities` array, and treat that as the contract. Don't trust this doc, the marketing page, or community wisdom over a fresh discovery response from your physical device.

## `device` is the MAC, formatted with colons, uppercase, with two extra octets

The `device` identifier returned by discovery looks like `AB:CD:EF:12:34:56:78:90` — 8 octets, not 6, and it is **not interchangeable with the Wi-Fi MAC** of the device. It's Govee's internal addressing scheme. Use whatever discovery returns verbatim. Don't try to derive it from the device's Wi-Fi MAC.

## `requestId` is correlation, not idempotency

Reusing the same `requestId` does not deduplicate retries server-side. If your retry logic resends the same control request, the device will execute it twice (no harm for idempotent commands like `power on`, harmful for things like "set custom mode"). Generate a fresh UUID per attempt.

## API key is account-scoped — protect it

The key from `Profile → About Us → Apply for API Key` can read **and write** every device on the account. There's no per-device or per-capability scoping. Treat it like a root credential:

- Store in `.env` (`GOVEE_API_KEY=...`), not in code or commits
- Don't share between hosts that don't all need full access
- Rotate by re-applying via the app — invalidates the old key

## The work_mode `STRUCT` value can break parsers

Most capability values in the API are scalars (`int` or string). `workMode` is a struct: `{workMode: <int>, modeValue: <int>}`. A naïvely-typed Python dataclass that assumes `state.value: int` will crash here. Type as `int | dict[str, int]` or use a discriminated union per capability type.

## Auto mode's RH setpoint floor is **40%**, not 0

The H7142's `humidity` range (Auto mode setpoint) is **40–80%** — same across the H71xx line. You cannot set a target below 40%. For a flower-late stage where stage RH ceiling is 55%, the device can target inside-band; for any future stage where you'd want lower RH, the device cannot help — but that's also outside the realistic range for a humidifier (sub-40% RH belongs to a dehumidifier's job, which we don't have yet). Note: we drive in Manual mode, not Auto, so this range is informational — Manual-mode `modeValue` ∈ 1..9 has no RH-bound coupling.

## "Off" via Auto mode means "in Auto mode, idle" — not powered off

If you have `workMode = Auto` and the current RH exceeds the setpoint, the device internally idles its mister but **stays in standby with the indicator lit**. To fully power-off (e.g. for a lights-off humidifier kill window) you must send `powerSwitch = 0` separately. Don't conflate "below setpoint" with "off."

## Lack-water event is read-only and only present-while-active

`lackWaterEvent` is an `event`-type capability. It only appears in `/device/state` responses while the alarm is active. If your code keys off "is the lackWaterEvent key present in state.capabilities?" you'll get a falsy reading once water is refilled. Treat absence as "no current alarm," not as "no alarm capability."

## Govee can change capabilities without notice

Firmware updates have historically added/removed capabilities silently. The H71xx capability list documented in [h714x-capabilities.md](h714x-capabilities.md) is a snapshot — the H7140's full list is verified per disforw/goveelife issue #6 (2026-04); the H7142's full list is **inferred from the shared API shape and the H7142 user manual** and pending live confirmation when the device arrives 2026-04-27. Re-discover quarterly (or when the device behaves unexpectedly) and update the doc.
