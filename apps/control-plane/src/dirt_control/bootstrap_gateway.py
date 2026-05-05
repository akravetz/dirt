from __future__ import annotations

import asyncio
import os

from dirt_control.bootstrap import GatewayCredentialSeed, ensure_gateway_credential


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"required environment variable is unset: {name}")
    return value


async def _main() -> None:
    gateway_id = _required_env("DIRT_CLOUD_GATEWAY_ID")
    await ensure_gateway_credential(
        database_url=_required_env("DIRT_CLOUD_DATABASE_URL"),
        seed=GatewayCredentialSeed(
            credential_id=os.environ.get(
                "DIRT_CLOUD_GATEWAY_CREDENTIAL_ID", gateway_id
            ),
            gateway_id=gateway_id,
            token_sha256=_required_env("DIRT_CLOUD_GATEWAY_TOKEN_SHA256"),
            allowed_site_id=_required_env("DIRT_CLOUD_SITE_ID"),
        ),
    )


def main() -> None:
    asyncio.run(_main())


if __name__ == "__main__":
    main()
