from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.dependencies import get_config, get_repository

router = APIRouter()
templates = Jinja2Templates(directory="app/web/templates")


@router.get("/runs/{run_id}", response_class=HTMLResponse)
def run_page(run_id: str, request: Request, repo=Depends(get_repository)):
    return templates.TemplateResponse("run.html", {"request": request, "run": repo.get_run(run_id), "results": repo.list_results(run_id), "notes": repo.list_notes(run_id)})


@router.get("/runs/{run_id}/review", response_class=HTMLResponse)
def review_page(run_id: str, request: Request, repo=Depends(get_repository), config=Depends(get_config)):
    return templates.TemplateResponse("review.html", {"request": request, "run": repo.get_run(run_id), "results": repo.list_results(run_id), "notes": repo.list_notes(run_id), "dashboards": config.get("splunk_dashboards", {}).get("dashboards", [])})


@router.get("/runs/{run_id}/{module}", response_class=HTMLResponse)
def module_page(run_id: str, module: str, request: Request, repo=Depends(get_repository), config=Depends(get_config)):
    if module == "splunk":
        return templates.TemplateResponse("splunk.html", {"request": request, "run": repo.get_run(run_id), "dashboards": config.get("splunk_dashboards", {}).get("dashboards", []), "notes": repo.list_notes(run_id)})
    return templates.TemplateResponse("module.html", {"request": request, "run": repo.get_run(run_id), "module": module, "results": repo.list_results(run_id, module), "notes": repo.list_notes(run_id)})
