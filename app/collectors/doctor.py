from __future__ import annotations

from typing import Any

from app.collectors.base import Collector
from app.config.schema import is_unresolved_placeholder
from app.orchestrator.run_context import RunContext
from app.time_utils import iso_now


class DoctorCollector(Collector):
    def collect(self, context: RunContext) -> dict[str, Any]:
        doctor = context.config.get("doctor", {}).get("doctor", {})
        if doctor.get("mode") == "manual":
            return {"mode": "manual", "manual_review": doctor.get("manual_review", {})}
        fixture = doctor.get("fixture_actual")
        if isinstance(fixture, dict):
            return {
                "mode": "api",
                "collection_timestamp": iso_now(),
                "sites": fixture.get("sites", fixture),
                "errors": [],
            }
        schema = (doctor.get("api") or {}).get("schema")
        if is_unresolved_placeholder(schema):
            return _blocked_payload(
                "DOCTOR_API_SCHEMA_UNVERIFIED",
                "DOCTOR API response schema/auth contract is not supplied or verified",
            )
        return _blocked_payload(
            "DOCTOR_API_ADAPTER_UNIMPLEMENTED",
            "DOCTOR live API adapter is not implemented for the supplied schema",
        )


def _blocked_payload(code: str, message: str) -> dict[str, Any]:
    return {
        "mode": "api",
        "collection_timestamp": iso_now(),
        "sites": {},
        "errors": [{"code": code, "message": message, "retryable": False}],
    }
