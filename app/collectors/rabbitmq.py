from __future__ import annotations

import copy
import os
import time
from dataclasses import dataclass
from typing import Any

import httpx

from app.collectors.base import Collector
from app.config.schema import is_unresolved_placeholder
from app.orchestrator.run_context import RunContext
from app.time_utils import iso_now

TRANSIENT_STATUS_CODES = {408, 429, 500, 502, 503, 504}
QUEUE_FIELDS = {
    "ready": "messages_ready",
    "unacked": "messages_unacknowledged",
    "total": "messages",
}
NODE_RAW_FIELDS = (
    "fd_used",
    "fd_total",
    "sockets_used",
    "sockets_total",
    "proc_used",
    "proc_total",
    "disk_free",
    "disk_free_limit",
    "disk_free_alarm",
)


class RabbitMQError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        site: str | None = None,
        status_code: int | None = None,
        retryable: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.site = site
        self.status_code = status_code
        self.retryable = retryable
        self.metadata = metadata or {}

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "metadata": self.metadata,
        }
        if self.site:
            payload["site"] = self.site
        if self.status_code is not None:
            payload["status_code"] = self.status_code
        return payload


@dataclass(slots=True)
class RabbitMQClientSettings:
    site: str
    base_url: str
    username: str
    password: str
    tls_verify: bool
    timeout_seconds: float
    retry_attempts: int


