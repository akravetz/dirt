"""Govee Public API v2 async client.

Thin wrapper over httpx.AsyncClient. No retries, no caching — the caller is
the retry boundary. Methods cover the four operations we need for the H7142
humidifier dispatch loop:

  - discover()          → GET  /user/devices
  - get_state(sku, mac) → POST /device/state
  - set_power(...)      → POST /device/control (on_off / powerSwitch)
  - set_manual_level()  → POST /device/control (work_mode / workMode STRUCT)

State parsing surfaces only the fields the loop cares about — online,
powerSwitch, workMode/modeValue, and presence of lackWaterEvent. Everything
else from the discovery / state response is dropped.

See docs/references/govee-api/INDEX.md for the wire format. The endpoint
methods (GET vs POST) and the message-field name ("message" on GET, "msg"
on POST) were verified live against the deployed H7142 on 2026-04-27 — the
public docs disagree.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import httpx

BASE_URL = "https://openapi.api.govee.com/router/api/v1"

WORKMODE_MANUAL = 1
WORKMODE_CUSTOM = 2
WORKMODE_AUTO = 3


class GoveeError(RuntimeError):
    """Non-success response from the Govee API. ``code`` is Govee's
    application-level code, which can diverge from HTTP status."""

    def __init__(
        self, code: int | None, message: str, *, http_status: int | None = None
    ) -> None:
        super().__init__(f"govee error code={code} http={http_status}: {message}")
        self.code = code
        self.message = message
        self.http_status = http_status


class GoveeRateLimitError(GoveeError):
    """Subclass for code=429 / HTTP 429 so the loop can swallow these
    quietly without alarm-level logging."""


@dataclass(frozen=True)
class DeviceInfo:
    sku: str
    device: str
    name: str
    type: str
    raw_capabilities: list[dict]


@dataclass(frozen=True)
class StateSnapshot:
    """Subset of /device/state that the humidifier loop reads each tick.

    Any field can be None if the device omits its capability from the
    response. ``lack_water`` is True iff the lackWaterEvent capability is
    present in the response — Govee only emits it while the event is
    active, so absence == "tank not empty".
    """

    online: bool
    power_on: bool | None
    work_mode: int | None
    mode_value: int | None
    lack_water: bool


class GoveeClient:
    def __init__(self, api_key: str, http: httpx.AsyncClient) -> None:
        if not api_key:
            raise ValueError("govee api key is required")
        self._key = api_key
        self._http = http

    def _headers(self) -> dict[str, str]:
        return {"Govee-API-Key": self._key, "Content-Type": "application/json"}

    @staticmethod
    def _check(body: dict, http_status: int) -> dict:
        code = body.get("code")
        # /user/devices returns "message"; POST endpoints return "msg".
        msg = body.get("msg") or body.get("message") or ""
        if code in (200, 0):
            return body
        if code == 429 or http_status == 429:
            raise GoveeRateLimitError(
                code, msg or "rate limited", http_status=http_status
            )
        raise GoveeError(code, msg or "unknown error", http_status=http_status)

    async def _get(self, path: str) -> dict:
        try:
            r = await self._http.get(f"{BASE_URL}{path}", headers=self._headers())
        except httpx.HTTPError as e:
            raise GoveeError(None, f"transport error: {e}") from e
        return self._check(r.json(), r.status_code)

    async def _post(self, path: str, payload: dict) -> dict:
        body = {"requestId": str(uuid.uuid4()), "payload": payload}
        try:
            r = await self._http.post(
                f"{BASE_URL}{path}", json=body, headers=self._headers()
            )
        except httpx.HTTPError as e:
            raise GoveeError(None, f"transport error: {e}") from e
        return self._check(r.json(), r.status_code)

    async def discover(self) -> list[DeviceInfo]:
        body = await self._get("/user/devices")
        data = body.get("data") or []
        # Some renders shape data as {"devices": [...]} — accept both.
        if isinstance(data, dict):
            data = data.get("devices", []) or []
        return [
            DeviceInfo(
                sku=d.get("sku", ""),
                device=d.get("device", ""),
                name=d.get("deviceName", ""),
                type=d.get("type", ""),
                raw_capabilities=list(d.get("capabilities") or []),
            )
            for d in data
        ]

    async def get_state(self, sku: str, mac: str) -> StateSnapshot:
        body = await self._post("/device/state", {"sku": sku, "device": mac})
        payload = body.get("payload") or body.get("data") or {}
        caps = payload.get("capabilities") or []
        return _parse_state(caps)

    async def set_power(self, sku: str, mac: str, *, on: bool) -> None:
        await self._post(
            "/device/control",
            {
                "sku": sku,
                "device": mac,
                "capability": {
                    "type": "devices.capabilities.on_off",
                    "instance": "powerSwitch",
                    "value": 1 if on else 0,
                },
            },
        )

    async def set_manual_level(self, sku: str, mac: str, level: int) -> None:
        # Caller must have validated the level against the device's
        # discovered Manual-mode options. We don't second-guess here.
        await self._post(
            "/device/control",
            {
                "sku": sku,
                "device": mac,
                "capability": {
                    "type": "devices.capabilities.work_mode",
                    "instance": "workMode",
                    "value": {"workMode": WORKMODE_MANUAL, "modeValue": int(level)},
                },
            },
        )


def _parse_state(caps: list[dict]) -> StateSnapshot:
    online = False
    power_on: bool | None = None
    work_mode: int | None = None
    mode_value: int | None = None
    lack_water = False

    for cap in caps:
        instance = cap.get("instance")
        state = cap.get("state") or {}
        value = state.get("value")
        if instance == "online":
            online = bool(value)
        elif instance == "powerSwitch":
            if isinstance(value, (int, bool)):
                power_on = bool(value)
        elif instance == "workMode":
            if isinstance(value, dict):
                wm = value.get("workMode")
                mv = value.get("modeValue")
                work_mode = int(wm) if isinstance(wm, int) else work_mode
                mode_value = int(mv) if isinstance(mv, int) else mode_value
        elif instance == "lackWaterEvent":
            lack_water = True

    return StateSnapshot(
        online=online,
        power_on=power_on,
        work_mode=work_mode,
        mode_value=mode_value,
        lack_water=lack_water,
    )
