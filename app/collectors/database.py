from __future__ import annotations

from typing import Any

from app.collectors.base import Collector
from app.orchestrator.run_context import RunContext


class DatabaseCollector(Collector):
    def collect(self, context: RunContext) -> dict[str, Any]:
        return context.config.get("rules", {}).get("database_fixture_actual", {"sites": {}})
