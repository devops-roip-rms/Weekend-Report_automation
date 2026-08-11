from __future__ import annotations

import traceback

from app.collectors.database import DatabaseCollector
from app.collectors.doctor import DoctorCollector
from app.collectors.infrastructure import InfrastructureCollector
from app.collectors.portainer import PortainerCollector
from app.collectors.rabbitmq import RabbitMQCollector
from app.collectors.recording import RecordingCollector
from app.domain import CheckResult, CheckStatus
from app.orchestrator.aggregation import aggregate_status
from app.orchestrator.execution_plan import build_execution_plan
from app.orchestrator.run_context import RunContext
from app.time_utils import iso_now
from app.validators.database import DatabaseValidator
from app.validators.doctor import DoctorValidator
from app.validators.infrastructure import InfrastructureValidator
from app.validators.portainer import PortainerValidator
from app.validators.rabbitmq import RabbitMQValidator
from app.validators.recording import RecordingValidator
from app.validators.site_parity import SiteParityValidator


COLLECTORS = {
    "portainer": PortainerCollector,
    "doctor": DoctorCollector,
    "rabbitmq": RabbitMQCollector,
    "recording": RecordingCollector,
    "infrastructure": InfrastructureCollector,
    "database": DatabaseCollector,
}

VALIDATORS = {
    "portainer": PortainerValidator,
    "doctor": DoctorValidator,
    "rabbitmq": RabbitMQValidator,
    "recording": RecordingValidator,
    "infrastructure": InfrastructureValidator,
    "database": DatabaseValidator,
}


class OrchestratorRunner:
    def run(self, context: RunContext) -> list[CheckResult]:
        all_results: list[CheckResult] = []
        for step in build_execution_plan(context.config):
            context.repository.heartbeat(context.run_id, current_module=step.module)
            started = iso_now()
            try:
                collector = COLLECTORS[step.module]()
                validator = VALIDATORS[step.module]()
                actual = collector.collect(context)
                results = validator.validate(actual, context.config, context)
            except Exception as exc:
                results = [
                    CheckResult(
                        run_id=context.run_id,
                        module=step.module,
                        check_id=f"{step.module}.module_error",
                        site=None,
                        target=step.module,
                        expected={"module": step.module},
                        actual={"exception": type(exc).__name__},
                        status=CheckStatus.ERROR,
                        message=f"{step.module} failed unexpectedly: {exc}",
                        started_at=started,
                        finished_at=iso_now(),
                        metadata={"traceback": traceback.format_exc(limit=8)},
                    )
                ]
            for result in results:
                stored = context.repository.add_result(result)
                result.id = stored
            all_results.extend(results)
        parity = SiteParityValidator().validate({"results": all_results}, context.config, context)
        for result in parity:
            result.id = context.repository.add_result(result)
        all_results.extend(parity)
        status = aggregate_status(all_results)
        context.repository.mark_review_ready(context.run_id, status)
        return all_results
