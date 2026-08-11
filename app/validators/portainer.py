from __future__ import annotations

from typing import Any

from app.domain import CheckResult, CheckStatus
from app.orchestrator.run_context import RunContext
from app.time_utils import iso_now
from app.validators.base import Validator


class PortainerValidator(Validator):
    def validate(self, actual: dict[str, Any], config: dict[str, Any], context: RunContext) -> list[CheckResult]:
        started = iso_now()
        results: list[CheckResult] = []
        expected_sites = config.get("portainer_expected", {}).get("sites", {})
        actual_sites = actual.get("sites", {})
        if actual.get("error"):
            return [
                CheckResult(
                    run_id=context.run_id,
                    module="portainer",
                    check_id="portainer.collection",
                    status=CheckStatus.ERROR,
                    message=actual["error"],
                    expected={"source": "Portainer API"},
                    actual={"error": actual["error"]},
                    started_at=started,
                    finished_at=iso_now(),
                )
            ]
        for site_id, site_cfg in expected_sites.items():
            services = site_cfg.get("services", [])
            site_actual = {s.get("name"): s for s in actual_sites.get(site_id, {}).get("services", [])}
            for service in services:
                name = service["name"]
                observed = site_actual.get(name)
                if observed is None:
                    results.append(_result(context.run_id, "service.exists", site_id, name, service, None, CheckStatus.FAIL, "required service missing", started))
                    continue
                results.append(_result(context.run_id, "service.exists", site_id, name, {"exists": True}, {"exists": True}, CheckStatus.PASS, "required service exists", started))
                expected_replicas = service.get("expected_replicas")
                healthy_required = service.get("healthy_replicas_required", expected_replicas)
                running = observed.get("running_replicas", 0)
                healthy = observed.get("healthy_replicas", 0)
                if running == expected_replicas and healthy >= healthy_required:
                    status = CheckStatus.PASS
                    msg = f"{running}/{expected_replicas} replicas running and {healthy} healthy"
                else:
                    status = CheckStatus.FAIL
                    msg = f"{running}/{expected_replicas} running, {healthy}/{healthy_required} healthy"
                results.append(_result(context.run_id, "service.replicas", site_id, name, service, observed, status, msg, started))
                if service.get("expected_image"):
                    img_status = CheckStatus.PASS if observed.get("image") == service.get("expected_image") else CheckStatus.FAIL
                    results.append(_result(context.run_id, "service.image", site_id, name, service.get("expected_image"), observed.get("image"), img_status, "image matches expected" if img_status == CheckStatus.PASS else "image mismatch", started))
        return results


def _result(run_id: str, check: str, site: str, target: str, expected: Any, actual: Any, status: CheckStatus, message: str, started: str) -> CheckResult:
    return CheckResult(
        run_id=run_id,
        module="portainer",
        check_id=f"portainer.{check}",
        site=site,
        target=target,
        expected=expected,
        actual=actual,
        status=status,
        message=message,
        started_at=started,
        finished_at=iso_now(),
    )
