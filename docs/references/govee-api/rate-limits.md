---
title: Govee API — Rate Limits & Quotas
parent: docs/references/govee-api/INDEX.md
updated: 2026-04-26
---

# Rate limits — two ceilings stacked

Govee enforces **two limits simultaneously**. Stay under both.

| Limit | Scope | Value |
|---|---|---|
| Daily | Per account (across all devices, all endpoints) | **10,000 requests / 24h rolling window** |
| Per-device burst | Per device | **~10 control changes / minute** |

Sources: [Govee rate limiting docs](https://govee.readme.io/reference/rate-limiting), and the well-documented community pain on the daily ceiling at [LaggAt/hacs-govee #107](https://github.com/LaggAt/hacs-govee/issues/107) and [#129](https://github.com/LaggAt/hacs-govee/issues/129).

Both `/device/control` and `/device/state` count against the daily 10K. `/user/devices` counts too but is called only at startup.

## What this means for the humidifier loop

The current `HumidifierLoopService` runs at ~30 s tick. Worst-case per-tick API traffic is:

- 1× `/device/state` to read current state (only if we want closed-loop verification)
- 1× `/device/control` if a state change is needed

Worst-case daily traffic at 30 s ticks with a state-change every tick: `2 × 2880 = 5760 calls/day` — **57% of the budget**. With state changes only on actual transitions (the bang-bang norm — most ticks do nothing) we use a small fraction of that.

**Comfortable.** Don't tighten the loop below 30 s without reconsidering. Don't add per-second polling for "live UI" purposes against the same key.

## Headers

The Govee API returns rate-limit headers on success/failure:

```
API-RateLimit-Limit:     10000
API-RateLimit-Remaining: 9847
API-RateLimit-Reset:     1714088400      # epoch seconds
```

Log these on every call (or at least every 100th call) so we can spot drift. Surface a warning to Telegram if `Remaining < 1000` so we have time to react before getting 429'd.

## 429 response shape

```json
{
  "requestId": "<echo>",
  "code":      429,
  "msg":       "Rate limit exceeded",
  "data":      {}
}
```

(HTTP status is also 429.) Back off with jitter; don't hammer-retry. There's no `Retry-After` header documented — assume at least 60 s before the next attempt, and re-read the `API-RateLimit-Reset` header on the next successful call to plan further.

## Things that quietly burn through quota

- **Polling for state** in a UI tile that auto-refreshes. Don't proxy the live UI through Govee — read our own DB instead and only call Govee from the control loop.
- **Re-discovery** (`/user/devices`) on every loop start. Discover once, cache.
- **Multiple processes sharing one API key** without coordinating. Two `dirt-hwd` instances during a deploy will double the rate. Stop the old one before starting the new one.
- **Per-tick state confirmation** ("did my command actually take?") if you confirm by polling. Cheaper: trust the response code from `/device/control`, only `/device/state` after a suspect failure.

## Things that don't help

- **Backing off `/device/control` calls under load** — the device's own internal cycle (especially in Auto mode) doesn't count against our quota. Reducing our actuator commands doesn't free more "headroom"; we're our own only consumer of the budget.
- **Multiple API keys for one account** — Govee scopes the quota to the account, not the key. Generating extra keys does nothing.
