from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.config.schema import (
    ALL_PLACEHOLDERS,
    NOT_APPLICABLE_ALLOWED_PATH_PARTS,
    PLACEHOLDER_NOT_APPLICABLE,
    UNRESOLVED_PLACEHOLDERS,
    VALID_CHECK_STATUSES,
    VALID_MODULES,
)


@dataclass(slots=True)
class ValidationIssue:
    path: str
    message: str
    severity: str = "ERROR"

    def render(self) -> str:
        return f"{self.severity}: {self.path}: {self.message}"


@dataclass(slots=True)
class ValidationReport:
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def add_error(self, path: str, message: str) -> None:
        self.errors.append(ValidationIssue(path, message, "ERROR"))

    def add_warning(self, path: str, message: str) -> None:
        self.warnings.append(ValidationIssue(path, message, "WARNING"))

    def lines(self) -> list[str]:
        return [i.render() for i in self.errors + self.warnings]


def iter_leaves(value: Any, prefix: str = ""):
    if isinstance(value, dict):
        for key, item in value.items():
            new_prefix = f"{prefix}.{key}" if prefix else str(key)
            yield from iter_leaves(item, new_prefix)
    elif isinstance(value, list):
        for idx, item in enumerate(value):
            yield from iter_leaves(item, f"{prefix}[{idx}]")
    else:
        yield prefix, value


def _module_rules(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    modules = config.get("rules", {}).get("modules", {})
    if not isinstance(modules, dict):
        return {}
    return modules


def _site_ids(config: dict[str, Any]) -> set[str]:
    sites = config.get("sites", {}).get("sites", [])
    if not isinstance(sites, list):
        return set()
    return {s.get("id") for s in sites if isinstance(s, dict) and isinstance(s.get("id"), str)}


def _has_enabled_required_automation(config: dict[str, Any]) -> bool:
    for name, module in _module_rules(config).items():
        if name == "doctor" and config.get("doctor", {}).get("doctor", {}).get("mode") == "manual":
            continue
        if module.get("enabled") and module.get("required"):
            return True
    return False


def validate_config(config: dict[str, Any], *, production_preflight: bool = True) -> ValidationReport:
    report = ValidationReport()
    sites = config.get("sites", {}).get("sites")
    if not isinstance(sites, list) or not sites:
        report.add_error("sites.sites", "must contain at least one site")
    else:
        seen: set[str] = set()
        for idx, site in enumerate(sites):
            if not isinstance(site, dict):
                report.add_error(f"sites.sites[{idx}]", "site must be an object")
                continue
            site_id = site.get("id")
            if not site_id:
                report.add_error(f"sites.sites[{idx}].id", "site id is required")
            elif site_id in seen:
                report.add_error(f"sites.sites[{idx}].id", f"duplicate site id {site_id!r}")
            else:
                seen.add(site_id)

    modules = _module_rules(config)
    for module_name, module in modules.items():
        if module_name not in VALID_MODULES:
            report.add_error(f"rules.modules.{module_name}", "unknown module")
        if module.get("if_unavailable_status") not in VALID_CHECK_STATUSES:
            report.add_error(
                f"rules.modules.{module_name}.if_unavailable_status",
                "invalid status enum",
            )

    site_ids = _site_ids(config)
    for area in ["portainer_expected", "rabbitmq_expected", "recording", "servers"]:
        by_site = config.get(area, {}).get("sites")
        if isinstance(by_site, dict):
            for site_id in by_site:
                if site_id not in site_ids:
                    report.add_error(f"{area}.sites.{site_id}", "unknown site reference")

    _validate_splunk(config, report)
    _validate_thresholds(config, report)
    _validate_placeholders(config, report, production_preflight=production_preflight)
    return report


def _validate_splunk(config: dict[str, Any], report: ValidationReport) -> None:
    dashboards = config.get("splunk_dashboards", {}).get("dashboards", [])
    if not isinstance(dashboards, list):
        report.add_error("splunk_dashboards.dashboards", "must be a list")
        return
    seen: set[str] = set()
    for idx, dashboard in enumerate(dashboards):
        if not isinstance(dashboard, dict):
            report.add_error(f"splunk_dashboards.dashboards[{idx}]", "dashboard must be object")
            continue
        dashboard_id = dashboard.get("id")
        if not dashboard_id:
            report.add_error(f"splunk_dashboards.dashboards[{idx}].id", "dashboard id required")
        elif dashboard_id in seen:
            report.add_error(
                f"splunk_dashboards.dashboards[{idx}].id",
                f"duplicate dashboard id {dashboard_id!r}",
            )
        else:
            seen.add(dashboard_id)


def _validate_thresholds(config: dict[str, Any], report: ValidationReport) -> None:
    for path, value in iter_leaves(config):
        if path.endswith("critical_messages"):
            warning_path = path.removesuffix("critical_messages") + "warning_messages"
            warning = _get_path(config, warning_path)
            if isinstance(value, int | float) and isinstance(warning, int | float):
                if value <= warning:
                    report.add_error(path, "critical threshold must be greater than warning threshold")
        if path.endswith("critical_percent"):
            warning_path = path.removesuffix("critical_percent") + "warning_percent"
            warning = _get_path(config, warning_path)
            if isinstance(value, int | float) and isinstance(warning, int | float):
                if value <= warning:
                    report.add_error(path, "critical threshold must be greater than warning threshold")


def _get_path(config: dict[str, Any], dotted: str) -> Any:
    current: Any = config
    normalized = dotted.replace("[", ".").replace("]", "")
    for part in normalized.split("."):
        if part == "":
            continue
        if part.isdigit() and isinstance(current, list):
            idx = int(part)
            if idx >= len(current):
                return None
            current = current[idx]
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _validate_placeholders(
    config: dict[str, Any],
    report: ValidationReport,
    *,
    production_preflight: bool,
) -> None:
    unresolved_is_blocking = production_preflight and _has_enabled_required_automation(config)
    for path, value in iter_leaves(config):
        if value not in ALL_PLACEHOLDERS:
            continue
        if value in UNRESOLVED_PLACEHOLDERS:
            message = f"unresolved value {value}"
            if unresolved_is_blocking:
                report.add_error(path, message)
            else:
                report.add_warning(path, message)
        elif value == PLACEHOLDER_NOT_APPLICABLE:
            if not any(part in path for part in NOT_APPLICABLE_ALLOWED_PATH_PARTS):
                report.add_error(path, "<NOT_APPLICABLE> is not permitted for this field")
