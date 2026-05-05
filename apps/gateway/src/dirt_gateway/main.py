"""Process entry point for the local cloud gateway service."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from dirt_gateway.cloud import HttpCloudGatewayClient
from dirt_gateway.commands import GatewayCommandService
from dirt_gateway.local import GatewayLocalServiceBundle
from dirt_gateway.outbox import OutboxRepository
from dirt_gateway.sync import AsyncioSleeper, GatewaySyncService
from dirt_shared.config import Settings
from dirt_shared.db import ping
from dirt_shared.services.commands import CommandService


async def run_gateway(settings: Settings | None = None) -> None:
    settings = settings or Settings()
    config = settings.cloud_gateway()
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    client = HttpCloudGatewayClient(
        base_url=config.api_base_url,
        gateway_token=config.gateway_token,
    )

    def clock() -> datetime:
        return datetime.now(UTC)

    try:
        await ping(engine)
        outbox = OutboxRepository(engine)
        sleeper = AsyncioSleeper()
        service = GatewaySyncService(
            config=config,
            outbox=outbox,
            local_services=GatewayLocalServiceBundle(engine, clock=clock),
            cloud_client=client,
            clock=clock,
            sleeper=sleeper,
        )
        commands = GatewayCommandService(
            config=config,
            cloud_client=client,
            command_ledger=CommandService(engine, clock=clock),
            outbox=outbox,
            clock=clock,
        )
        await asyncio.gather(
            service.run_forever(),
            commands.run_forever(sleeper),
        )
    finally:
        await client.aclose()
        await engine.dispose()


def main() -> None:
    asyncio.run(run_gateway())


if __name__ == "__main__":
    main()
