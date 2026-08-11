from __future__ import annotations

from typing import Any

from app.domain import CheckResult, CheckStatus
from app.orchestrator.run_context import RunContext
from app.time_utils import iso_now
from app.validators.base import Validator


class RecordingValidator(Validator):
    def validate(self, actual: dict[str, Any], config: dict[str, Any], context: RunContext) -> list[CheckResult]:
        started = iso_now()
        results: list[CheckResult] = []
        if actual.get("error"):
            return [CheckResult(context.run_id, "recording", "recording.safety_block", CheckStatus.ERROR, actual["error"], expected=config.get("recording", {}), actual=actual, started_at=started, finished_at=iso_now())]
        for site, observed in actual.get("sites", {}).items():
            identity = f"WEEKEND_TEST_{site.upper()}_{context.run_id}"
            expected = {"identity": identity, "cleanup_required": True}
            exact_ok = observed.get("identity") == identity and observed.get("exact_identity_verified") is True
            functional_status = CheckStatus(observed.get("functional_status", "ERROR"))
            cleanup_status = CheckStatus(observed.get("cleanup_status", "ERROR"))
            if not exact_ok and functional_status == CheckStatus.PASS:
                functional_status = CheckStatus.FAIL
            module_status = CheckStatus.FAIL if cleanup_status in {CheckStatus.FAIL, CheckStatus.ERROR} else functional_status
            results.append(CheckResult(context.run_id, "recording", "recording.functional", functional_status, "functional validation status", site=site, target=identity, expected=expected, actual=observed, started_at=started, finished_at=iso_now(), metadata={"cleanup_status": cleanup_status.value}))
            results.append(CheckResult(context.run_id, "recording", "recording.cleanup", cleanup_status, "cleanup validation status", site=site, target=identity, expected={"cleanup": "synthetic object absent and baseline restored where reliable"}, actual=observed, started_at=started, finished_at=iso_now()))
            results.append(CheckResult(context.run_id, "recording", "recording.module_status", module_status, "cleanup failure blocks the module even when functional validation passed", site=site, target=identity, expected=expected, actual=observed, started_at=started, finished_at=iso_now()))
        return results
