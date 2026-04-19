import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from dirt.api.auth import router as auth_router
from dirt.api.feed import router as feed_router
from dirt.api.ingest import router as ingest_router
from dirt.api.sensors import router as sensors_router
from dirt.api.snapshots import router as snapshots_router
from dirt.auth import AuthMiddleware
from dirt.config import TEMPLATES_DIR
from dirt.db import init_db
from dirt.mcp.app import create_mcp_app
from dirt.services.archive import archive_loop
from dirt.services.capture import capture_loop
from dirt.services.humidifier import humidifier_loop
from dirt.services.serial_reader import serial_reader_loop

_mcp_app, _mcp_run = create_mcp_app()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    stop_event = asyncio.Event()
    capture_task = asyncio.create_task(capture_loop(stop_event))
    archive_task = asyncio.create_task(archive_loop(stop_event))
    serial_task = asyncio.create_task(serial_reader_loop(stop_event))
    humidifier_task = asyncio.create_task(humidifier_loop(stop_event))
    async with _mcp_run():
        yield
    stop_event.set()
    await capture_task
    await archive_task
    await serial_task
    await humidifier_task


app = FastAPI(title="Dirt", lifespan=lifespan)
app.add_middleware(AuthMiddleware, exclude_prefixes=["/mcp", "/api/ingest"])
app.include_router(auth_router)
app.include_router(snapshots_router)
app.include_router(feed_router)
app.include_router(sensors_router)
app.include_router(ingest_router)
templates = Jinja2Templates(directory=TEMPLATES_DIR)
app.mount("/mcp", _mcp_app)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")
