from __future__ import annotations

import os
from urllib.parse import parse_qs

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import (
    SESSION_COOKIE_NAME,
    SESSION_TTL_SECONDS,
    authenticate_local_user,
    enforce_authorized_reviewer,
    issue_session_token,
    validate_session_token,
)

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")

MAX_LOGIN_BODY_BYTES = 16 * 1024


def _require_local_login_provider() -> None:
    mode = (
        os.getenv(
            "WEEKEND_REPORT_AUTH_MODE",
            "development",
        )
        .strip()
        .lower()
    )

    provider = (
        os.getenv(
            "WEEKEND_REPORT_AUTH_PROVIDER",
            "",
        )
        .strip()
        .lower()
    )

    if mode != "production" or provider != "local_login":
        raise HTTPException(status_code=404, detail="not found")


def _safe_next(value: str | None) -> str:
    if not value:
        return "/"

    value = value.strip()

    if not value.startswith("/"):
        return "/"

    if value.startswith("//"):
        return "/"

    return value


def _session_cookie_max_age() -> int:
    raw = os.getenv(
        "WEEKEND_REPORT_SESSION_TTL_SECONDS",
        str(SESSION_TTL_SECONDS),
    ).strip()

    try:
        ttl = int(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail="WEEKEND_REPORT_SESSION_TTL_SECONDS must be an integer",
        ) from exc

    if ttl <= 0:
        raise HTTPException(
            status_code=503,
            detail="WEEKEND_REPORT_SESSION_TTL_SECONDS must be greater than zero",
        )

    return ttl


def _first_value(
    form: dict[str, list[str]],
    name: str,
) -> str:
    values = form.get(name)

    if not values:
        return ""

    return values[0]


def _login_response(
    request: Request,
    *,
    next_url: str,
    error: str | None = None,
    username: str = "",
    status_code: int = 200,
) -> HTMLResponse:
    response = templates.TemplateResponse(
        request,
        "login.html",
        {
            "request": request,
            "next_url": next_url,
            "error": error,
            "username": username,
        },
        status_code=status_code,
    )

    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"

    return response


@router.get("/login", response_class=HTMLResponse)
def login_page(
    request: Request,
    next: str = "/",
):
    _require_local_login_provider()

    next_url = _safe_next(next)

    existing_token = request.cookies.get(
        SESSION_COOKIE_NAME,
        "",
    ).strip()

    if existing_token:
        try:
            reviewer = validate_session_token(existing_token)
            if reviewer:
                enforce_authorized_reviewer(reviewer)
                return RedirectResponse(
                    url=next_url,
                    status_code=303,
                )
        except HTTPException:
            pass

    return _login_response(
        request,
        next_url=next_url,
    )


@router.post("/login")
async def login(request: Request):
    _require_local_login_provider()

    body = await request.body()

    if len(body) > MAX_LOGIN_BODY_BYTES:
        raise HTTPException(
            status_code=413,
            detail="login request is too large",
        )

    try:
        decoded = body.decode("utf-8")
    except UnicodeDecodeError:
        return _login_response(
            request,
            next_url="/",
            error="Invalid username or password.",
            status_code=401,
        )

    form = parse_qs(
        decoded,
        keep_blank_values=True,
    )

    username = _first_value(form, "username").strip()
    password = _first_value(form, "password")
    next_url = _safe_next(_first_value(form, "next"))

    if not authenticate_local_user(username, password):
        return _login_response(
            request,
            next_url=next_url,
            username=username,
            error="Invalid username or password.",
            status_code=401,
        )

    try:
        enforce_authorized_reviewer(username)
    except HTTPException as exc:
        if exc.status_code == 403:
            return _login_response(
                request,
                next_url=next_url,
                username=username,
                error="Invalid username or password.",
                status_code=401,
            )
        raise

    token = issue_session_token(username)

    response = RedirectResponse(
        url=next_url,
        status_code=303,
    )

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=_session_cookie_max_age(),
        httponly=True,
        secure=True,
        samesite="lax",
        path="/",
    )

    response.headers["Cache-Control"] = "no-store"

    return response


@router.post("/logout")
def logout():
    _require_local_login_provider()

    response = RedirectResponse(
        url="/login",
        status_code=303,
    )

    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=True,
        httponly=True,
        samesite="lax",
    )

    response.headers["Cache-Control"] = "no-store"

    return response
