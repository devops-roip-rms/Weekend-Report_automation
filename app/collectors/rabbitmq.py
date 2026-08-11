from __future__ import annotations

from typing import Any

from app.collectors.base import Collector
from app.orchestrator.run_context import RunContext


class RabbitMQCollector(Collector):
    def collect(self, context: RunContext) -> dict[str, Any]:
        actual = context.config.get("rabbitmq_expected", {}).get("fixture_actual")
        if actual is not None:
            return {"sites": actual}
        return {
            "error": "RabbitMQ live collection is blocked until Management API values are approved",
            "sites": {},
        }
