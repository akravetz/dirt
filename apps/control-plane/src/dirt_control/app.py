from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI
from itsdangerous import URLSafeSerializer
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.middleware.cors import CORSMiddleware

from dirt_control.api.browser import router as browser_router
from dirt_control.api.gateway import router as gateway_router
from dirt_control.db import create_engine, create_sessionmaker, ping
from dirt_control.security import BrowserSessionManager
from dirt_control.settings import CloudSettings


def create_app(
    *,
    settings: CloudSettings | None = None,
    engine: AsyncEngine | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FastAPI:
    settings = settings or CloudSettings()
    owns_engine = engine is None
    engine = engine or create_engine(settings)
    sessionmaker = create_sessionmaker(engine)
    sessions = BrowserSessionManager(
        URLSafeSerializer(settings.session_secret),
        secure_cookie=settings.session_cookie_secure,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await ping(engine)
        try:
            yield
        finally:
            if owns_engine:
                await engine.dispose()

    app = FastAPI(title="Dirt Control Plane", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = sessionmaker
    app.state.sessions = sessions
    app.state.clock = clock

    if settings.allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "OPTIONS"],
            allow_headers=["authorization", "content-type"],
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, bool | str]:
        return {"service": "control-plane-api", "ok": True}

    app.include_router(browser_router)
    app.include_router(gateway_router)
    return app
