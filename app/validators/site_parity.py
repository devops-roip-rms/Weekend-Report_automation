from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.domain import CheckResult, CheckStatus
from app.orchestrator.run_context import RunContext
from app.time_utils import iso_now


class SiteParityValidator:
    def validate(self, actual: dict[str, Any], config: dict[str, Any], context: RunContext) -> list[CheckResult]:
        started = iso_now()
        parity = config.get("rules", {}).get("parity", [])
        results: list[CheckResult] = []
        observed_results: list[CheckResult] = actual.get("results", [])
        by_module_site: dict[tuple[str, str], list[CheckResult]] = defaultdict(list)
        for result in observed_results:
            if result.site:
                by_module_site[(result.module, result.site)].append(result)
        for rule in parity:
            if not rule.get("enabled", False):
                continue
            module = rule["module"]
            field = rule["field"]
            site1, site2 = rule["sites"]
            value1 = _extract(by_module_site.get((module, site1), []), field)
            value2 = _extract(by_module_site.get((module, site2), []), field)
            status = CheckStatus.PASS if value1 == value2 else CheckStatus(rule.get("mismatch_status", "WARNING"))
            results.append(CheckResult(context.run_id, "site_parity", f"parity.{module}.{field}", status, "parity compared separately from site health", site=None, target=f"{module}.{field}", expected={"site1": value1, "site2": value2}, actual={"match": value1 == value2}, started_at=started, finished_at=iso_now(), metadata={"parity_only": True}))
        return results


def _extract(results: list[CheckResult], field: str) -> Any:
    values = []
    for result in results:
        if isinstance(result.actual, dict) and field in result.actual:
            values.append(result.actual[field])
        elif isinstance(result.expected, dict) and field in result.expected:
            values.append(result.expected[field])
    return sorted(values, key=lambda x: str(x))
