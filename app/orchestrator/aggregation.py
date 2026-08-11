from __future__ import annotations

from collections import defaultdict

from app.domain import CheckResult, CheckStatus, ModuleSummary, SiteSummary, STATUS_STRENGTH


def aggregate_status(results: list[CheckResult]) -> CheckStatus:
    if not results:
        return CheckStatus.SKIPPED
    strongest = max((r.status for r in results), key=lambda s: STATUS_STRENGTH[s])
    return strongest


def site_summaries(results: list[CheckResult]) -> list[SiteSummary]:
    grouped: dict[str, list[CheckResult]] = defaultdict(list)
    for result in results:
        if result.site:
            grouped[result.site].append(result)
    return [
        SiteSummary(site=site, status=aggregate_status(items), result_count=len(items))
        for site, items in sorted(grouped.items())
    ]


def module_summaries(results: list[CheckResult]) -> list[ModuleSummary]:
    grouped: dict[str, list[CheckResult]] = defaultdict(list)
    for result in results:
        grouped[result.module].append(result)
    return [
        ModuleSummary(module=module, status=aggregate_status(items), result_count=len(items))
        for module, items in sorted(grouped.items())
    ]
