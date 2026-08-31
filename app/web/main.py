from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import quote

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    routes_auth,
    routes_evidence,
    routes_health,
    routes_notes,
    routes_reports,
    routes_review,
    routes_runs,
)


def _local_login_enabled() -> bool:
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

    return mode == "production" and provider == "local_login"


def _browser_wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "").lower()
    return "text/html" in accept


def _login_redirect_target(request: Request) -> str:
    path = request.url.path

    if request.url.query:
        path = f"{path}?{request.url.query}"

    return quote(path, safe="")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Weekend Report Automation",
    )

    static_dir = Path(__file__).parent / "static"

    app.mount(
        "/static",
        StaticFiles(directory=str(static_dir)),
        name="static",
    )

    @app.exception_handler(HTTPException)
    async def auth_exception_handler(
        request: Request,
        exc: HTTPException,
    ):
        if (
            exc.status_code == 401
            and _local_login_enabled()
            and _browser_wants_html(request)
            and request.url.path != "/login"
            and not request.url.path.startswith("/api/")
        ):
            return RedirectResponse(
                url=f"/login?next={_login_redirect_target(request)}",
                status_code=303,
            )

        return await http_exception_handler(
            request,
            exc,
        )

    app.include_router(routes_health.router)

    # Authentication endpoints must be registered before protected UI routes.
    app.include_router(routes_auth.router)

    app.include_router(routes_runs.router)
    app.include_router(routes_review.router)
    app.include_router(routes_notes.router)
    app.include_router(routes_evidence.router)
    app.include_router(routes_reports.router)

    return app


app = create_app()
