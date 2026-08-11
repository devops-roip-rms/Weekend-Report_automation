from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.api.dependencies import get_evidence_manager, get_repository

router = APIRouter()


@router.get("/api/runs/{run_id}/evidence")
def list_evidence(run_id: str, repo=Depends(get_repository)):
    return repo.list_evidence(run_id)


@router.get("/api/evidence/{path:path}")
def get_evidence(path: str, evidence=Depends(get_evidence_manager)):
    try:
        target = evidence.absolute(path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="unsafe evidence path") from exc
    if not target.exists():
        raise HTTPException(status_code=404, detail="evidence not found")
    return FileResponse(str(target))
