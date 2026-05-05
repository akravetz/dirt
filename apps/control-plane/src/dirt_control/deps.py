from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from datetime import datetime

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


def get_settings(request: Request):
    return request.app.state.settings


def get_clock(request: Request) -> Callable[[], datetime]:
    return request.app.state.clock
