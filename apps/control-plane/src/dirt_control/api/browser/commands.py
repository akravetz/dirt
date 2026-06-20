from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from fastapi import APIRouter, Depends, status

from dirt_control.api.browser_schemas.commands import (
    CommandCreateRequest,
    CommandResponse,
)
from dirt_control.deps import get_clock, get_session, get_settings
from dirt_control.security import require_browser_user
from dirt_control.services.browser_commands import (
    create_command as create_command_service,
)
from dirt_control.services.browser_commands import (
    get_command as get_command_service,
)
from dirt_control.services.browser_commands import (
    list_commands as list_commands_service,
)
from dirt_control.settings import CloudSettings

router = APIRouter()


@router.post(
    "/commands",
    status_code=status.HTTP_201_CREATED,
    response_model=CommandResponse,
)
async def create_command(
    body: CommandCreateRequest,
    user: str = Depends(require_browser_user),
    settings: CloudSettings = Depends(get_settings),
    session=Depends(get_session),
    clock: Callable[[], datetime] = Depends(get_clock),
) -> CommandResponse:
    return await create_command_service(
        body,
        user=user,
        settings=settings,
        session=session,
        now=clock(),
    )


@router.get("/commands/{command_id}", response_model=CommandResponse)
async def get_command(
    command_id: str,
    user: str = Depends(require_browser_user),
    session=Depends(get_session),
) -> CommandResponse:
    return await get_command_service(session, command_id=command_id, user=user)


@router.get("/commands", response_model=list[CommandResponse])
async def list_commands(
    status: str | None = None,
    user: str = Depends(require_browser_user),
    session=Depends(get_session),
) -> list[CommandResponse]:
    return await list_commands_service(session, user=user, status_filter=status)
