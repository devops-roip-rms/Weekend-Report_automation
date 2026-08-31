from __future__ import annotations

import copy
from typing import Any


def resolve_portainer_expected(config: dict[str, Any]) -> dict[str, Any]:
    portainer = config.get("portainer_expected", config)
    resolved = copy.deepcopy(portainer)
    common_services = portainer.get("services")
    defaults = portainer.get("defaults", {})
    sites = portainer.get("sites", {})
    if not isinstance(sites, dict):
        resolved["sites"] = {}
        return resolved
    if not isinstance(common_services, dict):
        return resolved
    resolved_sites: dict[str, Any] = {}
    for site_id, site_config in sites.items():
        if not isinstance(site_config, dict):
            continue
        site = copy.deepcopy(site_config)
        if site.get("service_inventory") == "common" or "services" not in site:
            service_overrides = _named_overrides(site.get("overrides", {}), "services")
            site["services"] = [
                _resolve_portainer_service(name, service, defaults, service_overrides.get(name, {}))
                for name, service in common_services.items()
                if isinstance(service, dict)
            ]
        else:
            site["services"] = [
                _normalize_portainer_service(service.get("name", str(idx)), service, defaults)
                for idx, service in enumerate(site.get("services", []))
                if isinstance(service, dict)
            ]
        resolved_sites[site_id] = site
    resolved["sites"] = resolved_sites
    return resolved


def resolve_rabbitmq_expected(
    config: dict[str, Any],
) -> dict[str, Any]:
    """Return the current RabbitMQ queue/node configuration."""
    rabbitmq = config.get(
        "rabbitmq_expected",
        config,
    )
    return copy.deepcopy(rabbitmq)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _resolve_portainer_service(
    name: str,
    service: dict[str, Any],
    defaults: dict[str, Any],
    override: dict[str, Any],
) -> dict[str, Any]:
    return _normalize_portainer_service(name, deep_merge(service, override), defaults)


def _normalize_portainer_service(
    name: str,
    service: dict[str, Any],
    defaults: dict[str, Any],
) -> dict[str, Any]:
    merged = deep_merge(defaults, service)
    merged.setdefault("name", name)
    merged.setdefault("required", True)
    return merged


def _named_overrides(overrides: Any, section: str) -> dict[str, Any]:
    if not isinstance(overrides, dict):
        return {}
    nested = overrides.get(section)
    if isinstance(nested, dict):
        return nested
    return overrides
