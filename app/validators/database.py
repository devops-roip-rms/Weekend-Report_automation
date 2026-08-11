from __future__ import annotations

from typing import Any

from app.domain import CheckResult, CheckStatus
from app.orchestrator.run_context import RunContext
from app.time_utils import iso_now
from app.validators.base import Validator


class DatabaseValidator(Validator):
    def validate(self, actual: dict[str, Any], config: dict[str, Any], context: RunContext) -> list[CheckResult]:
        started = iso_now()
        results: list[CheckResult] = []
        for site, observed in actual.get("sites", {}).items():
            exit_code = observed.get("exit_code")
            contract = config.get("rules", {}).get("database_exit_code_contract", {"0": "PASS"})
            status_name = contract.get(str(exit_code), "ERROR")
            status = CheckStatus(status_name)
            results.append(CheckResult(context.run_id, "database", "database.script_contract", status, f"database script exit code {exit_code}", site=site, target=observed.get("target", "db-script"), expected=contract, actual=observed, started_at=started, finished_at=iso_now()))
        return results
