from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.dependencies import get_config, get_repository, get_reviewer
from app.config.validation import validate_config
from app.orchestrator.lock import DuplicateActiveRun

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/", response_class=HTMLResponse)
def index(request: Request, repo=Depends(get_repository), config=Depends(get_config)):
    preflight = validate_config(config)
    return templates.TemplateResponse("index.html", {"request": request, "runs": repo.list_runs(), "preflight": preflight})


@router.post("/api/runs")
def create_run(config=Depends(get_config), repo=Depends(get_repository), reviewer: str = Depends(get_reviewer)):
    preflight = validate_config(config)
    if not preflight.ok:
        raise HTTPException(status_code=400, detail=preflight.lines())
    try:
        run = repo.create_run(started_by=reviewer, config_version=config.get("_config_hash", "UNKNOWN"))
    except DuplicateActiveRun as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"run_id": run.run_id, "state": run.state}


@router.post("/runs")
def create_run_form(config=Depends(get_config), repo=Depends(get_repository), reviewer: str = Depends(get_reviewer)):
    preflight = validate_config(config)
    if not preflight.ok:
        return RedirectResponse("/", status_code=303)
    run = repo.create_run(started_by=reviewer, config_version=config.get("_config_hash", "UNKNOWN"))
    return RedirectResponse(f"/runs/{run.run_id}", status_code=303)