class RabbitMQClient:
    def __init__(
        self,
        settings: RabbitMQClientSettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport

    def get_json(self, path: str) -> Any:
        timeout = httpx.Timeout(
            connect=self.settings.timeout_seconds,
            read=self.settings.timeout_seconds,
            write=self.settings.timeout_seconds,
            pool=self.settings.timeout_seconds,
        )
        with httpx.Client(
            auth=(self.settings.username, self.settings.password),
            timeout=timeout,
            verify=self.settings.tls_verify,
            transport=self.transport,
        ) as client:
            return self._get_with_retries(client, path)

    def _get_with_retries(self, client: httpx.Client, path: str) -> Any:
        attempts = max(1, self.settings.retry_attempts)
        last_error: RabbitMQError | None = None
        for attempt in range(1, attempts + 1):
            try:
                response = client.get(
                    self._url(path),
                    headers={"Accept": "application/json"},
                )
                if response.status_code in {401, 403}:
                    raise RabbitMQError(
                        "RABBITMQ_AUTHENTICATION_ERROR",
                        f"RabbitMQ authentication failed with HTTP {response.status_code}",
                        site=self.settings.site,
                        status_code=response.status_code,
                        metadata={"path": path, "api_attempt": attempt},
                    )
                if response.status_code in TRANSIENT_STATUS_CODES and attempt < attempts:
                    last_error = RabbitMQError(
                        "RABBITMQ_COLLECTION_ERROR",
                        f"RabbitMQ transient HTTP {response.status_code}",
                        site=self.settings.site,
                        status_code=response.status_code,
                        retryable=True,
                        metadata={"path": path, "api_attempt": attempt},
                    )
                    continue
                if response.status_code >= 400:
                    raise RabbitMQError(
                        "RABBITMQ_COLLECTION_ERROR",
                        f"RabbitMQ HTTP {response.status_code}",
                        site=self.settings.site,
                        status_code=response.status_code,
                        metadata={"path": path, "api_attempt": attempt},
                    )
                try:
                    return response.json()
                except ValueError as exc:
                    raise RabbitMQError(
                        "RABBITMQ_INVALID_RESPONSE",
                        "RabbitMQ response was not valid JSON",
                        site=self.settings.site,
                        metadata={"path": path, "api_attempt": attempt},
                    ) from exc
            except httpx.TimeoutException as exc:
                last_error = RabbitMQError(
                    "RABBITMQ_TIMEOUT",
                    "RabbitMQ request timed out after configured retry policy",
                    site=self.settings.site,
                    retryable=True,
                    metadata={"path": path, "api_attempt": attempt},
                )
                if attempt >= attempts:
                    raise last_error from exc
            except httpx.HTTPError as exc:
                code = (
                    "RABBITMQ_TLS_ERROR"
                    if _looks_like_tls_error(exc)
                    else "RABBITMQ_COLLECTION_ERROR"
                )
                last_error = RabbitMQError(
                    code,
                    "RabbitMQ TLS/certificate error"
                    if code == "RABBITMQ_TLS_ERROR"
                    else "RabbitMQ connection failed",
                    site=self.settings.site,
                    retryable=code != "RABBITMQ_TLS_ERROR",
                    metadata={"path": path, "api_attempt": attempt},
                )
                if code == "RABBITMQ_TLS_ERROR" or attempt >= attempts:
                    raise last_error from exc
        if last_error is not None:
            raise last_error
        raise RabbitMQError(
            "RABBITMQ_COLLECTION_ERROR",
            "RabbitMQ request failed without a response",
            site=self.settings.site,
            metadata={"path": path},
        )

    def _url(self, path: str) -> str:
        normalized = path if path.startswith("/") else f"/{path}"
        return f"{self.settings.base_url.rstrip('/')}{normalized}"


class RabbitMQCollector(Collector):
    def __init__(self, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport

    def collect(self, context: RunContext) -> dict[str, Any]:
        config = context.config.get("rabbitmq_expected", {})
        mode = config.get("collection_mode") or (
            "fixture" if config.get("fixture_actual") is not None else "live"
        )
        if mode == "fixture":
            return _collect_fixture(config, context)
        if mode != "live":
            return _collection_with_error(
                "RABBITMQ_CONFIGURATION_ERROR",
                f"Unsupported RabbitMQ collection_mode: {mode}",
                context,
            )
        return self._collect_live(config, context)

    def _collect_live(self, config: dict[str, Any], context: RunContext) -> dict[str, Any]:
        sites: dict[str, Any] = {}
        errors: list[dict[str, Any]] = []
        for site_id, site_config in (config.get("sites") or {}).items():
            try:
                settings = _client_settings(
                    site_id,
                    (config.get("connections") or {}).get(site_id),
                )
                client = RabbitMQClient(settings, transport=self.transport)
                queue_snapshots = _collect_queue_snapshots(client, config.get("queues") or {})
                raw_nodes = client.get_json("/api/nodes")

                if not isinstance(raw_nodes, list):
                    raise RabbitMQError(
                        "RABBITMQ_INVALID_RESPONSE",
                        "RabbitMQ /api/nodes response was not a list",
                        site=site_id,
                    )

                if not raw_nodes:
                    raise RabbitMQError(
                        "RABBITMQ_INVALID_RESPONSE",
                        "RabbitMQ /api/nodes returned no nodes",
                        site=site_id,
                    )
                sites[site_id] = {
                    "site": site_id,
                    "required": site_config.get("required", True)
                    if isinstance(site_config, dict)
                    else True,
                    "collection_timestamp": iso_now(),
                    "queues": _final_queue_states(queue_snapshots),
                    "nodes": [
                        _normalize_node(node) for node in raw_nodes if isinstance(node, dict)
                    ],
                    "raw_api": {
                        "queue_snapshots": queue_snapshots,
                        "nodes": raw_nodes,
                    },
                    "metadata": {
                        "source": "rabbitmq_management_api",
                        "queue_rechecks_configured": _refresh_attempts(config.get("queues") or {}),
                    },
                }
            except RabbitMQError as exc:
                errors.append(exc.to_payload())
        return {
            "mode": "live",
            "collection_timestamp": iso_now(),
            "metadata": {
                "source": "rabbitmq_management_api",
                "configuration_hash": context.config.get("_config_hash"),
                "read_only": True,
            },
            "sites": sites,
            "errors": errors,
        }


def _collect_fixture(config: dict[str, Any], context: RunContext) -> dict[str, Any]:
    fixture = copy.deepcopy(config.get("fixture_actual") or {})
    fixture_sites = fixture.get("sites", fixture) if isinstance(fixture, dict) else {}
    return {
        "mode": "fixture",
        "collection_timestamp": iso_now(),
        "metadata": {
            "source": "fixture",
            "configuration_hash": context.config.get("_config_hash"),
            "read_only": True,
        },
        "sites": fixture_sites if isinstance(fixture_sites, dict) else {},
        "errors": [],
    }


def _collection_with_error(code: str, message: str, context: RunContext) -> dict[str, Any]:
    return {
        "mode": "configuration_error",
        "collection_timestamp": iso_now(),
        "metadata": {
            "source": "configuration",
            "configuration_hash": context.config.get("_config_hash"),
            "read_only": True,
        },
        "sites": {},
        "errors": [{"code": code, "message": message, "retryable": False}],
    }


def _client_settings(site_id: str, connection: Any) -> RabbitMQClientSettings:
    if not isinstance(connection, dict):
        raise RabbitMQError(
            "RABBITMQ_CONFIGURATION_ERROR",
            "RabbitMQ live collection requires a connection object",
            site=site_id,
        )
    url_env = _required_string(connection.get("url_env"), site_id, "url_env")
    user_env = _required_string(connection.get("user_env"), site_id, "user_env")
    password_env = _required_string(connection.get("password_env"), site_id, "password_env")
    tls_verify = connection.get("tls_verify")
    if not isinstance(tls_verify, bool):
        raise RabbitMQError(
            "RABBITMQ_CONFIGURATION_ERROR",
            "RabbitMQ tls_verify must be boolean",
            site=site_id,
        )
    return RabbitMQClientSettings(
        site=site_id,
        base_url=_env_required(url_env, site_id, "RabbitMQ URL"),
        username=_env_required(user_env, site_id, "RabbitMQ user"),
        password=_env_required(password_env, site_id, "RabbitMQ password"),
        tls_verify=tls_verify,
        timeout_seconds=_positive_number(
            connection.get("timeout_seconds"), site_id, "timeout_seconds"
        ),
        retry_attempts=_positive_integer(
            connection.get("retry_attempts"), site_id, "retry_attempts"
        ),
    )


def _collect_queue_snapshots(
    client: RabbitMQClient,
    queue_config: dict[str, Any],
) -> list[list[dict[str, Any]]]:
    refresh_attempts = _refresh_attempts(queue_config)
    delay_seconds = _delay_seconds(queue_config)
    snapshots: list[list[dict[str, Any]]] = []

    for check_index in range(1, refresh_attempts + 2):
        raw_queues = client.get_json("/api/queues")

        if not isinstance(raw_queues, list):
            raise RabbitMQError(
                "RABBITMQ_INVALID_RESPONSE",
                "RabbitMQ /api/queues response was not a list",
                site=client.settings.site,
            )

        if not raw_queues:
            raise RabbitMQError(
                "RABBITMQ_INVALID_RESPONSE",
                "RabbitMQ /api/queues returned no queues",
                site=client.settings.site,
            )

        normalized = [_normalize_queue(queue) for queue in raw_queues if isinstance(queue, dict)]

        snapshots.append(normalized)

        if _all_queues_zero(normalized) or check_index > refresh_attempts:
            break

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    return snapshots


def _refresh_attempts(queue_config: dict[str, Any]) -> int:
    recheck = queue_config.get("recheck") or {}
    value = recheck.get("refresh_attempts", 0)
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else 0


def _delay_seconds(queue_config: dict[str, Any]) -> float:
    recheck = queue_config.get("recheck") or {}
    value = recheck.get("delay_seconds", 0)
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else 0.0


def _all_queues_zero(queues: list[dict[str, Any]]) -> bool:
    for queue in queues:
        if any(queue.get(field) != 0 for field in QUEUE_FIELDS):
            return False
    return True


def _final_queue_states(snapshots: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    by_key: dict[tuple[str | None, str], dict[str, Any]] = {}
    for check_number, queues in enumerate(snapshots, start=1):
        for queue in queues:
            key = (queue.get("vhost"), str(queue.get("name") or ""))
            entry = by_key.setdefault(
                key,
                {
                    "vhost": queue.get("vhost"),
                    "name": queue.get("name"),
                    "snapshots": [],
                },
            )
            entry["snapshots"].append({"check": check_number, **queue})
            for field in QUEUE_FIELDS:
                entry[field] = queue.get(field)
            entry["checks_performed"] = check_number
    return sorted(by_key.values(), key=lambda item: (str(item.get("vhost")), str(item.get("name"))))


def _normalize_queue(queue: dict[str, Any]) -> dict[str, Any]:
    return {
        "vhost": queue.get("vhost"),
        "name": queue.get("name"),
        "ready": queue.get("messages_ready"),
        "unacked": queue.get("messages_unacknowledged"),
        "total": queue.get("messages"),
    }


def _normalize_node(node: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": node.get("name") or node.get("node"),
        "resource_states": _known_resource_states(node),
        "raw_resource_metrics": {
            field: node.get(field) for field in NODE_RAW_FIELDS if field in node
        },
        "raw": node,
    }


def _known_resource_states(node: dict[str, Any]) -> dict[str, str]:
    states: dict[str, str] = {}

    if isinstance(node.get("disk_free_alarm"), bool):
        states["disk_space"] = "red" if node["disk_free_alarm"] else "green"

    return states


def _required_string(value: Any, site: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or is_unresolved_placeholder(value):
        raise RabbitMQError(
            "RABBITMQ_CONFIGURATION_ERROR",
            f"RabbitMQ {field} is required for live collection",
            site=site,
        )
    return value.strip()


def _env_required(env_name: str, site: str, label: str) -> str:
    value = os.getenv(env_name, "").strip()
    if not value or is_unresolved_placeholder(value):
        raise RabbitMQError(
            "RABBITMQ_CONFIGURATION_ERROR",
            f"{label} runtime environment variable is missing or unresolved: {env_name}",
            site=site,
            metadata={"env": env_name},
        )
    return value


def _positive_number(value: Any, site: str, field: str) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool) and value > 0:
        return float(value)
    raise RabbitMQError(
        "RABBITMQ_CONFIGURATION_ERROR",
        f"RabbitMQ {field} must be a positive number",
        site=site,
    )


def _positive_integer(value: Any, site: str, field: str) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    raise RabbitMQError(
        "RABBITMQ_CONFIGURATION_ERROR",
        f"RabbitMQ {field} must be a positive integer",
        site=site,
    )


def _looks_like_tls_error(exc: httpx.HTTPError) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in ["ssl", "tls", "certificate", "cert_verify"])
