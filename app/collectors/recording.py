from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.collectors.base import Collector
from app.domain import CheckStatus
from app.orchestrator.run_context import RunContext


@dataclass(slots=True)
class RecordingOutcome:
    functional_status: CheckStatus
    cleanup_status: CheckStatus
    cleanup_attempted: bool
    exact_identity_verified: bool
    message: str


class RecordingCollector(Collector):
    def collect(self, context: RunContext) -> dict[str, Any]:
        config = context.config.get("recording", {})
        fixture = config.get("fixture_actual")
        if fixture is not None:
            return fixture
        return {
            "error": "Recording synthetic test is blocked until safe create/delete/cleanup definitions are approved",
            "sites": {},
        }


class RecordingTestOrchestrator:
    def run(self, *, create_ok: bool, propagation_ok: bool, backend_ok: bool, cleanup_ok: bool) -> RecordingOutcome:
        functional = CheckStatus.ERROR
        cleanup_attempted = False
        identity_verified = False
        try:
            if not create_ok:
                functional = CheckStatus.FAIL
                return RecordingOutcome(functional, CheckStatus.PASS, False, False, "create failed")
            identity_verified = propagation_ok
            if not propagation_ok:
                functional = CheckStatus.FAIL
            elif not backend_ok:
                functional = CheckStatus.FAIL
            else:
                functional = CheckStatus.PASS
            return RecordingOutcome(functional, CheckStatus.ERROR, True, identity_verified, "cleanup pending")
        finally:
            cleanup_attempted = create_ok
            cleanup_status = CheckStatus.PASS if cleanup_ok else CheckStatus.FAIL
            if create_ok and not cleanup_ok:
                functional = CheckStatus.FAIL
            self.last_outcome = RecordingOutcome(
                functional,
                cleanup_status,
                cleanup_attempted,
                identity_verified,
                "cleanup completed" if cleanup_ok else "cleanup failed",
            )
