from __future__ import annotations

import argparse
import asyncio
import os

from dirt_camera_agent.config import CameraAgentSettings
from dirt_camera_agent.service import CameraAgentService, build_camera_source
from dirt_shared.camera import SnapshotSpool
from dirt_shared.cloud_assets import (
    AssetUploader,
    AssetUploadRequest,
    HttpCloudAssetClient,
)
from dirt_shared.observability import log_event


def build_service(settings: CameraAgentSettings | None = None) -> CameraAgentService:
    settings = settings or CameraAgentSettings()
    settings.validate_source()
    os.environ.setdefault("DIRT_LOGS_DIR", str(settings.data_dir / "logs"))
    client = HttpCloudAssetClient(
        base_url=settings.cloud_api_base_url,
        gateway_token=settings.cloud_gateway_token,
    )

    def on_failure_report_error(
        payload: AssetUploadRequest,
        idempotency_key: str,
        exc: Exception,
    ) -> None:
        log_event(
            "camera_agent",
            "asset_failure_report_failed",
            site_id=settings.site_id,
            tent_id=settings.tent_id,
            gateway_id=settings.cloud_gateway_id,
            device_id=settings.camera_device_id,
            asset_id=payload.sign_request.asset_id,
            object_key=payload.sign_request.object_key,
            idempotency_key=idempotency_key,
            error=type(exc).__name__,
        )

    return CameraAgentService(
        settings=settings,
        source=build_camera_source(settings),
        spool=SnapshotSpool(settings.spool_dir),
        uploader=AssetUploader(
            client,
            on_failure_report_error=on_failure_report_error,
        ),
        closer=client,
    )


async def run_agent(*, once: bool = False) -> None:
    service = build_service()
    try:
        if once:
            await service.run_once()
            return
        await service.run_forever()
    finally:
        await service.aclose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Dirt camera edge agent")
    parser.add_argument("--once", action="store_true", help="capture and upload once")
    args = parser.parse_args()
    asyncio.run(run_agent(once=args.once))


if __name__ == "__main__":
    main()
