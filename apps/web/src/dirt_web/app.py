import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from itsdangerous import URLSafeSerializer
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from dirt_mcp.app import create_mcp_app
from dirt_shared.app_wiring import build_core_services
from dirt_shared.config import Settings
from dirt_shared.db import ping
from dirt_web.api.auth import router as auth_router
from dirt_web.api.feed import router as feed_router
from dirt_web.api.grow import router as grow_router
from dirt_web.api.humidifier import router as humidifier_router
from dirt_web.api.sensors import router as sensors_router
from dirt_web.api.snapshots import router as snapshots_router
from dirt_web.auth import AuthMiddleware, SessionManager

_log = logging.getLogger(__name__)


def create_app(
    *,
    engine: AsyncEngine | None = None,
    settings: Settings | None = None,
    web_ui_dist_dir: Path | None = None,
    run_mcp: bool = True,
) -> FastAPI:
    """Compose the dirt-web FastAPI app.

    Args:
        engine: AsyncEngine for DB-backed services. Defaults to one built
            from Settings (production path).
        settings: Settings instance. Defaults to ``Settings()``.
        web_ui_dist_dir: override for the built SPA bundle path. Tests
            point this at a tmp_path fixture containing a minimal
            ``index.html`` + ``assets/`` layout; production leaves it
            ``None`` and inherits ``settings.web_ui_dist_dir``.
        run_mcp: when False, the MCP sub-app is not created or mounted.

    Service instances are stored on ``app.state.<name>`` and resolved by
    ``Depends`` providers in ``dirt_web.deps``. Override behaviour in
    tests with ``app.dependency_overrides[provider] = lambda: fake``.

    The built SPA bundle is mounted at ``/assets`` and an
    ``SPAFallbackMiddleware`` serves ``index.html`` for every non-/api/
    path that would otherwise 404, so TanStack Router can handle
    deeplinks on refresh. Implementing SPA fallback as middleware
    (instead of a ``/{full_path:path}`` catch-all route) keeps the
    registered route table identical to the OpenAPI contract, which
    ``test_api_contract.py`` audits.
    """
    core = build_core_services(engine=engine, settings=settings)
    engine = core.engine
    settings = core.settings
    if web_ui_dist_dir is None:
        web_ui_dist_dir = settings.web_ui_dist_dir

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

    # Middleware order: Starlette runs middleware in reverse-registration
    # order, so the LAST add_middleware call wraps OUTERMOST. We want the
    # flow: request → SPAFallbackMiddleware (outer, so it can rewrite
    # non-/api/ 404s into index.html before auth sees them) → AuthMiddleware
    # (inner) → routers. That means AuthMiddleware is added FIRST here.
    app.add_middleware(AuthMiddleware, sessions=sessions, exclude_prefixes=["/mcp"])
    app.add_middleware(SPAFallbackMiddleware, dist_dir=web_ui_dist_dir)

    app.include_router(auth_router)
    app.include_router(snapshots_router)
    app.include_router(feed_router)
    app.include_router(sensors_router)
    app.include_router(grow_router)
    app.include_router(humidifier_router)
    if mcp_app is not None:
        app.mount("/mcp", mcp_app)

    _mount_spa_assets(app, web_ui_dist_dir)

    return app


def _mount_spa_assets(app: FastAPI, dist_dir: Path) -> None:
    """Mount the built SPA's /assets directory if present.

    Missing dist_dir is a soft-fail — the asset mount simply isn't
    registered, and SPAFallbackMiddleware covers non-/api/ 404s with a
    503 placeholder. This lets the API be usable for development
    against a backend-only stack (fresh clone before ``pnpm build``).
    """
    assets_dir = dist_dir / "assets"
    if assets_dir.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=assets_dir),
            name="spa-assets",
        )


class SPAFallbackMiddleware(BaseHTTPMiddleware):
    """Serve the SPA shell for any non-/api/ path the routers 404ed on.

    Registered in ``create_app`` outside AuthMiddleware. Order of
    operations per request:

    1. Request enters SPAFallbackMiddleware.
    2. Forwarded to AuthMiddleware → routers.
    3. If the downstream response is a 404 AND the path is not /api/*
       AND the SPA dist exists, rewrite the response to ``index.html``.
    4. Otherwise pass the response through unchanged.

    This keeps the API's route table contract-accurate (no catch-all
    registered in ``app.routes``) while still serving client-side-routed
    SPA deeplinks.

    Missing dist — log WARN once, return 503 for non-/api/ 404s so
    operators see a clear "you haven't built the frontend" signal
    instead of an ambiguous 404.
    """

    def __init__(self, app, dist_dir: Path) -> None:
        super().__init__(app)
        self._dist_dir = dist_dir
        self._index_html = dist_dir / "index.html"
        # Cache the dist-present check at startup. If the bundle is
        # built later, operators restart dirt-web (pnpm build isn't
        # watched). Avoids a stat() on every non-/api/ 404.
        self._dist_present = self._index_html.is_file()
        if not self._dist_present:
            _log.warning(
                "web-ui dist missing at %s; non-/api/ routes will return "
                "503 until `pnpm --dir web-ui build` runs + service restart.",
                self._dist_dir,
            )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        if response.status_code != 404:
            return response

        path = request.url.path
        # /api/*, /mcp, and /assets/* 404s are real — don't hide them.
        if path.startswith(("/api/", "/mcp", "/assets/")):
            return response

        if not self._dist_present:
            return JSONResponse(
                {"detail": "web-ui bundle not built"},
                status_code=503,
            )

        return FileResponse(self._index_html, media_type="text/html")


# Module-level instance for `uvicorn dirt_web.app:app`.
app = create_app()
