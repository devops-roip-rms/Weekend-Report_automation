from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import (
    get_config,
    get_mutating_reviewer,
    get_repository,
)
from app.domain import (
    ManualDBReview,
    ManualDBReviewResult,
    to_jsonable,
)
from app.orchestrator.lock import InvalidRunTransition
from app.review.manual_db import (
    ManualDBReviewValidationError,
    record_manual_db_review,
)

router = APIRouter()

RepoDep = Annotated[Any, Depends(get_repository)]
ConfigDep = Annotated[dict[str, Any], Depends(get_config)]
ReviewerDep = Annotated[str, Depends(get_mutating_reviewer)]


@router.put("/api/runs/{run_id}/manual-db-review")
def save_manual_db_review(
    run_id: str,
    payload: dict[str, Any],
    repo: RepoDep,
    config: ConfigDep,
    reviewer: ReviewerDep,
):
    manual_config = config.get("manual_db_check")

    if not isinstance(manual_config, dict):
        raise HTTPException(
            status_code=400,
            detail="manual DB check configuration is unavailable",
        )

    if manual_config.get("enabled") is not True:
        raise HTTPException(
            status_code=400,
            detail="manual DB check is disabled",
        )

    raw_result = payload.get("result")

    if not isinstance(raw_result, str):
        raise HTTPException(
            status_code=400,
            detail="manual DB result is required",
        )

    try:
        result = ManualDBReviewResult(raw_result)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail="manual DB result must be PASS, FAIL, or NOT RUN",
        ) from exc

    review = ManualDBReview(
        run_id=run_id,
        display_name=str(
            manual_config.get("display_name", "")
        ),
        script_path=str(
            manual_config.get("script_path", "")
        ),
        result=result,
        comment=payload.get("comment", ""),
        reviewer=reviewer,
    )

    try:
        review_id = record_manual_db_review(
            repo,
            review,
        )
    except ManualDBReviewValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except InvalidRunTransition as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="run not found",
        ) from exc

    saved = repo.get_manual_db_review(run_id)

    if saved is None:
        raise HTTPException(
            status_code=500,
            detail="manual DB review was not persisted",
        )

    return {
        "id": review_id,
        "review": to_jsonable(saved),
    }