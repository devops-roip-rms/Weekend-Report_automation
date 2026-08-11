from __future__ import annotations

from typing import Any

from app.collectors.base import Collector
from app.orchestrator.run_context import RunContext


class InfrastructureCollector(Collector):
    def collect(self, context: RunContext) -> dict[str, Any]:
        return context.config.get("servers", {}).get("fixture_actual", {"sites": {}})
