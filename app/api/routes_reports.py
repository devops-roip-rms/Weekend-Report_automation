from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import get_config, get_evidence_manager, get_repository, get_reviewer
from app.domain import ReviewDecision
from app.reporting.snapshot import finalize_run

router = APIRouter()


@router.post("/api/runs/{run_id}/finalize")
def finalize(run_id: str, payload: dict, repo=Depends(get_repository), evidence=Depends(get_evidence_manager), config=Depends(get_config), reviewer: str = Depends(get_reviewer)):
    try:
        decision = ReviewDecision(payload["decision"])
        snapshot = finalize_run(repo, evidence, config, run_id, reviewer, decision)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run_id": run_id, "decision": decision.value, "snapshot_results": len(snapshot["results"])}
