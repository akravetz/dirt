from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from dirt_mcp.app import create_mcp_app
from dirt_shared.db import init_db
from dirt_web import TEMPLATES_DIR
from dirt_web.api.auth import router as auth_router
from dirt_web.api.feed import router as feed_router
from dirt_web.api.sensors import router as sensors_router
from dirt_web.api.snapshots import router as snapshots_router
from dirt_web.auth import AuthMiddleware

_mcp_app, _mcp_run = create_mcp_app()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await init_db()
    async with _mcp_run():
        yield


app = FastAPI(title="Dirt Web", lifespan=lifespan)
app.add_middleware(AuthMiddleware, exclude_prefixes=["/mcp"])
app.include_router(auth_router)
app.include_router(snapshots_router)
app.include_router(feed_router)
app.include_router(sensors_router)
templates = Jinja2Templates(directory=TEMPLATES_DIR)
app.mount("/mcp", _mcp_app)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "index.html")
