from __future__ import annotations

import copy
from typing import Any

from app.collectors.base import Collector
from app.executors.database_sync_test import DatabaseSyncScriptBlocked, run_database_sync_test
from app.orchestrator.run_context import RunContext
from app.time_utils import iso_now


class DatabaseCollector(Collector):
    def collect(self, context: RunContext) -> dict[str, Any]:
        config = context.config.get("database", {})
        mode = config.get("collection_mode") or (
            "fixture" if config.get("fixture_actual") is not None else "live"
        )
        fixture = config.get("fixture_actual")
        if mode == "fixture":
            if fixture is None:
                return {
                    "mode": "fixture",
                    "sites": {},
                    "error": "Database fixture mode is configured without fixture_actual",
                }
            sites = fixture.get("sites", fixture) if isinstance(fixture, dict) else {}
            return {
                "mode": "fixture",
                "collection_timestamp": iso_now(),
                "sites": copy.deepcopy(sites),
                "errors": [],
            }
        if mode != "live":
            return {
                "mode": "configuration_error",
                "sites": {},
                "error": f"Unsupported database collection_mode: {mode}",
            }
        try:
            actual = run_database_sync_test(config, context.config)
        except DatabaseSyncScriptBlocked as exc:
            return _error_payload(exc.code, exc.message, metadata=exc.metadata)
        except Exception as exc:
            return _error_payload("DATABASE_SYNC_SCRIPT_ADAPTER_ERROR", str(exc))
        if not isinstance(actual, dict):
            return _error_payload(
                "DATABASE_SYNC_SCRIPT_INVALID_RESULT",
                "Database synchronization script adapter did not return an object",
            )
        return actual


def _error_payload(
    code: str,
    message: str,
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "mode": "live",
        "collection_timestamp": iso_now(),
        "sites": {},
        "error": message,
        "errors": [{"code": code, "message": message, "metadata": metadata or {}}],
    }
