"""Process entry point for the local cloud gateway service."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import replace
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


async def run_gateway_once(
    settings: Settings | None = None,
    *,
    dry_run: bool | None = None,
) -> None:
    settings = settings or Settings()
    config = settings.cloud_gateway()
    if dry_run is not None:
        config = replace(config, dry_run=dry_run)
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
            sleeper=AsyncioSleeper(),
        )
        await service.run_once()
    finally:
        await client.aclose()
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Dirt cloud gateway")
    parser.add_argument("--once", action="store_true", help="run one sync cycle")
    parser.add_argument("--dry-run", action="store_true", help="force dry-run mode")
    args = parser.parse_args()
    if args.once:
        asyncio.run(run_gateway_once(dry_run=True if args.dry_run else None))
        return
    asyncio.run(run_gateway())


if __name__ == "__main__":
    main()
