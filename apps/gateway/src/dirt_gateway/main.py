"""Process entry point for the local cloud gateway service."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from dirt_gateway.cloud import HttpCloudGatewayClient
from dirt_gateway.local import GatewayLocalServiceBundle
from dirt_gateway.outbox import OutboxRepository
from dirt_gateway.sync import GatewaySyncService
from dirt_shared.config import Settings
from dirt_shared.db import ping


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
        service = GatewaySyncService(
            config=config,
            outbox=OutboxRepository(engine),
            local_services=GatewayLocalServiceBundle(engine, clock=clock),
            cloud_client=client,
            clock=clock,
        )
        await service.run_forever()
    finally:
        await client.aclose()
        await engine.dispose()


def main() -> None:
    asyncio.run(run_gateway())


if __name__ == "__main__":
    main()
