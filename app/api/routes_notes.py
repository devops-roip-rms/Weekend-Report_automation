from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import get_config, get_repository, get_reviewer
from app.domain import NoteScope, ReviewNote

router = APIRouter()


@router.put("/api/runs/{run_id}/notes/module/{module}")
def save_module_note(run_id: str, module: str, payload: dict, repo=Depends(get_repository), reviewer: str = Depends(get_reviewer)):
    note_id = repo.save_note(ReviewNote(run_id, NoteScope.MODULE, reviewer, payload.get("note", ""), module=module))
    return {"id": note_id}


@router.put("/api/runs/{run_id}/notes/result/{result_id}")
def save_result_note(run_id: str, result_id: int, payload: dict, repo=Depends(get_repository), reviewer: str = Depends(get_reviewer)):
    note_id = repo.save_note(ReviewNote(run_id, NoteScope.RESULT, reviewer, payload.get("note", ""), result_id=result_id))
    return {"id": note_id}


@router.put("/api/runs/{run_id}/notes/splunk/{dashboard_id}")
def save_splunk_note(run_id: str, dashboard_id: str, payload: dict, repo=Depends(get_repository), reviewer: str = Depends(get_reviewer)):
    note_id = repo.save_note(ReviewNote(run_id, NoteScope.SPLUNK_DASHBOARD, reviewer, payload.get("note", ""), dashboard_id=dashboard_id))
    return {"id": note_id}


@router.put("/api/runs/{run_id}/notes/general")
def save_general_note(run_id: str, payload: dict, repo=Depends(get_repository), reviewer: str = Depends(get_reviewer)):
    note_id = repo.save_note(ReviewNote(run_id, NoteScope.GENERAL, reviewer, payload.get("note", "")))
    return {"id": note_id}
