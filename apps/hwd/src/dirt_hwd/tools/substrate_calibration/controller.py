from __future__ import annotations

from collections.abc import Iterable

import httpx

from dirt_hwd.tools.substrate_calibration.schemas import (
    ControllerCommandResponse,
    ControllerStatus,
    ProbeIdentity,
    ProbeSample,
    SamplesResponse,
)


class SubstrateControllerClient:
    def __init__(
        self,
        base_url: str,
        *,
        http: httpx.AsyncClient | None = None,
        timeout_s: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._http = http or httpx.AsyncClient(timeout=timeout_s)
        self._owns_http = http is None

    async def aclose(self) -> None:
        if self._owns_http:
            await self._http.aclose()

    async def status(self) -> ControllerStatus:
        response = await self._http.get(f"{self.base_url}/status")
        response.raise_for_status()
        return ControllerStatus.model_validate(response.json())

    async def samples(self, *, window_s: int = 120) -> SamplesResponse:
        response = await self._http.get(
            f"{self.base_url}/samples",
            params={"window_s": window_s},
        )
        response.raise_for_status()
        return SamplesResponse.model_validate(response.json())

    async def start_calibration(
        self,
        *,
        duration_s: int = 900,
        interval_ms: int = 2000,
    ) -> ControllerCommandResponse:
        response = await self._http.post(
            f"{self.base_url}/calibration/start",
            params={"duration_s": duration_s, "interval_ms": interval_ms},
        )
        response.raise_for_status()
        return ControllerCommandResponse.model_validate(response.json())

    async def stop_calibration(self) -> ControllerCommandResponse:
        response = await self._http.post(f"{self.base_url}/calibration/stop")
        response.raise_for_status()
        return ControllerCommandResponse.model_validate(response.json())


def probe_map_from_status(status: ControllerStatus) -> list[ProbeIdentity]:
    return [
        ProbeIdentity(
            probe_id=slot.probe_id,
            modbus_address=slot.modbus_address,
            device_id=slot.device_id,
        )
        for slot in status.slots
        if slot.enabled
    ]


def samples_for_probe(
    response: SamplesResponse,
    *,
    probe_id: int,
) -> Iterable[ProbeSample]:
    for slot in response.slots:
        if slot.probe_id != probe_id:
            continue
        yield from (
            ProbeSample.model_validate(sample.model_dump())
            for sample in slot.samples
            if sample.probe_id == probe_id
        )
