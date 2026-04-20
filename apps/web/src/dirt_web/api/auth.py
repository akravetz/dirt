from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

from dirt_shared.config import Settings
from dirt_web import TEMPLATES_DIR
from dirt_web.auth import SessionManager, get_sessions
from dirt_web.deps import get_settings

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@router.get("/login", response_model=None)
async def login_page(
    request: Request,
    sessions: SessionManager = Depends(get_sessions),
) -> Response:
    if sessions.get_current_user(request) is not None:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login", response_model=None)
async def login_submit(
    request: Request,
    sessions: SessionManager = Depends(get_sessions),
    settings: Settings = Depends(get_settings),
) -> Response:
    form = await request.form()
    username = form.get("username", "")
    password = form.get("password", "")

    if username == settings.auth_username and password == settings.auth_password:
        response = RedirectResponse(url="/", status_code=302)
        sessions.create_cookie(response, username)
        return response

    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": "Invalid username or password"},
        status_code=401,
    )


@router.get("/logout")
async def logout(
    sessions: SessionManager = Depends(get_sessions),
) -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=302)
    sessions.clear_cookie(response)
    return response
