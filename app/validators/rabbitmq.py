from __future__ import annotations

from typing import Any

from app.domain import CheckResult, CheckStatus
from app.orchestrator.run_context import RunContext
from app.time_utils import iso_now
from app.validators.base import Validator
from app.validators.engine import threshold_status


class RabbitMQValidator(Validator):
    def validate(self, actual: dict[str, Any], config: dict[str, Any], context: RunContext) -> list[CheckResult]:
        started = iso_now()
        if actual.get("error"):
            return [CheckResult(context.run_id, "rabbitmq", "rabbitmq.collection", CheckStatus.ERROR, actual["error"], expected={"source": "RabbitMQ Management API"}, actual=actual, started_at=started, finished_at=iso_now())]
        results: list[CheckResult] = []
        expected_sites = config.get("rabbitmq_expected", {}).get("sites", {})
        actual_sites = actual.get("sites", {})
        for site, expected in expected_sites.items():
            observed = actual_sites.get(site, {})
            vhosts = {v.get("name") for v in observed.get("vhosts", [])}
            for vhost in expected.get("vhosts", []):
                status = CheckStatus.PASS if vhost["name"] in vhosts else CheckStatus.FAIL
                results.append(_r(context.run_id, "vhost.exists", site, vhost["name"], vhost, {"exists": vhost["name"] in vhosts}, status, "vhost exists" if status == CheckStatus.PASS else "required vhost missing", started))
            queues = {(q.get("vhost"), q.get("name")): q for q in observed.get("queues", [])}
            for queue in expected.get("queues", []):
                key = (queue["vhost"], queue["name"])
                q = queues.get(key)
                if q is None:
                    results.append(_r(context.run_id, "queue.exists", site, queue["name"], queue, None, CheckStatus.FAIL, "required queue missing", started))
                    continue
                for prop in ["durable", "auto_delete", "exclusive"]:
                    if prop in queue:
                        status = CheckStatus.PASS if q.get(prop) == queue[prop] else CheckStatus.FAIL
                        results.append(_r(context.run_id, f"queue.{prop}", site, queue["name"], queue[prop], q.get(prop), status, f"queue {prop} {'matches' if status == CheckStatus.PASS else 'mismatch'}", started))
                min_consumers = queue.get("min_consumers", 0)
                consumers = q.get("consumers", 0)
                status = CheckStatus.PASS if consumers >= min_consumers else CheckStatus.FAIL
                results.append(_r(context.run_id, "queue.consumers", site, queue["name"], min_consumers, consumers, status, "consumer count satisfies minimum" if status == CheckStatus.PASS else "consumers below minimum", started))
                metric = queue.get("backlog_metric", "messages")
                messages = q.get(metric, q.get("messages", 0))
                status = threshold_status(float(messages), float(queue["warning_messages"]), float(queue["critical_messages"]))
                results.append(_r(context.run_id, "queue.backlog", site, queue["name"], {"metric": metric, "warning": queue["warning_messages"], "critical": queue["critical_messages"]}, {metric: messages}, status, f"{metric}={messages}", started))
            exchanges = {(e.get("vhost"), e.get("name")): e for e in observed.get("exchanges", [])}
            for exchange in expected.get("exchanges", []):
                e = exchanges.get((exchange["vhost"], exchange["name"]))
                if e is None:
                    results.append(_r(context.run_id, "exchange.exists", site, exchange["name"], exchange, None, CheckStatus.FAIL, "required exchange missing", started))
                    continue
                for prop in ["type", "durable", "auto_delete"]:
                    status = CheckStatus.PASS if e.get(prop) == exchange[prop] else CheckStatus.FAIL
                    results.append(_r(context.run_id, f"exchange.{prop}", site, exchange["name"], exchange[prop], e.get(prop), status, f"exchange {prop} {'matches' if status == CheckStatus.PASS else 'mismatch'}", started))
            binding_set = {(b.get("vhost"), b.get("source"), b.get("destination_type"), b.get("destination"), b.get("routing_key")) for b in observed.get("bindings", [])}
            for binding in expected.get("bindings", []):
                key = (binding["vhost"], binding["source"], binding["destination_type"], binding["destination"], binding["routing_key"])
                status = CheckStatus.PASS if key in binding_set else CheckStatus.FAIL
                results.append(_r(context.run_id, "binding.exists", site, binding["destination"], binding, {"exists": key in binding_set}, status, "binding exists" if status == CheckStatus.PASS else "required binding missing", started))
            for node in observed.get("nodes", []):
                if node.get("mem_alarm"):
                    results.append(_r(context.run_id, "node.memory_alarm", site, node.get("name", "node"), {"alarm": False}, {"alarm": True}, CheckStatus.FAIL, "memory alarm active", started))
                if node.get("disk_free_alarm"):
                    results.append(_r(context.run_id, "node.disk_alarm", site, node.get("name", "node"), {"alarm": False}, {"alarm": True}, CheckStatus.FAIL, "disk alarm active", started))
        return results


def _r(run_id: str, check: str, site: str, target: str, expected: Any, actual: Any, status: CheckStatus, message: str, started: str) -> CheckResult:
    return CheckResult(run_id, "rabbitmq", f"rabbitmq.{check}", status, message, site=site, target=target, expected=expected, actual=actual, started_at=started, finished_at=iso_now())
