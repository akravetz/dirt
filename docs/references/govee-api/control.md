---
title: Govee API — Control & State Endpoints
parent: docs/references/govee-api/INDEX.md
updated: 2026-04-26
---

# Endpoints, request/response shapes, auth

All endpoints are POST against `https://openapi.api.govee.com/router/api/v1/`. JSON body required even on operations that look like reads. Auth is a single header.

## Auth

Every request:

```
Govee-API-Key: <api key>
```

Get an API key from the Govee Home app: **Profile → About Us → Apply for API Key** (account email gets the key by mail within ~24 hours; the user already has theirs).

The key is **account-wide** — it can address every device on the account. Rotate by re-applying; the previous key is invalidated.

## Endpoints

| Path | Purpose | When to call |
|---|---|---|
| `POST /user/devices` | List every device on the account, with full capability discovery per device | Once at startup; cache result. **Re-fetch only on device add/remove.** |
| `POST /device/state` | Read current state of one device | Whenever you need fresh state. Counts against quota — don't poll. |
| `POST /device/control` | Send a single capability change to one device | Every time you want the device to do something different |

## Request envelope (every call)

```json
{
  "requestId": "<uuid v4 you generate per call>",
  "payload": { ...see below per endpoint... }
}
```

`requestId` is purely a correlation id you choose — Govee echoes it in the response. **It is not idempotency-keyed**: sending the same `requestId` twice does not deduplicate. If you want at-most-once semantics, dedupe on your side.

## Response envelope (every call)

```json
{
  "requestId": "<echo of yours>",
  "msg":  "success",
  "code": 200,
  "data": { ...endpoint-specific... }
}
```

`code` mirrors HTTP status for the happy path; for application-level failures the HTTP layer can still be 200 while `code` is 400/401/403/429. **Always check `code`, not just HTTP status.** Common failure codes:

| `code` | Meaning |
|---|---|
| 400 | Malformed payload (missing field, wrong shape, capability not supported by this SKU) |
| 401 | Missing or invalid API key |
| 403 | API key valid but doesn't own this device, or device offline |
| 429 | Rate limit exceeded (see [rate-limits.md](rate-limits.md)) |
| 500 | Govee cloud error — retry with backoff |

## `POST /user/devices` — discovery

**Request payload:** empty object `{}` (the body is `{requestId, payload: {}}`).

**Response `data.devices`:** array of device objects. Each one looks like:

```json
{
  "sku":        "H7142",
  "device":     "AB:CD:EF:12:34:56:78:90",
  "deviceName": "Tent Humidifier",
  "type":       "devices.types.humidifier",
  "capabilities": [
    { "type": "devices.capabilities.on_off",   "instance": "powerSwitch", "parameters": {...} },
    { "type": "devices.capabilities.work_mode","instance": "workMode",    "parameters": {...} },
    { "type": "devices.capabilities.range",    "instance": "humidity",    "parameters": {...} },
    ...
  ]
}
```

The full per-device capability list is the **authoritative source of truth** for what you can send to that device — every `parameters.options` enum or `parameters.range` numeric bound below is what the cloud will accept. Cache the discovery result and re-discover only when a device is added/removed; it's the most expensive call quota-wise to repeat.

For the H71xx line's capability list (and our H7142 deployment specifics) see [h714x-capabilities.md](h714x-capabilities.md).

## `POST /device/state` — read current state

**Request payload:**

```json
{
  "requestId": "<uuid>",
  "payload": {
    "sku":    "H7142",
    "device": "AB:CD:EF:12:34:56:78:90"
  }
}
```

**Response `data.capabilities`** is an array of `{type, instance, state: {value}}` objects, one per readable capability on that device. Example slice:

```json
[
  {"type": "devices.capabilities.on_off",    "instance": "powerSwitch", "state": {"value": 1}},
  {"type": "devices.capabilities.work_mode", "instance": "workMode",
   "state": {"value": {"workMode": 1, "modeValue": 5}}},
  {"type": "devices.capabilities.range",     "instance": "humidity",    "state": {"value": 60}}
]
```

State events for `event`-typed capabilities (e.g. `lackWaterEvent`) come back here as `{state: {value: {... event payload ...}}}` only when the event is currently active.

## `POST /device/control` — send a command

**Request payload:**

```json
{
  "requestId": "<uuid>",
  "payload": {
    "sku":    "H7142",
    "device": "AB:CD:EF:12:34:56:78:90",
    "capability": {
      "type":     "devices.capabilities.on_off",
      "instance": "powerSwitch",
      "value":    1
    }
  }
}
```

`value` shape depends on the capability's `parameters.dataType`:

| `dataType` | `value` shape |
|---|---|
| `ENUM` | The numeric `value` from `parameters.options` (e.g. `1` for "on") |
| `INTEGER` | A plain integer within `parameters.range` (e.g. `60` for 60% humidity) |
| `STRUCT` | A nested object whose fields match `parameters.fields` (e.g. work_mode wants `{workMode: <enum>, modeValue: <int>}`) |

**One capability per call.** To turn the unit on AND set a humidity setpoint AND set work_mode=Auto, send three separate `POST /device/control` requests. Don't try to bundle them; the API rejects multi-capability bodies.

**No optimistic concurrency.** Last write wins. If two clients race, one of the writes is silently lost.

## Practical Python sketch

```python
import httpx, uuid

async def govee_call(client: httpx.AsyncClient, api_key: str, path: str, payload: dict) -> dict:
    body = {"requestId": str(uuid.uuid4()), "payload": payload}
    r = await client.post(
        f"https://openapi.api.govee.com/router/api/v1{path}",
        json=body,
        headers={"Govee-API-Key": api_key, "Content-Type": "application/json"},
        timeout=10.0,
    )
    r.raise_for_status()                    # catches transport-level failure
    body = r.json()
    if body["code"] != 200:                 # catches application-level failure
        raise RuntimeError(f"govee {path}: code={body['code']} msg={body['msg']}")
    return body["data"]

async def power(client, key, sku, device, on: bool):
    return await govee_call(client, key, "/device/control", {
        "sku": sku, "device": device,
        "capability": {
            "type": "devices.capabilities.on_off",
            "instance": "powerSwitch",
            "value": 1 if on else 0,
        },
    })
```

Place a real client at `apps/shared/src/dirt_shared/services/govee.py` once we cut over from the Kasa-plug Raydrop loop.
