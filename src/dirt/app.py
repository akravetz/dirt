import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from dirt.api.feed import router as feed_router
from dirt.api.snapshots import router as snapshots_router
from dirt.config import TEMPLATES_DIR
from dirt.db import init_db
from dirt.services.capture import capture_loop


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    stop_event = asyncio.Event()
    task = asyncio.create_task(capture_loop(stop_event))
    yield
    stop_event.set()
    await task


app = FastAPI(title="Dirt", lifespan=lifespan)
app.include_router(snapshots_router)
app.include_router(feed_router)
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")
