from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeSerializer
from sqlalchemy.ext.asyncio import AsyncEngine

from dirt_mcp.app import create_mcp_app
from dirt_shared.app_wiring import build_core_services
from dirt_shared.config import Settings
from dirt_shared.db import ping
from dirt_web import TEMPLATES_DIR
from dirt_web.api.auth import router as auth_router
from dirt_web.api.feed import router as feed_router
from dirt_web.api.sensors import router as sensors_router
from dirt_web.api.snapshots import router as snapshots_router
from dirt_web.auth import AuthMiddleware, SessionManager


def create_app(
    *,
    engine: AsyncEngine | None = None,
    settings: Settings | None = None,
    run_mcp: bool = True,
) -> FastAPI:
    """Compose the dirt-web FastAPI app.

    Args:
        engine: AsyncEngine for DB-backed services. Defaults to one built
            from Settings (production path).
        settings: Settings instance. Defaults to ``Settings()``.
        run_mcp: when False, the MCP sub-app is not created or mounted.

    Service instances are stored on ``app.state.<name>`` and resolved by
    ``Depends`` providers in ``dirt_web.deps``. Override behaviour in
    tests with ``app.dependency_overrides[provider] = lambda: fake``.
    """
    core = build_core_services(engine=engine, settings=settings)
    engine = core.engine
    settings = core.settings

    sessions = SessionManager(URLSafeSerializer(settings.secret_key))

    if run_mcp:
        mcp_app, mcp_run = create_mcp_app(
            snapshots=core.snapshots,
            bearer_token=settings.mcp_bearer_token,
        )
    else:
        mcp_app, mcp_run = None, None

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await ping(engine)
        if mcp_run is not None:
            async with mcp_run():
                yield
        else:
            yield

    app = FastAPI(title="Dirt Web", lifespan=lifespan)
    app.state.engine = engine
    app.state.settings = settings
    app.state.snapshots = core.snapshots
    app.state.readings = core.readings
    app.state.grow = core.grow
    app.state.plant_detail = core.plant_detail
    app.state.plants = core.plants
    app.state.humidifier_state = core.humidifier_state
    app.state.system_status = core.system_status
    app.state.sessions = sessions

    app.add_middleware(
        AuthMiddleware, sessions=sessions, exclude_prefixes=["/mcp"]
    )
    app.include_router(auth_router)
    app.include_router(snapshots_router)
    app.include_router(feed_router)
    app.include_router(sensors_router)
    if mcp_app is not None:
        app.mount("/mcp", mcp_app)

    templates = Jinja2Templates(directory=TEMPLATES_DIR)

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(request, "index.html")

    return app


# Module-level instance for `uvicorn dirt_web.app:app`.
app = create_app()
