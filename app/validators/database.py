from __future__ import annotations

from typing import Any

from app.domain import CheckResult, CheckStatus
from app.orchestrator.run_context import RunContext
from app.time_utils import iso_now
from app.validators.base import Validator


class DatabaseValidator(Validator):
    def validate(
        self,
        actual: dict[str, Any],
        config: dict[str, Any],
        context: RunContext,
    ) -> list[CheckResult]:
        started = iso_now()

        if actual.get("error"):
            return [
                _result(
                    context.run_id,
                    actual,
                    CheckStatus.ERROR,
                    actual["error"],
                    started,
                )
            ]

        # The real script result contract has not yet been verified.
        #
        # Do not infer PASS/FAIL from invented fields or generic exit codes.
        return [
            _result(
                context.run_id,
                actual,
                CheckStatus.ERROR,
                ("Database synchronization script result contract has not been verified."),
                started,
                error_code="DATABASE_SYNC_SCRIPT_RESULT_CONTRACT_UNVERIFIED",
            )
        ]


def _result(
    run_id: str,
    actual: Any,
    status: CheckStatus,
    message: str,
    started: str,
    *,
    error_code: str | None = None,
) -> CheckResult:
    metadata = {}

    if error_code:
        metadata["error_code"] = error_code

    if isinstance(actual, dict) and actual.get("errors"):
        metadata["errors"] = actual["errors"]

    return CheckResult(
        run_id=run_id,
        module="database",
        check_id="database.sync_execution",
        status=status,
        message=message,
        site=None,
        target="database_sync_test",
        expected={
            "adapter": "existing_powershell_script",
            "verified_result_contract": True,
        },
        actual=actual,
        started_at=started,
        finished_at=iso_now(),
        metadata=metadata,
    )
