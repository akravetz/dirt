from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from dirt_control.db import create_sessionmaker
from dirt_control.models import GatewayCredential
from dirt_control.settings import normalize_async_database_url


@dataclass(frozen=True)
class GatewayCredentialSeed:
    credential_id: str
    gateway_id: str
    token_sha256: str
    allowed_site_id: str


async def ensure_gateway_credential(
    *,
    database_url: str,
    seed: GatewayCredentialSeed,
    now: datetime | None = None,
    engine: AsyncEngine | None = None,
) -> None:
    """Create or update the single V1 gateway credential row."""

    owns_engine = engine is None
    engine = engine or create_async_engine(normalize_async_database_url(database_url))
    sessionmaker = create_sessionmaker(engine)
    timestamp = now or datetime.now(UTC)
    try:
        async with sessionmaker() as session:
            credential = await session.get(GatewayCredential, seed.credential_id)
            if credential is None:
                session.add(
                    GatewayCredential(
                        credential_id=seed.credential_id,
                        gateway_id=seed.gateway_id,
                        token_sha256=seed.token_sha256,
                        allowed_site_id=seed.allowed_site_id,
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                )
            else:
                credential.gateway_id = seed.gateway_id
                credential.token_sha256 = seed.token_sha256
                credential.allowed_site_id = seed.allowed_site_id
                credential.is_active = True
                credential.revoked_at = None
                credential.updated_at = timestamp
            await session.commit()
    finally:
        if owns_engine:
            await engine.dispose()
