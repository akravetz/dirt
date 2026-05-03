"""HTTP client for the fan-controller ESP32 dual-role node.

The node exposes two endpoints on its LAN interface:

    POST /fan   {"duty_pct": 0..100}   -> sets fan speed
    GET  /fan                           -> {"set_duty_pct":N,"reported_duty_pct":N}

This module is a thin async wrapper used by dirt-hwd to command the fan.
Takes an ``httpx.AsyncClient`` by injection so tests can swap the transport
via ``httpx.MockTransport`` without monkeypatching.

Notes on ``reported_duty_pct``:
    Currently MOCKED in firmware — the device returns the last value set
    via POST. Once the D- tach input is wired up, firmware replaces the
    mock with real tach-derived measurement and this client's contract
    doesn't change. See ``wiki/hardware/ac-infinity-fan-control.md``
    section "Tach (D−) input — deferred".

Host-side trim:
    ``dirt_hwd.services.fan_controller.FanTrimLoopService`` reads tent
    RH/VPD from ``ReadingsService`` and drives ``set_duty`` here. Tracked
    in ``wiki/hardware/ac-infinity-fan-control.md``.
"""

from __future__ import annotations

from typing import TypedDict

import httpx

DEFAULT_BASE_URL = "http://fan-controller.local"
DEFAULT_TIMEOUT_S = 5.0


class FanState(TypedDict):
    set_duty_pct: int
    reported_duty_pct: int


class FanNodeError(RuntimeError):
    """Raised on non-2xx responses or transport failures from the fan node."""


class FanNodeClient:
    """Async client for the fan-controller HTTP control surface."""

    def __init__(
        self,
        http: httpx.AsyncClient,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout_s: float = DEFAULT_TIMEOUT_S,
    ) -> None:
        self._http = http
        self._base_url = base_url.rstrip("/")
        self._timeout_s = timeout_s

    async def set_duty(self, duty_pct: int) -> int:
        """Command the fan to ``duty_pct`` (0..100). Returns the duty the
        node acknowledged — should equal the requested value."""
        if not 0 <= duty_pct <= 100:
            raise ValueError(f"duty_pct must be in [0, 100], got {duty_pct}")
        data = await self._post_json("/fan", {"duty_pct": duty_pct})
        return int(data["duty_pct"])

    async def get_state(self) -> FanState:
        """Fetch the current fan state from the node."""
        data = await self._get_json("/fan")
        return FanState(
            set_duty_pct=int(data["set_duty_pct"]),
            reported_duty_pct=int(data["reported_duty_pct"]),
        )

    async def _post_json(self, path: str, body: dict) -> dict:
        url = f"{self._base_url}{path}"
        try:
            resp = await self._http.post(url, json=body, timeout=self._timeout_s)
        except httpx.HTTPError as exc:
            raise FanNodeError(f"transport error: {exc!r}") from exc
        return _parse_ok(resp)

    async def _get_json(self, path: str) -> dict:
        url = f"{self._base_url}{path}"
        try:
            resp = await self._http.get(url, timeout=self._timeout_s)
        except httpx.HTTPError as exc:
            raise FanNodeError(f"transport error: {exc!r}") from exc
        return _parse_ok(resp)


def _parse_ok(resp: httpx.Response) -> dict:
    if resp.status_code >= 400:
        raise FanNodeError(
            f"fan node returned HTTP {resp.status_code}: {resp.text}",
        )
    try:
        return resp.json()
    except ValueError as exc:
        raise FanNodeError(f"fan node returned non-JSON body: {resp.text!r}") from exc
