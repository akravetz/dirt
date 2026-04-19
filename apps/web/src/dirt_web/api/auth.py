from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.responses import Response

from dirt_shared.config import settings
from dirt_web import TEMPLATES_DIR
from dirt_web.auth import clear_session_cookie, create_session_cookie, get_current_user

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@router.get("/login", response_model=None)
async def login_page(request: Request) -> Response:
    user = get_current_user(request)
    if user is not None:
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(request, "login.html", {"error": None})


@router.post("/login", response_model=None)
async def login_submit(request: Request) -> Response:
    form = await request.form()
    username = form.get("username", "")
    password = form.get("password", "")

    if username == settings.auth_username and password == settings.auth_password:
        response = RedirectResponse(url="/", status_code=302)
        create_session_cookie(response, username)
        return response

    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": "Invalid username or password"},
        status_code=401,
    )


@router.get("/logout")
async def logout() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=302)
    clear_session_cookie(response)
    return response
