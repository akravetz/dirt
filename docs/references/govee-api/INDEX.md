---
title: Govee Developer API Reference Pack
concept: govee-api
mode: hosted-cloud-api
api_version: Public API v2 (openapi.api.govee.com/router/api/v1)
updated: 2026-04-26
---

# Govee Developer API (Public v2)

This pack covers the **Govee Public API v2** at `https://openapi.api.govee.com/router/api/v1/`, the cloud-only HTTP surface used to discover and control Wi-Fi-connected Govee devices. We use it to drive a **GoveeLife Smart Humidifier model H7142** (6 L cool-mist ultrasonic, 9 Manual-mode levels) as the tent humidifier — replacing the Raydrop KC-RD03A + Kasa EP10 + planned MCU mist-intensity mod (see [pivot decision 2026-04-26](../../../wiki/decisions/2026-04-26-govee-humidifier-pivot.md)). The capability shape is shared across the H71xx humidifier line; per-SKU differences are documented in [h714x-capabilities.md](h714x-capabilities.md).

## When to consult this pack

Read this INDEX first (and the linked topic files) before writing code that:

- Calls `https://openapi.api.govee.com/router/api/v1/...`
- Uses the `Govee-API-Key` header
- Sends a JSON body with the shape `{requestId, payload: {sku, device, capability: {...}}}`
- Edits the humidifier control loop in `apps/hwd/src/dirt_hwd/services/humidifier.py` post-pivot
- Builds any Python client wrapper around Govee for `apps/shared/src/dirt_shared/services/`
- Decides between Manual and Auto work mode, sets a humidity setpoint via the API, or wires up the lack-water event

Prefer what is in this pack over recollection. The Govee API has **two coexisting surfaces** — the legacy v1 (different paths, different capability shape) and the current v2 used here. Training data still mixes them. Public docs live at `developer.govee.com` and `govee.readme.io` but the readme.io renders are sparse — community sources (the disforw/goveelife Home Assistant integration, the wez/govee2mqtt project, scattered blog posts) carry the real surface area.

## TL;DR — control shape

```http
POST https://openapi.api.govee.com/router/api/v1/device/control
Content-Type: application/json
Govee-API-Key: <your api key>

{
  "requestId": "<uuid v4>",
  "payload": {
    "sku": "H7142",
    "device": "<device MAC, colon-separated, uppercase>",
    "capability": {
      "type":     "devices.capabilities.on_off",
      "instance": "powerSwitch",
      "value":    1
    }
  }
}
```

Discovery shape (one-time at startup, then cache):

```http
POST https://openapi.api.govee.com/router/api/v1/user/devices
Govee-API-Key: <your api key>
```

Returns every device on the account with its `sku`, `device` MAC, friendly name, type (e.g. `devices.types.humidifier`), and the **full capability list with parameter ranges/options**. Full request/response shapes in [control.md](control.md). Per-device discovered capability list for the H7142 (and the rest of the H71xx line) in [h714x-capabilities.md](h714x-capabilities.md).

## Topics

- **[control.md](control.md)** — Endpoint URLs, HTTP shape, authentication header, request body wire format, response envelope and the `code/message/data` triplet semantics. Idempotency & `requestId` rules.
- **[h714x-capabilities.md](h714x-capabilities.md)** — Capability map for the H71xx humidifier line, with the H7142 (deployed) called out. Each capability with its `type` / `instance` / `parameters` (data type, options/ranges) and what value to send to do what. The Manual vs Custom vs Auto work modes and what each one actually does. The `lackWaterEvent` event capability. Per-SKU comparison table (H7140 / H7142 / H7143).
- **[rate-limits.md](rate-limits.md)** — Two stacked quotas (per-account daily, per-device per-minute). What the response headers tell us about remaining budget. The 429 shape. How to design a control loop that stays under both ceilings (the 30s humidifier loop is fine; tighter polling is not).
- **[gotchas.md](gotchas.md)** — Cloud-only (no LAN fallback for humidifiers, unlike Kasa); the API key is account-wide and rotatable; `device` field is MAC-with-colons (not hex); `sku` and `device` are both required on every call; capability discovery is the only way to know what the device actually supports — silkscreen/marketing copy lies.

## Things to ignore (training-data drift)

- ❌ **Govee API v1 endpoints** at `developer-api.govee.com/v1/devices/control` with the `cmd: {name, value}` payload shape. That's the old (still working but deprecated) light-only API. ✅ Use v2 at `openapi.api.govee.com/router/api/v1/` with the `capability: {type, instance, value}` payload shape.
- ❌ **`X-Govee-API-Key` or `Authorization: Bearer …`** as the auth header. ✅ The header name is exactly `Govee-API-Key` with the raw key as its value.
- ❌ **Hard-coded `"value": <int>`** without first discovering capability options. Different SKUs use different value enums for the same instance name; always read `parameters.options` from the discovery response.
- ❌ **LAN-only Govee API for non-light devices.** A subset of Govee lighting products supports LAN UDP control, but humidifiers (every H71xx model including our H7142) are cloud-only. Design for `openapi.api.govee.com` reachability or fail-safe.
- ❌ **Polling for state at high cadence** to drive a tight control loop. State queries count against the per-account 10K/day budget too. The device emits state changes back through the cloud; if you want push-style updates, look at the Govee event/webhook hooks rather than polling.

## Source links (for future agents needing more depth)

- [Govee Developer API homepage](https://developer.govee.com/)
- [Public API v2 reference (readme.io render)](https://govee.readme.io/reference/getting-started)
- [Control endpoint reference](https://developer.govee.com/reference/control-you-devices)
- [Get device state reference](https://developer.govee.com/reference/get-devices-status)
- [Rate limiting reference](https://govee.readme.io/reference/rate-limiting)
- [Reference v2 PDF (canonical, S3-hosted)](https://govee-public.s3.amazonaws.com/developer-docs/GoveeDeveloperAPIReference.pdf)
- [disforw/goveelife — Home Assistant integration tracking the v2 API surface](https://github.com/disforw/goveelife)
- [disforw/goveelife issue #6 — H7140 capability discovery JSON, verbatim (same shape applies to H7142)](https://github.com/disforw/goveelife/issues/6)
- [wez/govee2mqtt — separate community client, useful cross-reference for capability shapes](https://github.com/wez/govee2mqtt)
- [Carrington's blog — practical H7140 control example (translates directly to H7142)](https://blog.thecarringtons.org.uk/story/posts/humidifer.md)
- [GoveeLife H7142 user manual (manuals.plus)](https://manuals.plus/govee/h7142-smart-humidifier-manual) — confirms 9 mist levels via app
- [GoveeLife H7142 user manual (ManualsLib)](https://www.manualslib.com/manual/2707587/Govee-H7142.html)
- [GoveeLife H7142 on Amazon (B098PWLX4C)](https://www.amazon.com/Govee-Humidifiers-Humidifier-Essential-H7142101/dp/B098PWLX4C)
- [GoveeLife H7140 product page (Lite, 3L — earlier comparison)](https://www.goveelife.com/products/goveelife-smart-home-appliances-H7140)
- [GoveeLife H7143 Smart Humidifier Max (7L — earlier comparison)](https://us.govee.com/products/goveelife-smart-humidifier-max)
