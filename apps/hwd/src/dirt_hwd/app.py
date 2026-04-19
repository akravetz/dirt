import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from dirt_hwd.api.ingest import router as ingest_router
from dirt_hwd.services.archive import archive_loop
from dirt_hwd.services.humidifier import humidifier_loop
from dirt_hwd.services.serial_reader import serial_reader_loop
from dirt_shared.db import init_db
from dirt_shared.services.capture import capture_loop


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    stop_event = asyncio.Event()
    capture_task = asyncio.create_task(capture_loop(stop_event))
    archive_task = asyncio.create_task(archive_loop(stop_event))
    serial_task = asyncio.create_task(serial_reader_loop(stop_event))
    humidifier_task = asyncio.create_task(humidifier_loop(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        await capture_task
        await archive_task
        await serial_task
        await humidifier_task


app = FastAPI(title="Dirt HWD", lifespan=lifespan)
app.include_router(ingest_router)
